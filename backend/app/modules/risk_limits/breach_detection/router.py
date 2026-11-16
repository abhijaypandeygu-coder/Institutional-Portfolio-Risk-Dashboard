"""
FastAPI router for M11.06 — Breach Detection.
"""

from typing import List, Optional, Dict
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.risk_limits.breach_detection.repositories.breach_detection_repository import (
    BreachDetectionRepository,
)
from backend.app.modules.risk_limits.breach_detection.services.breach_detection_service import (
    BreachDetectionService,
)
from backend.app.modules.risk_limits.breach_detection.schemas.breach_detection_schemas import (
    RiskMetricInput,
    BatchMetricInput,
    BreachEvaluationResponse,
    BreachEventResponse,
    BreachEpisodeResponse,
    BreachObservationResponse,
    DetectionRuleCreate,
    DetectionRuleResponse,
    BreachMonitoringOverviewResponse,
    BreachAuditEventResponse,
)

router = APIRouter(prefix="/api/v1/breach-detection", tags=["Risk Limits - Breach Detection"])


def get_service(db: AsyncSession = Depends(get_db)) -> BreachDetectionService:
    repo = BreachDetectionRepository(db)
    return BreachDetectionService(repo)


# -------------------------------------------------------------
# Health Check
# -------------------------------------------------------------

@router.get("/health", summary="Breach Detection Engine Health Check")
async def health_check():
    return {
        "module": "M11.06 — Breach Detection",
        "status": "healthy",
        "features": [
            "Active Limit Resolution",
            "Warning & Hard Boundary Detection",
            "Stateful Breach Episodes & Deduplication",
            "Persistence & Recovery Hysteresis",
            "Stale & Invalid Input Rejection",
            "Immutable Cryptographic Evidence",
        ],
    }


# -------------------------------------------------------------
# Breach Evaluation Endpoints
# -------------------------------------------------------------

@router.post("/evaluate", response_model=BreachEvaluationResponse, status_code=status.HTTP_201_CREATED)
async def evaluate_single_metric(
    metric: RiskMetricInput,
    hard_threshold: Optional[Decimal] = Query(None),
    warning_threshold: Optional[Decimal] = Query(None),
    limit_nature: str = Query("CAP"),
    comparison_operator: str = Query("GREATER_THAN"),
    active_limit_id: Optional[str] = Query(None),
    effective_limit_snapshot_id: Optional[str] = Query(None),
    service: BreachDetectionService = Depends(get_service),
):
    try:
        return await service.evaluate_metric(
            metric=metric,
            hard_threshold=hard_threshold,
            warning_threshold=warning_threshold,
            limit_nature=limit_nature,
            comparison_operator=comparison_operator,
            active_limit_id=active_limit_id,
            effective_limit_snapshot_id=effective_limit_snapshot_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/evaluate/batch", response_model=List[BreachEvaluationResponse])
async def evaluate_batch_metrics(
    payload: BatchMetricInput,
    service: BreachDetectionService = Depends(get_service),
):
    # Evaluates batch with default or metric-mapped limits
    try:
        # Default mapping fallback for testing / ingestion
        hard_thresholds: Dict[str, Decimal] = {}
        for m in payload.metrics:
            hard_thresholds[m.metric_code] = Decimal("10.0")  # Default mock 10% cap
        return await service.evaluate_batch(payload.metrics, hard_thresholds=hard_thresholds)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/evaluations/{evaluation_id}", response_model=BreachEvaluationResponse)
async def get_evaluation(evaluation_id: str, service: BreachDetectionService = Depends(get_service)):
    eval_record = await service.repo.get_evaluation_by_id(evaluation_id)
    if not eval_record:
        raise HTTPException(status_code=404, detail=f"Evaluation '{evaluation_id}' not found.")
    return eval_record


@router.get("/evaluations", response_model=List[BreachEvaluationResponse])
async def list_evaluations(
    portfolio_id: Optional[str] = Query(None),
    metric_code: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=500),
    service: BreachDetectionService = Depends(get_service),
):
    return await service.repo.list_evaluations(
        portfolio_id=portfolio_id, metric_code=metric_code, status=status_filter, limit=limit
    )


# -------------------------------------------------------------
# Breach Events Endpoints
# -------------------------------------------------------------

@router.get("/events", response_model=List[BreachEventResponse])
async def list_events(
    portfolio_id: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    service: BreachDetectionService = Depends(get_service),
):
    return await service.repo.list_events(
        portfolio_id=portfolio_id, severity=severity, event_type=event_type, limit=limit
    )


@router.get("/events/{event_id}", response_model=BreachEventResponse)
async def get_event(event_id: str, service: BreachDetectionService = Depends(get_service)):
    event = await service.repo.get_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Breach event '{event_id}' not found.")
    return event


# -------------------------------------------------------------
# Breach Episodes Endpoints
# -------------------------------------------------------------

@router.get("/episodes", response_model=List[BreachEpisodeResponse])
async def list_episodes(
    portfolio_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=500),
    service: BreachDetectionService = Depends(get_service),
):
    return await service.repo.list_episodes(portfolio_id=portfolio_id, status=status_filter, limit=limit)


@router.get("/episodes/{episode_id}", response_model=BreachEpisodeResponse)
async def get_episode(episode_id: str, service: BreachDetectionService = Depends(get_service)):
    episode = await service.repo.get_episode_by_id(episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail=f"Breach episode '{episode_id}' not found.")
    return episode


@router.get("/episodes/{episode_id}/observations", response_model=List[BreachObservationResponse])
async def list_episode_observations(episode_id: str, service: BreachDetectionService = Depends(get_service)):
    return await service.repo.list_observations_for_episode(episode_id)


# -------------------------------------------------------------
# Detection Rules Endpoints
# -------------------------------------------------------------

@router.post("/rules", response_model=DetectionRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(data: DetectionRuleCreate, service: BreachDetectionService = Depends(get_service)):
    try:
        return await service.create_rule(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/rules", response_model=List[DetectionRuleResponse])
async def list_rules(
    status_filter: Optional[str] = Query(None, alias="status"),
    service: BreachDetectionService = Depends(get_service),
):
    return await service.repo.list_rules(status=status_filter)


@router.get("/rules/{rule_id}", response_model=DetectionRuleResponse)
async def get_rule(rule_id: str, service: BreachDetectionService = Depends(get_service)):
    r = await service.repo.get_rule_by_id(rule_id)
    if not r:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found.")
    return r


# -------------------------------------------------------------
# Monitoring & Audit Endpoints
# -------------------------------------------------------------

@router.get("/monitoring/overview", response_model=BreachMonitoringOverviewResponse)
async def get_monitoring_overview(service: BreachDetectionService = Depends(get_service)):
    return await service.repo.get_monitoring_overview()


@router.get("/audit", response_model=List[BreachAuditEventResponse])
async def list_audit_events(
    entity_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    service: BreachDetectionService = Depends(get_service),
):
    return await service.repo.list_audit_events(entity_id=entity_id, limit=limit)
