"""
FastAPI Router for M04.02 Security Classification.
Mounts endpoints under /api/v1/classifications.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, Path, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import get_current_user, require_role, UserRole, AuthenticatedUser
from backend.app.modules.instrument_reference_data.security_classification.schemas import (
    ClassificationSchemeCreate,
    ClassificationSchemeResponse,
    ClassificationNodeCreate,
    ClassificationNodeResponse,
    ClassificationAssignRequest,
    AssetCategoryAssignRequest,
    BulkClassificationLookupRequest,
    BulkClassificationLookupResponse,
    InstrumentClassificationDetail,
    ClassificationCoverageMetrics,
)
from backend.app.modules.instrument_reference_data.security_classification.services.service import (
    SecurityClassificationService,
)
from backend.app.modules.instrument_reference_data.security_classification.repositories.repository import (
    ClassificationRepository,
)

router = APIRouter(prefix="/classifications", tags=["M04.02 - Security Classification"])


# 1. Classification Scheme Endpoints
@router.post("/schemes", response_model=ClassificationSchemeResponse, status_code=status.HTTP_201_CREATED)
async def create_classification_scheme(
    req: ClassificationSchemeCreate,
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.ADMIN)),
):
    """Registers a new classification scheme (e.g. GICS, ICB, or Proprietary Internal)."""
    return await SecurityClassificationService.create_scheme(session, req, actor_id=user.username)


@router.get("/schemes", response_model=List[ClassificationSchemeResponse])
async def list_classification_schemes(
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """Lists registered classification schemes."""
    stmt = (await session.execute(ClassificationRepository.select(ClassificationRepository.models.ClassificationScheme))).scalars().all() if hasattr(ClassificationRepository, "select") else []
    from backend.app.modules.instrument_reference_data.security_classification.models import ClassificationScheme
    from sqlalchemy import select
    schemes = list((await session.execute(select(ClassificationScheme))).scalars().all())
    return schemes


# 2. Taxonomy Nodes (Sectors, Industries)
@router.post("/schemes/{scheme_code}/versions/{version_code}/nodes", response_model=ClassificationNodeResponse, status_code=status.HTTP_201_CREATED)
async def create_taxonomy_node(
    req: ClassificationNodeCreate,
    scheme_code: str = Path(...),
    version_code: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.ADMIN)),
):
    """Creates a Sector or Industry node, validating hierarchy relationships."""
    return await SecurityClassificationService.create_node(
        session, scheme_code, version_code, req, actor_id=user.username
    )


@router.get("/schemes/{scheme_code}/sectors", response_model=List[ClassificationNodeResponse])
async def list_scheme_sectors(
    scheme_code: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """Lists all active sectors for a scheme."""
    scheme = await ClassificationRepository.get_scheme_by_code(session, scheme_code)
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found.")
    return await ClassificationRepository.list_sectors(session, scheme.id)


@router.get("/sectors/{sector_node_id}/industries", response_model=List[ClassificationNodeResponse])
async def list_sector_industries(
    sector_node_id: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """Lists industries belonging to a parent sector."""
    return await ClassificationRepository.list_industries_for_sector(session, sector_node_id)


# 3. Instrument Classification Assignments
@router.post("/instruments/{instrument_id}/assignments", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def assign_instrument_classification(
    req: ClassificationAssignRequest,
    instrument_id: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """Assigns sector and industry classification with bitemporal history."""
    assignment = await SecurityClassificationService.assign_classification(
        session, instrument_id, req, actor_id=user.username
    )
    return {"status": "ASSIGNED", "assignment_id": assignment.assignment_id, "version": assignment.assignment_version}


@router.post("/instruments/{instrument_id}/asset-category", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def assign_instrument_asset_category(
    req: AssetCategoryAssignRequest,
    instrument_id: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """Assigns analytical asset category, validating M04.01 instrument type compatibility."""
    assignment = await SecurityClassificationService.assign_asset_category(
        session, instrument_id, req, actor_id=user.username
    )
    return {"status": "ASSIGNED", "assignment_id": assignment.assignment_id, "category_code": assignment.category_code}


@router.get("/instruments/{instrument_id}", response_model=Optional[InstrumentClassificationDetail])
async def get_instrument_classification(
    instrument_id: str = Path(...),
    scheme_code: Optional[str] = Query(None),
    as_of_valid_time: Optional[datetime] = Query(None),
    as_of_transaction_time: Optional[datetime] = Query(None),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """Retrieves point-in-time classification for an instrument."""
    return await SecurityClassificationService.lookup_instrument_classification(
        session, instrument_id, scheme_code, as_of_valid_time, as_of_transaction_time
    )


# 4. Bulk Lookups & Coverage Metrics (Portfolio & Risk Consumer Endpoints)
@router.post("/bulk-lookup", response_model=BulkClassificationLookupResponse)
async def bulk_lookup_classifications(
    req: BulkClassificationLookupRequest,
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """Bulk classification retrieval for portfolio concentration and risk analytics."""
    return await SecurityClassificationService.bulk_lookup(session, req)


@router.get("/metrics/coverage", response_model=ClassificationCoverageMetrics)
async def get_coverage_metrics(
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """Retrieves sector, industry, and asset-category coverage statistics across active instruments."""
    return await ClassificationRepository.get_coverage_metrics(session)
