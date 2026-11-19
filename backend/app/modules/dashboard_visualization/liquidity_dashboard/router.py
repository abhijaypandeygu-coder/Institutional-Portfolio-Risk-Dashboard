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
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.market_data_ingestion.adapters.yfinance.adapter import YFinanceMarketDataAdapter
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


@router.post("/portfolio/{portfolio_id}/instrument/{instrument_id}/remove")
async def remove_local_position(portfolio_id: str, instrument_id: str, db: AsyncSession = Depends(get_db)):
    """Close local position books with audited corrections, never broker orders."""
    from sqlalchemy import select, desc
    from backend.app.modules.portfolio_management.position_management.models import PositionBook, PositionSnapshot, PositionStatus, PositionEventType
    from backend.app.modules.portfolio_management.position_management.schemas import PositionEventRegisterRequest
    from backend.app.modules.portfolio_management.position_management.services.service import PositionManagementService
    books = (await db.execute(select(PositionBook).where(PositionBook.portfolio_id == portfolio_id, PositionBook.instrument_id == instrument_id))).scalars().all()
    if not books:
        raise HTTPException(404, "No local position book exists for this instrument in the selected portfolio.")
    service = PositionManagementService(db)
    for book in books:
        snap = (await db.execute(select(PositionSnapshot).where(PositionSnapshot.position_id == book.position_id).order_by(desc(PositionSnapshot.snapshot_version)).limit(1))).scalar_one_or_none()
        quantity = snap.net_signed_quantity if snap else Decimal(0)
        if quantity:
            await service.apply_position_event(PositionEventRegisterRequest(
                portfolio_id=portfolio_id, account_id=book.account_id, instrument_id=instrument_id, listing_id=book.listing_id,
                event_type=PositionEventType.POSITION_CORRECTION, signed_quantity_delta=-quantity,
                settled_quantity_delta=-snap.settled_quantity, unsettled_quantity_delta=-snap.unsettled_quantity,
                idempotency_key=f"UI_REMOVE_{book.position_id}_{snap.snapshot_version}", source_system="PORTFOLIO_DESK_UI",
                reason="User removed local portfolio position; bookkeeping correction only, no broker execution.",
            ))
        book.position_status = PositionStatus.CLOSED
    await db.commit()
    return {"status": "REMOVED", "instrument_id": instrument_id, "portfolio_id": portfolio_id, "broker_order_sent": False}


@router.get("/market-quote")
async def get_latest_market_quote(
    symbol: str = Query(..., min_length=1, max_length=24, pattern=r"^[A-Za-z0-9^][A-Za-z0-9.\-^=]{0,23}$"),
):
    from backend.app.modules.market_data_ingestion.adapters.yfinance.latest_quote import latest_market_quote
    return await latest_market_quote(symbol.upper())


@router.get("/stock-history")
async def stock_price_history(
    symbol: str = Query(..., min_length=1, max_length=24, pattern=r"^[A-Za-z0-9][A-Za-z0-9.\-^=]{0,23}$"),
):
    """One month of adjusted daily closes for the exact requested symbol."""
    from backend.app.modules.market_data_ingestion.adapters.yfinance.stock_history import get_stock_history
    return await get_stock_history(symbol.upper())


# ---------------------------------------------------------------------------
# Global Stock / Ticker Search & Live Market Watch Quotes (yfinance)
# ---------------------------------------------------------------------------
@router.get("/search-tickers")
async def search_market_tickers(
    q: str = Query(..., min_length=1, description="Ticker or company name"),
    limit: int = Query(8, ge=1, le=25),
):
    """
    Searches live market tickers across global equities and ETFs using yfinance.
    """
    return await YFinanceMarketDataAdapter.search_tickers(query=q, max_results=limit)


@router.get("/market-watch")
async def get_live_market_watch(
    symbols: Optional[str] = Query(None, description="Comma-separated ticker symbols"),
):
    """
    Fetches real-time market watch quotes (price, change, up/down) using yfinance.
    """
    sym_list = [s.strip().upper() for s in symbols.split(",")] if symbols else None
    return await YFinanceMarketDataAdapter.get_market_watch_quotes(sym_list)


@router.get("/benchmark-history")
async def get_dated_benchmark_history(
    symbol: str = Query("SPY", min_length=1, max_length=24, pattern=r"^[A-Za-z0-9^][A-Za-z0-9.\-^=]{0,23}$"),
    range: str = Query("1Y", pattern=r"^(1D|1W|1M|3M|6M|1Y|All)$"),
):
    from backend.app.modules.market_data_ingestion.adapters.yfinance.benchmark_history import benchmark_history
    return await benchmark_history(symbol.upper(), range.upper())


@router.get("/benchmark-performance")
async def get_benchmark_performance(
    range: str = Query("1Y", description="Time horizon: 1D, 1W, 1M, 3M, 6M, 1Y, All"),
    nav: float = Query(1000000.0, description="Current portfolio NAV to scale against"),
):
    """
    Returns real benchmark price trajectory (SPY) scaled to the portfolio's active NAV.
    """
    period_map = {
        "1D": ("1d", "15m"),
        "1W": ("5d", "1d"),
        "1M": ("1mo", "1d"),
        "3M": ("3mo", "1d"),
        "6M": ("6mo", "1wk"),
        "1Y": ("1y", "1wk"),
        "ALL": ("2y", "1mo"),
    }
    p, i = period_map.get(range.upper(), ("1y", "1wk"))
    res = await YFinanceMarketDataAdapter.get_benchmark_performance_series(period=p, interval=i, current_nav=nav)
    if not res:
        return {"status": "unavailable", "dates": [], "nav_series": [], "error": "Benchmark history unavailable."}
    return res


# ---------------------------------------------------------------------------
# Portfolio Overview
# ---------------------------------------------------------------------------
@router.get("/portfolio/{portfolio_id}", response_model=PortfolioLiquidityDashboardResponse)
async def get_portfolio_liquidity_overview(
    portfolio_id: str,
    participation_rate: Decimal = Query(Decimal("0.10"), gt=Decimal("0.0"), le=Decimal("1.0")),
    db: AsyncSession = Depends(get_db),
):
    """Returns aggregated liquidity intelligence and holdings rankings for a portfolio."""
    svc = LiquidityDashboardService(db)
    return await svc.get_portfolio_liquidity_overview(portfolio_id, participation_rate=participation_rate)


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
@router.get("/instrument/{instrument_id}/market-context")
async def get_market_context(instrument_id: str, db: AsyncSession = Depends(get_db)):
    return await LiquidityDashboardService(db).get_market_context(instrument_id)


@router.get("/instrument/{instrument_id}/depth-history")
async def get_depth_history(instrument_id: str, levels: int = Query(5, ge=1, le=20), hours: int = Query(24, ge=1, le=168), db: AsyncSession = Depends(get_db)):
    return await LiquidityDashboardService(db).get_depth_history(instrument_id, levels, hours)


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
