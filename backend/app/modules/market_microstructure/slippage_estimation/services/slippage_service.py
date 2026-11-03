"""
Service layer for M09.05 Slippage Estimation.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_microstructure.slippage_estimation.calculations.slippage_math import (
    FillExecutionData,
    SlippageMath,
)
from backend.app.modules.market_microstructure.slippage_estimation.models.slippage_models import (
    SlippageBenchmarkConfig,
    SlippageExecutionSummary,
    SlippageFillAttribution,
    SlippageOpportunityCost,
    SlippageCalibrationObservation,
    SlippageCalibrationRun,
)
from backend.app.modules.market_microstructure.slippage_estimation.repositories.slippage_repository import (
    SlippageRepository,
)
from backend.app.modules.market_microstructure.slippage_estimation.schemas.slippage_schemas import (
    BenchmarkConfigCreate,
    BenchmarkConfigResponse,
    SlippageAnalysisRequest,
    SlippageExecutionSummaryResponse,
    FillAttributionSchema,
    CalibrationRunRequest,
    CalibrationRunResponse,
)


class SlippageService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SlippageRepository(session)

    async def get_or_create_benchmark_config(
        self, config_in: BenchmarkConfigCreate
    ) -> BenchmarkConfigResponse:
        existing = await self.repo.get_benchmark_config(config_in.config_code)
        if existing:
            return BenchmarkConfigResponse.model_validate(existing)

        db_config = SlippageBenchmarkConfig(
            config_code=config_in.config_code,
            version=config_in.version,
            description=config_in.description,
            benchmark_type=config_in.benchmark_type,
            max_quote_age_seconds=config_in.max_quote_age_seconds,
            allow_cross_venue_benchmarking=config_in.allow_cross_venue_benchmarking,
            currency=config_in.currency,
            multiplier=config_in.multiplier,
            is_active=config_in.is_active,
        )
        saved = await self.repo.create_benchmark_config(db_config)
        await self.session.commit()
        return BenchmarkConfigResponse.model_validate(saved)

    async def analyze_and_record_execution(
        self, req: SlippageAnalysisRequest
    ) -> SlippageExecutionSummaryResponse:
        # Convert fills to calculation data models
        calc_fills = [
            FillExecutionData(
                fill_id=f.fill_id,
                fill_timestamp=f.fill_timestamp.isoformat(),
                price=f.price,
                quantity=f.quantity,
                venue=f.venue or "DEFAULT",
                bid_at_fill=f.bid_at_fill,
                ask_at_fill=f.ask_at_fill,
                midpoint_at_fill=f.midpoint_at_fill,
                fees=f.fees,
            )
            for f in req.fills
        ]

        summary_res, fill_attr_res = SlippageMath.calculate_execution_summary(
            side=req.side,
            requested_quantity=req.requested_quantity,
            benchmark_price=req.benchmark_price,
            benchmark_type=req.benchmark_type,
            fills=calc_fills,
            terminal_price=req.terminal_price,
            multiplier=req.multiplier,
        )

        completed_at = max(f.fill_timestamp for f in req.fills) if req.fills else req.order_created_at

        # Save summary
        db_summary = SlippageExecutionSummary(
            order_id=req.order_id,
            symbol=req.symbol,
            side=req.side.upper(),
            order_created_at=req.order_created_at,
            execution_completed_at=completed_at,
            requested_quantity=summary_res.total_requested_quantity,
            filled_quantity=summary_res.total_filled_quantity,
            unfilled_quantity=summary_res.unfilled_quantity,
            fill_rate_pct=summary_res.fill_rate_pct,
            benchmark_type=summary_res.benchmark_type,
            benchmark_price=summary_res.benchmark_price,
            benchmark_timestamp=req.benchmark_timestamp or req.order_created_at,
            vwap_execution_price=summary_res.vwap_execution_price,
            gross_executed_notional=summary_res.gross_executed_notional,
            slippage_price_units=summary_res.slippage_price_units,
            slippage_bps=summary_res.slippage_bps,
            slippage_monetary_amount=summary_res.slippage_monetary_amount,
            is_favorable=summary_res.is_favorable,
            market_movement_monetary=summary_res.total_market_movement_money,
            spread_crossing_monetary=summary_res.total_spread_crossing_money,
            residual_execution_monetary=summary_res.total_residual_execution_money,
            attribution_reconciled=summary_res.attribution_reconciled,
            total_explicit_fees=summary_res.total_explicit_fees,
            total_all_in_cost=summary_res.total_all_in_cost,
        )
        await self.repo.save_execution_summary(db_summary)

        # Save fill attributions
        db_fills = []
        fill_schemas = []
        for f_in, f_attr in zip(req.fills, fill_attr_res):
            db_fills.append(
                SlippageFillAttribution(
                    order_id=req.order_id,
                    fill_id=f_attr.fill_id,
                    symbol=req.symbol,
                    side=req.side.upper(),
                    fill_timestamp=f_in.fill_timestamp,
                    venue=f_in.venue or "DEFAULT",
                    fill_quantity=f_attr.quantity,
                    fill_price=f_attr.fill_price,
                    benchmark_price=f_attr.reference_price,
                    bid_at_fill=f_in.bid_at_fill,
                    ask_at_fill=f_in.ask_at_fill,
                    midpoint_at_fill=f_in.midpoint_at_fill,
                    fill_slippage_price=f_attr.fill_slippage_price,
                    fill_slippage_bps=f_attr.fill_slippage_bps,
                    fill_slippage_money=f_attr.fill_slippage_money,
                    market_movement_price=f_attr.market_movement_price,
                    market_movement_bps=f_attr.market_movement_bps,
                    market_movement_money=f_attr.market_movement_money,
                    spread_crossing_price=f_attr.spread_crossing_price,
                    spread_crossing_bps=f_attr.spread_crossing_bps,
                    spread_crossing_money=f_attr.spread_crossing_money,
                    residual_execution_price=f_attr.residual_execution_price,
                    residual_execution_bps=f_attr.residual_execution_bps,
                    residual_execution_money=f_attr.residual_execution_money,
                    reconciliation_discrepancy=f_attr.reconciliation_discrepancy,
                    fees=f_in.fees,
                )
            )
            fill_schemas.append(
                FillAttributionSchema(
                    fill_id=f_attr.fill_id,
                    quantity=f_attr.quantity,
                    fill_price=f_attr.fill_price,
                    multiplier=f_attr.multiplier,
                    side=f_attr.side,
                    reference_price=f_attr.reference_price,
                    fill_slippage_price=f_attr.fill_slippage_price,
                    fill_slippage_bps=f_attr.fill_slippage_bps,
                    fill_slippage_money=f_attr.fill_slippage_money,
                    market_movement_price=f_attr.market_movement_price,
                    market_movement_bps=f_attr.market_movement_bps,
                    market_movement_money=f_attr.market_movement_money,
                    spread_crossing_price=f_attr.spread_crossing_price,
                    spread_crossing_bps=f_attr.spread_crossing_bps,
                    spread_crossing_money=f_attr.spread_crossing_money,
                    residual_execution_price=f_attr.residual_execution_price,
                    residual_execution_bps=f_attr.residual_execution_bps,
                    residual_execution_money=f_attr.residual_execution_money,
                    total_reconciled=f_attr.total_reconciled,
                    reconciliation_discrepancy=f_attr.reconciliation_discrepancy,
                )
            )
        await self.repo.save_fill_attributions(db_fills)

        # Opportunity cost if terminal price provided and unfilled qty > 0
        if req.terminal_price is not None and summary_res.unfilled_quantity > Decimal("0.0"):
            db_opp = SlippageOpportunityCost(
                order_id=req.order_id,
                symbol=req.symbol,
                side=req.side.upper(),
                unfilled_quantity=summary_res.unfilled_quantity,
                benchmark_price=summary_res.benchmark_price,
                terminal_price=req.terminal_price,
                terminal_timestamp=completed_at,
                terminal_price_source="TERMINAL_SPECIFIED",
                opportunity_cost_price_units=summary_res.opportunity_cost_price_units or Decimal("0.0"),
                opportunity_cost_bps=summary_res.opportunity_cost_bps or Decimal("0.0"),
                opportunity_cost_monetary_amount=summary_res.opportunity_cost_monetary_amount or Decimal("0.0"),
                implementation_shortfall_monetary_amount=summary_res.implementation_shortfall_monetary_amount or Decimal("0.0"),
            )
            await self.repo.save_opportunity_cost(db_opp)

        await self.session.commit()

        return SlippageExecutionSummaryResponse(
            order_id=req.order_id,
            symbol=req.symbol,
            side=req.side.upper(),
            order_created_at=req.order_created_at,
            execution_completed_at=completed_at,
            requested_quantity=summary_res.total_requested_quantity,
            filled_quantity=summary_res.total_filled_quantity,
            unfilled_quantity=summary_res.unfilled_quantity,
            fill_rate_pct=summary_res.fill_rate_pct,
            benchmark_type=summary_res.benchmark_type,
            benchmark_price=summary_res.benchmark_price,
            vwap_execution_price=summary_res.vwap_execution_price,
            gross_executed_notional=summary_res.gross_executed_notional,
            slippage_price_units=summary_res.slippage_price_units,
            slippage_bps=summary_res.slippage_bps,
            slippage_monetary_amount=summary_res.slippage_monetary_amount,
            is_favorable=summary_res.is_favorable,
            total_market_movement_price=summary_res.total_market_movement_price,
            total_market_movement_bps=summary_res.total_market_movement_bps,
            total_market_movement_money=summary_res.total_market_movement_money,
            total_spread_crossing_price=summary_res.total_spread_crossing_price,
            total_spread_crossing_bps=summary_res.total_spread_crossing_bps,
            total_spread_crossing_money=summary_res.total_spread_crossing_money,
            total_residual_execution_price=summary_res.total_residual_execution_price,
            total_residual_execution_bps=summary_res.total_residual_execution_bps,
            total_residual_execution_money=summary_res.total_residual_execution_money,
            attribution_reconciled=summary_res.attribution_reconciled,
            total_explicit_fees=summary_res.total_explicit_fees,
            total_all_in_cost=summary_res.total_all_in_cost,
            terminal_price=summary_res.terminal_price,
            opportunity_cost_price_units=summary_res.opportunity_cost_price_units,
            opportunity_cost_bps=summary_res.opportunity_cost_bps,
            opportunity_cost_monetary_amount=summary_res.opportunity_cost_monetary_amount,
            implementation_shortfall_monetary_amount=summary_res.implementation_shortfall_monetary_amount,
            fill_attributions=fill_schemas,
        )

    async def run_calibration_evaluation(
        self, req: CalibrationRunRequest
    ) -> CalibrationRunResponse:
        calc_obs = []
        db_obs = []
        start_date = min(o.observation_timestamp for o in req.observations)
        end_date = max(o.observation_timestamp for o in req.observations)

        for o in req.observations:
            calc_obs.append(
                (
                    o.estimated_slippage_bps,
                    o.realized_slippage_bps,
                    o.predicted_lower_bound_bps,
                    o.predicted_upper_bound_bps,
                )
            )
            err = o.estimated_slippage_bps - o.realized_slippage_bps
            in_int = None
            if o.predicted_lower_bound_bps is not None and o.predicted_upper_bound_bps is not None:
                in_int = o.predicted_lower_bound_bps <= o.realized_slippage_bps <= o.predicted_upper_bound_bps

            db_obs.append(
                SlippageCalibrationObservation(
                    order_id=o.order_id,
                    symbol=o.symbol,
                    side=o.side.upper(),
                    observation_timestamp=o.observation_timestamp,
                    estimated_slippage_bps=o.estimated_slippage_bps,
                    realized_slippage_bps=o.realized_slippage_bps,
                    error_bps=err,
                    predicted_lower_bound_bps=o.predicted_lower_bound_bps,
                    predicted_upper_bound_bps=o.predicted_upper_bound_bps,
                    is_within_interval=in_int,
                )
            )

        metrics = SlippageMath.calculate_calibration_metrics(calc_obs)

        db_run = SlippageCalibrationRun(
            run_code=req.run_code,
            model_name=req.model_name,
            start_date=start_date,
            end_date=end_date,
            observation_count=metrics.observation_count,
            mean_error_bps=metrics.mean_error,
            mean_absolute_error_bps=metrics.mean_absolute_error,
            root_mean_squared_error_bps=metrics.root_mean_squared_error,
            t_statistic=metrics.t_statistic,
            p_value=metrics.p_value_approx,
            is_bias_significant=metrics.is_bias_significant,
            interval_coverage_pct=metrics.interval_coverage_pct,
        )

        await self.repo.save_calibration_run(db_run, db_obs)
        await self.session.commit()

        return CalibrationRunResponse(
            run_code=req.run_code,
            model_name=req.model_name,
            observation_count=metrics.observation_count,
            mean_error_bps=metrics.mean_error,
            mean_absolute_error_bps=metrics.mean_absolute_error,
            root_mean_squared_error_bps=metrics.root_mean_squared_error,
            t_statistic=metrics.t_statistic,
            p_value=metrics.p_value_approx,
            is_bias_significant=metrics.is_bias_significant,
            interval_coverage_pct=metrics.interval_coverage_pct,
        )

