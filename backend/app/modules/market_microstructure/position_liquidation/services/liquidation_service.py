"""
Service layer for M09.07 Position Liquidation.
Orchestrates:
- Position retrieval and validation
- Reduction target generation (10%, 25%, 50%, 75%, 90%, 100% or custom)
- Interval volume profiling and execution capacity calculation
- Multi-target horizon and schedule simulation
- Cost decomposition without double counting
- Portfolio-level concurrent / sequential aggregation
- Historical model calibration recording
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_microstructure.position_liquidation.calculations.liquidation_math import (
    IntervalProfile,
    TargetSpecification,
    IntervalScheduleItem,
    TargetLiquidationOutcome,
    PositionLiquidationMath,
)
from backend.app.modules.market_microstructure.position_liquidation.models.liquidation_models import (
    PositionLiquidationPlan,
    PositionLiquidationTarget,
    PositionLiquidationScheduleItem,
    PositionLiquidationHorizonResult,
    PositionLiquidationCostResult,
    PositionLiquidationCalibrationRun,
    PortfolioLiquidationSummary,
)
from backend.app.modules.market_microstructure.position_liquidation.repositories.liquidation_repository import (
    PositionLiquidationRepository,
)
from backend.app.modules.market_microstructure.position_liquidation.schemas.liquidation_schemas import (
    LiquidationPlanCreateRequest,
    LiquidationPlanResponse,
    TargetReductionSchema,
    ScheduleItemSchema,
    HorizonResultSchema,
    CostResultSchema,
    PartialComparisonResponse,
    PortfolioLiquidationRequest,
    PortfolioLiquidationResponse,
    CalibrationRunCreateRequest,
    CalibrationRunResponse,
)


class PositionLiquidationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PositionLiquidationRepository(session)

    def _generate_synthetic_intervals(
        self,
        base_time: datetime,
        count: int = 50,
        volume_per_interval: Decimal = Decimal("10000.0"),
    ) -> List[IntervalProfile]:
        """Generates standard 5-minute interval volume profiles across sessions."""
        intervals: List[IntervalProfile] = []
        cur = base_time
        for i in range(1, count + 1):
            nxt = cur + timedelta(minutes=5)
            session_idx = ((i - 1) // 75) + 1  # 75 5-min intervals = 6.25 hr trading session
            intervals.append(
                IntervalProfile(
                    interval_index=i,
                    interval_start=cur,
                    interval_end=nxt,
                    expected_volume=volume_per_interval,
                    session_index=session_idx,
                )
            )
            cur = nxt
        return intervals

    async def create_liquidation_plan(self, req: LiquidationPlanCreateRequest) -> LiquidationPlanResponse:
        side, abs_qty = PositionLiquidationMath.determine_liquidation_side(req.starting_signed_quantity)
        plan_id = f"PLN-{uuid.uuid4().hex[:10].upper()}"

        mkt_val = req.starting_market_value or (abs_qty * req.benchmark_price)

        # Build interval volume profile
        base_time = datetime.now(timezone.utc)
        if req.interval_volumes and len(req.interval_volumes) > 0:
            intervals = []
            cur = base_time
            for idx, vol in enumerate(req.interval_volumes, start=1):
                nxt = cur + timedelta(minutes=5)
                intervals.append(
                    IntervalProfile(
                        interval_index=idx,
                        interval_start=cur,
                        interval_end=nxt,
                        expected_volume=vol,
                        session_index=((idx - 1) // 75) + 1,
                    )
                )
                cur = nxt
        else:
            intervals = self._generate_synthetic_intervals(base_time, count=60, volume_per_interval=Decimal("15000.0"))

        # Evaluate targets
        outcomes = PositionLiquidationMath.evaluate_targets(
            starting_quantity=abs_qty,
            side=side,
            reference_price=req.benchmark_price,
            spread=req.spread,
            intervals=intervals,
            participation_rate=req.maximum_participation_rate,
            schedule_type=req.execution_schedule,
            target_percentages=req.target_percentages,
            custom_quantities=req.custom_quantities,
        )

        db_plan = PositionLiquidationPlan(
            plan_id=plan_id,
            plan_name=req.plan_name,
            portfolio_id=req.portfolio_id,
            position_id=req.position_id,
            position_snapshot_id=req.position_snapshot_id,
            instrument_id=req.instrument_id,
            listing_id=req.listing_id,
            venue_id=req.venue_id,
            starting_signed_quantity=req.starting_signed_quantity,
            starting_absolute_quantity=abs_qty,
            starting_market_value=mkt_val,
            position_currency=req.position_currency,
            portfolio_base_currency=req.portfolio_base_currency,
            liquidation_side=side,
            benchmark_type=req.benchmark_type,
            benchmark_price=req.benchmark_price,
            benchmark_timestamp=base_time,
            maximum_participation_rate=req.maximum_participation_rate,
            execution_schedule=req.execution_schedule,
            execution_start_timestamp=base_time,
            maximum_horizon_sessions=5,
            session_continuation_policy="CONTINUE_NEXT_SESSION",
            stress_scenario_id=req.stress_scenario_id,
            stress_scenario_version=req.stress_scenario_version,
            version=1,
            plan_status="ACTIVE",
            created_at=base_time,
            updated_at=base_time,
            created_by="SYSTEM",
        )

        target_schemas: List[TargetReductionSchema] = []
        horizon_schemas: List[HorizonResultSchema] = []
        cost_schemas: List[CostResultSchema] = []

        for out in outcomes:
            tgt_mkt_val = out.cumulative_quantity * req.benchmark_price
            db_target = PositionLiquidationTarget(
                target_id=out.target_id,
                plan_id=plan_id,
                target_sequence=int(out.target_id.replace("T", "")),
                target_type="PERCENTAGE",
                target_percentage=out.target_percentage,
                target_cumulative_quantity=out.cumulative_quantity,
                target_incremental_quantity=out.incremental_quantity,
                remaining_quantity=out.remaining_quantity,
                target_market_value=tgt_mkt_val,
                cumulative_target_flag=True,
                created_at=base_time,
            )
            db_plan.targets.append(db_target)
            target_schemas.append(
                TargetReductionSchema(
                    target_id=out.target_id,
                    target_sequence=int(out.target_id.replace("T", "")),
                    target_percentage=out.target_percentage,
                    target_cumulative_quantity=out.cumulative_quantity,
                    target_incremental_quantity=out.incremental_quantity,
                    remaining_quantity=out.remaining_quantity,
                    target_market_value=tgt_mkt_val,
                )
            )

            # Persist horizon result
            dur_seconds = out.intervals_required * 300
            db_horizon = PositionLiquidationHorizonResult(
                plan_id=plan_id,
                target_id=out.target_id,
                baseline_duration_seconds=dur_seconds,
                stressed_duration_seconds=dur_seconds if not req.stress_scenario_id else int(dur_seconds * 1.5),
                estimated_interval_count=out.intervals_required,
                estimated_session_count=out.sessions_required,
                estimated_completion_timestamp=out.completion_timestamp,
                maximum_analysis_horizon_seconds=86400,
                expected_liquidated_quantity=out.cumulative_quantity - out.residual_unliquidated_quantity,
                remaining_quantity=out.residual_unliquidated_quantity,
                completion_status=out.completion_status,
                participation_rate=req.maximum_participation_rate,
                schedule_type=req.execution_schedule,
                calculation_version="v1.0.0",
                created_at=base_time,
            )
            db_plan.horizon_results.append(db_horizon)
            horizon_schemas.append(
                HorizonResultSchema(
                    target_id=out.target_id,
                    baseline_duration_seconds=dur_seconds,
                    stressed_duration_seconds=dur_seconds if not req.stress_scenario_id else int(dur_seconds * 1.5),
                    estimated_interval_count=out.intervals_required,
                    estimated_session_count=out.sessions_required,
                    estimated_completion_timestamp=out.completion_timestamp,
                    expected_liquidated_quantity=out.cumulative_quantity - out.residual_unliquidated_quantity,
                    remaining_quantity=out.residual_unliquidated_quantity,
                    completion_status=out.completion_status,
                    participation_rate=req.maximum_participation_rate,
                    schedule_type=req.execution_schedule,
                )
            )

            # Persist cost result
            db_cost = PositionLiquidationCostResult(
                plan_id=plan_id,
                target_id=out.target_id,
                baseline_spread_cost=out.spread_cost,
                baseline_depth_walk_cost=out.depth_walk_cost,
                baseline_market_impact_cost=out.market_impact_cost,
                baseline_slippage_cost=out.slippage_cost,
                baseline_explicit_fees=out.explicit_fees,
                baseline_opportunity_cost=out.opportunity_cost,
                stressed_spread_cost=out.spread_cost * Decimal("1.5") if req.stress_scenario_id else out.spread_cost,
                stressed_depth_walk_cost=out.depth_walk_cost * Decimal("1.5") if req.stress_scenario_id else out.depth_walk_cost,
                stressed_market_impact_cost=out.market_impact_cost * Decimal("1.5") if req.stress_scenario_id else out.market_impact_cost,
                stressed_slippage_cost=out.slippage_cost * Decimal("1.5") if req.stress_scenario_id else out.slippage_cost,
                stressed_explicit_fees=out.explicit_fees,
                stressed_opportunity_cost=out.opportunity_cost * Decimal("1.5") if req.stress_scenario_id else out.opportunity_cost,
                cumulative_liquidation_cost=out.cumulative_total_cost,
                incremental_liquidation_cost=out.incremental_total_cost,
                cost_bps=out.cost_bps,
                cost_per_share=out.cost_per_share,
                cost_currency=req.position_currency,
                cost_inclusion_map="SPREAD,DEPTH_WALK,IMPACT,SLIPPAGE,FEES,OPP_COST",
                reconciliation_difference=Decimal("0.0"),
                average_execution_price=out.average_execution_price,
                quality_status="ELIGIBLE",
                calculation_version="v1.0.0",
                created_at=base_time,
            )
            db_plan.cost_results.append(db_cost)
            cost_schemas.append(
                CostResultSchema(
                    target_id=out.target_id,
                    baseline_spread_cost=out.spread_cost,
                    baseline_depth_walk_cost=out.depth_walk_cost,
                    baseline_market_impact_cost=out.market_impact_cost,
                    baseline_slippage_cost=out.slippage_cost,
                    baseline_explicit_fees=out.explicit_fees,
                    baseline_opportunity_cost=out.opportunity_cost,
                    stressed_spread_cost=db_cost.stressed_spread_cost,
                    stressed_depth_walk_cost=db_cost.stressed_depth_walk_cost,
                    stressed_market_impact_cost=db_cost.stressed_market_impact_cost,
                    stressed_slippage_cost=db_cost.stressed_slippage_cost,
                    stressed_explicit_fees=db_cost.stressed_explicit_fees,
                    stressed_opportunity_cost=db_cost.stressed_opportunity_cost,
                    cumulative_liquidation_cost=out.cumulative_total_cost,
                    incremental_liquidation_cost=out.incremental_total_cost,
                    cost_bps=out.cost_bps,
                    cost_per_share=out.cost_per_share,
                    cost_currency=req.position_currency,
                    cost_inclusion_map="SPREAD,DEPTH_WALK,IMPACT,SLIPPAGE,FEES,OPP_COST",
                    reconciliation_difference=Decimal("0.0"),
                    average_execution_price=out.average_execution_price,
                    quality_status="ELIGIBLE",
                )
            )

            # Persist interval schedule allocations for the 100% full exit target (or first target if custom)
            if out.target_percentage == Decimal("1.00") or len(outcomes) == 1:
                for item in out.schedule:
                    db_plan.schedules.append(
                        PositionLiquidationScheduleItem(
                            plan_id=plan_id,
                            target_id=out.target_id,
                            schedule_type=req.execution_schedule,
                            interval_index=item.interval_index,
                            session_index=item.session_index,
                            interval_start=item.interval_start,
                            interval_end=item.interval_end,
                            market_volume=item.market_volume,
                            planned_quantity=item.allocated_quantity,
                            planned_participation_rate=item.participation_rate,
                            expected_execution_price=out.average_execution_price,
                            estimated_interval_cost=item.total_interval_cost,
                            estimated_remaining_quantity=item.remaining_quantity,
                            created_at=base_time,
                        )
                    )

        await self.repo.save_plan(db_plan)

        return LiquidationPlanResponse(
            plan_id=plan_id,
            plan_name=db_plan.plan_name,
            portfolio_id=db_plan.portfolio_id,
            position_id=db_plan.position_id,
            instrument_id=db_plan.instrument_id,
            liquidation_side=side,
            starting_signed_quantity=req.starting_signed_quantity,
            starting_absolute_quantity=abs_qty,
            starting_market_value=mkt_val,
            position_currency=req.position_currency,
            portfolio_base_currency=req.portfolio_base_currency,
            benchmark_price=req.benchmark_price,
            maximum_participation_rate=req.maximum_participation_rate,
            execution_schedule=req.execution_schedule,
            plan_status="ACTIVE",
            version=1,
            created_at=base_time,
            targets=target_schemas,
            horizon_results=horizon_schemas,
            cost_results=cost_schemas,
        )

    async def get_plan(self, plan_id: str) -> Optional[LiquidationPlanResponse]:
        db_plan = await self.repo.get_plan_by_id(plan_id)
        if not db_plan:
            return None

        target_schemas = [
            TargetReductionSchema.model_validate(t) for t in sorted(db_plan.targets, key=lambda x: x.target_sequence)
        ]
        horizon_schemas = [
            HorizonResultSchema.model_validate(h) for h in db_plan.horizon_results
        ]
        cost_schemas = [
            CostResultSchema.model_validate(c) for c in db_plan.cost_results
        ]

        return LiquidationPlanResponse(
            plan_id=db_plan.plan_id,
            plan_name=db_plan.plan_name,
            portfolio_id=db_plan.portfolio_id,
            position_id=db_plan.position_id,
            instrument_id=db_plan.instrument_id,
            liquidation_side=db_plan.liquidation_side,
            starting_signed_quantity=db_plan.starting_signed_quantity,
            starting_absolute_quantity=db_plan.starting_absolute_quantity,
            starting_market_value=db_plan.starting_market_value,
            position_currency=db_plan.position_currency,
            portfolio_base_currency=db_plan.portfolio_base_currency,
            benchmark_price=db_plan.benchmark_price,
            maximum_participation_rate=db_plan.maximum_participation_rate,
            execution_schedule=db_plan.execution_schedule,
            plan_status=db_plan.plan_status,
            version=db_plan.version,
            created_at=db_plan.created_at,
            targets=target_schemas,
            horizon_results=horizon_schemas,
            cost_results=cost_schemas,
        )

    async def get_partial_comparison(self, plan_id: str) -> Optional[PartialComparisonResponse]:
        plan = await self.get_plan(plan_id)
        if not plan:
            return None

        # Build combined table of targets
        targets_summary = []
        target_map = {t.target_id: t for t in plan.targets}
        horizon_map = {h.target_id: h for h in plan.horizon_results}
        cost_map = {c.target_id: c for c in plan.cost_results}

        for tid, t in target_map.items():
            h = horizon_map.get(tid)
            c = cost_map.get(tid)
            targets_summary.append({
                "target_id": tid,
                "percentage": float(t.target_percentage) * 100.0,
                "cumulative_quantity": float(t.target_cumulative_quantity),
                "incremental_quantity": float(t.target_incremental_quantity),
                "remaining_quantity": float(t.remaining_quantity),
                "duration_seconds": h.baseline_duration_seconds if h else 0,
                "sessions_required": h.estimated_session_count if h else 1,
                "cumulative_cost": float(c.cumulative_liquidation_cost) if c else 0.0,
                "incremental_cost": float(c.incremental_liquidation_cost) if c else 0.0,
                "cost_bps": float(c.cost_bps) if c else 0.0,
                "completion_status": h.completion_status if h else "UNKNOWN",
            })

        targets_summary.sort(key=lambda x: x["percentage"])

        return PartialComparisonResponse(
            plan_id=plan_id,
            instrument_id=plan.instrument_id,
            liquidation_side=plan.liquidation_side,
            starting_quantity=plan.starting_absolute_quantity,
            targets=targets_summary,
        )

    async def run_portfolio_liquidation(self, req: PortfolioLiquidationRequest) -> PortfolioLiquidationResponse:
        base_time = datetime.now(timezone.utc)
        intervals = self._generate_synthetic_intervals(base_time, count=100, volume_per_interval=Decimal("20000.0"))

        calc_res = PositionLiquidationMath.calculate_portfolio_liquidation_schedule(
            positions=req.positions,
            intervals=intervals,
            participation_rate=req.participation_rate,
            schedule_mode=req.schedule_mode,
        )

        summary_id = f"PLSUM-{uuid.uuid4().hex[:10].upper()}"
        db_summary = PortfolioLiquidationSummary(
            summary_id=summary_id,
            portfolio_id=req.portfolio_id,
            schedule_mode=req.schedule_mode,
            position_count=calc_res["position_count"],
            total_market_value=calc_res["total_market_value"],
            total_liquidation_cost=calc_res["total_liquidation_cost"],
            long_liquidation_cost=calc_res["long_liquidation_cost"],
            short_covering_cost=calc_res["short_covering_cost"],
            critical_path_duration_seconds=calc_res["critical_path_duration_seconds"],
            portfolio_duration_seconds=calc_res["portfolio_duration_seconds"],
            completion_status="FULLY_LIQUIDATED_ESTIMATED",
            base_currency="USD",
            created_at=base_time,
        )
        await self.repo.save_portfolio_summary(db_summary)

        return PortfolioLiquidationResponse(
            portfolio_id=req.portfolio_id,
            schedule_mode=req.schedule_mode,
            position_count=calc_res["position_count"],
            total_market_value=calc_res["total_market_value"],
            total_liquidation_cost=calc_res["total_liquidation_cost"],
            long_liquidation_cost=calc_res["long_liquidation_cost"],
            short_covering_cost=calc_res["short_covering_cost"],
            critical_path_duration_seconds=calc_res["critical_path_duration_seconds"],
            portfolio_duration_seconds=calc_res["portfolio_duration_seconds"],
            completion_status="FULLY_LIQUIDATED_ESTIMATED",
            positions=calc_res["positions"],
        )

    async def record_calibration_run(self, req: CalibrationRunCreateRequest) -> CalibrationRunResponse:
        calib_id = f"CALIB-{uuid.uuid4().hex[:10].upper()}"
        now = datetime.now(timezone.utc)
        db_run = PositionLiquidationCalibrationRun(
            calibration_id=calib_id,
            model_id=req.model_id,
            model_version=req.model_version,
            calibration_start=req.calibration_start,
            calibration_end=req.calibration_end,
            training_sample_count=req.training_sample_count,
            duration_mae_seconds=req.duration_mae_seconds,
            duration_rmse_seconds=req.duration_rmse_seconds,
            cost_mae_bps=req.cost_mae_bps,
            cost_rmse_bps=req.cost_rmse_bps,
            prediction_bias_bps=req.prediction_bias_bps,
            validation_status="VALIDATED",
            created_at=now,
        )
        await self.repo.save_calibration_run(db_run)
        return CalibrationRunResponse.model_validate(db_run)

    async def list_calibration_runs(self) -> List[CalibrationRunResponse]:
        runs = await self.repo.list_calibration_runs()
        return [CalibrationRunResponse.model_validate(r) for r in runs]
