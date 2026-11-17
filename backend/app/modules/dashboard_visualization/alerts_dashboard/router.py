"""
FastAPI router for M13.08 — Alerts Dashboard.

Exposes RESTful endpoints for:
- Active breaches summary, listing, and detail.
- Recent alerts summary, feed, detail, and chronological audit history.
- Operational workflow actions (Acknowledge, Assign, Close, Reopen).
- Dashboard user preferences and saved custom views.
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Path, Body, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.dashboard_visualization.alerts_dashboard.services.alerts_dashboard_service import (
    AlertsDashboardService,
)
from backend.app.modules.dashboard_visualization.alerts_dashboard.schemas.alerts_dashboard_schemas import (
    ActiveBreachSummaryResponse,
    ActiveBreachListResponse,
    BreachDetailResponse,
    RecentAlertSummaryResponse,
    RecentAlertListResponse,
    AlertDetailResponse,
    AlertHistoryResponse,
    AlertAcknowledgeActionRequest,
    AlertAssignActionRequest,
    AlertCloseActionRequest,
    AlertReopenActionRequest,
    BreachAcknowledgeActionRequest,
    ActionExecutionResult,
    AlertsPreferenceCreateRequest,
    AlertsPreferenceResponse,
    AlertsSavedViewCreateRequest,
    AlertsSavedViewResponse,
)

router = APIRouter(prefix="/api/v1/dashboard/alerts", tags=["M13.08 Alerts Dashboard"])


# ============================================================================
# 1. Active Breaches Endpoints
# ============================================================================

@router.get("/breaches/summary", response_model=ActiveBreachSummaryResponse)
async def get_active_breaches_summary(
    portfolio_id: Optional[str] = Query(None, description="Filter summary by portfolio ID"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves consolidated active risk-limit breach summary counts from M11."""
    svc = AlertsDashboardService(db)
    return await svc.get_active_breaches_summary(portfolio_id=portfolio_id)


