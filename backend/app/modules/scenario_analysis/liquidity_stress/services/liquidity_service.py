"""
M10.06 Liquidity Stress Testing Orchestration & Calculation Services.
Integrates:
- M05 authoritative position quantities & market values
- M09.01 baseline spreads & M09.02 baseline depths
- Simultaneous spread widening, depth reduction, and volume contraction
- Position-level capacity and trading calendar-aware liquidation durations
- Stressed liquidation cost decomposition (spread, depth-walk, impact, slippage, fees)
- Progressive horizon liquidation ratios and residual exposure
- Portfolio-level aggregation and narrative generation
- Versioned immutable execution history and audit logs
"""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
import time
from typing import Dict, List, Optional, Tuple, Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.modules.portfolio_management.position_valuation.models import PositionValuation
from backend.app.modules.scenario_analysis.liquidity_stress.models import (
    LiquidityStressScenario,
    LiquidityStressConfiguration,
    LiquidityStressInstrumentOverride,
    LiquidityStressRun,
    LiquidityStressMarketSnapshot,
    LiquidityStressDepthLevel,
    LiquidityStressPositionResult,
    LiquidityStressHorizonResult,
    LiquidityStressCostAttribution,
    LiquidityStressAuditEvent,
    ScenarioCategory,
    ScenarioStatus,
    RunStatus,
)
from backend.app.modules.scenario_analysis.liquidity_stress.schemas import (
    LiquidityStressScenarioCreate,
    LiquidityStressScenarioResponse,
    ExecuteLiquidityStressRequest,
    PositionResultResponse,
    HorizonResultResponse,
    CostAttributionResponse,
    LiquidityStressRunResponse,
)
from backend.app.modules.scenario_analysis.liquidity_stress.calculations import (
    calculate_stressed_spread,
    apply_depth_stress,
    execute_order_book_walk,
    calculate_interval_capacity,
    build_liquidation_schedule,
    calculate_stressed_execution_costs,
    OrderBookLevel,
)
from backend.app.modules.scenario_analysis.liquidity_stress.repositories import (
    LiquidityStressRepository,
)


