"""
Module 03.03: Timestamp Validation - FastAPI Router.
Provides REST API endpoints for:
- Single & Batch observation timestamp validation (/validate, /validate/batch)
- Rule management (/rules)
- Validation outcomes and observation inspection (/results, /results/{result_id})
- Ordering anomalies inspection (/ordering/incidents, /ordering/summary)
- Clock status & drift telemetry (/clock/status)
- Freshness & staleness summary (/freshness/summary)
- Exchange session alignment checking (/session-check)
- Timestamp anomaly incident lifecycle (/incidents)
- Quality summary metrics (/summary)
"""
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import AuthenticatedUser, UserRole, require_role
from backend.app.modules.market_data_quality.timestamp_validation.models import (
    FinalTimestampStatus,
    TimestampAnomalyStatus,
)
from backend.app.modules.market_data_quality.timestamp_validation.schemas import (
    BatchTimestampObservationInput,
    ClockStatusResponse,
    SessionCheckRequest,
    SessionCheckResponse,
    TimestampAnomalyIncidentResponse,
    TimestampAnomalyResolutionRequest,
    TimestampObservationInput,
    TimestampQualitySummary,
    TimestampRuleCreate,
    TimestampRuleResponse,
    TimestampRuleUpdate,
    TimestampValidationResultResponse,
)
from backend.app.modules.market_data_quality.timestamp_validation.service import (
    TimestampValidationService,
)

router = APIRouter(prefix="/quality/timestamp-validation", tags=["M03.03 - Timestamp Validation"])


def get_service(session: AsyncSession = Depends(get_db)) -> TimestampValidationService:
    return TimestampValidationService(session)


# ============================================================================
# Validation Endpoints
# ============================================================================

@router.post(
    "/validate",
    response_model=TimestampValidationResultResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate observation timestamp integrity",
)
async def validate_observation(
    obs: TimestampObservationInput,
    service: TimestampValidationService = Depends(get_service),
    actor: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    return await service.validate_observation(obs)


@router.post(
    "/validate/batch",
    response_model=List[TimestampValidationResultResponse],
    status_code=status.HTTP_200_OK,
    summary="Validate a batch of observation timestamps",
)
async def validate_batch(
    payload: BatchTimestampObservationInput,
    service: TimestampValidationService = Depends(get_service),
    actor: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    return await service.validate_batch(payload.observations)


@router.get(
    "/results",
    response_model=List[TimestampValidationResultResponse],
    summary="List timestamp validation results with optional filters",
)
async def list_results(
    instrument_id: Optional[str] = Query(None),
    feed_id: Optional[str] = Query(None),
    final_status: Optional[FinalTimestampStatus] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    service: TimestampValidationService = Depends(get_service),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    results = await service.repo.list_results(
        instrument_id=instrument_id, feed_id=feed_id, final_status=final_status, limit=limit
    )
    out = []
    for r in results:
        evs = [
            {
                "rule_code": ev.rule_code,
                "evidence_type": ev.evidence_type,
                "previous_value": ev.previous_value,
                "current_value": ev.current_value,
                "calculated_value": ev.calculated_value,
                "threshold_value": ev.threshold_value,
                "source_reference": ev.source_reference,
                "status": ev.status,
                "evidence_payload": ev.evidence_payload,
            }
            for ev in r.evidence_items
        ]
        out.append(service._build_response(r, evs))
    return out


@router.get(
    "/results/{result_id}",
    response_model=TimestampValidationResultResponse,
    summary="Get detailed timestamp validation result by ID",
)
async def get_result_by_id(
    result_id: UUID,
    service: TimestampValidationService = Depends(get_service),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    r = await service.repo.get_result_by_id(result_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validation result not found")
    evs = [
        {
            "rule_code": ev.rule_code,
            "evidence_type": ev.evidence_type,
            "previous_value": ev.previous_value,
            "current_value": ev.current_value,
            "calculated_value": ev.calculated_value,
            "threshold_value": ev.threshold_value,
            "source_reference": ev.source_reference,
            "status": ev.status,
            "evidence_payload": ev.evidence_payload,
        }
        for ev in r.evidence_items
    ]
    return service._build_response(r, evs)


# ============================================================================
# Rule Management Endpoints
# ============================================================================

@router.post(
    "/rules",
    response_model=TimestampRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new timestamp validation rule",
)
async def create_rule(
    payload: TimestampRuleCreate,
    service: TimestampValidationService = Depends(get_service),
    actor: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    return await service.create_rule(payload)


@router.get(
    "/rules",
    response_model=List[TimestampRuleResponse],
    summary="List timestamp validation rules",
)
async def list_rules(
    enabled_only: bool = Query(False),
    service: TimestampValidationService = Depends(get_service),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    return await service.list_rules(enabled_only=enabled_only)


@router.patch(
    "/rules/{rule_id}",
    response_model=TimestampRuleResponse,
    summary="Update or tune an existing timestamp validation rule",
)
async def update_rule(
    rule_id: UUID,
    payload: TimestampRuleUpdate,
    service: TimestampValidationService = Depends(get_service),
    actor: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    updates = payload.model_dump(exclude_unset=True)
    return await service.update_rule(rule_id, updates)


@router.post(
    "/rules/{rule_id}/disable",
    response_model=TimestampRuleResponse,
    summary="Disable a timestamp validation rule",
)
async def disable_rule(
    rule_id: UUID,
    service: TimestampValidationService = Depends(get_service),
    actor: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    return await service.disable_rule(rule_id)


# ============================================================================
# Anomaly Incident Endpoints
# ============================================================================

@router.get(
    "/incidents",
    response_model=List[TimestampAnomalyIncidentResponse],
    summary="List timestamp anomaly incidents",
)
async def list_incidents(
    status: Optional[TimestampAnomalyStatus] = Query(None),
    instrument_id: Optional[str] = Query(None),
    service: TimestampValidationService = Depends(get_service),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    return await service.list_incidents(status=status, instrument_id=instrument_id)


@router.post(
    "/incidents/{incident_id}/resolve",
    response_model=TimestampAnomalyIncidentResponse,
    summary="Resolve a timestamp anomaly incident with documented reasoning",
)
async def resolve_incident(
    incident_id: UUID,
    payload: TimestampAnomalyResolutionRequest,
    service: TimestampValidationService = Depends(get_service),
    actor: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    return await service.resolve_incident(
        incident_id=incident_id,
        req_status=payload.status,
        reason=payload.resolution_reason,
        user=actor.username,
    )


# ============================================================================
# Session Check & Summary Endpoints
# ============================================================================

@router.post(
    "/session-check",
    response_model=SessionCheckResponse,
    summary="Check timestamp alignment against exchange trading session and calendar",
)
async def check_session(
    payload: SessionCheckRequest,
    service: TimestampValidationService = Depends(get_service),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    return service.check_session(payload)


@router.get(
    "/summary",
    response_model=TimestampQualitySummary,
    summary="Retrieve overall timestamp validation metrics",
)
async def get_summary(
    service: TimestampValidationService = Depends(get_service),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    return await service.get_quality_summary()
