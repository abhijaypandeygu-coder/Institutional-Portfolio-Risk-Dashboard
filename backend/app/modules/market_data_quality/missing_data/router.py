"""
Module 03.01: Missing Data Detection - FastAPI REST Router.
Provides REST endpoints for:
- Viewing and acknowledging missing data incidents
- Querying coverage windows
- Configuring expected observation policies
- Retrieving quality health summary
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import AuthenticatedUser, UserRole, require_role
from backend.app.modules.market_data_quality.missing_data.schemas import (
    CoverageWindowResponse,
    IncidentActionRequest,
    IncidentResponse,
    PolicyCreate,
    PolicyResponse,
    QualitySummaryResponse,
)
from backend.app.modules.market_data_quality.missing_data.service import MissingDataService

router = APIRouter(prefix="/quality/missing-data", tags=["Market Data Quality & Missing Data Detection"])


# ============================================================================
# Quality Summary & Incidents
# ============================================================================

@router.get(
    "/summary",
    response_model=QualitySummaryResponse,
    summary="Get aggregated missing data quality status",
)
async def get_quality_summary(
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    service = MissingDataService(db)
    return await service.get_summary()


@router.get(
    "/incidents",
    response_model=List[IncidentResponse],
    summary="List missing data incidents (sequence gaps, missing bars, stale books)",
)
async def list_incidents(
    instrument_id: Optional[str] = Query(default=None),
    issue_status: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    service = MissingDataService(db)
    return await service.list_incidents(
        instrument_id=instrument_id,
        issue_status=issue_status,
        limit=limit,
    )


@router.post(
    "/incidents/{incident_id}/resolve",
    response_model=IncidentResponse,
    summary="Acknowledge and mark a missing data incident as resolved",
)
async def resolve_incident(
    incident_id: UUID,
    payload: IncidentActionRequest,
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    service = MissingDataService(db)
    return await service.resolve_incident(incident_id, payload.reason)


# ============================================================================
# Coverage Windows
# ============================================================================

@router.get(
    "/coverage",
    response_model=List[CoverageWindowResponse],
    summary="List calculated data availability coverage windows",
)
async def list_coverage(
    instrument_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    service = MissingDataService(db)
    return await service.repo.list_coverage_windows(
        instrument_id=instrument_id,
        limit=limit,
    )


# ============================================================================
# Policies
# ============================================================================

@router.post(
    "/policies",
    response_model=PolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an expected observation policy",
)
async def create_policy(
    payload: PolicyCreate,
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    service = MissingDataService(db)
    return await service.create_policy(payload)


@router.get(
    "/policies",
    response_model=List[PolicyResponse],
    summary="List configured expected observation policies",
)
async def list_policies(
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    service = MissingDataService(db)
    return await service.list_policies()
