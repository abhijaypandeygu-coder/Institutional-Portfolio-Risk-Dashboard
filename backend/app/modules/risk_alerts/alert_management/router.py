"""
FastAPI router for M12.06 — Alert Management.
Prefix: /api/v1/alert-management
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.risk_alerts.alert_management.schemas.alert_management_schemas import (
    AlertAcknowledgeRequest,
    AlertAcknowledgementResponse,
    AlertAssignRequest,
    AlertAssignmentResponse,
    AlertWorkflowTransitionRequest,
    AlertWorkflowStateResponse,
    AlertWorkflowEventResponse,
    AlertCommentCreate,
    AlertCommentUpdate,
    AlertCommentResponse,
    AlertEvidenceCreate,
    AlertEvidenceResponse,
    AlertDispositionCreate,
    AlertDispositionResponse,
    AlertResolutionAssessmentCreate,
    AlertResolutionAssessmentResponse,
    AlertCloseRequest,
    AlertClosureResponse,
    AlertReopenRequest,
    AlertReopeningResponse,
    AlertWorkQueueItem,
    AlertManagementSummary,
)
from backend.app.modules.risk_alerts.alert_management.services.alert_management_service import (
    AlertManagementService,
)

router = APIRouter(prefix="/alert-management", tags=["M12.06 — Alert Management"])


# ------------------ Acknowledgement ------------------
@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertAcknowledgementResponse)
async def acknowledge_alert(
    alert_id: str,
    payload: AlertAcknowledgeRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AlertManagementService(db)
    return await service.acknowledge_alert(alert_id, payload)


# ------------------ Ownership Assignment ------------------
@router.post("/alerts/{alert_id}/assign", response_model=AlertAssignmentResponse)
async def assign_alert(
    alert_id: str,
    payload: AlertAssignRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AlertManagementService(db)
    return await service.assign_alert(alert_id, payload)


@router.delete("/alerts/{alert_id}/assignment", response_model=Optional[AlertAssignmentResponse])
async def unassign_alert(
    alert_id: str,
    unassigned_by_user_id: str = Query(...),
    reason: str = Query("Manual unassignment"),
    db: AsyncSession = Depends(get_db),
):
    service = AlertManagementService(db)
    res = await service.unassign_alert(alert_id, unassigned_by_user_id, reason)
    if not res:
        raise HTTPException(status_code=404, detail="No active assignment found for alert")
    return res


# ------------------ State Machine Transitions ------------------
@router.patch("/alerts/{alert_id}/workflow/status", response_model=AlertWorkflowStateResponse)
async def transition_workflow_status(
    alert_id: str,
    payload: AlertWorkflowTransitionRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AlertManagementService(db)
    try:
        return await service.transition_state(alert_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/alerts/{alert_id}/workflow", response_model=AlertWorkflowStateResponse)
async def get_workflow_state(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = AlertManagementService(db)
    return await service.get_workflow_state(alert_id)


@router.get("/alerts/{alert_id}/workflow/timeline", response_model=List[AlertWorkflowEventResponse])
async def get_workflow_timeline(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = AlertManagementService(db)
    return await service.get_workflow_timeline(alert_id)


# ------------------ Comments & Evidence ------------------
@router.post("/alerts/{alert_id}/comments", response_model=AlertCommentResponse, status_code=status.HTTP_201_CREATED)
async def add_investigation_comment(
    alert_id: str,
    payload: AlertCommentCreate,
    db: AsyncSession = Depends(get_db),
):
    service = AlertManagementService(db)
    return await service.add_comment(alert_id, payload)


@router.get("/alerts/{alert_id}/comments", response_model=List[AlertCommentResponse])
async def list_investigation_comments(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = AlertManagementService(db)
    return await service.list_comments(alert_id)


@router.patch("/comments/{comment_id}", response_model=AlertCommentResponse)
async def update_comment(
    comment_id: str,
    payload: AlertCommentUpdate,
    db: AsyncSession = Depends(get_db),
):
    service = AlertManagementService(db)
    try:
        return await service.update_comment(comment_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/alerts/{alert_id}/evidence", response_model=AlertEvidenceResponse, status_code=status.HTTP_201_CREATED)
async def add_investigation_evidence(
    alert_id: str,
    payload: AlertEvidenceCreate,
    db: AsyncSession = Depends(get_db),
):
    service = AlertManagementService(db)
    return await service.add_evidence(alert_id, payload)


@router.get("/alerts/{alert_id}/evidence", response_model=List[AlertEvidenceResponse])
async def list_investigation_evidence(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = AlertManagementService(db)
    return await service.list_evidence(alert_id)


# ------------------ Disposition & Resolution ------------------
@router.post("/alerts/{alert_id}/disposition", response_model=AlertDispositionResponse)
async def record_disposition(
    alert_id: str,
    payload: AlertDispositionCreate,
    db: AsyncSession = Depends(get_db),
):
    service = AlertManagementService(db)
    return await service.record_disposition(alert_id, payload)


@router.post("/alerts/{alert_id}/resolution", response_model=AlertResolutionAssessmentResponse)
async def assess_resolution(
    alert_id: str,
    payload: AlertResolutionAssessmentCreate,
    db: AsyncSession = Depends(get_db),
):
    service = AlertManagementService(db)
    return await service.assess_resolution(alert_id, payload)


# ------------------ Closure & Reopening ------------------
@router.post("/alerts/{alert_id}/close", response_model=AlertClosureResponse)
async def close_alert(
    alert_id: str,
    payload: AlertCloseRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AlertManagementService(db)
    try:
        return await service.close_alert(alert_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/alerts/{alert_id}/reopen", response_model=AlertReopeningResponse)
async def reopen_alert(
    alert_id: str,
    payload: AlertReopenRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AlertManagementService(db)
    try:
        return await service.reopen_alert(alert_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ------------------ Work Queue & Summary ------------------
@router.get("/queue", response_model=List[AlertWorkQueueItem])
async def get_work_queue(
    current_state: Optional[str] = Query(None),
    assigned_user_id: Optional[str] = Query(None),
    assigned_role_id: Optional[str] = Query(None),
    portfolio_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    service = AlertManagementService(db)
    return await service.list_work_queue(
        current_state, assigned_user_id, assigned_role_id, portfolio_id, limit, offset
    )


@router.get("/summary", response_model=AlertManagementSummary)
async def get_management_summary(
    db: AsyncSession = Depends(get_db),
):
    service = AlertManagementService(db)
    return await service.get_management_summary()

