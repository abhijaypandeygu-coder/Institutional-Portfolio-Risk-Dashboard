"""
M09.04 Market Impact - Service Layer.
Coordinates:
- Static Displayed-Book Depth Walks from direct inputs or M02 reconstructed books
- Order-size sensitivity and marginal cost analysis
- Participation rate constraints and horizon execution schedules
- Empirical impact model predictions (Square-root, Log-linear regression, Kyle OFI)
- Model backtesting and validation metrics
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_microstructure.order_book_depth.models import OrderBookDepthSnapshot, OrderBookDepthLevel
from backend.app.modules.market_microstructure.market_impact.models import (
    MarketImpactConfig,
    MarketImpactScenario,
    MarketImpactDepthWalk,
    MarketImpactDepthWalkLevel,
    MarketImpactEstimate,
    MarketImpactModelConfig,
    MarketImpactModelValidationRun,
)
from backend.app.modules.market_microstructure.market_impact.repositories.repository import MarketImpactRepository
from backend.app.modules.market_microstructure.market_impact.calculations.impact_math import (
    simulate_depth_walk,
    compute_order_size_sensitivity,
    compute_participation_cap,
    compute_execution_schedule,
    compute_square_root_impact,
    compute_empirical_regression_impact,
    compute_kyle_order_flow_impact,
    _normalize_tz,
)


class MarketImpactService:
    """Institutional service layer for M09.04 Market Impact."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = MarketImpactRepository(db)

    # 1. Config Management
    async def create_impact_config(self, req: Dict[str, Any]) -> MarketImpactConfig:
        existing = await self.repo.get_active_impact_config(req["config_code"])
        new_version = (existing.version + 1) if existing else 1
        cfg = MarketImpactConfig(
            config_id=f"MIC_{uuid.uuid4().hex[:12]}",
            config_code=req["config_code"],
            version=new_version,
            name=req["name"],
            reference_price_method=req.get("reference_price_method", "MIDPOINT"),
            default_execution_horizon_seconds=req.get("default_execution_horizon_seconds", 300),
            default_max_participation_rate=req.get("default_max_participation_rate", 0.10),
            default_schedule=req.get("default_schedule", "UNIFORM"),
            square_root_y_coefficient=req.get("square_root_y_coefficient", 0.50),
            is_active=True,
            created_at=datetime.now(timezone.utc),
            created_by="SYSTEM"
        )
        return await self.repo.create_impact_config(cfg)

    async def create_model_config(self, req: Dict[str, Any]) -> MarketImpactModelConfig:
        existing = await self.repo.get_active_model_config(req["model_code"])
        new_version = (existing.version + 1) if existing else 1
        cfg = MarketImpactModelConfig(
            model_id=f"MIM_{uuid.uuid4().hex[:12]}",
            model_code=req["model_code"],
            version=new_version,
            name=req["name"],
            model_type=req["model_type"],
            parameter_values=req["parameter_values"],
            calibration_sample_count=req.get("calibration_sample_count", 0),
            model_status="ACTIVE",
            created_at=datetime.now(timezone.utc),
            created_by="SYSTEM"
        )
        return await self.repo.create_model_config(cfg)

    # 2. Scenario Creation
    async def create_scenario(self, req: Dict[str, Any]) -> MarketImpactScenario:
        scen = MarketImpactScenario(
            scenario_id=f"MIS_{uuid.uuid4().hex[:12]}",
            instrument_id=req["instrument_id"],
            exchange=req.get("exchange", "NSE"),
            venue=req.get("venue", "NSE_CASH"),
            order_side=req["order_side"].upper(),
            proposed_quantity=Decimal(str(req["proposed_quantity"])),
            reference_price=Decimal(str(req["reference_price"])),
            reference_price_method=req.get("reference_price_method", "MIDPOINT"),
            currency=req.get("currency", "USD"),
            execution_horizon_seconds=req.get("execution_horizon_seconds", 0),
            maximum_participation_rate=req.get("maximum_participation_rate", 0.10),
            execution_schedule=req.get("execution_schedule", "IMMEDIATE"),
            market_regime=req.get("market_regime", "NORMAL"),
            created_at=datetime.now(timezone.utc)
        )
        return await self.repo.create_scenario(scen)

    # 3. Static Depth-Walk Simulation
    async def execute_depth_walk(
        self,
        scenario_id: str,
        side: str,
        proposed_quantity: Decimal,
        reference_price: Decimal,
        levels: Optional[List[Dict[str, Any]]] = None,
        source_book_snapshot_id: Optional[str] = None,
        instrument_multiplier: Decimal = Decimal("1.0")
    ) -> MarketImpactDepthWalk:
        """
        Executes depth walk simulation. Uses levels if passed, else resolves from M09.02 OrderBookDepthLevel.
        """
        book_levels = []
        if levels is not None:
            book_levels = levels
        elif source_book_snapshot_id is not None:
            # Query levels from M09.02
            stmt = (
                select(OrderBookDepthLevel)
                .where(
                    OrderBookDepthLevel.snapshot_id == source_book_snapshot_id,
                    OrderBookDepthLevel.side == ("BID" if side.upper() == "SELL" else "ASK")
                )
                .order_by(
                    OrderBookDepthLevel.price.desc() if side.upper() == "SELL" else OrderBookDepthLevel.price.asc()
                )
            )
            res = await self.db.execute(stmt)
            for lvl in res.scalars().all():
                book_levels.append({
                    "price": lvl.price,
                    "quantity": lvl.quantity,
                    "level": lvl.level
                })

        sim = simulate_depth_walk(
            side=side,
            proposed_quantity=proposed_quantity,
            levels=book_levels,
            reference_price=reference_price,
            instrument_multiplier=instrument_multiplier
        )

        walk_id = f"MDW_{uuid.uuid4().hex[:12]}"
        walk = MarketImpactDepthWalk(
            depth_walk_id=walk_id,
            scenario_id=scenario_id,
            source_book_snapshot_id=source_book_snapshot_id,
            order_side=side.upper(),
            proposed_quantity=proposed_quantity,
            visible_fill_quantity=sim["visible_fill_quantity"],
            residual_unfilled_quantity=sim["residual_unfilled_quantity"],
            fill_percentage=sim["fill_percentage"],
            reference_price=reference_price,
            average_execution_price=sim["average_execution_price"],
            marginal_execution_price=sim["marginal_execution_price"],
            gross_execution_value=sim["gross_execution_value"],
            estimated_cost_amount=sim["estimated_cost_amount"],
            estimated_cost_bps=sim["estimated_cost_bps"],
            spread_crossing_bps=sim["spread_crossing_bps"],
            additional_depth_bps=sim["additional_depth_bps"],
            consumed_level_count=sim["consumed_level_count"],
            available_level_count=sim["available_level_count"],
            quality_status="ELIGIBLE",
            calculation_version="1.0.0",
            created_at=datetime.now(timezone.utc)
        )

        level_entities = []
        for cl in sim["consumed_levels"]:
            level_entities.append(MarketImpactDepthWalkLevel(
                depth_walk_id=walk_id,
                level_index=cl["level_index"],
                side=side.upper(),
                price=cl["price"],
                available_quantity=cl["available_quantity"],
                consumed_quantity=cl["consumed_quantity"],
                remaining_quantity=cl["remaining_quantity"],
                executed_value=cl["executed_value"],
                created_at=datetime.now(timezone.utc)
            ))

        return await self.repo.save_depth_walk(walk, level_entities)

    # 4. Model Predictions & Estimates
    async def evaluate_empirical_impact(
        self,
        scenario_id: str,
        model_type: str,
        order_quantity: float,
        expected_horizon_volume: float,
        volatility: float,
        reference_price: Decimal,
        spread_bps: float = 5.0,
        depth_notional: float = 1000000.0,
        regime_multiplier: float = 1.0,
        impact_coefficient_y: float = 0.50,
        signed_order_flow: Optional[float] = None
    ) -> MarketImpactEstimate:
        """
        Calculates empirical market impact using chosen model (SQUARE_ROOT, EMPIRICAL_REGRESSION, KYLE_OFI).
        """
        if model_type == "SQUARE_ROOT":
            pred = compute_square_root_impact(
                order_quantity=order_quantity,
                expected_horizon_volume=expected_horizon_volume,
                horizon_volatility=volatility,
                impact_coefficient_y=impact_coefficient_y
            )
            temp_bps = None
            perm_bps = None
        elif model_type == "KYLE_OFI":
            pred = compute_kyle_order_flow_impact(
                signed_order_flow=signed_order_flow or order_quantity
            )
            pred["impact_bps"] = pred["price_change"]
            temp_bps = None
            perm_bps = None
        else:
            # EMPIRICAL_REGRESSION default
            pr = order_quantity / expected_horizon_volume if expected_horizon_volume > 0.0 else 0.0
            pred = compute_empirical_regression_impact(
                participation_rate=pr,
                spread_bps=spread_bps,
                depth_notional=depth_notional,
                volatility=volatility,
                regime_multiplier=regime_multiplier
            )
            temp_bps = pred.get("temporary_impact_bps")
            perm_bps = pred.get("permanent_impact_bps")

        # Monetary cost = notional * impact_bps / 10000
        cost_amt = None
        if pred.get("impact_bps") is not None:
            notional = Decimal(str(order_quantity)) * reference_price
            cost_amt = notional * Decimal(str(pred["impact_bps"])) / Decimal("10000.0")

        est = MarketImpactEstimate(
            estimate_id=f"MIE_{uuid.uuid4().hex[:12]}",
            scenario_id=scenario_id,
            model_type=model_type,
            model_version="1.0.0",
            reference_price=reference_price,
            estimated_impact_bps=pred.get("impact_bps"),
            estimated_temporary_impact_bps=temp_bps,
            estimated_permanent_impact_bps=perm_bps,
            estimated_cost_amount=cost_amt,
            participation_rate=pred.get("participation_rate"),
            prediction_lower_bps=pred.get("prediction_lower_bps"),
            prediction_upper_bps=pred.get("prediction_upper_bps"),
            standard_error_bps=pred.get("standard_error_bps"),
            market_regime="NORMAL" if regime_multiplier == 1.0 else "STRESSED",
            estimation_status=pred.get("status", "VALID"),
            calculation_version="1.0.0",
            created_at=datetime.now(timezone.utc)
        )
        return await self.repo.save_estimate(est)

    # 5. Validation Run
    async def record_validation_run(self, req: Dict[str, Any]) -> MarketImpactModelValidationRun:
        run = MarketImpactModelValidationRun(
            run_id=f"MVR_{uuid.uuid4().hex[:12]}",
            model_code=req["model_code"],
            model_version=1,
            sample_count=req["sample_count"],
            mae=req["mae"],
            rmse=req["rmse"],
            mean_bias_error=req["mean_bias_error"],
            interval_coverage_pct=req["interval_coverage_pct"],
            validation_status=req.get("validation_status", "PASSED"),
            created_at=datetime.now(timezone.utc)
        )
        return await self.repo.save_validation_run(run)

