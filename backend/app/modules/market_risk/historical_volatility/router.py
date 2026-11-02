"""
Module M07.01: Historical Volatility API Router.
Mounted at /api/v1/market-risk/historical-volatility.
"""
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.market_risk.historical_volatility.models import (
    ReturnType,
    ReturnFrequency,
    PriceSourceType,
    PriceMeasure,
    CorporateActionAdjustmentPolicy,
    VolatilityScopeType,
)
from backend.app.modules.market_risk.historical_volatility.schemas import (
    AnnualizationConventionCreateRequest,
    AnnualizationConventionResponse,
    VolatilityConfigCreateRequest,
    VolatilityConfigResponse,
    HistoricalVolatilityCalculateRequest,
    HistoricalVolatilityResultResponse,
    RollingVolatilitySeriesResponse,
    WindowComparisonResponse,
    VolatilityTrendResponse,
    IntradayVolatilityResponse,
    VolatilityDiagnosticItemResponse,
)
from backend.app.modules.market_risk.historical_volatility.services.service import HistoricalVolatilityService

router = APIRouter(
    prefix="/market-risk/historical-volatility",
    tags=["M07.01 - Historical Volatility"],
)


@router.post(
    "/conventions",
    response_model=AnnualizationConventionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create annualization convention",
)
async def create_annualization_convention(
    req: AnnualizationConventionCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    svc = HistoricalVolatilityService(db)
    conv = await svc.create_annualization_convention(req)
    return AnnualizationConventionResponse.model_validate(conv)


@router.get(
    "/conventions",
    response_model=List[AnnualizationConventionResponse],
    summary="List annualization conventions",
)
async def list_annualization_conventions(
    market_code: Optional[str] = Query(None, description="Filter by market code (e.g. US, IN)"),
    db: AsyncSession = Depends(get_db),
):
    svc = HistoricalVolatilityService(db)
    items = await svc.repo.list_annualization_conventions(market_code=market_code)
    return [AnnualizationConventionResponse.model_validate(i) for i in items]


@router.post(
    "/configurations",
    response_model=VolatilityConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create volatility calculation configuration",
)
async def create_volatility_config(
    req: VolatilityConfigCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    svc = HistoricalVolatilityService(db)
    cfg = await svc.create_config(req)
    return VolatilityConfigResponse.model_validate(cfg)


@router.get(
    "/configurations",
    response_model=List[VolatilityConfigResponse],
    summary="List volatility calculation configurations",
)
async def list_volatility_configs(
    instrument_id: Optional[str] = Query(None, description="Filter by instrument"),
    portfolio_id: Optional[str] = Query(None, description="Filter by portfolio"),
    db: AsyncSession = Depends(get_db),
):
    svc = HistoricalVolatilityService(db)
    items = await svc.repo.list_configs(instrument_id=instrument_id, portfolio_id=portfolio_id)
    return [VolatilityConfigResponse.model_validate(i) for i in items]


@router.get(
    "",
    response_model=HistoricalVolatilityResultResponse,
    summary="Get current historical volatility",
)
async def get_historical_volatility(
    instrument_id: Optional[str] = Query(None, description="Target canonical instrument"),
    listing_id: Optional[str] = Query(None, description="Target exchange listing"),
    portfolio_id: Optional[str] = Query(None, description="Target portfolio (if portfolio scope)"),
    scope_type: VolatilityScopeType = Query(VolatilityScopeType.INSTRUMENT, description="Scope type"),
    return_type: ReturnType = Query(ReturnType.LOGARITHMIC, description="Return calculation type"),
    return_frequency: ReturnFrequency = Query(ReturnFrequency.DAILY, description="Return frequency"),
    lookback_window: int = Query(20, description="Lookback window length (trading sessions)"),
    price_source: PriceSourceType = Query(PriceSourceType.OFFICIAL_CLOSE, description="Authoritative price source"),
    as_of: Optional[date] = Query(None, description="Historical as-of date"),
    db: AsyncSession = Depends(get_db),
):
    if not instrument_id and not portfolio_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either instrument_id or portfolio_id must be provided.",
        )

    req = HistoricalVolatilityCalculateRequest(
        instrument_id=instrument_id,
        listing_id=listing_id,
        portfolio_id=portfolio_id,
        scope_type=scope_type,
        return_type=return_type,
        return_frequency=return_frequency,
        lookback_window=lookback_window,
        price_source=price_source,
        as_of=as_of,
    )
    svc = HistoricalVolatilityService(db)
    return await svc.calculate_historical_volatility(req)


@router.get(
    "/rolling",
    response_model=RollingVolatilitySeriesResponse,
    summary="Get rolling volatility time series",
)
async def get_rolling_volatility_series(
    instrument_id: Optional[str] = Query(None, description="Target canonical instrument"),
    portfolio_id: Optional[str] = Query(None, description="Target portfolio"),
    lookback_window: int = Query(20, description="Rolling window length (sessions)"),
    from_date: Optional[date] = Query(None, description="Start date filter"),
    to_date: Optional[date] = Query(None, description="End date filter"),
    db: AsyncSession = Depends(get_db),
):
    if not instrument_id and not portfolio_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either instrument_id or portfolio_id must be provided.",
        )

    svc = HistoricalVolatilityService(db)
    return await svc.calculate_rolling_volatility_series(
        instrument_id=instrument_id,
        portfolio_id=portfolio_id,
        lookback_window=lookback_window,
        from_date=from_date,
        to_date=to_date,
    )


