"""
M13.09 - Historical Analytics Router.
FastAPI endpoints for:
- Historical portfolio values (NAV, valuation snapshots)
- Historical P&L
- Historical risk trends (VaR, ES, Volatility, Drawdown)
- Historical exposure trends
- Material event overlays (alerts, breaches, trades)
- Point-in-time state reconstruction & bitemporal provenance manifests
- Historical version comparisons
- User preferences and saved views
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Path, Body, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.dashboard_visualization.historical_analytics.schemas import (
    HistoricalMode,
    HistoricalPortfolioValueResponse,
    HistoricalPnLResponse,
    HistoricalRiskTrendResponse,
    HistoricalExposureResponse,
    HistoricalEventsResponse,
    PointInTimeStateResponse,
    HistoricalVersionComparisonResponse,
    HistoricalPreferenceResponse,
    HistoricalPreferenceUpdate,
    HistoricalSavedViewResponse,
    HistoricalSavedViewCreate,
)
from backend.app.modules.dashboard_visualization.historical_analytics.services import (
    HistoricalAnalyticsService,
)

router = APIRouter(prefix="/history", tags=["M13.09 Historical Analytics"])


# -------------------------------------------------------------
# Preferences & Saved Views (Placed first to avoid route shadowing)
# -------------------------------------------------------------
@router.get("/preferences/me", response_model=HistoricalPreferenceResponse)
async def get_user_preferences(
    user_id: str = Query("default_user", description="Current user ID"),
    dashboard_name: Optional[str] = Query(None, description="Dashboard layout title"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve user dashboard preferences for historical analytics."""
    service = HistoricalAnalyticsService(db)
    return await service.get_or_create_user_preferences(user_id=user_id, dashboard_name=dashboard_name)


@router.put("/preferences/me", response_model=HistoricalPreferenceResponse)
async def update_user_preferences(
    payload: HistoricalPreferenceUpdate,
    user_id: str = Query("default_user", description="Current user ID"),
    db: AsyncSession = Depends(get_db),
):
    """Update user dashboard preferences."""
    service = HistoricalAnalyticsService(db)
    return await service.update_user_preferences(payload, user_id=user_id)


@router.get("/saved-views", response_model=List[HistoricalSavedViewResponse])
async def list_saved_views(
    user_id: str = Query("default_user", description="Current user ID"),
    db: AsyncSession = Depends(get_db),
):
    """List saved historical analysis views for the user."""
    service = HistoricalAnalyticsService(db)
    return await service.list_saved_views(user_id=user_id)


@router.post("/saved-views", response_model=HistoricalSavedViewResponse)
async def create_saved_view(
    payload: HistoricalSavedViewCreate,
    user_id: str = Query("default_user", description="Current user ID"),
    db: AsyncSession = Depends(get_db),
):
    """Create a new saved historical workspace view."""
    service = HistoricalAnalyticsService(db)
    return await service.create_saved_view(payload, user_id=user_id)


