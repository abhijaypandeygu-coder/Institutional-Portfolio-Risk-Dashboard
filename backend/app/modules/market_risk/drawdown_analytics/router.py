"""
Module M07.04: Drawdown Analytics FastAPI Routes.
Mounted at:
- `/api/v1/market-risk/drawdown` (Global Instrument & Portfolio Drawdown routes)
- `/api/v1/portfolios/{portfolio_id}/risk/drawdown` (Portfolio Drawdown routes)
- `/api/v1/portfolio-groups/{group_id}/risk/drawdown` (Group Drawdown routes)
"""
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.market_risk.drawdown_analytics.models import (
    DrawdownScopeType,
    DrawdownValueSeriesType,
    HighWaterMarkPolicy,
)
from backend.app.modules.market_risk.drawdown_analytics.schemas import (
    DrawdownConfigCreateRequest,
    DrawdownConfigResponse,
    CurrentDrawdownResponse,
    MaximumDrawdownResponse,
    DrawdownEpisodeResponse,
    DrawdownHistoryResponse,
    RecoveryStatisticsResponse,
    DrawdownLookbackComparisonResponse,
    DrawdownSummaryResponse,
)
from backend.app.modules.market_risk.drawdown_analytics.services.service import DrawdownAnalyticsService

global_router = APIRouter(prefix="/api/v1/market-risk/drawdown", tags=["M07.04 - Drawdown Analytics Global"])
portfolio_router = APIRouter(prefix="/api/v1/portfolios/{portfolio_id}/risk/drawdown", tags=["M07.04 - Drawdown Analytics Portfolio"])
group_router = APIRouter(prefix="/api/v1/portfolio-groups/{group_id}/risk/drawdown", tags=["M07.04 - Drawdown Analytics Group"])


