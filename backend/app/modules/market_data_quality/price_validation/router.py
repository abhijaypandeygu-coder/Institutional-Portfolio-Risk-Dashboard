"""
Module 03.02: Price Validation - FastAPI Router.
Provides REST API endpoints for:
- Single & Batch observation validation (/validate, /validate/batch)
- Rule management (/rules)
- Validation outcomes and observation inspection (/results, /results/{result_id})
- Anomaly incident resolution lifecycle (/anomalies)
- Reference snapshots & cross-source comparisons (/reference-snapshots, /reference-compare)
- Price quality summary metrics (/summary)
"""
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import AuthenticatedUser, UserRole, require_role
from backend.app.modules.market_data_quality.price_validation.models import (
    AnomalyIncidentStatus,
    ValidationStatus,
)
from backend.app.modules.market_data_quality.price_validation.schemas import (
    BatchPriceObservationInput,
    CrossSourceCompareRequest,
    CrossSourceCompareResponse,
    IncidentResolutionRequest,
    PriceAnomalyIncidentResponse,
    PriceObservationInput,
    PriceQualitySummary,
    ReferenceSnapshotCreate,
    ReferenceSnapshotResponse,
    RuleCreate,
    RuleResponse,
    RuleUpdate,
    ValidationResultResponse,
)
from backend.app.modules.market_data_quality.price_validation.service import (
    PriceValidationService,
)

router = APIRouter(prefix="/quality/price-validation", tags=["M03.02 - Price Validation"])


def get_service(session: AsyncSession = Depends(get_db)) -> PriceValidationService:
    return PriceValidationService(session)


# ============================================================================
# Validation Endpoints
# ============================================================================

