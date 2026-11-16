"""
FastAPI router for M11.07 — Breach Classification.
"""

from typing import List, Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.risk_limits.breach_classification.repositories.breach_classification_repository import (
    BreachClassificationRepository,
)
from backend.app.modules.risk_limits.breach_classification.services.breach_classification_service import (
    BreachClassificationService,
)
from backend.app.modules.risk_limits.breach_classification.schemas.breach_classification_schemas import (
    ClassificationPolicyCreate,
    ClassificationPolicyResponse,
    ClassificationPolicyVersionCreate,
    ClassificationPolicyVersionResponse,
    PolicyApprovalRequest,
    ClassifyBreachRequest,
    BatchClassifyRequest,
    ReclassificationRequest,
    BreachClassificationResponse,
    ClassificationOverviewResponse,
    ClassificationHistoryResponse,
    ClassificationAuditEventResponse,
)

router = APIRouter(prefix="/api/v1/breach-classification", tags=["Risk Limits - Breach Classification"])


def get_service(db: AsyncSession = Depends(get_db)) -> BreachClassificationService:
    repo = BreachClassificationRepository(db)
    return BreachClassificationService(repo)


# -------------------------------------------------------------
# Health Check
# -------------------------------------------------------------

@router.get("/health", summary="Breach Classification Engine Health Check")
async def health_check():
    return {
        "module": "M11.07 — Breach Classification",
        "status": "healthy",
        "features": [
            "Configurable Classification Policies",
            "WARNING / CRITICAL / EMERGENCY Classification",
            "Portfolio Materiality Assessment",
            "Deterministic Severity Precedence",
            "Governed Reclassification & Downstream Events",
        ],
    }


# -------------------------------------------------------------
# Policy Management Endpoints
# -------------------------------------------------------------

@router.post("/policies", response_model=ClassificationPolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(data: ClassificationPolicyCreate, service: BreachClassificationService = Depends(get_service)):
    try:
        return await service.create_policy(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/policies", response_model=List[ClassificationPolicyResponse])
async def list_policies(
    status_filter: Optional[str] = Query(None, alias="status"),
    service: BreachClassificationService = Depends(get_service),
):
    return await service.repo.list_policies(status=status_filter)


@router.get("/policies/{policy_id}", response_model=ClassificationPolicyResponse)
async def get_policy(policy_id: str, service: BreachClassificationService = Depends(get_service)):
    policy = await service.repo.get_policy_by_id(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_id}' not found.")
    return policy


@router.post("/policies/{policy_id}/versions", response_model=ClassificationPolicyVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_policy_version(
    policy_id: str,
    data: ClassificationPolicyVersionCreate,
    author: str = Query("risk_analyst"),
    service: BreachClassificationService = Depends(get_service),
):
    try:
        return await service.create_policy_version(policy_id, data, author=author)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/policies/{policy_id}/versions/{version_id}/approve", response_model=ClassificationPolicyVersionResponse)
async def approve_policy_version(
    policy_id: str,
    version_id: str,
    approval: PolicyApprovalRequest,
    service: BreachClassificationService = Depends(get_service),
):
    try:
        return await service.approve_policy_version(policy_id, version_id, approval)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------------------------------------------------------------
# Classification Operations Endpoints
# -------------------------------------------------------------

@router.post("/classify", response_model=BreachClassificationResponse, status_code=status.HTTP_201_CREATED)
async def classify_breach(req: ClassifyBreachRequest, service: BreachClassificationService = Depends(get_service)):
    try:
        return await service.classify_breach(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/classify/batch", response_model=List[BreachClassificationResponse])
async def classify_batch(req: BatchClassifyRequest, service: BreachClassificationService = Depends(get_service)):
    results = []
    for item in req.items:
        try:
            res = await service.classify_breach(item)
            results.append(res)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    return results


@router.get("/classifications", response_model=List[BreachClassificationResponse])
async def list_classifications(
    portfolio_id: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    service: BreachClassificationService = Depends(get_service),
):
    return await service.repo.list_classifications(portfolio_id=portfolio_id, severity=severity, limit=limit)


@router.get("/classifications/{classification_id}", response_model=BreachClassificationResponse)
async def get_classification(classification_id: str, service: BreachClassificationService = Depends(get_service)):
    record = await service.repo.get_classification_by_id(classification_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Classification '{classification_id}' not found.")
    return record


# -------------------------------------------------------------
# Reclassification Workflow Endpoints
# -------------------------------------------------------------

@router.post("/classifications/{classification_id}/reclassify", response_model=BreachClassificationResponse)
async def reclassify(
    classification_id: str,
    req: ReclassificationRequest,
    service: BreachClassificationService = Depends(get_service),
):
    try:
        return await service.reclassify(classification_id, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/reclassification-history", response_model=List[ClassificationHistoryResponse])
async def list_reclassification_history(
    classification_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    service: BreachClassificationService = Depends(get_service),
):
    return await service.repo.list_history(classification_id=classification_id, limit=limit)


# -------------------------------------------------------------
# Monitoring & Audit Endpoints
# -------------------------------------------------------------

@router.get("/monitoring/overview", response_model=ClassificationOverviewResponse)
async def get_overview(service: BreachClassificationService = Depends(get_service)):
    return await service.repo.get_overview_statistics()


@router.get("/audit", response_model=List[ClassificationAuditEventResponse])
async def list_audit_events(
    entity_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    service: BreachClassificationService = Depends(get_service),
):
    return await service.repo.list_audit_events(entity_id=entity_id, limit=limit)
