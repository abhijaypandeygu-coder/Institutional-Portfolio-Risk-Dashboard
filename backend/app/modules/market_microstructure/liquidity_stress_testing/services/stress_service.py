"""
Service layer for M09.06 Liquidity Stress Testing.
"""

from datetime import datetime
from decimal import Decimal
import math
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_microstructure.liquidity_stress_testing.calculations.stress_math import (
    OrderBookLevel,
    IntervalVolumeProfile,
    LiquidityStressMath,
)
from backend.app.modules.market_microstructure.liquidity_stress_testing.models.stress_models import (
    LiquidityStressConfig,
    LiquidityStressScenarioRun,
    LiquidityStressMonitoringSnapshot,
)
from backend.app.modules.market_microstructure.liquidity_stress_testing.repositories.stress_repository import (
    LiquidityStressRepository,
)
from backend.app.modules.market_microstructure.liquidity_stress_testing.schemas.stress_schemas import (
    StressConfigCreate,
    StressConfigResponse,
    StressRunRequest,
    StressRunResponse,
    CostDecompositionSchema,
    BookLevelSchema,
    SyntheticStressBookResponse,
    ReverseStressRequest,
    ReverseStressResponse,
    PortfolioStressRequest,
    PortfolioStressResponse,
    PortfolioPositionStressResult,
)


