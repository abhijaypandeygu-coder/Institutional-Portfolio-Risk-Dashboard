"""
FastAPI router for M12.05 — Alert Prioritization.
Prefix: /api/v1/alert-prioritization
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.risk_alerts.alert_prioritization.schemas.alert_prioritization_schemas import (
    AlertPriorityPolicyCreate,
    AlertPriorityPolicyResponse,
    AlertPrioritizationRequest,
    AlertPriorityEvaluationResponse,
    AlertPriorityHistoryResponse,
    AlertGroupResponse,
    AlertOccurrenceResponse,
    PrioritizationSummaryAnalytics,
)
from backend.app.modules.risk_alerts.alert_prioritization.services.alert_prioritization_service import (
    AlertPrioritizationService,
)

router = APIRouter(prefix="/alert-prioritization", tags=["M12.05 — Alert Prioritization"])


# ------------------ Policy Endpoints ------------------
@router.post("/policies", response_model=AlertPriorityPolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_priority_policy(
    payload: AlertPriorityPolicyCreate,
    db: AsyncSession = Depends(get_db),
):
    service = AlertPrioritizationService(db)
    return await service.create_policy(payload)


@router.get("/policies", response_model=List[AlertPriorityPolicyResponse])
async def list_priority_policies(
    enabled_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    service = AlertPrioritizationService(db)
    return await service.list_policies(enabled_only=enabled_only)


# ------------------ Prioritization Pipeline ------------------
@router.post("/prioritize", response_model=AlertPriorityEvaluationResponse)
async def prioritize_alert(
    payload: AlertPrioritizationRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AlertPrioritizationService(db)
    return await service.prioritize_alert(payload)


@router.get("/evaluations/{alert_id}", response_model=AlertPriorityEvaluationResponse)
async def get_alert_evaluation(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = AlertPrioritizationService(db)
    eval_rec = await service.get_evaluation_by_alert_id(alert_id)
    if not eval_rec:
        raise HTTPException(status_code=404, detail=f"No priority evaluation found for alert {alert_id}")
    return eval_rec


@router.get("/evaluations", response_model=List[AlertPriorityEvaluationResponse])
async def list_evaluations(
    priority_band: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    urgency: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    service = AlertPrioritizationService(db)
    return await service.list_evaluations(priority_band, severity, urgency, limit, offset)


@router.get("/history/{alert_id}", response_model=List[AlertPriorityHistoryResponse])
async def get_alert_priority_history(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = AlertPrioritizationService(db)
    return await service.get_alert_history(alert_id)


@router.get("/occurrences/{alert_id}", response_model=List[AlertOccurrenceResponse])
async def get_alert_occurrences(
    alert_id: str,
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    service = AlertPrioritizationService(db)
    return await service.get_alert_occurrences(alert_id, limit)


# ------------------ Groups & Correlation ------------------
@router.get("/groups", response_model=List[AlertGroupResponse])
async def list_alert_groups(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    service = AlertPrioritizationService(db)
    return await service.list_groups(status, limit)


@router.get("/groups/{group_id}", response_model=AlertGroupResponse)
async def get_alert_group(
    group_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = AlertPrioritizationService(db)
    group = await service.get_group_details(group_id)
    if not group:
        raise HTTPException(status_code=404, detail=f"Alert group {group_id} not found")
    return group


# ------------------ Analytics ------------------
@router.get("/analytics/summary", response_model=PrioritizationSummaryAnalytics)
async def get_prioritization_summary(
    db: AsyncSession = Depends(get_db),
):
    service = AlertPrioritizationService(db)
    return await service.get_analytics_summary()

