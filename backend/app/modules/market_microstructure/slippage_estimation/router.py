"""
FastAPI router for M09.05 Slippage Estimation.
"""

from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.market_microstructure.slippage_estimation.schemas.slippage_schemas import (
    BenchmarkConfigCreate,
    BenchmarkConfigResponse,
    SlippageAnalysisRequest,
    SlippageExecutionSummaryResponse,
    CalibrationRunRequest,
    CalibrationRunResponse,
)
from backend.app.modules.market_microstructure.slippage_estimation.services.slippage_service import (
    SlippageService,
)

router = APIRouter(
    prefix="/api/v1/market-microstructure/slippage",
    tags=["M09.05 - Slippage Estimation"],
)


@router.post(
    "/benchmark-config",
    response_model=BenchmarkConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or get active benchmark configuration",
)
async def create_benchmark_config(
    config: BenchmarkConfigCreate,
    session: AsyncSession = Depends(get_db),
):
    """
    Creates or retrieves a benchmark configuration defining the benchmark price type
    (Arrival Midpoint, Decision, etc.), max age tolerances, and asset multiplier.
    """
    service = SlippageService(session)
    return await service.get_or_create_benchmark_config(config)


@router.post(
    "/analyze-execution",
    response_model=SlippageExecutionSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Compute realized slippage and attribution for an execution order",
)
async def analyze_execution(
    request: SlippageAnalysisRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Computes realized slippage across all fills of an order against the benchmark price.
    Produces exact additive attribution decomposition:
    Total Price Deviation == Market Movement + Spread Crossing + Residual Execution.
    Includes opportunity cost and Implementation Shortfall if terminal price is supplied.
    """
    service = SlippageService(session)
    return await service.analyze_and_record_execution(request)


@router.get(
    "/execution-summary/{order_id}",
    response_model=Optional[SlippageExecutionSummaryResponse],
    summary="Retrieve recorded slippage execution summary and fill attributions",
)
async def get_execution_summary(
    order_id: str,
    session: AsyncSession = Depends(get_db),
):
    """
    Fetches the persisted slippage execution summary and individual fill attributions by order_id.
    """
    service = SlippageService(session)
    summary = await service.repo.get_execution_summary(order_id)
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Slippage summary for order '{order_id}' not found.",
        )
    fills = await service.repo.get_fill_attributions(order_id)
    opp = await service.repo.get_opportunity_cost(order_id)

    fill_schemas = [
        {
            "fill_id": f.fill_id,
            "quantity": f.fill_quantity,
            "fill_price": f.fill_price,
            "multiplier": Decimal("1.0"),
            "side": f.side,
            "reference_price": f.benchmark_price,
            "fill_slippage_price": f.fill_slippage_price,
            "fill_slippage_bps": f.fill_slippage_bps,
            "fill_slippage_money": f.fill_slippage_money,
            "market_movement_price": f.market_movement_price,
            "market_movement_bps": f.market_movement_bps,
            "market_movement_money": f.market_movement_money,
            "spread_crossing_price": f.spread_crossing_price,
            "spread_crossing_bps": f.spread_crossing_bps,
            "spread_crossing_money": f.spread_crossing_money,
            "residual_execution_price": f.residual_execution_price,
            "residual_execution_bps": f.residual_execution_bps,
            "residual_execution_money": f.residual_execution_money,
            "total_reconciled": True,
            "reconciliation_discrepancy": f.reconciliation_discrepancy,
        }
        for f in fills
    ]

    return SlippageExecutionSummaryResponse(
        order_id=summary.order_id,
        symbol=summary.symbol,
        side=summary.side,
        order_created_at=summary.order_created_at,
        execution_completed_at=summary.execution_completed_at,
        requested_quantity=summary.requested_quantity,
        filled_quantity=summary.filled_quantity,
        unfilled_quantity=summary.unfilled_quantity,
        fill_rate_pct=summary.fill_rate_pct,
        benchmark_type=summary.benchmark_type,
        benchmark_price=summary.benchmark_price,
        vwap_execution_price=summary.vwap_execution_price,
        gross_executed_notional=summary.gross_executed_notional,
        slippage_price_units=summary.slippage_price_units,
        slippage_bps=summary.slippage_bps,
        slippage_monetary_amount=summary.slippage_monetary_amount,
        is_favorable=summary.is_favorable,
        total_market_movement_price=Decimal("0.0"),
        total_market_movement_bps=Decimal("0.0"),
        total_market_movement_money=summary.market_movement_monetary,
        total_spread_crossing_price=Decimal("0.0"),
        total_spread_crossing_bps=Decimal("0.0"),
        total_spread_crossing_money=summary.spread_crossing_monetary,
        total_residual_execution_price=Decimal("0.0"),
        total_residual_execution_bps=Decimal("0.0"),
        total_residual_execution_money=summary.residual_execution_monetary,
        attribution_reconciled=summary.attribution_reconciled,
        total_explicit_fees=summary.total_explicit_fees,
        total_all_in_cost=summary.total_all_in_cost,
        terminal_price=opp.terminal_price if opp else None,
        opportunity_cost_price_units=opp.opportunity_cost_price_units if opp else None,
        opportunity_cost_bps=opp.opportunity_cost_bps if opp else None,
        opportunity_cost_monetary_amount=opp.opportunity_cost_monetary_amount if opp else None,
        implementation_shortfall_monetary_amount=opp.implementation_shortfall_monetary_amount if opp else None,
        fill_attributions=fill_schemas,
    )


@router.post(
    "/calibration/run",
    response_model=CalibrationRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate historical calibration of slippage predictions vs realizations",
)
async def run_calibration(
    request: CalibrationRunRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Evaluates ex-ante estimated slippage against ex-post realized slippage:
    Mean Error (Bias), MAE, RMSE, t-statistic, and prediction interval coverage.
    """
    service = SlippageService(session)
    return await service.run_calibration_evaluation(request)