class LiquidityStressService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = LiquidityStressRepository(session)

    async def get_or_create_config(self, cfg_in: StressConfigCreate) -> StressConfigResponse:
        existing = await self.repo.get_config_by_code(cfg_in.scenario_code)
        if existing:
            return StressConfigResponse.model_validate(existing)

        db_cfg = LiquidityStressConfig(
            scenario_code=cfg_in.scenario_code,
            version=cfg_in.version,
            name=cfg_in.name,
            description=cfg_in.description,
            scenario_type=cfg_in.scenario_type,
            spread_shock_method=cfg_in.spread_shock_method,
            spread_multiplier=cfg_in.spread_multiplier,
            spread_additive_bps=cfg_in.spread_additive_bps,
            depth_shock_method=cfg_in.depth_shock_method,
            bid_depth_reduction=cfg_in.bid_depth_reduction,
            ask_depth_reduction=cfg_in.ask_depth_reduction,
            volume_shock_method=cfg_in.volume_shock_method,
            volume_contraction=cfg_in.volume_contraction,
            participation_rate=cfg_in.participation_rate,
            execution_horizon_intervals=cfg_in.execution_horizon_intervals,
            is_active=cfg_in.is_active,
        )
        saved = await self.repo.create_config(db_cfg)
        await self.session.commit()
        return StressConfigResponse.model_validate(saved)

    async def run_liquidity_stress_test(self, req: StressRunRequest) -> StressRunResponse:
        # 1. Resolve configuration or overrides
        cfg = await self.repo.get_config_by_code(req.scenario_code)
        
        spread_mult = (
            req.spread_multiplier
            if req.spread_multiplier is not None
            else (cfg.spread_multiplier if cfg else Decimal("1.50"))
        )
        bid_red = (
            req.bid_depth_reduction
            if req.bid_depth_reduction is not None
            else (cfg.bid_depth_reduction if cfg else Decimal("0.25"))
        )
        ask_red = (
            req.ask_depth_reduction
            if req.ask_depth_reduction is not None
            else (cfg.ask_depth_reduction if cfg else Decimal("0.25"))
        )
        vol_cont = (
            req.volume_contraction
            if req.volume_contraction is not None
            else (cfg.volume_contraction if cfg else Decimal("0.20"))
        )
        part_rate = (
            req.participation_rate
            if req.participation_rate is not None
            else (cfg.participation_rate if cfg else Decimal("0.10"))
        )
        horizon = cfg.execution_horizon_intervals if cfg else 20

        # 2. Build synthetic stressed book
        base_bids = [OrderBookLevel(price=b.price, quantity=b.quantity) for b in req.baseline_bids]
        base_asks = [OrderBookLevel(price=a.price, quantity=a.quantity) for a in req.baseline_asks]
        
        stress_book = LiquidityStressMath.construct_synthetic_stress_book(
            baseline_midpoint=req.reference_price,
            baseline_spread=req.baseline_spread,
            baseline_bids=base_bids,
            baseline_asks=base_asks,
            spread_multiplier=spread_mult,
            bid_reduction=bid_red,
            ask_reduction=ask_red,
        )

        base_vis_depth = sum(a.quantity for a in base_asks) if req.side.upper() == "BUY" else sum(b.quantity for b in base_bids)
        stress_vis_depth = stress_book.total_ask_depth if req.side.upper() == "BUY" else stress_book.total_bid_depth

        # 3. Simulate depth-walk price concession
        relevant_base_levels = base_asks if req.side.upper() == "BUY" else base_bids
        relevant_stress_levels = stress_book.asks if req.side.upper() == "BUY" else stress_book.bids
        
        _, _, base_depth_conc = LiquidityStressMath.simulate_depth_walk_concession(
            levels=relevant_base_levels,
            order_quantity=req.order_quantity,
            side=req.side,
            benchmark_price=req.reference_price,
        )
        _, _, stress_depth_conc = LiquidityStressMath.simulate_depth_walk_concession(
            levels=relevant_stress_levels,
            order_quantity=req.order_quantity,
            side=req.side,
            benchmark_price=req.reference_price,
        )

        # 4. Liquidation schedule across interval volume profiles
        volume_profiles = []
        raw_vols = req.interval_volumes if req.interval_volumes else [Decimal("10000.0")] * horizon
        for idx, v in enumerate(raw_vols):
            volume_profiles.append(
                IntervalVolumeProfile(
                    interval_index=idx,
                    baseline_volume=v,
                    volume_contraction_ratio=vol_cont,
                    participation_rate=part_rate,
                )
            )

        sched_res = LiquidityStressMath.calculate_liquidation_schedule(
            target_quantity=req.order_quantity,
            volume_profiles=volume_profiles,
            max_horizon_intervals=horizon,
        )

        # 5. Stressed Execution Cost Decomposition
        cost_res = LiquidityStressMath.calculate_stressed_execution_cost(
            order_quantity=req.order_quantity,
            side=req.side,
            reference_price=req.reference_price,
            baseline_spread=req.baseline_spread,
            stressed_spread=stress_book.stressed_spread,
            baseline_depth_concession=base_depth_conc,
            stressed_depth_concession=stress_depth_conc,
            baseline_impact_bps=Decimal("5.0"),  # baseline model output
            stressed_impact_bps=Decimal("5.0") * spread_mult,  # impact scales with stressed friction
            explicit_fees=req.explicit_fees,
            unfilled_quantity=sched_res.stressed_residual_quantity,
            terminal_price=req.terminal_price,
        )

        # 6. Persist scenario run
        db_run = LiquidityStressScenarioRun(
            run_id=req.run_id,
            scenario_code=req.scenario_code,
            scenario_version=cfg.version if cfg else 1,
            instrument_id=req.instrument_id,
            venue=req.venue,
            side=req.side.upper(),
            order_quantity=req.order_quantity,
            reference_price=req.reference_price,
            baseline_spread=req.baseline_spread,
            stressed_spread=stress_book.stressed_spread,
            baseline_visible_depth=base_vis_depth,
            stressed_visible_depth=stress_vis_depth,
            baseline_duration_intervals=sched_res.baseline_duration_intervals,
            stressed_duration_intervals=sched_res.stressed_duration_intervals,
            duration_increase_intervals=sched_res.duration_increase_intervals,
            liquidation_status=sched_res.status,
            stressed_fillable_quantity=sched_res.stressed_fillable_quantity,
            stressed_residual_quantity=sched_res.stressed_residual_quantity,
            baseline_total_cost=cost_res.baseline_cost.total_cost,
            stressed_total_cost=cost_res.stressed_cost.total_cost,
            cost_escalation_monetary=cost_res.cost_escalation_monetary,
            cost_escalation_pct=cost_res.cost_escalation_pct,
            cost_escalation_bps=cost_res.cost_escalation_bps,
        )
        await self.repo.save_scenario_run(db_run)
        await self.session.commit()

        # Build schema response
        stress_book_resp = SyntheticStressBookResponse(
            baseline_midpoint=stress_book.baseline_midpoint,
            stressed_midpoint=stress_book.stressed_midpoint,
            baseline_spread=stress_book.baseline_spread,
            stressed_spread=stress_book.stressed_spread,
            bids=[BookLevelSchema(price=b.price, quantity=b.quantity, notional=b.notional) for b in stress_book.bids],
            asks=[BookLevelSchema(price=a.price, quantity=a.quantity, notional=a.notional) for a in stress_book.asks],
            total_bid_depth=stress_book.total_bid_depth,
            total_ask_depth=stress_book.total_ask_depth,
            total_bid_notional=stress_book.total_bid_notional,
            total_ask_notional=stress_book.total_ask_notional,
        )

        return StressRunResponse(
            run_id=req.run_id,
            scenario_code=req.scenario_code,
            instrument_id=req.instrument_id,
            venue=req.venue,
            side=req.side.upper(),
            order_quantity=req.order_quantity,
            reference_price=req.reference_price,
            baseline_spread=req.baseline_spread,
            stressed_spread=stress_book.stressed_spread,
            baseline_visible_depth=base_vis_depth,
            stressed_visible_depth=stress_vis_depth,
            baseline_duration_intervals=sched_res.baseline_duration_intervals,
            stressed_duration_intervals=sched_res.stressed_duration_intervals,
            duration_increase_intervals=sched_res.duration_increase_intervals,
            liquidation_status=sched_res.status,
            stressed_fillable_quantity=sched_res.stressed_fillable_quantity,
            stressed_residual_quantity=sched_res.stressed_residual_quantity,
            baseline_cost=CostDecompositionSchema.model_validate(cost_res.baseline_cost),
            stressed_cost=CostDecompositionSchema.model_validate(cost_res.stressed_cost),
            cost_escalation_monetary=cost_res.cost_escalation_monetary,
            cost_escalation_pct=cost_res.cost_escalation_pct,
            cost_escalation_bps=cost_res.cost_escalation_bps,
            synthetic_stress_book=stress_book_resp,
            created_at=datetime.utcnow(),
        )

    async def execute_reverse_stress(self, req: ReverseStressRequest) -> ReverseStressResponse:
        res = LiquidityStressMath.reverse_stress_search(
            baseline_spread=req.baseline_spread,
            baseline_interval_volume=req.baseline_interval_volume,
            order_quantity=req.order_quantity,
            max_acceptable_cost=req.max_acceptable_cost,
            max_acceptable_intervals=req.max_acceptable_intervals,
            participation_rate=req.participation_rate,
            reference_price=req.reference_price,
        )
        return ReverseStressResponse(
            instrument_id=req.instrument_id,
            time_breached_at_baseline=res["time_breached_at_baseline"],
            critical_volume_contraction_pct=res["critical_volume_contraction_pct"],
            critical_spread_multiplier=res["critical_spread_multiplier"],
            max_acceptable_cost=req.max_acceptable_cost,
            max_acceptable_intervals=req.max_acceptable_intervals,
        )

    async def execute_portfolio_stress(self, req: PortfolioStressRequest) -> PortfolioStressResponse:
        pos_results: List[PortfolioPositionStressResult] = []
        tot_base_cost = Decimal("0.0")
        tot_stress_cost = Decimal("0.0")
        crit_path_dur = 0

        for p in req.positions:
            stressed_spread = LiquidityStressMath.calculate_stressed_spread(
                baseline_spread=p.baseline_spread,
                multiplier=req.spread_multiplier,
            )
            base_cost = p.quantity * (p.baseline_spread / Decimal("2.0"))
            stress_cost = p.quantity * (stressed_spread / Decimal("2.0"))
            cost_esc = stress_cost - base_cost

            # Liquidation duration
            base_interval_cap = p.interval_volume * req.participation_rate
            stress_interval_cap = (p.interval_volume * (Decimal("1.0") - req.volume_contraction)) * req.participation_rate

            base_dur = int(math.ceil(float(p.quantity / base_interval_cap))) if base_interval_cap > 0 else 999
            stress_dur = int(math.ceil(float(p.quantity / stress_interval_cap))) if stress_interval_cap > 0 else 999

            if stress_dur > crit_path_dur:
                crit_path_dur = stress_dur

            tot_base_cost += base_cost
            tot_stress_cost += stress_cost

            pos_results.append(
                PortfolioPositionStressResult(
                    instrument_id=p.instrument_id,
                    quantity=p.quantity,
                    baseline_cost=base_cost,
                    stressed_cost=stress_cost,
                    cost_escalation=cost_esc,
                    baseline_duration_intervals=base_dur,
                    stressed_duration_intervals=stress_dur,
                )
            )

        tot_esc = tot_stress_cost - tot_base_cost
        tot_esc_pct = (tot_esc / tot_base_cost) * Decimal("100.0") if tot_base_cost > Decimal("0.0") else None

        return PortfolioStressResponse(
            portfolio_id=req.portfolio_id,
            scenario_code=req.scenario_code,
            total_positions=len(req.positions),
            portfolio_baseline_cost=tot_base_cost,
            portfolio_stressed_cost=tot_stress_cost,
            portfolio_cost_escalation=tot_esc,
            portfolio_cost_escalation_pct=tot_esc_pct,
            critical_path_duration_intervals=crit_path_dur,
            position_results=pos_results,
        )