# -------------------------------------------------------------
# Historical Portfolio Values & P&L
# -------------------------------------------------------------
@router.get("/portfolio-values", response_model=HistoricalPortfolioValueResponse)
async def get_historical_portfolio_values(
    portfolio_id: str = Query(..., description="Target portfolio identifier"),
    start_time: Optional[datetime] = Query(None, description="Start timestamp (UTC)"),
    end_time: Optional[datetime] = Query(None, description="End timestamp (UTC)"),
    metric: str = Query("NAV", description="Valuation metric (NAV, MARKET_VALUE)"),
    frequency: str = Query("DAILY", description="Observation frequency"),
    historical_mode: HistoricalMode = Query(HistoricalMode.AS_KNOWN_AT_TIME, description="Bitemporal mode"),
    downsample_limit: int = Query(500, description="Max observations before LTTB downsampling"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve authoritative historical portfolio valuation records."""
    service = HistoricalAnalyticsService(db)
    return await service.get_historical_portfolio_values(
        portfolio_id=portfolio_id,
        start_time=start_time,
        end_time=end_time,
        metric=metric,
        frequency=frequency,
        historical_mode=historical_mode,
        downsample_limit=downsample_limit,
    )


@router.get("/pnl", response_model=HistoricalPnLResponse)
async def get_historical_pnl(
    portfolio_id: str = Query(..., description="Target portfolio identifier"),
    start_time: Optional[datetime] = Query(None, description="Start timestamp (UTC)"),
    end_time: Optional[datetime] = Query(None, description="End timestamp (UTC)"),
    pnl_type: str = Query("DAILY", description="P&L type: DAILY, CUMULATIVE, REALIZED, UNREALIZED"),
    frequency: str = Query("DAILY", description="Observation frequency"),
    historical_mode: HistoricalMode = Query(HistoricalMode.AS_KNOWN_AT_TIME, description="Bitemporal mode"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve authoritative historical P&L observations."""
    service = HistoricalAnalyticsService(db)
    return await service.get_historical_pnl(
        portfolio_id=portfolio_id,
        start_time=start_time,
        end_time=end_time,
        pnl_type=pnl_type,
        frequency=frequency,
        historical_mode=historical_mode,
    )


# -------------------------------------------------------------
# Historical Risk Trends & Exposures
# -------------------------------------------------------------
@router.get("/risk", response_model=HistoricalRiskTrendResponse)
async def get_historical_risk_trends(
    portfolio_id: str = Query(..., description="Target portfolio identifier"),
    metric: str = Query("VAR", description="Risk metric: VAR, ES, VOLATILITY, DRAWDOWN"),
    start_time: Optional[datetime] = Query(None, description="Start timestamp (UTC)"),
    end_time: Optional[datetime] = Query(None, description="End timestamp (UTC)"),
    confidence_level: Optional[float] = Query(None, description="Confidence level for VaR/ES (e.g. 0.99)"),
    frequency: str = Query("DAILY", description="Observation frequency"),
    historical_mode: HistoricalMode = Query(HistoricalMode.AS_KNOWN_AT_TIME, description="Bitemporal mode"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve authoritative historical risk measurements from M07."""
    service = HistoricalAnalyticsService(db)
    return await service.get_historical_risk_trends(
        portfolio_id=portfolio_id,
        metric=metric,
        start_time=start_time,
        end_time=end_time,
        confidence_level=confidence_level,
        frequency=frequency,
        historical_mode=historical_mode,
    )


@router.get("/exposures", response_model=HistoricalExposureResponse)
async def get_historical_exposures(
    portfolio_id: str = Query(..., description="Target portfolio identifier"),
    exposure_type: str = Query("GROSS", description="Exposure type: GROSS, NET, LONG, SHORT"),
    start_time: Optional[datetime] = Query(None, description="Start timestamp (UTC)"),
    end_time: Optional[datetime] = Query(None, description="End timestamp (UTC)"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve historical exposure trends."""
    service = HistoricalAnalyticsService(db)
    return await service.get_historical_exposure(
        portfolio_id=portfolio_id,
        exposure_type=exposure_type,
        start_time=start_time,
        end_time=end_time,
    )


# -------------------------------------------------------------
# Historical Events & Overlays
# -------------------------------------------------------------
@router.get("/events", response_model=HistoricalEventsResponse)
async def get_historical_events(
    portfolio_id: Optional[str] = Query(None, description="Portfolio filter"),
    start_time: Optional[datetime] = Query(None, description="Start timestamp (UTC)"),
    end_time: Optional[datetime] = Query(None, description="End timestamp (UTC)"),
    event_types: Optional[List[str]] = Query(None, description="Filter categories (ALERT, BREACH, TRADE)"),
    severity: Optional[str] = Query(None, description="Filter severity"),
    instrument_id: Optional[str] = Query(None, description="Filter instrument"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Page size"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve material historical events for chart overlay."""
    service = HistoricalAnalyticsService(db)
    return await service.get_historical_events(
        portfolio_id=portfolio_id,
        start_time=start_time,
        end_time=end_time,
        event_types=event_types,
        severity=severity,
        instrument_id=instrument_id,
        page=page,
        page_size=page_size,
    )


# -------------------------------------------------------------
# Point-in-Time State & Version Comparison
# -------------------------------------------------------------
@router.get("/point-in-time", response_model=PointInTimeStateResponse)
async def get_point_in_time_state(
    portfolio_id: str = Query(..., description="Target portfolio identifier"),
    effective_at: datetime = Query(..., description="Historical business timestamp"),
    known_at: Optional[datetime] = Query(None, description="Knowledge timestamp (as-known-at-time)"),
    historical_mode: HistoricalMode = Query(HistoricalMode.AS_KNOWN_AT_TIME, description="Temporal query mode"),
    db: AsyncSession = Depends(get_db),
):
    """Reconstruct point-in-time portfolio holdings, valuations, risk outputs, and data provenance manifest."""
    service = HistoricalAnalyticsService(db)
    return await service.reconstruct_point_in_time_state(
        portfolio_id=portfolio_id,
        effective_at=effective_at,
        known_at=known_at,
        historical_mode=historical_mode,
    )


@router.get("/version-comparison", response_model=HistoricalVersionComparisonResponse)
async def compare_historical_versions(
    portfolio_id: str = Query(..., description="Target portfolio identifier"),
    metric: str = Query("NAV", description="Metric to compare"),
    effective_at: datetime = Query(..., description="Historical observation effective date"),
    version_a_id: str = Query(..., description="Snapshot / calculation ID for Version A"),
    version_b_id: str = Query(..., description="Snapshot / calculation ID for Version B"),
    db: AsyncSession = Depends(get_db),
):
    """Compare two historical versions of a calculation or snapshot without overwriting historical records."""
    service = HistoricalAnalyticsService(db)
    return await service.compare_historical_versions(
        portfolio_id=portfolio_id,
        metric=metric,
        effective_at=effective_at,
        version_a_id=version_a_id,
        version_b_id=version_b_id,
    )
