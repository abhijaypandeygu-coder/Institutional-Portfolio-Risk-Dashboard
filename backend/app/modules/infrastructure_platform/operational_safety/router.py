"""
FastAPI Router for M15.12 Operational Safety.
Exposes endpoints for safety overview, kill switch activation/reactivation,
pre-dispatch safety checks, incidents, and runbooks.
"""
from typing import List, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, status
from backend.app.modules.infrastructure_platform.operational_safety.schemas import (
    KillSwitchActivateRequest,
    KillSwitchReactivateRequest,
    KillSwitchResponse,
    ExecutionPrecheckRequest,
    ExecutionPrecheckResponse,
    IncidentCreateRequest,
    IncidentResponse,
    OperationalSafetyOverviewResponse,
)
from backend.app.modules.infrastructure_platform.operational_safety.services import (
    KillSwitchManager,
    ExecutionSafetyGateway,
    IncidentManager,
)
from backend.app.modules.infrastructure_platform.operational_safety.models.safety_models import (
    SafetyStateCategory,
    KillSwitchState,
)

router = APIRouter(prefix="/api/v1/operational-safety", tags=["M15.12 Operational Safety"])


@router.get("/status", response_model=OperationalSafetyOverviewResponse)
async def get_operational_safety_overview():
    """Returns platform safety overview, active kill switches, and incidents."""
    switches = KillSwitchManager.list_switches()
    incidents = IncidentManager.list_incidents()
    global_blocked = KillSwitchManager.is_global_execution_blocked()

    overall = SafetyStateCategory.NORMAL
    if global_blocked:
        overall = SafetyStateCategory.BLOCKED
    elif any(s["state"] == KillSwitchState.ACTIVE for s in switches):
        overall = SafetyStateCategory.DEGRADED

    return {
        "overall_safety_state": overall,
        "global_execution_enabled": not global_blocked,
        "active_kill_switches_count": sum(1 for s in switches if s["state"] == KillSwitchState.ACTIVE),
        "active_incidents_count": sum(1 for inc in incidents if inc["status"] != "RESOLVED"),
        "safety_policy_version": "1.0.0",
        "kill_switches": switches,
        "incidents": incidents,
        "timestamp": datetime.now(timezone.utc),
    }


@router.get("/kill-switches", response_model=List[KillSwitchResponse])
async def list_kill_switches():
    """Lists all registered global and scoped kill switches."""
    return KillSwitchManager.list_switches()


@router.post("/kill-switches/activate", response_model=KillSwitchResponse)
async def activate_kill_switch(req: KillSwitchActivateRequest):
    """
    Activates target kill switch. Requires explicit confirm_action=True.
    """
    if not req.confirm_action:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Safety rule: confirm_action must be explicitly set to True."
        )

    sw = KillSwitchManager.activate_switch(
        switch_code=req.switch_code,
        reason=req.reason,
        activated_by=req.activated_by or "operator",
    )

    # Log corresponding incident
    IncidentManager.create_incident(
        title=f"Kill Switch Activated: {req.switch_code}",
        description=req.reason,
        severity="SEV1_CRITICAL" if req.switch_code == "GLOBAL_EXECUTION" else "SEV2_HIGH",
        affected_scope=req.switch_code,
        detected_by=req.activated_by or "operator",
    )

    return sw


@router.post("/kill-switches/reactivate", response_model=KillSwitchResponse)
async def reactivate_kill_switch(req: KillSwitchReactivateRequest):
    """Reactivates a kill switch after verified recovery."""
    try:
        sw = KillSwitchManager.reactivate_switch(
            switch_code=req.switch_code,
            reason=req.reason,
            requested_by=req.requested_by or "operator",
        )
        return sw
    except ValueError as ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ex))


@router.post("/execution-gateway/precheck", response_model=ExecutionPrecheckResponse)
async def precheck_execution_permission(req: ExecutionPrecheckRequest):
    """
    Pre-dispatch execution gateway check evaluating kill switches and limits.
    """
    return ExecutionSafetyGateway.evaluate_execution_permission(
        instrument_id=req.instrument_id,
        requested_quantity=req.requested_quantity,
        side=req.side,
        adapter_id=req.adapter_id,
    )


@router.get("/incidents", response_model=List[IncidentResponse])
async def list_safety_incidents():
    """Lists recent operational incidents."""
    return IncidentManager.list_incidents()


@router.get("/runbooks", response_model=List[Dict[str, Any]])
async def list_safety_runbooks():
    """Returns procedural runbooks for emergency containment and recovery."""
    return IncidentManager.list_runbooks()
