"""
FastAPI router for M11.05 — Dynamic Limits.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.risk_limits.dynamic_limits.repositories.dynamic_limit_repository import DynamicLimitRepository
from backend.app.modules.risk_limits.dynamic_limits.services.dynamic_limit_service import DynamicLimitService
from backend.app.modules.risk_limits.dynamic_limits.schemas.dynamic_limit_schemas import (
    PolicyCreate,
    PolicyResponse,
    PolicyVersionCreate,
    PolicyVersionResponse,
    PolicyApprovalRequest,
    OverrideCreate,
    OverrideResponse,
    OverrideApprovalRequest,
    OverrideRejectRequest,
    OverrideRevokeRequest,
    DynamicLimitEvaluationRequest,
    EffectiveLimitSnapshotResponse,
    DynamicLimitAuditEventResponse,
)

router = APIRouter(prefix="/api/v1/risk-limits/dynamic", tags=["Risk Limits - Dynamic Limits"])


def get_service(db: AsyncSession = Depends(get_db)) -> DynamicLimitService:
    repo = DynamicLimitRepository(db)
    return DynamicLimitService(repo)


# -------------------------------------------------------------
# Health Check
# -------------------------------------------------------------

@router.get("/health", summary="Dynamic Limits Engine Health Check")
async def health_check():
    return {
        "module": "M11.05 — Dynamic Limits",
        "status": "healthy",
        "features": [
            "Condition-Based Adjustments",
            "Session Time-Based Profiles",
            "Maker-Checker Manual Overrides",
            "Immutable Effective Snapshots",
            "Conflict Resolution Precedence",
        ],
    }


# -------------------------------------------------------------
# Policy Management Endpoints
# -------------------------------------------------------------

@router.post("/policies", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(data: PolicyCreate, service: DynamicLimitService = Depends(get_service)):
    try:
        return await service.create_policy(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/policies", response_model=List[PolicyResponse])
async def list_policies(
    portfolio_id: Optional[str] = Query(None),
    market: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    service: DynamicLimitService = Depends(get_service),
):
    return await service.repo.list_policies(portfolio_id=portfolio_id, market=market, status=status_filter)


@router.get("/policies/{policy_id}", response_model=PolicyResponse)
async def get_policy(policy_id: str, service: DynamicLimitService = Depends(get_service)):
    pol = await service.repo.get_policy_by_id(policy_id)
    if not pol:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_id}' not found.")
    return pol


@router.post("/policies/{policy_id}/versions", response_model=PolicyVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_policy_version(
    policy_id: str, data: PolicyVersionCreate, service: DynamicLimitService = Depends(get_service)
):
    try:
        return await service.create_policy_version(policy_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/policies/{policy_id}/versions/{version_id}/approve", response_model=PolicyVersionResponse)
async def approve_policy_version(
    policy_id: str,
    version_id: str,
    approval: PolicyApprovalRequest,
    service: DynamicLimitService = Depends(get_service),
):
    try:
        return await service.approve_policy_version(policy_id, version_id, approval)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------------------------------------------------------------
# Maker-Checker Manual Overrides
# -------------------------------------------------------------

@router.post("/overrides", response_model=OverrideResponse, status_code=status.HTTP_201_CREATED)
async def request_override(data: OverrideCreate, service: DynamicLimitService = Depends(get_service)):
    try:
        return await service.request_override(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/overrides/{override_id}/approve", response_model=OverrideResponse)
async def approve_override(
    override_id: str, approval: OverrideApprovalRequest, service: DynamicLimitService = Depends(get_service)
):
    try:
        return await service.approve_override(override_id, approval)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/overrides/{override_id}/reject", response_model=OverrideResponse)
async def reject_override(
    override_id: str, rejection: OverrideRejectRequest, service: DynamicLimitService = Depends(get_service)
):
    try:
        return await service.reject_override(override_id, rejection)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/overrides/{override_id}/revoke", response_model=OverrideResponse)
async def revoke_override(
    override_id: str, revocation: OverrideRevokeRequest, service: DynamicLimitService = Depends(get_service)
):
    try:
        return await service.revoke_override(override_id, revocation)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------------------------------------------------------------
# Evaluation & Effective Limit Snapshots
# -------------------------------------------------------------

@router.post("/evaluate", response_model=List[EffectiveLimitSnapshotResponse])
async def evaluate_limits(
    req: DynamicLimitEvaluationRequest, service: DynamicLimitService = Depends(get_service)
):
    try:
        return await service.evaluate_limits(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/snapshots", response_model=List[EffectiveLimitSnapshotResponse])
async def list_snapshots(
    portfolio_id: Optional[str] = Query(None),
    target_limit_code: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    service: DynamicLimitService = Depends(get_service),
):
    return await service.repo.list_snapshots(portfolio_id=portfolio_id, target_limit_code=target_limit_code, limit=limit)


# -------------------------------------------------------------
# Audit Log
# -------------------------------------------------------------

@router.get("/audit", response_model=List[DynamicLimitAuditEventResponse])
async def list_audit_events(
    entity_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    service: DynamicLimitService = Depends(get_service),
):
    return await service.repo.list_audit_events(entity_id=entity_id, limit=limit)

