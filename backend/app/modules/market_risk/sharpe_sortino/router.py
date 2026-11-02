"""
M07.08 Sharpe & Sortino FastAPI Router.
Mounted under:
- /api/v1/market-risk/ratios
- /api/v1/portfolios/{portfolio_id}/risk/ratios
"""
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.market_risk.sharpe_sortino.services.service import SharpeSortinoService
from backend.app.modules.market_risk.sharpe_sortino.repositories.repository import SharpeSortinoRepository
from backend.app.modules.market_risk.sharpe_sortino.models import (
    RiskFreeRateSeries,
    RiskFreeRateObservation,
    SharpeDenominatorPolicy,
    SortinoTargetPolicy,
    SortinoDenominatorPolicy,
)
from backend.app.modules.market_risk.sharpe_sortino.schemas import (
    RiskFreeRateSeriesCreate,
    RiskFreeRateSeriesResponse,
    RiskFreeRateObservationCreate,
    RiskFreeRateObservationResponse,
    SharpeRatioRequest,
    SharpeRatioResponse,
    SortinoRatioRequest,
    SortinoRatioResponse,
    CombinedRatiosRequest,
    CombinedRatiosResponse,
    RollingRatiosRequest,
    RollingRatiosResponse,
)

router = APIRouter()
portfolio_router = APIRouter()


# ---------------------------------------------------------
# Core Ratio Endpoints
# ---------------------------------------------------------
@router.post("/sharpe", response_model=SharpeRatioResponse, summary="Calculate Sharpe Ratio")
async def calculate_sharpe(
    request: SharpeRatioRequest,
    session: AsyncSession = Depends(get_db),
):
    service = SharpeSortinoService(session)
    return await service.calculate_sharpe(request)


@router.post("/sortino", response_model=SortinoRatioResponse, summary="Calculate Sortino Ratio")
async def calculate_sortino(
    request: SortinoRatioRequest,
    session: AsyncSession = Depends(get_db),
):
    service = SharpeSortinoService(session)
    return await service.calculate_sortino(request)


@router.post("/combined", response_model=CombinedRatiosResponse, summary="Calculate Sharpe & Sortino Ratios Concurrently")
async def calculate_combined(
    request: CombinedRatiosRequest,
    session: AsyncSession = Depends(get_db),
):
    service = SharpeSortinoService(session)
    return await service.calculate_combined(request)


@router.post("/rolling", response_model=RollingRatiosResponse, summary="Calculate Rolling Sharpe & Sortino Time Series")
async def calculate_rolling(
    request: RollingRatiosRequest,
    session: AsyncSession = Depends(get_db),
):
    service = SharpeSortinoService(session)
    return await service.calculate_rolling_ratios(request)


# ---------------------------------------------------------
# Risk-Free Rate Series & Observation Management
# ---------------------------------------------------------
@router.post("/risk-free-rates", response_model=RiskFreeRateSeriesResponse, summary="Register Risk-Free Rate Series")
async def register_rate_series(
    payload: RiskFreeRateSeriesCreate,
    session: AsyncSession = Depends(get_db),
):
    repo = SharpeSortinoRepository(session)
    series = RiskFreeRateSeries(
        series_code=payload.series_code,
        rate_name=payload.rate_name,
        currency=payload.currency,
        market=payload.market,
        provider=payload.provider,
        rate_convention=payload.rate_convention,
        day_count_convention=payload.day_count_convention,
        is_active=payload.is_active,
    )
    return await repo.create_rate_series(series)


@router.get("/risk-free-rates", response_model=List[RiskFreeRateSeriesResponse], summary="List Registered Risk-Free Rate Series")
async def list_rate_series(
    session: AsyncSession = Depends(get_db),
):
    repo = SharpeSortinoRepository(session)
    return await repo.list_rate_series(active_only=True)


@router.post("/risk-free-rates/observations", response_model=RiskFreeRateObservationResponse, summary="Add Risk-Free Rate Observation")
async def add_rate_observation(
    payload: RiskFreeRateObservationCreate,
    session: AsyncSession = Depends(get_db),
):
    repo = SharpeSortinoRepository(session)
    obs = RiskFreeRateObservation(
        series_id=payload.series_id,
        rate_date=payload.rate_date,
        annualized_rate=float(payload.annualized_rate),
    )
    return await repo.add_rate_observation(obs)


# ---------------------------------------------------------
# Portfolio Nested Endpoints: /api/v1/portfolios/{portfolio_id}/risk/ratios
# ---------------------------------------------------------
@portfolio_router.get(
    "/{portfolio_id}/risk/ratios",
    response_model=CombinedRatiosResponse,
    summary="Get Portfolio Sharpe & Sortino Risk-Adjusted Return Ratios",
)
async def get_portfolio_ratios(
    portfolio_id: str = Path(..., description="Target portfolio UUID"),
    lookback_days: int = Query(60, description="Lookback window in days"),
    as_of: Optional[date] = Query(None, description="Evaluation date"),
    risk_free_series_code: Optional[str] = Query(None, description="Optional custom rate series"),
    constant_mar_annual: Optional[float] = Query(None, description="Optional annualized MAR"),
    session: AsyncSession = Depends(get_db),
):
    service = SharpeSortinoService(session)
    req = CombinedRatiosRequest(
        scope="PORTFOLIO",
        entity_id=portfolio_id,
        risk_free_series_code=risk_free_series_code,
        constant_mar_annual=constant_mar_annual,
        lookback_days=lookback_days,
        as_of=as_of,
    )
    return await service.calculate_combined(req)