@router.get(
    "/window-comparison",
    response_model=WindowComparisonResponse,
    summary="Compare short-, medium-, and long-horizon volatility",
)
async def get_window_comparison(
    instrument_id: str = Query(..., description="Target canonical instrument"),
    listing_id: Optional[str] = Query(None, description="Target listing"),
    short_window: int = Query(20, description="Short lookback sessions"),
    medium_window: int = Query(60, description="Medium lookback sessions"),
    long_window: int = Query(252, description="Long lookback sessions"),
    as_of: Optional[date] = Query(None, description="As-of date"),
    db: AsyncSession = Depends(get_db),
):
    svc = HistoricalVolatilityService(db)
    return await svc.calculate_window_comparison(
        instrument_id=instrument_id,
        listing_id=listing_id,
        short_window=short_window,
        medium_window=medium_window,
        long_window=long_window,
        as_of=as_of,
    )


@router.get(
    "/trend",
    response_model=VolatilityTrendResponse,
    summary="Evaluate historical volatility trend and slope",
)
async def get_volatility_trend(
    instrument_id: str = Query(..., description="Target canonical instrument"),
    lookback_window: int = Query(20, description="Window size for rolling volatility"),
    trend_lookback_points: int = Query(10, description="Number of rolling points for trend slope"),
    as_of: Optional[date] = Query(None, description="As-of date"),
    db: AsyncSession = Depends(get_db),
):
    svc = HistoricalVolatilityService(db)
    return await svc.evaluate_volatility_trend(
        instrument_id=instrument_id,
        lookback_window=lookback_window,
        trend_lookback_points=trend_lookback_points,
        as_of=as_of,
    )


@router.get(
    "/intraday",
    response_model=IntradayVolatilityResponse,
    summary="Calculate intraday realized volatility with microstructure checks",
)
async def get_intraday_volatility(
    instrument_id: str = Query(..., description="Target canonical instrument"),
    sampling_interval: str = Query("5m", description="Sampling bar interval (1m, 5m, 15m, 30m)"),
    as_of: Optional[date] = Query(None, description="As-of date"),
    db: AsyncSession = Depends(get_db),
):
    svc = HistoricalVolatilityService(db)
    return await svc.calculate_intraday_volatility(
        instrument_id=instrument_id,
        sampling_interval=sampling_interval,
        as_of=as_of,
    )


@router.get(
    "/diagnostics",
    response_model=List[VolatilityDiagnosticItemResponse],
    summary="List calculation and data-suitability diagnostics",
)
async def list_diagnostics(
    result_id: Optional[str] = Query(None, description="Filter by result ID"),
    instrument_id: Optional[str] = Query(None, description="Filter by instrument"),
    db: AsyncSession = Depends(get_db),
):
    svc = HistoricalVolatilityService(db)
    items = await svc.repo.list_diagnostics(result_id=result_id, instrument_id=instrument_id)
    return [VolatilityDiagnosticItemResponse.model_validate(d) for d in items]

