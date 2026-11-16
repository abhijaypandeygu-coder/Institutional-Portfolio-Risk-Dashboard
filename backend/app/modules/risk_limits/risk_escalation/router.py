"""
FastAPI router for M11.08 Risk Escalation.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.risk_limits.risk_escalation.schemas.risk_escalation_schemas import (
    RiskWorkflowCreateInput,
    BreachAcknowledgeInput,
    BreachAssignInput,
    ManualEscalateInput,
    ResolutionPlanCreateInput,
    ResolutionActionProgressInput,
    MitigationEvidenceInput,
    ClosureRequestInput,
    ClosureApproveInput,
    ClosureRejectInput,
    BreachReopenInput,
    RiskBreachWorkflowResponse,
    RiskBreachAcknowledgementResponse,
    RiskBreachAssignmentResponse,
    RiskEscalationEventResponse,
    RiskResolutionPlanResponse,
    RiskResolutionActionResponse,
    EscalationDashboardSummary,
)
from backend.app.modules.risk_limits.risk_escalation.services.risk_escalation_service import RiskEscalationService

router = APIRouter(prefix="/api/v1/risk-escalation", tags=["M11.08 Risk Escalation"])


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "module": "M11.08 — Risk Escalation",
        "version": "1.0.0",
        "capabilities": [
            "breach_acknowledgement",
            "breach_assignment",
            "escalation_policies",
            "automatic_escalation",
            "manual_escalation",
            "resolution_plans",
            "mitigation_tracking",
            "lifecycle_state_machine",
            "closure_governance",
            "reopening_management",
            "escalation_analytics",
        ]
    }


@router.get("/dashboard", response_model=EscalationDashboardSummary)
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    svc = RiskEscalationService(db)
    return await svc.get_dashboard_summary()


@router.post("/workflows", response_model=RiskBreachWorkflowResponse)
async def create_or_get_workflow(payload: RiskWorkflowCreateInput, db: AsyncSession = Depends(get_db)):
    svc = RiskEscalationService(db)
    return await svc.get_or_create_workflow(payload)


@router.get("/workflows", response_model=List[RiskBreachWorkflowResponse])
async def list_workflows(
    portfolio_id: Optional[str] = Query(None),
    lifecycle_state: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    owner_user_id: Optional[str] = Query(None),
    is_overdue: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    svc = RiskEscalationService(db)
    return await svc.repo.list_workflows(
        portfolio_id=portfolio_id,
        lifecycle_state=lifecycle_state,
        severity=severity,
        owner_user_id=owner_user_id,
        is_overdue=is_overdue,
        limit=limit,
        offset=offset,
    )


@router.get("/workflows/{workflow_id}", response_model=RiskBreachWorkflowResponse)
async def get_workflow(workflow_id: str, db: AsyncSession = Depends(get_db)):
    svc = RiskEscalationService(db)
    wf = await svc.repo.get_workflow_by_id(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    return wf


@router.post("/workflows/{workflow_id}/acknowledge", response_model=RiskBreachWorkflowResponse)
async def acknowledge_workflow(workflow_id: str, payload: BreachAcknowledgeInput, db: AsyncSession = Depends(get_db)):
    svc = RiskEscalationService(db)
    return await svc.acknowledge_breach(workflow_id, payload)


@router.post("/workflows/{workflow_id}/assign", response_model=RiskBreachWorkflowResponse)
async def assign_workflow(workflow_id: str, payload: BreachAssignInput, db: AsyncSession = Depends(get_db)):
    svc = RiskEscalationService(db)
    return await svc.assign_breach(workflow_id, payload)


@router.post("/workflows/{workflow_id}/escalate", response_model=RiskBreachWorkflowResponse)
async def escalate_workflow(workflow_id: str, payload: ManualEscalateInput, db: AsyncSession = Depends(get_db)):
    svc = RiskEscalationService(db)
    return await svc.escalate_breach(
        workflow_id=workflow_id,
        target_level_name=payload.target_level_name,
        escalation_reason=payload.escalation_reason,
        initiated_by_user_id=payload.initiated_by_user_id,
        idempotency_key=payload.idempotency_key,
    )


@router.post("/workflows/{workflow_id}/resolution-plans", response_model=RiskResolutionPlanResponse)
async def create_plan(workflow_id: str, payload: ResolutionPlanCreateInput, db: AsyncSession = Depends(get_db)):
    svc = RiskEscalationService(db)
    return await svc.create_resolution_plan(workflow_id, payload)


@router.post("/actions/{action_id}/progress", response_model=RiskResolutionActionResponse)
async def update_action(action_id: str, payload: ResolutionActionProgressInput, db: AsyncSession = Depends(get_db)):
    svc = RiskEscalationService(db)
    return await svc.update_action_progress(action_id, payload)


@router.post("/workflows/{workflow_id}/evidence")
async def submit_evidence(workflow_id: str, payload: MitigationEvidenceInput, db: AsyncSession = Depends(get_db)):
    svc = RiskEscalationService(db)
    ev = await svc.submit_mitigation_evidence(workflow_id, payload)
    return {"status": "SUCCESS", "evidence_id": ev.id, "verified": ev.verified_risk_reduction}


@router.post("/workflows/{workflow_id}/request-closure")
async def request_closure(workflow_id: str, payload: ClosureRequestInput, db: AsyncSession = Depends(get_db)):
    svc = RiskEscalationService(db)
    req = await svc.request_closure(workflow_id, payload)
    return {"status": "PENDING_APPROVAL", "request_id": req.id}


@router.post("/workflows/{workflow_id}/approve-closure", response_model=RiskBreachWorkflowResponse)
async def approve_closure(workflow_id: str, payload: ClosureApproveInput, db: AsyncSession = Depends(get_db)):
    svc = RiskEscalationService(db)
    return await svc.approve_closure(workflow_id, payload)


@router.post("/workflows/{workflow_id}/reopen", response_model=RiskBreachWorkflowResponse)
async def reopen_workflow(workflow_id: str, payload: BreachReopenInput, db: AsyncSession = Depends(get_db)):
    svc = RiskEscalationService(db)
    return await svc.reopen_breach(workflow_id, payload)

