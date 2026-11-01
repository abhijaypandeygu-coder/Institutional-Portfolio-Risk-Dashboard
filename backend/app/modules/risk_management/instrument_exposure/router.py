"""
M06.04 Instrument Exposure - FastAPI Router.
Provides endpoints for calculating portfolio/group instrument exposures,
querying summaries, rankings, comparisons, dominant holdings, and settings.
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.risk_management.instrument_exposure.models import (
    ExposureWeightBasis,
    ExposureRankingBasis,
)
from backend.app.modules.risk_management.instrument_exposure.schemas import (
    InstrumentExposureCalculateRequest,
    InstrumentExposureSummaryResponse,
    InstrumentExposureItemResponse,
    InstrumentExposureRankingsResponse,
    InstrumentExposureComparisonResponse,
    InstrumentExposureSettingsSchema,
)
from backend.app.modules.risk_management.instrument_exposure.services.service import (
    InstrumentExposureService,
)

router = APIRouter(tags=["M06.04 - Instrument Exposure"])


@router.post(
    "/portfolios/{portfolio_id}/risk/instrument-exposure/calculate",
    response_model=InstrumentExposureSummaryResponse,
    summary="Calculate portfolio instrument exposure",
)
async def calculate_instrument_exposure(
    portfolio_id: str = Path(..., description="Target portfolio ID"),
    request: InstrumentExposureCalculateRequest = None,
    db: AsyncSession = Depends(get_db),
):
    if request is None:
        request = InstrumentExposureCalculateRequest(portfolio_id=portfolio_id)
    svc = InstrumentExposureService(db)
    return await svc.calculate_portfolio_instrument_exposure(portfolio_id, request)


@router.post(
    "/portfolio-groups/{group_id}/risk/instrument-exposure/calculate",
    response_model=InstrumentExposureSummaryResponse,
    summary="Calculate consolidated group instrument exposure",
)
async def calculate_group_instrument_exposure(
    group_id: str = Path(..., description="Target portfolio group ID"),
    request: InstrumentExposureCalculateRequest = None,
    db: AsyncSession = Depends(get_db),
):
    if request is None:
        request = InstrumentExposureCalculateRequest(portfolio_group_id=group_id)
    svc = InstrumentExposureService(db)
    return await svc.calculate_group_instrument_exposure(group_id, request)


@router.get(
    "/portfolios/{portfolio_id}/risk/instrument-exposure",
    response_model=List[InstrumentExposureItemResponse],
    summary="Get instrument exposure items for portfolio",
)
async def get_instrument_exposures(
    portfolio_id: str = Path(..., description="Target portfolio ID"),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    svc = InstrumentExposureService(db)
    run = await svc.repo.get_latest_run(portfolio_id)
    if not run:
        # Calculate on the fly if no run exists
        req = InstrumentExposureCalculateRequest(portfolio_id=portfolio_id)
        summary = await svc.calculate_portfolio_instrument_exposure(portfolio_id, req)
        return summary.instruments[:limit]

    results = await svc.repo.get_run_results(run.run_id)
    return [
        InstrumentExposureItemResponse(
            instrument_id=r.instrument_id,
            symbol=r.symbol,
            instrument_name=r.instrument_name,
            exchange_code=r.exchange_code,
            asset_class=r.asset_class,
            reporting_currency=r.reporting_currency,
            long_quantity=r.long_quantity,
            short_quantity=r.short_quantity,
            net_quantity=r.net_quantity,
            long_market_value=r.long_market_value,
            short_market_value=r.short_market_value,
            net_market_value=r.net_market_value,
            gross_market_value=r.gross_market_value,
            long_nav_weight=r.long_nav_weight,
            short_nav_weight=r.short_nav_weight,
            net_nav_weight=r.net_nav_weight,
            gross_nav_weight=r.gross_nav_weight,
            gross_contribution_weight=r.gross_contribution_weight,
            long_contribution_weight=r.long_contribution_weight,
            short_contribution_weight=r.short_contribution_weight,
            long_rank=r.long_rank,
            short_rank=r.short_rank,
            gross_rank=r.gross_rank,
            net_rank=r.net_rank,
            valuation_status=r.valuation_status,
            price_source=r.price_source,
            mark_price=r.mark_price,
            mark_price_currency=r.mark_price_currency,
            valuation_timestamp=r.valuation_timestamp,
            dominance_severity=r.dominance_severity,
            dominance_flag_reason=r.dominance_flag_reason,
        )
        for r in results[:limit]
    ]


@router.get(
    "/portfolios/{portfolio_id}/risk/instrument-exposure/rankings",
    response_model=InstrumentExposureRankingsResponse,
    summary="Get ranked holdings (LONG, SHORT, GROSS, ABSOLUTE_NET)",
)
async def get_instrument_rankings(
    portfolio_id: str = Path(..., description="Target portfolio ID"),
    mode: ExposureRankingBasis = Query(ExposureRankingBasis.GROSS),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    svc = InstrumentExposureService(db)
    run = await svc.repo.get_latest_run(portfolio_id)
    if not run:
        req = InstrumentExposureCalculateRequest(portfolio_id=portfolio_id)
        await svc.calculate_portfolio_instrument_exposure(portfolio_id, req)
        run = await svc.repo.get_latest_run(portfolio_id)

    results = await svc.repo.get_run_results(run.run_id)

    # Sort according to ranking mode
    if mode == ExposureRankingBasis.LONG:
        sorted_res = sorted([r for r in results if r.long_market_value > 0], key=lambda x: x.long_market_value, reverse=True)
    elif mode == ExposureRankingBasis.SHORT:
        sorted_res = sorted([r for r in results if r.short_market_value > 0], key=lambda x: x.short_market_value, reverse=True)
    elif mode == ExposureRankingBasis.ABSOLUTE_NET:
        sorted_res = sorted(results, key=lambda x: abs(x.net_market_value), reverse=True)
    else:  # GROSS
        sorted_res = sorted(results, key=lambda x: x.gross_market_value, reverse=True)

    items = [
        InstrumentExposureItemResponse(
            instrument_id=r.instrument_id,
            symbol=r.symbol,
            instrument_name=r.instrument_name,
            exchange_code=r.exchange_code,
            asset_class=r.asset_class,
            reporting_currency=r.reporting_currency,
            long_quantity=r.long_quantity,
            short_quantity=r.short_quantity,
            net_quantity=r.net_quantity,
            long_market_value=r.long_market_value,
            short_market_value=r.short_market_value,
            net_market_value=r.net_market_value,
            gross_market_value=r.gross_market_value,
            long_nav_weight=r.long_nav_weight,
            short_nav_weight=r.short_nav_weight,
            net_nav_weight=r.net_nav_weight,
            gross_nav_weight=r.gross_nav_weight,
            gross_contribution_weight=r.gross_contribution_weight,
            long_contribution_weight=r.long_contribution_weight,
            short_contribution_weight=r.short_contribution_weight,
            long_rank=r.long_rank,
            short_rank=r.short_rank,
            gross_rank=r.gross_rank,
            net_rank=r.net_rank,
            valuation_status=r.valuation_status,
            price_source=r.price_source,
            mark_price=r.mark_price,
            mark_price_currency=r.mark_price_currency,
            valuation_timestamp=r.valuation_timestamp,
            dominance_severity=r.dominance_severity,
            dominance_flag_reason=r.dominance_flag_reason,
        )
        for r in sorted_res[:limit]
    ]

    return InstrumentExposureRankingsResponse(
        ranking_basis=mode,
        weight_basis=ExposureWeightBasis(run.weight_basis),
        items=items,
    )


@router.get(
    "/portfolios/{portfolio_id}/risk/instrument-exposure/comparison",
    response_model=InstrumentExposureComparisonResponse,
    summary="Compare instrument exposures across snapshots",
)
async def compare_instrument_exposures(
    portfolio_id: str = Path(..., description="Target portfolio ID"),
    current_snapshot_id: str = Query(..., description="Current snapshot ID"),
    prior_snapshot_id: str = Query(..., description="Prior snapshot ID"),
    db: AsyncSession = Depends(get_db),
):
    svc = InstrumentExposureService(db)
    return await svc.compare_snapshots(portfolio_id, current_snapshot_id, prior_snapshot_id)


@router.get(
    "/portfolios/{portfolio_id}/risk/instrument-exposure/dominant",
    response_model=List[InstrumentExposureItemResponse],
    summary="Get instruments triggering dominance thresholds",
)
async def get_dominant_exposures(
    portfolio_id: str = Path(..., description="Target portfolio ID"),
    db: AsyncSession = Depends(get_db),
):
    svc = InstrumentExposureService(db)
    run = await svc.repo.get_latest_run(portfolio_id)
    if not run:
        return []
    results = await svc.repo.get_run_results(run.run_id)
    dominant = [r for r in results if r.dominance_severity in ["ELEVATED", "HIGH", "CRITICAL"]]
    return [
        InstrumentExposureItemResponse(
            instrument_id=r.instrument_id,
            symbol=r.symbol,
            instrument_name=r.instrument_name,
            exchange_code=r.exchange_code,
            asset_class=r.asset_class,
            reporting_currency=r.reporting_currency,
            long_quantity=r.long_quantity,
            short_quantity=r.short_quantity,
            net_quantity=r.net_quantity,
            long_market_value=r.long_market_value,
            short_market_value=r.short_market_value,
            net_market_value=r.net_market_value,
            gross_market_value=r.gross_market_value,
            long_nav_weight=r.long_nav_weight,
            short_nav_weight=r.short_nav_weight,
            net_nav_weight=r.net_nav_weight,
            gross_nav_weight=r.gross_nav_weight,
            gross_contribution_weight=r.gross_contribution_weight,
            long_contribution_weight=r.long_contribution_weight,
            short_contribution_weight=r.short_contribution_weight,
            long_rank=r.long_rank,
            short_rank=r.short_rank,
            gross_rank=r.gross_rank,
            net_rank=r.net_rank,
            valuation_status=r.valuation_status,
            price_source=r.price_source,
            mark_price=r.mark_price,
            mark_price_currency=r.mark_price_currency,
            valuation_timestamp=r.valuation_timestamp,
            dominance_severity=r.dominance_severity,
            dominance_flag_reason=r.dominance_flag_reason,
        )
        for r in dominant
    ]

