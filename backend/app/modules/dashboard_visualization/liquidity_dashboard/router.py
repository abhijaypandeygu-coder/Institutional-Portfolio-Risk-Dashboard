"""
FastAPI Router for M13.06 — Liquidity Dashboard.

Endpoints:
- GET  /api/v1/dashboard/liquidity/portfolio/{portfolio_id}
- GET  /api/v1/dashboard/liquidity/instrument/{instrument_id}/quote
- GET  /api/v1/dashboard/liquidity/instrument/{instrument_id}/spread
- GET  /api/v1/dashboard/liquidity/instrument/{instrument_id}/depth
- GET  /api/v1/dashboard/liquidity/instrument/{instrument_id}/score
- GET  /api/v1/dashboard/liquidity/instrument/{instrument_id}/liquidation
- GET  /api/v1/dashboard/liquidity/preferences
- POST /api/v1/dashboard/liquidity/preferences
- GET  /api/v1/dashboard/liquidity/saved-views
- POST /api/v1/dashboard/liquidity/saved-views
- GET  /api/v1/dashboard/liquidity/investigations
- POST /api/v1/dashboard/liquidity/investigations
"""

from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.dashboard_visualization.liquidity_dashboard.services.liquidity_dashboard_service import (
    LiquidityDashboardService,
)
from backend.app.modules.dashboard_visualization.liquidity_dashboard.schemas.liquidity_dashboard_schemas import (
    CurrentQuoteItem,
    InstrumentSpreadDetail,
    OrderBookDepthLadder,
    InstrumentLiquidityScore,
    InstrumentLiquidationProfile,
    PortfolioLiquidityDashboardResponse,
    PreferenceCreateRequest,
    PreferenceResponse,
    SavedViewCreateRequest,
    SavedViewResponse,
    InvestigationCreateRequest,
    InvestigationResponse,
)

router = APIRouter(prefix="/api/v1/dashboard/liquidity", tags=["Dashboard - Liquidity"])


# ---------------------------------------------------------------------------
# Portfolio Overview
# ---------------------------------------------------------------------------
@router.get("/portfolio/{portfolio_id}", response_model=PortfolioLiquidityDashboardResponse)
async def get_portfolio_liquidity_overview(
    portfolio_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Returns aggregated liquidity intelligence and holdings rankings for a portfolio."""
    svc = LiquidityDashboardService(db)
    return await svc.get_portfolio_liquidity_overview(portfolio_id)


# ---------------------------------------------------------------------------
# Instrument Spread & Quotes
# ---------------------------------------------------------------------------
@router.get("/instrument/{instrument_id}/quote", response_model=CurrentQuoteItem)
async def get_current_quote(
    instrument_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Returns latest best bid/ask, spread metrics, and quote condition flags."""
    svc = LiquidityDashboardService(db)
    return await svc.get_current_quote(instrument_id)


@router.get("/instrument/{instrument_id}/spread", response_model=InstrumentSpreadDetail)
async def get_instrument_spread_detail(
    instrument_id: str,
    lookback_days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Returns historical spread timeseries, rolling statistics, and percentile rankings."""
    svc = LiquidityDashboardService(db)
    return await svc.get_instrument_spread_detail(instrument_id, lookback_days=lookback_days)


# ---------------------------------------------------------------------------
# Instrument Order Book Depth
# ---------------------------------------------------------------------------
@router.get("/instrument/{instrument_id}/depth", response_model=OrderBookDepthLadder)
async def get_order_book_depth_ladder(
    instrument_id: str,
    levels: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """Returns structured multi-level bid/ask depth ladder and cumulative imbalance."""
    svc = LiquidityDashboardService(db)
    return await svc.get_order_book_depth_ladder(instrument_id, levels_count=levels)


# ---------------------------------------------------------------------------
# Instrument Liquidity Score
# ---------------------------------------------------------------------------
@router.get("/instrument/{instrument_id}/score", response_model=InstrumentLiquidityScore)
async def get_instrument_liquidity_score(
    instrument_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Returns authoritative composite liquidity score and component breakdown."""
    svc = LiquidityDashboardService(db)
    return await svc.get_instrument_liquidity_score(instrument_id)


# ---------------------------------------------------------------------------
# Instrument Liquidation Modeling
# ---------------------------------------------------------------------------
@router.get("/instrument/{instrument_id}/liquidation", response_model=InstrumentLiquidationProfile)
async def get_instrument_liquidation_profile(
    instrument_id: str,
    portfolio_id: Optional[str] = Query(None),
    participation_rate: Decimal = Query(Decimal("0.10"), gt=Decimal("0.0"), le=Decimal("1.0")),
    db: AsyncSession = Depends(get_db),
):
    """Returns partial & full position liquidation cost, duration, and capacity exhaustion."""
    svc = LiquidityDashboardService(db)
    return await svc.get_instrument_liquidation_profile(
        instrument_id=instrument_id,
        portfolio_id=portfolio_id,
        participation_rate=participation_rate,
    )


# ---------------------------------------------------------------------------
# User Preferences & Settings
# ---------------------------------------------------------------------------
@router.get("/preferences", response_model=PreferenceResponse)
async def get_user_preferences(
    user_id: str = Query("default_user"),
    dashboard_name: str = Query("Default Liquidity Dashboard"),
    db: AsyncSession = Depends(get_db),
):
    svc = LiquidityDashboardService(db)
    return await svc.get_or_create_user_preferences(user_id=user_id, dashboard_name=dashboard_name)


@router.post("/preferences", response_model=PreferenceResponse)
async def update_user_preferences(
    req: PreferenceCreateRequest,
    user_id: str = Query("default_user"),
    db: AsyncSession = Depends(get_db),
):
    svc = LiquidityDashboardService(db)
    return await svc.update_user_preferences(user_id=user_id, req=req)


# ---------------------------------------------------------------------------
# Saved Views
# ---------------------------------------------------------------------------
@router.get("/saved-views", response_model=List[SavedViewResponse])
async def list_saved_views(
    user_id: str = Query("default_user"),
    db: AsyncSession = Depends(get_db),
):
    svc = LiquidityDashboardService(db)
    return await svc.list_saved_views(user_id=user_id)


@router.post("/saved-views", response_model=SavedViewResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_view(
    req: SavedViewCreateRequest,
    user_id: str = Query("default_user"),
    db: AsyncSession = Depends(get_db),
):
    svc = LiquidityDashboardService(db)
    return await svc.create_saved_view(user_id=user_id, req=req)


# ---------------------------------------------------------------------------
# Liquidity Investigations
# ---------------------------------------------------------------------------
@router.get("/investigations", response_model=List[InvestigationResponse])
async def list_investigations(
    user_id: Optional[str] = Query(None),
    instrument_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    svc = LiquidityDashboardService(db)
    return await svc.list_investigations(user_id=user_id, instrument_id=instrument_id)


@router.post("/investigations", response_model=InvestigationResponse, status_code=status.HTTP_201_CREATED)
async def create_investigation(
    req: InvestigationCreateRequest,
    user_id: str = Query("default_user"),
    db: AsyncSession = Depends(get_db),
):
    svc = LiquidityDashboardService(db)
    return await svc.create_investigation(user_id=user_id, req=req)