@router.post(
    "/validate",
    response_model=ValidationResultResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate a single price observation",
)
async def validate_observation(
    obs: PriceObservationInput,
    service: PriceValidationService = Depends(get_service),
    actor: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    return await service.validate_observation(obs)


@router.post(
    "/validate/batch",
    response_model=List[ValidationResultResponse],
    status_code=status.HTTP_200_OK,
    summary="Validate a batch of price observations",
)
async def validate_batch(
    payload: BatchPriceObservationInput,
    service: PriceValidationService = Depends(get_service),
    actor: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    return await service.validate_batch(payload.observations)


@router.get(
    "/results",
    response_model=List[ValidationResultResponse],
    summary="List validation results with optional filters",
)
async def list_results(
    instrument_id: Optional[str] = Query(None),
    feed_id: Optional[str] = Query(None),
    validation_status: Optional[ValidationStatus] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    service: PriceValidationService = Depends(get_service),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    results = await service.repo.list_results(
        instrument_id=instrument_id, feed_id=feed_id, status=validation_status, limit=limit
    )
    out = []
    for r in results:
        is_eligible = r.validation_status in (
            ValidationStatus.ACCEPTED,
            ValidationStatus.ACCEPTED_WITH_WARNING,
        )
        out.append(
            ValidationResultResponse(
                id=r.id,
                observation_id=r.observation_id,
                instrument_id=r.instrument_id,
                feed_id=r.feed_id,
                provider_id=r.provider_id,
                exchange=r.exchange,
                observation_type=r.observation_type,
                price_field=r.price_field,
                original_price_value=r.original_price_value,
                parsed_price_value=r.parsed_price_value,
                validation_status=r.validation_status,
                overall_severity=r.overall_severity,
                failed_rule_count=r.failed_rule_count,
                warning_count=r.warning_count,
                is_downstream_eligible=is_eligible,
                rule_version_summary=r.rule_version_summary,
                evidence_summary=r.evidence_summary,
                validation_timestamp=r.validation_timestamp,
                evidence_items=[
                    {
                        "rule_code": ev.rule_code,
                        "evidence_type": ev.evidence_type,
                        "observed_value": ev.observed_value,
                        "reference_value": ev.reference_value,
                        "threshold_value": ev.threshold_value,
                        "calculated_difference": ev.calculated_difference,
                        "calculated_percentage": ev.calculated_percentage,
                        "source_reference": ev.source_reference,
                        "status": ev.status,
                        "evidence_payload": ev.evidence_payload,
                    }
                    for ev in r.evidence_items
                ],
            )
        )
    return out


@router.get(
    "/results/{result_id}",
    response_model=ValidationResultResponse,
    summary="Get detailed validation result by ID",
)
async def get_result_by_id(
    result_id: UUID,
    service: PriceValidationService = Depends(get_service),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    r = await service.repo.get_result_by_id(result_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validation result not found")
    is_eligible = r.validation_status in (
        ValidationStatus.ACCEPTED,
        ValidationStatus.ACCEPTED_WITH_WARNING,
    )
    return ValidationResultResponse(
        id=r.id,
        observation_id=r.observation_id,
        instrument_id=r.instrument_id,
        feed_id=r.feed_id,
        provider_id=r.provider_id,
        exchange=r.exchange,
        observation_type=r.observation_type,
        price_field=r.price_field,
        original_price_value=r.original_price_value,
        parsed_price_value=r.parsed_price_value,
        validation_status=r.validation_status,
        overall_severity=r.overall_severity,
        failed_rule_count=r.failed_rule_count,
        warning_count=r.warning_count,
        is_downstream_eligible=is_eligible,
        rule_version_summary=r.rule_version_summary,
        evidence_summary=r.evidence_summary,
        validation_timestamp=r.validation_timestamp,
        evidence_items=[
            {
                "rule_code": ev.rule_code,
                "evidence_type": ev.evidence_type,
                "observed_value": ev.observed_value,
                "reference_value": ev.reference_value,
                "threshold_value": ev.threshold_value,
                "calculated_difference": ev.calculated_difference,
                "calculated_percentage": ev.calculated_percentage,
                "source_reference": ev.source_reference,
                "status": ev.status,
                "evidence_payload": ev.evidence_payload,
            }
            for ev in r.evidence_items
        ],
    )


# ============================================================================
# Rule Management Endpoints
# ============================================================================

@router.post(
    "/rules",
    response_model=RuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new price validation rule",
)
async def create_rule(
    payload: RuleCreate,
    service: PriceValidationService = Depends(get_service),
    actor: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    return await service.create_rule(payload)


@router.get(
    "/rules",
    response_model=List[RuleResponse],
    summary="List price validation rules",
)
async def list_rules(
    enabled_only: bool = Query(False),
    service: PriceValidationService = Depends(get_service),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    return await service.list_rules(enabled_only=enabled_only)


@router.patch(
    "/rules/{rule_id}",
    response_model=RuleResponse,
    summary="Update or tune an existing price validation rule",
)
async def update_rule(
    rule_id: UUID,
    payload: RuleUpdate,
    service: PriceValidationService = Depends(get_service),
    actor: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    updates = payload.model_dump(exclude_unset=True)
    return await service.update_rule(rule_id, updates)


@router.post(
    "/rules/{rule_id}/disable",
    response_model=RuleResponse,
    summary="Disable a price validation rule",
)
async def disable_rule(
    rule_id: UUID,
    service: PriceValidationService = Depends(get_service),
    actor: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    return await service.disable_rule(rule_id)


# ============================================================================
# Anomaly Incidents Endpoints
# ============================================================================

@router.get(
    "/anomalies",
    response_model=List[PriceAnomalyIncidentResponse],
    summary="List price anomaly incidents",
)
async def list_anomalies(
    status: Optional[AnomalyIncidentStatus] = Query(None),
    instrument_id: Optional[str] = Query(None),
    service: PriceValidationService = Depends(get_service),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    return await service.list_incidents(status=status, instrument_id=instrument_id)


@router.post(
    "/anomalies/{incident_id}/resolve",
    response_model=PriceAnomalyIncidentResponse,
    summary="Resolve a price anomaly incident with documented reasoning",
)
async def resolve_anomaly(
    incident_id: UUID,
    payload: IncidentResolutionRequest,
    service: PriceValidationService = Depends(get_service),
    actor: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    return await service.resolve_incident(
        incident_id=incident_id,
        req_status=payload.status,
        reason=payload.resolution_reason,
        user=actor.username,
    )


# ============================================================================
# Reference Price & Cross-Source Comparisons
# ============================================================================

@router.post(
    "/reference-compare",
    response_model=CrossSourceCompareResponse,
    summary="Compare observations between two independent providers",
)
async def compare_cross_sources(
    payload: CrossSourceCompareRequest,
    service: PriceValidationService = Depends(get_service),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    return service.compare_cross_sources(payload)


@router.post(
    "/reference-snapshots",
    response_model=ReferenceSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an authoritative price reference snapshot",
)
async def save_reference_snapshot(
    payload: ReferenceSnapshotCreate,
    service: PriceValidationService = Depends(get_service),
    actor: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    return await service.save_reference_snapshot(payload)


# ============================================================================
# Summary Metrics Endpoint
# ============================================================================

@router.get(
    "/summary",
    response_model=PriceQualitySummary,
    summary="Retrieve overall price quality and validation metrics",
)
async def get_summary(
    service: PriceValidationService = Depends(get_service),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    return await service.get_quality_summary()