@router.get("/breaches", response_model=ActiveBreachListResponse)
async def list_active_breaches(
    portfolio_id: Optional[str] = Query(None, description="Portfolio filter"),
    severity: Optional[str] = Query(None, description="WARNING, CRITICAL, EMERGENCY"),
    breach_type: Optional[str] = Query(None, description="PORTFOLIO, POSITION, SECTOR, LIQUIDITY"),
    status: Optional[str] = Query(None, description="OPEN, ACKNOWLEDGED, MITIGATED, CLOSED"),
    assigned_to: Optional[str] = Query(None, description="Assigned user ID"),
    detected_from: Optional[datetime] = Query(None, description="Start detection timestamp"),
    detected_to: Optional[datetime] = Query(None, description="End detection timestamp"),
    search: Optional[str] = Query(None, description="Search metric, ID, or portfolio"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=200, description="Page size"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves paginated active risk limit breaches from authoritative M11 records."""
    svc = AlertsDashboardService(db)
    return await svc.list_active_breaches(
        portfolio_id=portfolio_id,
        severity=severity,
        breach_type=breach_type,
        status=status,
        assigned_to=assigned_to,
        detected_from=detected_from,
        detected_to=detected_to,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get("/breaches/{breach_id}", response_model=BreachDetailResponse)
async def get_breach_detail(
    breach_id: str = Path(..., description="Unique breach identifier"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves full context, threshold parameters, and escalation state for a breach."""
    svc = AlertsDashboardService(db)
    return await svc.get_breach_detail(breach_id)


@router.post("/breaches/{breach_id}/acknowledge", response_model=ActionExecutionResult)
async def acknowledge_breach(
    breach_id: str = Path(..., description="Unique breach identifier"),
    req: BreachAcknowledgeActionRequest = Body(...),
    user_id: str = Query("CURRENT_USER", description="Authenticated operator ID"),
    db: AsyncSession = Depends(get_db),
):
    """Forwards formal breach acknowledgement to M11.08 RiskEscalationService."""
    svc = AlertsDashboardService(db)
    return await svc.acknowledge_breach(breach_id=breach_id, user_id=user_id, req=req)


# ============================================================================
# 2. Recent Alerts Endpoints
# ============================================================================

@router.get("/summary", response_model=RecentAlertSummaryResponse)
async def get_recent_alerts_summary(
    portfolio_id: Optional[str] = Query(None, description="Portfolio filter"),
    time_preset: Optional[str] = Query("LAST_24_HOURS", description="Time window preset"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves recent alert counts categorized by priority and lifecycle state."""
    svc = AlertsDashboardService(db)
    return await svc.get_recent_alerts_summary(
        portfolio_id=portfolio_id, time_preset=time_preset
    )


@router.get("", response_model=RecentAlertListResponse)
@router.get("/feed", response_model=RecentAlertListResponse)
async def list_recent_alerts(
    portfolio_id: Optional[str] = Query(None, description="Portfolio filter"),
    severity: Optional[str] = Query(None, description="Alert priority or severity"),
    alert_category: Optional[str] = Query(None, description="VAR, VOLATILITY, LIQUIDITY, etc."),
    status: Optional[str] = Query(None, description="OPEN, ACKNOWLEDGED, ASSIGNED, CLOSED"),
    assigned_to: Optional[str] = Query(None, description="Assigned operator ID"),
    instrument_id: Optional[str] = Query(None, description="Associated instrument ID"),
    source_module: Optional[str] = Query(None, description="Originating M12 rule module"),
    time_preset: Optional[str] = Query("LAST_24_HOURS", description="Time preset window"),
    triggered_from: Optional[datetime] = Query(None, description="Custom start timestamp"),
    triggered_to: Optional[datetime] = Query(None, description="Custom end timestamp"),
    search: Optional[str] = Query(None, description="Search alert title or ID"),
    sort_by: str = Query("triggered_at", description="triggered_at, priority, status"),
    sort_order: str = Query("desc", description="asc or desc"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Page size"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves chronological, filterable risk alerts from authoritative M12 records."""
    svc = AlertsDashboardService(db)
    return await svc.list_recent_alerts(
        portfolio_id=portfolio_id,
        severity=severity,
        alert_category=alert_category,
        status=status,
        assigned_to=assigned_to,
        instrument_id=instrument_id,
        source_module=source_module,
        time_preset=time_preset,
        triggered_from=triggered_from,
        triggered_to=triggered_to,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )


# ============================================================================
# 4. Dashboard Preferences and Saved Views
# ============================================================================

@router.get("/preferences/me", response_model=AlertsPreferenceResponse)
async def get_user_preferences(
    user_id: str = Query("DEFAULT_ANALYST", description="User ID"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves user dashboard preferences."""
    svc = AlertsDashboardService(db)
    return await svc.get_or_create_user_preferences(user_id=user_id)


@router.put("/preferences/me", response_model=AlertsPreferenceResponse)
async def update_user_preferences(
    req: AlertsPreferenceCreateRequest = Body(...),
    user_id: str = Query("DEFAULT_ANALYST", description="User ID"),
    db: AsyncSession = Depends(get_db),
):
    """Updates user dashboard preferences."""
    svc = AlertsDashboardService(db)
    return await svc.update_user_preferences(user_id=user_id, req=req)


@router.post("/saved-views", response_model=AlertsSavedViewResponse)
async def create_saved_view(
    req: AlertsSavedViewCreateRequest = Body(...),
    user_id: str = Query("DEFAULT_ANALYST", description="User ID"),
    db: AsyncSession = Depends(get_db),
):
    """Saves a custom breach and alert filter configuration."""
    svc = AlertsDashboardService(db)
    return await svc.create_saved_view(user_id=user_id, req=req)


@router.get("/saved-views", response_model=List[AlertsSavedViewResponse])
async def list_saved_views(
    portfolio_id: Optional[str] = Query(None, description="Optional portfolio filter"),
    user_id: str = Query("DEFAULT_ANALYST", description="User ID"),
    db: AsyncSession = Depends(get_db),
):
    """Lists saved custom views accessible to the user."""
    svc = AlertsDashboardService(db)
    return await svc.list_saved_views(user_id=user_id, portfolio_id=portfolio_id)


# ============================================================================
# 3. Alert Detail & Workflow Endpoints
# ============================================================================

@router.get("/{alert_id}", response_model=AlertDetailResponse)
async def get_alert_detail(
    alert_id: str = Path(..., description="Unique alert identifier"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves full alert identity, trigger conditions, evidence, and permitted actions."""
    svc = AlertsDashboardService(db)
    return await svc.get_alert_detail(alert_id)


@router.get("/{alert_id}/history", response_model=AlertHistoryResponse)
async def get_alert_history(
    alert_id: str = Path(..., description="Unique alert identifier"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves chronological immutable audit event history for an alert."""
    svc = AlertsDashboardService(db)
    return await svc.get_alert_history(alert_id)


@router.post("/{alert_id}/acknowledge", response_model=ActionExecutionResult)
async def acknowledge_alert(
    alert_id: str = Path(..., description="Unique alert identifier"),
    req: AlertAcknowledgeActionRequest = Body(...),
    user_id: str = Query("CURRENT_USER", description="Authenticated user ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Formally acknowledges an alert via M12.
    Important: Does NOT resolve or mitigate any underlying M11 risk limit breach.
    """
    svc = AlertsDashboardService(db)
    return await svc.acknowledge_alert(alert_id=alert_id, user_id=user_id, req=req)


@router.post("/{alert_id}/assign", response_model=ActionExecutionResult)
async def assign_alert(
    alert_id: str = Path(..., description="Unique alert identifier"),
    req: AlertAssignActionRequest = Body(...),
    user_id: str = Query("CURRENT_USER", description="Authenticated user ID"),
    db: AsyncSession = Depends(get_db),
):
    """Assigns alert responsibility to an authorized user via M12."""
    svc = AlertsDashboardService(db)
    return await svc.assign_alert(alert_id=alert_id, user_id=user_id, req=req)


@router.post("/{alert_id}/close", response_model=ActionExecutionResult)
async def close_alert(
    alert_id: str = Path(..., description="Unique alert identifier"),
    req: AlertCloseActionRequest = Body(...),
    user_id: str = Query("CURRENT_USER", description="Authenticated user ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Closes an eligible alert with mandatory resolution documentation.
    Displays warning if linked to an active M11 breach.
    """
    svc = AlertsDashboardService(db)
    return await svc.close_alert(alert_id=alert_id, user_id=user_id, req=req)


@router.post("/{alert_id}/reopen", response_model=ActionExecutionResult)
async def reopen_alert(
    alert_id: str = Path(..., description="Unique alert identifier"),
    req: AlertReopenActionRequest = Body(...),
    user_id: str = Query("CURRENT_USER", description="Authenticated user ID"),
    db: AsyncSession = Depends(get_db),
):
    """Reopens an eligible closed alert with mandatory reason via M12."""
    svc = AlertsDashboardService(db)
    return await svc.reopen_alert(alert_id=alert_id, user_id=user_id, req=req)
