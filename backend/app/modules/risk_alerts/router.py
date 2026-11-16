"""
FastAPI router for M12 Risk Alerts & Notification Engine.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.risk_alerts.schemas.risk_alerts_schemas import (
    AlertRuleCreateInput,
    ThresholdMetricEvaluateInput,
    EventAlertCreateInput,
    AlertAcknowledgeInput,
    AlertAssignInput,
    AlertResolveInput,
    AlertReopenInput,
    AlertRuleResponse,
    AlertEventResponse,
    ThresholdEvaluationResultResponse,
    AlertDashboardSummary,
)
from backend.app.modules.risk_alerts.services.risk_alerts_service import RiskAlertsService

router = APIRouter(prefix="/api/v1/alerts", tags=["M12 - Risk Alerts & Notification Engine"])


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "module": "M12 — Risk Alerts & Notification Engine",
        "version": "1.0.0",
        "features": [
            "M12.01 Threshold Alerts (VaR, Volatility, Exposure, Drawdown)",
            "M12.02 Event-Based Risk Alerts (Breach, Escalation, Pretrade)",
            "M12.03 Data & Feed Health Alerts",
            "M12.04 Liquidity & Microstructure Alerts",
            "M12.05 Portfolio & Position Change Alerts",
            "M12.06 Alert Deduplication & Prioritization",
            "M12.07 Notification Preferences & Delivery",
            "M12.08 Alert Lifecycle, History & Analytics",
        ]
    }


@router.get("/dashboard", response_model=AlertDashboardSummary)
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    svc = RiskAlertsService(db)
    return await svc.get_dashboard_summary()


@router.post("/rules", response_model=AlertRuleResponse)
async def create_rule(payload: AlertRuleCreateInput, db: AsyncSession = Depends(get_db)):
    svc = RiskAlertsService(db)
    rule = await svc.create_alert_rule(payload)
    return rule


@router.get("/rules", response_model=List[AlertRuleResponse])
async def list_rules(metric_category: Optional[str] = Query(None), db: AsyncSession = Depends(get_db)):
    svc = RiskAlertsService(db)
    return await svc.repo.list_rules(metric_category)


@router.post("/thresholds/evaluate", response_model=ThresholdEvaluationResultResponse)
async def evaluate_threshold(payload: ThresholdMetricEvaluateInput, db: AsyncSession = Depends(get_db)):
    svc = RiskAlertsService(db)
    return await svc.evaluate_threshold_metric(payload)


@router.post("/events", response_model=AlertEventResponse)
async def create_event_alert(payload: EventAlertCreateInput, db: AsyncSession = Depends(get_db)):
    svc = RiskAlertsService(db)
    return await svc.create_event_alert(payload)


@router.get("", response_model=List[AlertEventResponse])
async def list_alerts(
    portfolio_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    svc = RiskAlertsService(db)
    alerts = await svc.repo.list_alerts(
        portfolio_id=portfolio_id,
        status=status,
        priority=priority,
        category=category,
        limit=limit,
        offset=offset,
    )
    return [svc._serialize_alert(a) for a in alerts]


@router.get("/{alert_id}", response_model=AlertEventResponse)
async def get_alert(alert_id: str, db: AsyncSession = Depends(get_db)):
    svc = RiskAlertsService(db)
    alert = await svc.repo.get_alert_by_id(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return svc._serialize_alert(alert)


@router.post("/{alert_id}/acknowledge", response_model=AlertEventResponse)
async def acknowledge_alert(alert_id: str, payload: AlertAcknowledgeInput, db: AsyncSession = Depends(get_db)):
    svc = RiskAlertsService(db)
    return await svc.acknowledge_alert(alert_id, payload)


@router.post("/{alert_id}/assign", response_model=AlertEventResponse)
async def assign_alert(alert_id: str, payload: AlertAssignInput, db: AsyncSession = Depends(get_db)):
    svc = RiskAlertsService(db)
    return await svc.assign_alert(alert_id, payload)


@router.post("/{alert_id}/resolve", response_model=AlertEventResponse)
async def resolve_alert(alert_id: str, payload: AlertResolveInput, db: AsyncSession = Depends(get_db)):
    svc = RiskAlertsService(db)
    return await svc.resolve_alert(alert_id, payload)


@router.post("/{alert_id}/reopen", response_model=AlertEventResponse)
async def reopen_alert(alert_id: str, payload: AlertReopenInput, db: AsyncSession = Depends(get_db)):
    svc = RiskAlertsService(db)
    return await svc.reopen_alert(alert_id, payload)