class LiquidityStressService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = LiquidityStressRepository(session)

    # ---------------------------------------------------------
    # 1. Scenario Lifecycle & Versioning
    # ---------------------------------------------------------
    async def create_scenario(
        self, payload: LiquidityStressScenarioCreate
    ) -> LiquidityStressScenarioResponse:
        # Create parent scenario
        scenario = LiquidityStressScenario(
            scenario_code=payload.scenario_code,
            name=payload.name,
            description=payload.description,
            scenario_category=payload.scenario_category,
            status=ScenarioStatus.ACTIVE,
            version=1,
            created_by=payload.created_by,
        )
        scenario = await self.repo.create_scenario(scenario)

        # Create immutable initial configuration (version 1)
        config = LiquidityStressConfiguration(
            scenario_id=scenario.id,
            version_number=1,
            spread_stress_type=payload.spread_stress_type,
            spread_increase_pct=payload.spread_increase_pct,
            spread_multiplier=payload.spread_multiplier,
            absolute_spread_change=payload.absolute_spread_change,
            bid_depth_multiplier=payload.bid_depth_multiplier,
            ask_depth_multiplier=payload.ask_depth_multiplier,
            depth_stress_profile=payload.depth_stress_profile,
            market_volume_multiplier=payload.market_volume_multiplier,
            participation_multiplier=payload.participation_multiplier,
            base_participation_cap=payload.base_participation_cap,
            impact_multiplier=payload.impact_multiplier,
            execution_horizon_sessions=payload.execution_horizon_sessions,
            market_price_shock_pct=payload.market_price_shock_pct,
            configuration_json=payload.model_dump(mode="json"),
        )
        config = await self.repo.create_configuration(config)

        # Add instrument overrides if any
        if payload.overrides:
            for ov in payload.overrides:
                override_rec = LiquidityStressInstrumentOverride(
                    scenario_id=scenario.id,
                    instrument_id=ov.instrument_id,
                    listing_id=ov.listing_id,
                    spread_widening_override_pct=ov.spread_widening_override_pct,
                    depth_multiplier_override=ov.depth_multiplier_override,
                    volume_multiplier_override=ov.volume_multiplier_override,
                    participation_cap_override=ov.participation_cap_override,
                    override_metadata=ov.override_metadata or {},
                )
                self.session.add(override_rec)

        await self.session.commit()
        return self._format_scenario_response(scenario, config)

    async def list_scenarios(
        self, status: Optional[ScenarioStatus] = None
    ) -> List[LiquidityStressScenarioResponse]:
        scenarios = await self.repo.list_scenarios(status=status)
        responses = []
        for s in scenarios:
            cfg = await self.repo.get_latest_configuration(s.id)
            if cfg:
                responses.append(self._format_scenario_response(s, cfg))
        return responses

    async def get_scenario(self, scenario_id: str) -> Optional[LiquidityStressScenarioResponse]:
        scenario = await self.repo.get_scenario_by_id(scenario_id)
        if not scenario:
            return None
        cfg = await self.repo.get_latest_configuration(scenario.id)
        if not cfg:
            return None
        return self._format_scenario_response(scenario, cfg)

    # ---------------------------------------------------------
    # 2. Execution Pipeline Orchestration
    # ---------------------------------------------------------
    async def execute_scenario(
        self,
        scenario_id: str,
        request: ExecuteLiquidityStressRequest,
    ) -> LiquidityStressRunResponse:
        start_time = time.time()
        scenario = await self.repo.get_scenario_by_id(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")

        config = await self.repo.get_latest_configuration(scenario_id)
        if not config:
            raise ValueError(f"No configuration found for scenario {scenario_id}")

        run_code = f"RUN_LIQ_{uuid.uuid4().hex[:10].upper()}"
        run = LiquidityStressRun(
            run_code=run_code,
            scenario_id=scenario.id,
            scenario_version=config.version_number,
            portfolio_id=request.portfolio_id,
            baseline_snapshot_id=request.baseline_snapshot_id,
            status=RunStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            created_by=request.executed_by or "lead_risk_officer",
        )
        run = await self.repo.create_run(run)

        try:
            # 1. Resolve Portfolio Positions & Market Inputs
            positions = await self._resolve_portfolio_positions(
                portfolio_id=request.portfolio_id, custom_positions=request.custom_positions
            )
            if not positions:
                raise ValueError(f"No active positions found for portfolio {request.portfolio_id}")

            # Collect override map for instrument-specific shocks
            override_map = {ov.instrument_id: ov for ov in scenario.overrides}

            # Portfolio aggregation counters
            total_baseline_notional = Decimal("0.0")
            total_stressed_notional = Decimal("0.0")
            total_baseline_cost = Decimal("0.0")
            total_stressed_cost = Decimal("0.0")
            max_stressed_sessions = Decimal("0.0")
            max_baseline_sessions = Decimal("0.0")
            unliquidated_count = 0
            total_residual_mv = Decimal("0.0")

            # Cost attribution accumulators across portfolio
            total_spread_cost_base = Decimal("0.0")
            total_spread_cost_stress = Decimal("0.0")
            total_depth_cost_base = Decimal("0.0")
            total_depth_cost_stress = Decimal("0.0")
            total_impact_cost_base = Decimal("0.0")
            total_impact_cost_stress = Decimal("0.0")
            total_slippage_cost_base = Decimal("0.0")
            total_slippage_cost_stress = Decimal("0.0")
            total_fees_cost_base = Decimal("0.0")
            total_fees_cost_stress = Decimal("0.0")

            position_response_list: List[PositionResultResponse] = []
            portfolio_horizon_buckets: Dict[str, Dict[str, Any]] = {}

            # 2. Iterate each holding and perform stressed liquidation modeling
            for p in positions:
                inst_id = p["instrument_id"]
                symbol = p.get("symbol", inst_id)
                qty = Decimal(str(p["quantity"]))
                abs_qty = abs(qty)
                side = "SELL" if qty > Decimal("0.0") else "BUY"
                base_price = Decimal(str(p.get("price", "100.00")))
                market_val = abs_qty * base_price
                total_baseline_notional += market_val

                # Resolve applicable stress multipliers (with instrument override support)
                ov = override_map.get(inst_id)
                spread_widening_pct = (
                    ov.spread_widening_override_pct
                    if (ov and ov.spread_widening_override_pct is not None)
                    else config.spread_increase_pct
                )
                depth_multiplier = (
                    ov.depth_multiplier_override
                    if (ov and ov.depth_multiplier_override is not None)
                    else config.bid_depth_multiplier
                )
                vol_multiplier = (
                    ov.volume_multiplier_override
                    if (ov and ov.volume_multiplier_override is not None)
                    else config.market_volume_multiplier
                )
                vol_contraction_pct = max(Decimal("0.0"), Decimal("1.0") - vol_multiplier)
                
                part_multiplier = (
                    ov.participation_cap_override
                    if (ov and ov.participation_cap_override is not None)
                    else config.participation_multiplier
                )
                part_reduction_pct = max(Decimal("0.0"), Decimal("1.0") - part_multiplier)

                # A. Baseline Market Data (observed or standard defaults)
                base_spread = Decimal(str(p.get("spread", "0.05")))
                base_bid = base_price - (base_spread / Decimal("2.0"))
                base_ask = base_price + (base_spread / Decimal("2.0"))
                base_vol = Decimal(str(p.get("volume", "200000")))
                base_depth_qty = Decimal(str(p.get("depth", "50000")))

                # B. Stressed Spread & Midpoint Calculation
                (
                    stress_spread,
                    stress_mid,
                    stress_bid,
                    stress_ask,
                ) = calculate_stressed_spread(
                    baseline_bid=base_bid,
                    baseline_ask=base_ask,
                    spread_widening_pct=spread_widening_pct,
                    spread_multiplier=config.spread_multiplier,
                    tick_size=Decimal("0.01"),
                    market_price_shock_pct=config.market_price_shock_pct,
                )
                stressed_mv = abs_qty * stress_mid
                total_stressed_notional += stressed_mv

                # C. Baseline and Stressed L2 Depth Profiles
                raw_bids = [{"price": base_bid - Decimal(i)*Decimal("0.02"), "quantity": base_depth_qty / Decimal("5")} for i in range(5)]
                raw_asks = [{"price": base_ask + Decimal(i)*Decimal("0.02"), "quantity": base_depth_qty / Decimal("5")} for i in range(5)]
                
                stressed_bids = apply_depth_stress(raw_bids, depth_multiplier=depth_multiplier)
                stressed_asks = apply_depth_stress(raw_asks, depth_multiplier=depth_multiplier)
                
                # Snapshot DB record
                mkt_snap = LiquidityStressMarketSnapshot(
                    run_id=run.id,
                    instrument_id=inst_id,
                    listing_id=p.get("listing_id"),
                    baseline_bid=base_bid,
                    baseline_ask=base_ask,
                    baseline_midpoint=base_price,
                    stressed_bid=stress_bid,
                    stressed_ask=stress_ask,
                    stressed_midpoint=stress_mid,
                    baseline_spread=base_spread,
                    stressed_spread=stress_spread,
                    spread_widening_multiple=(stress_spread / base_spread).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    baseline_bid_depth=base_depth_qty,
                    baseline_ask_depth=base_depth_qty,
                    stressed_bid_depth=sum(b.quantity for b in stressed_bids),
                    stressed_ask_depth=sum(a.quantity for a in stressed_asks),
                    baseline_volume=base_vol,
                    stressed_volume=base_vol * vol_multiplier,
                    data_quality_status="OBSERVED_INPUT",
                )
                self.session.add(mkt_snap)
                await self.session.flush()

                # Persist Depth Levels
                for b_lvl in stressed_bids:
                    self.session.add(
                        LiquidityStressDepthLevel(
                            market_snapshot_id=mkt_snap.id,
                            side="BID",
                            level_number=1,
                            baseline_price=b_lvl.price,
                            baseline_quantity=base_depth_qty / Decimal("5"),
                            stressed_price=b_lvl.price,
                            stressed_quantity=b_lvl.quantity,
                            depth_multiplier=depth_multiplier,
                            level_notional=b_lvl.quantity * b_lvl.price,
                        )
                    )

                # D. Book-Walk Concession
                walk_levels = stressed_bids if side == "SELL" else stressed_asks
                _, _, _, depth_walk_concession = execute_order_book_walk(
                    levels=walk_levels,
                    target_quantity=abs_qty,
                    side=side,
                    reference_midpoint=stress_mid,
                )

                # E. Capacity & Liquidation Scheduling
                # 26 intervals per trading day (15 min buckets in 6.5h session)
                daily_intervals = 26
                int_base_vol = (base_vol / Decimal(daily_intervals)).quantize(Decimal("1"), rounding=ROUND_DOWN)

                # Baseline Capacity (no volume contraction, baseline 10% cap)
                _, _, base_int_cap = calculate_interval_capacity(
                    interval_baseline_volume=int_base_vol,
                    volume_reduction_pct=Decimal("0.0"),
                    participation_cap=config.base_participation_cap,
                    participation_reduction_pct=Decimal("0.0"),
                )
                baseline_capacities = [base_int_cap] * (daily_intervals * config.execution_horizon_sessions)

                # Stressed Capacity
                _, _, stress_int_cap = calculate_interval_capacity(
                    interval_baseline_volume=int_base_vol,
                    volume_reduction_pct=vol_contraction_pct,
                    participation_cap=config.base_participation_cap,
                    participation_reduction_pct=part_reduction_pct,
                )
                stressed_capacities = [stress_int_cap] * (daily_intervals * config.execution_horizon_sessions)

                # Build Schedules
                base_horizons, base_ints_needed, base_filled_qty, base_res_qty, base_completed = build_liquidation_schedule(
                    target_quantity=abs_qty,
                    interval_capacities=baseline_capacities,
                    interval_minutes=15,
                    reference_price=base_price,
                )
                stress_horizons, stress_ints_needed, stress_filled_qty, stress_res_qty, stress_completed = build_liquidation_schedule(
                    target_quantity=abs_qty,
                    interval_capacities=stressed_capacities,
                    interval_minutes=15,
                    reference_price=stress_mid,
                )

                base_duration_sessions = (Decimal(base_ints_needed) / Decimal(daily_intervals)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                stress_duration_sessions = (Decimal(stress_ints_needed) / Decimal(daily_intervals)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                max_baseline_sessions = max(max_baseline_sessions, base_duration_sessions)
                max_stressed_sessions = max(max_stressed_sessions, stress_duration_sessions)

                if not stress_completed or stress_res_qty > Decimal("0.0"):
                    unliquidated_count += 1
                    total_residual_mv += (stress_res_qty * stress_mid)

                # F. Stressed Execution Cost Breakdown
                # Baseline Cost Breakdown
                base_cost_obj = calculate_stressed_execution_costs(
                    executed_quantity=base_filled_qty,
                    reference_midpoint=base_price,
                    stressed_spread=base_spread,
                    daily_volatility=Decimal("0.02"),
                    market_volume=base_vol,
                    impact_multiplier=Decimal("1.0"),
                    brokerage_bps=Decimal("2.0"),
                    depth_walk_concession=Decimal("0.0"),
                )
                # Stressed Cost Breakdown
                stress_cost_obj = calculate_stressed_execution_costs(
                    executed_quantity=stress_filled_qty,
                    reference_midpoint=stress_mid,
                    stressed_spread=stress_spread,
                    daily_volatility=Decimal("0.02"),
                    market_volume=base_vol * vol_multiplier,
                    impact_multiplier=config.impact_multiplier,
                    brokerage_bps=Decimal("2.0"),
                    depth_walk_concession=depth_walk_concession,
                )

                base_pos_cost = base_cost_obj.total_liquidation_cost
                stress_pos_cost = stress_cost_obj.total_liquidation_cost
                inc_pos_cost = stress_pos_cost - base_pos_cost

                total_baseline_cost += base_pos_cost
                total_stressed_cost += stress_pos_cost

                # Accumulate for portfolio attribution
                total_spread_cost_base += base_cost_obj.spread_crossing_cost
                total_spread_cost_stress += stress_cost_obj.spread_crossing_cost
                total_depth_cost_base += base_cost_obj.depth_walk_cost
                total_depth_cost_stress += stress_cost_obj.depth_walk_cost
                total_impact_cost_base += base_cost_obj.market_impact_cost
                total_impact_cost_stress += stress_cost_obj.market_impact_cost
                total_slippage_cost_base += base_cost_obj.slippage_cost
                total_slippage_cost_stress += stress_cost_obj.slippage_cost
                total_fees_cost_base += base_cost_obj.explicit_fees
                total_fees_cost_stress += stress_cost_obj.explicit_fees

                # G. Position Result Record
                pos_status = "COMPLETED" if stress_completed else "PARTIALLY_LIQUIDATED"
                pos_res = LiquidityStressPositionResult(
                    run_id=run.id,
                    portfolio_id=request.portfolio_id,
                    instrument_id=inst_id,
                    symbol=symbol,
                    listing_id=p.get("listing_id"),
                    signed_position_quantity=qty,
                    liquidation_side=side,
                    market_value=market_val,
                    baseline_capacity=base_int_cap * Decimal(daily_intervals * config.execution_horizon_sessions),
                    stressed_capacity=stress_int_cap * Decimal(daily_intervals * config.execution_horizon_sessions),
                    baseline_duration_sessions=base_duration_sessions,
                    stressed_duration_sessions=stress_duration_sessions,
                    baseline_liquidation_cost=base_pos_cost,
                    stressed_liquidation_cost=stress_pos_cost,
                    incremental_liquidation_cost=inc_pos_cost,
                    baseline_cost_bps=base_cost_obj.cost_bps,
                    stressed_cost_bps=stress_cost_obj.cost_bps,
                    residual_quantity=stress_res_qty,
                    residual_market_value=stress_res_qty * stress_mid,
                    completion_status=pos_status,
                    quality_status="OBSERVED_INPUT",
                )
                self.session.add(pos_res)

                position_response_list.append(
                    PositionResultResponse(
                        instrument_id=inst_id,
                        symbol=symbol,
                        signed_position_quantity=qty,
                        liquidation_side=side,
                        market_value=market_val,
                        baseline_capacity=pos_res.baseline_capacity,
                        stressed_capacity=pos_res.stressed_capacity,
                        baseline_duration_sessions=base_duration_sessions,
                        stressed_duration_sessions=stress_duration_sessions,
                        baseline_liquidation_cost=base_pos_cost,
                        stressed_liquidation_cost=stress_pos_cost,
                        incremental_liquidation_cost=inc_pos_cost,
                        baseline_cost_bps=base_cost_obj.cost_bps,
                        stressed_cost_bps=stress_cost_obj.cost_bps,
                        residual_quantity=stress_res_qty,
                        residual_market_value=stress_res_qty * stress_mid,
                        completion_status=pos_status,
                    )
                )

                # H. Accumulate Horizon Analysis for Portfolio
                for h in stress_horizons:
                    if h.horizon_name not in portfolio_horizon_buckets:
                        portfolio_horizon_buckets[h.horizon_name] = {
                            "minutes": h.interval_minutes,
                            "executed_qty": Decimal("0.0"),
                            "total_target_qty": Decimal("0.0"),
                            "cost": Decimal("0.0"),
                        }
                    b = portfolio_horizon_buckets[h.horizon_name]
                    b["executed_qty"] += h.executable_quantity
                    b["total_target_qty"] += abs_qty
                    b["cost"] += h.estimated_cost

            # 3. Persist Portfolio-Level Horizon Results
            horizon_response_list: List[HorizonResultResponse] = []
            for h_name, data in portfolio_horizon_buckets.items():
                tot_target = data["total_target_qty"]
                tot_exec = data["executed_qty"]
                tot_res = max(Decimal("0.0"), tot_target - tot_exec)
                ratio = (tot_exec / tot_target) if tot_target > Decimal("0.0") else Decimal("1.0")
                h_cost = data["cost"]
                h_bps = ((h_cost / (tot_exec * Decimal("100.00"))) * Decimal("10000.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if tot_exec > Decimal("0.0") else Decimal("0.0")

                h_status = "COMPLETED" if tot_res == Decimal("0.0") else "IN_PROGRESS"
                hr_db = LiquidityStressHorizonResult(
                    run_id=run.id,
                    instrument_id=None,
                    horizon_type=h_name,
                    horizon_minutes=data["minutes"],
                    cumulative_executed_quantity=tot_exec,
                    residual_quantity=tot_res,
                    liquidation_ratio=ratio.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
                    estimated_cost=h_cost,
                    estimated_cost_bps=h_bps,
                    completion_status=h_status,
                )
                self.session.add(hr_db)

                horizon_response_list.append(
                    HorizonResultResponse(
                        horizon_type=h_name,
                        horizon_minutes=data["minutes"],
                        cumulative_executed_quantity=tot_exec,
                        residual_quantity=tot_res,
                        liquidation_ratio=ratio.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
                        estimated_cost=h_cost,
                        estimated_cost_bps=h_bps,
                        completion_status=h_status,
                    )
                )

            # 4. Persist Portfolio Cost Attributions
            cost_attribution_list: List[CostAttributionResponse] = []
            for comp_name, b_val, s_val in [
                ("SPREAD_CROSSING", total_spread_cost_base, total_spread_cost_stress),
                ("DEPTH_WALK_CONCESSION", total_depth_cost_base, total_depth_cost_stress),
                ("MARKET_IMPACT", total_impact_cost_base, total_impact_cost_stress),
                ("SLIPPAGE", total_slippage_cost_base, total_slippage_cost_stress),
                ("EXPLICIT_FEES", total_fees_cost_base, total_fees_cost_stress),
            ]:
                inc_val = s_val - b_val
                ca_db = LiquidityStressCostAttribution(
                    run_id=run.id,
                    instrument_id=None,
                    cost_component=comp_name,
                    baseline_cost=b_val,
                    stressed_cost=s_val,
                    incremental_cost=inc_val,
                    attribution_method="STANDALONE_FACTORIAL",
                )
                self.session.add(ca_db)
                cost_attribution_list.append(
                    CostAttributionResponse(
                        cost_component=comp_name,
                        baseline_cost=b_val,
                        stressed_cost=s_val,
                        incremental_cost=inc_val,
                        attribution_method="STANDALONE_FACTORIAL",
                    )
                )

            # 5. Finalize Portfolio Aggregates & Narrative
            total_inc_cost = total_stressed_cost - total_baseline_cost
            base_bps = ((total_baseline_cost / total_baseline_notional) * Decimal("10000.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if total_baseline_notional > Decimal("0.0") else Decimal("0.0")
            stress_bps = ((total_stressed_cost / total_stressed_notional) * Decimal("10000.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if total_stressed_notional > Decimal("0.0") else Decimal("0.0")
            
            run.baseline_portfolio_notional = total_baseline_notional
            run.stressed_portfolio_notional = total_stressed_notional
            run.baseline_total_cost = total_baseline_cost
            run.stressed_total_cost = total_stressed_cost
            run.incremental_cost = total_inc_cost
            run.baseline_cost_bps = base_bps
            run.stressed_cost_bps = stress_bps
            run.baseline_duration_sessions = max_baseline_sessions
            run.stressed_duration_sessions = max_stressed_sessions
            run.portfolio_liquidation_ratio = (
                (Decimal("1.0") - (total_residual_mv / total_stressed_notional)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
                if total_stressed_notional > Decimal("0.0")
                else Decimal("1.0")
            )
            run.residual_market_value = total_residual_mv
            run.unliquidated_positions_count = unliquidated_count
            run.status = RunStatus.COMPLETED if unliquidated_count == 0 else RunStatus.COMPLETED_WITH_WARNINGS
            run.completed_at = datetime.now(timezone.utc)
            run.execution_duration_ms = int((time.time() - start_time) * 1000)

            # Narrative formulation
            narrative = (
                f"Under the '{scenario.name}' scenario, portfolio liquidation cost escalates by "
                f"${total_inc_cost:,.2f} (+{(stress_bps - base_bps):.2f} bps), from ${total_baseline_cost:,.2f} ({base_bps:.2f} bps) "
                f"to ${total_stressed_cost:,.2f} ({stress_bps:.2f} bps). "
                f"Liquidation duration extends from {max_baseline_sessions:.1f} sessions to {max_stressed_sessions:.1f} sessions. "
                f"{unliquidated_count} positions face incomplete liquidation within the {config.execution_horizon_sessions}-session horizon, "
                f"leaving ${total_residual_mv:,.2f} in residual market exposure."
            )

            # 6. Audit Logging
            await self.repo.log_audit_event(
                run_id=run.id,
                event_type="RUN_COMPLETED",
                description=f"Liquidity stress run {run.run_code} completed across {len(positions)} positions.",
                payload={"incremental_cost": float(total_inc_cost), "unliquidated_count": unliquidated_count},
                user_id=request.executed_by or "lead_risk_officer",
            )

            await self.session.commit()

            return LiquidityStressRunResponse(
                run_id=run.id,
                run_code=run.run_code,
                scenario_id=scenario.id,
                scenario_version=config.version_number,
                portfolio_id=request.portfolio_id,
                status=run.status,
                started_at=run.started_at,
                completed_at=run.completed_at,
                execution_duration_ms=run.execution_duration_ms,
                baseline_portfolio_notional=total_baseline_notional,
                stressed_portfolio_notional=total_stressed_notional,
                baseline_total_cost=total_baseline_cost,
                stressed_total_cost=total_stressed_cost,
                incremental_cost=total_inc_cost,
                baseline_cost_bps=base_bps,
                stressed_cost_bps=stress_bps,
                baseline_duration_sessions=max_baseline_sessions,
                stressed_duration_sessions=max_stressed_sessions,
                portfolio_liquidation_ratio=run.portfolio_liquidation_ratio,
                residual_market_value=total_residual_mv,
                unliquidated_positions_count=unliquidated_count,
                position_results=position_response_list,
                horizon_results=horizon_response_list,
                cost_attributions=cost_attribution_list,
                narrative=narrative,
            )

        except Exception as e:
            await self.session.rollback()
            run.status = RunStatus.FAILED
            run.error_summary = str(e)
            run.completed_at = datetime.now(timezone.utc)
            self.session.add(run)
            await self.session.commit()
            raise

    # ---------------------------------------------------------
    # Internal Position Resolver
    # ---------------------------------------------------------
    async def _resolve_portfolio_positions(
        self,
        portfolio_id: str,
        custom_positions: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        if custom_positions:
            return custom_positions

        # Query authoritative M05 Position Valuations
        stmt = select(PositionValuation).where(PositionValuation.portfolio_id == portfolio_id)
        res = await self.session.execute(stmt)
        records = list(res.scalars().all())

        positions = []
        for r in records:
            positions.append({
                "instrument_id": r.instrument_id,
                "listing_id": r.listing_id,
                "quantity": Decimal(str(r.signed_quantity)),
                "price": Decimal(str(r.mark_price)),
                "spread": (Decimal(str(r.mark_price)) * Decimal("0.0005")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                "volume": Decimal("250000"),
                "depth": Decimal("50000"),
            })
        return positions

    def _format_scenario_response(
        self, scenario: LiquidityStressScenario, config: LiquidityStressConfiguration
    ) -> LiquidityStressScenarioResponse:
        return LiquidityStressScenarioResponse(
            id=scenario.id,
            scenario_code=scenario.scenario_code,
            name=scenario.name,
            description=scenario.description,
            scenario_category=scenario.scenario_category,
            status=scenario.status,
            version=scenario.version,
            parent_scenario_id=scenario.parent_scenario_id,
            created_by=scenario.created_by,
            created_at=scenario.created_at,
            updated_at=scenario.updated_at,
            spread_increase_pct=config.spread_increase_pct,
            bid_depth_multiplier=config.bid_depth_multiplier,
            ask_depth_multiplier=config.ask_depth_multiplier,
            market_volume_multiplier=config.market_volume_multiplier,
            participation_multiplier=config.participation_multiplier,
            impact_multiplier=config.impact_multiplier,
            execution_horizon_sessions=config.execution_horizon_sessions,
        )