# 1. Global Endpoints (support both instrument and portfolio queries)
@global_router.get("/current", response_model=CurrentDrawdownResponse)
async def get_current_drawdown(
    scope_type: DrawdownScopeType = Query(default=DrawdownScopeType.PORTFOLIO),
    portfolio_id: Optional[str] = Query(default=None),
    portfolio_group_id: Optional[str] = Query(default=None),
    instrument_id: Optional[str] = Query(default=None),
    as_of: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    svc = DrawdownAnalyticsService(db)
    return await svc.get_current_drawdown(
        scope_type=scope_type,
        portfolio_id=portfolio_id,
        portfolio_group_id=portfolio_group_id,
        instrument_id=instrument_id,
        as_of=as_of,
    )


@global_router.get("/maximum", response_model=MaximumDrawdownResponse)
async def get_maximum_drawdown(
    scope_type: DrawdownScopeType = Query(default=DrawdownScopeType.PORTFOLIO),
    portfolio_id: Optional[str] = Query(default=None),
    portfolio_group_id: Optional[str] = Query(default=None),
    instrument_id: Optional[str] = Query(default=None),
    lookback_window_name: str = Query(default="SINCE_INCEPTION"),
    as_of: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    svc = DrawdownAnalyticsService(db)
    return await svc.get_maximum_drawdown(
        scope_type=scope_type,
        portfolio_id=portfolio_id,
        portfolio_group_id=portfolio_group_id,
        instrument_id=instrument_id,
        lookback_window_name=lookback_window_name,
        as_of=as_of,
    )


@global_router.get("/episodes", response_model=List[DrawdownEpisodeResponse])
async def list_drawdown_episodes(
    scope_type: DrawdownScopeType = Query(default=DrawdownScopeType.PORTFOLIO),
    portfolio_id: Optional[str] = Query(default=None),
    portfolio_group_id: Optional[str] = Query(default=None),
    instrument_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
    as_of: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    svc = DrawdownAnalyticsService(db)
    return await svc.list_drawdown_episodes(
        scope_type=scope_type,
        portfolio_id=portfolio_id,
        portfolio_group_id=portfolio_group_id,
        instrument_id=instrument_id,
        limit=limit,
        offset=offset,
        as_of=as_of,
    )


@global_router.get("/history", response_model=DrawdownHistoryResponse)
async def get_drawdown_history(
    scope_type: DrawdownScopeType = Query(default=DrawdownScopeType.PORTFOLIO),
    portfolio_id: Optional[str] = Query(default=None),
    instrument_id: Optional[str] = Query(default=None),
    limit: int = Query(default=252, ge=1, le=1000),
    as_of: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    svc = DrawdownAnalyticsService(db)
    return await svc.get_drawdown_history(
        scope_type=scope_type,
        portfolio_id=portfolio_id,
        instrument_id=instrument_id,
        limit=limit,
        as_of=as_of,
    )


@global_router.get("/recovery-statistics", response_model=RecoveryStatisticsResponse)
async def get_recovery_statistics(
    scope_type: DrawdownScopeType = Query(default=DrawdownScopeType.PORTFOLIO),
    portfolio_id: Optional[str] = Query(default=None),
    instrument_id: Optional[str] = Query(default=None),
    as_of: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    svc = DrawdownAnalyticsService(db)
    return await svc.get_recovery_statistics(
        scope_type=scope_type,
        portfolio_id=portfolio_id,
        instrument_id=instrument_id,
        as_of=as_of,
    )


@global_router.get("/comparison", response_model=DrawdownLookbackComparisonResponse)
async def compare_lookback_windows(
    scope_type: DrawdownScopeType = Query(default=DrawdownScopeType.PORTFOLIO),
    portfolio_id: Optional[str] = Query(default=None),
    instrument_id: Optional[str] = Query(default=None),
    as_of: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    svc = DrawdownAnalyticsService(db)
    return await svc.compare_lookback_windows(
        scope_type=scope_type,
        portfolio_id=portfolio_id,
        instrument_id=instrument_id,
        as_of=as_of,
    )


@global_router.post("/configs", response_model=DrawdownConfigResponse)
async def create_drawdown_config(
    req: DrawdownConfigCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    svc = DrawdownAnalyticsService(db)
    return await svc.create_config(req)


# 2. Portfolio Dedicated Endpoints
@portfolio_router.get("", response_model=DrawdownSummaryResponse)
async def get_portfolio_drawdown_summary(
    portfolio_id: str = Path(...),
    as_of: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    svc = DrawdownAnalyticsService(db)
    return await svc.get_drawdown_summary(
        scope_type=DrawdownScopeType.PORTFOLIO,
        portfolio_id=portfolio_id,
        as_of=as_of,
    )


@portfolio_router.get("/episodes", response_model=List[DrawdownEpisodeResponse])
async def get_portfolio_episodes(
    portfolio_id: str = Path(...),
    limit: int = Query(default=50, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
    as_of: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    svc = DrawdownAnalyticsService(db)
    return await svc.list_drawdown_episodes(
        scope_type=DrawdownScopeType.PORTFOLIO,
        portfolio_id=portfolio_id,
        limit=limit,
        offset=offset,
        as_of=as_of,
    )


@portfolio_router.get("/history", response_model=DrawdownHistoryResponse)
async def get_portfolio_drawdown_history(
    portfolio_id: str = Path(...),
    limit: int = Query(default=252),
    as_of: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    svc = DrawdownAnalyticsService(db)
    return await svc.get_drawdown_history(
        scope_type=DrawdownScopeType.PORTFOLIO,
        portfolio_id=portfolio_id,
        limit=limit,
        as_of=as_of,
    )


@portfolio_router.get("/comparison", response_model=DrawdownLookbackComparisonResponse)
async def get_portfolio_drawdown_comparison(
    portfolio_id: str = Path(...),
    as_of: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    svc = DrawdownAnalyticsService(db)
    return await svc.compare_lookback_windows(
        scope_type=DrawdownScopeType.PORTFOLIO,
        portfolio_id=portfolio_id,
        as_of=as_of,
    )


# 3. Portfolio Group Dedicated Endpoints
@group_router.get("", response_model=DrawdownSummaryResponse)
async def get_group_drawdown_summary(
    group_id: str = Path(...),
    as_of: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    svc = DrawdownAnalyticsService(db)
    return await svc.get_drawdown_summary(
        scope_type=DrawdownScopeType.PORTFOLIO_GROUP,
        portfolio_group_id=group_id,
        as_of=as_of,
    )

