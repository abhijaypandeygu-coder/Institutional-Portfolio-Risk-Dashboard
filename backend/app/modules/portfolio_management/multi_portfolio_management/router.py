"""
M05.08 Multi-Portfolio Management Router.
FastAPI endpoints for group creation, lifecycle, membership management, hierarchy,
cross-portfolio consolidation runs, holdings, gross/net exposures, cash, and comparisons.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.portfolio_management.multi_portfolio_management.models import GroupStatus
from backend.app.modules.portfolio_management.multi_portfolio_management.schemas import (
    PortfolioGroupCreateRequest,
    PortfolioGroupUpdateRequest,
    PortfolioGroupResponse,
    PortfolioGroupMembershipAddRequest,
    PortfolioGroupMembershipResponse,
    PortfolioGroupMembershipEventResponse,
    PortfolioGroupPolicyCreateRequest,
    PortfolioGroupPolicyResponse,
    PortfolioGroupOverrideCreateRequest,
    PortfolioGroupOverrideResponse,
    ResolvedGroupSettingResponse,
    ConsolidationRunExecuteRequest,
    ConsolidationRunResponse,
    GroupExposureSummaryResponse,
    PortfolioGroupSnapshotResponse,
    GroupComparisonResponse,
)
from backend.app.modules.portfolio_management.multi_portfolio_management.services.service import (
    MultiPortfolioService,
)

router = APIRouter(
    prefix="/api/v1/portfolio-groups",
    tags=["Multi-Portfolio Management (M05.08)"],
)


# ==========================================
# Group CRUD & Lifecycle
# ==========================================

@router.post("", response_model=PortfolioGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    request: PortfolioGroupCreateRequest,
    session: AsyncSession = Depends(get_db),
):
    service = MultiPortfolioService(session)
    try:
        return await service.create_group(request)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=List[PortfolioGroupResponse])
async def list_groups(
    group_type: Optional[str] = None,
    status: Optional[str] = None,
    owner_reference: Optional[str] = None,
    parent_group_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
):
    service = MultiPortfolioService(session)
    groups = await service.repo.list_groups(
        group_type=group_type,
        status=status,
        owner_reference=owner_reference,
        parent_group_id=parent_group_id,
        limit=limit,
    )
    return [PortfolioGroupResponse.model_validate(g) for g in groups]


@router.get("/{group_id}", response_model=PortfolioGroupResponse)
async def get_group(
    group_id: str,
    session: AsyncSession = Depends(get_db),
):
    service = MultiPortfolioService(session)
    group = await service.get_group(group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Group '{group_id}' not found")
    return group


@router.post("/{group_id}/activate", response_model=PortfolioGroupResponse)
async def activate_group(
    group_id: str,
    actor_id: str = "SYSTEM_ADMIN",
    session: AsyncSession = Depends(get_db),
):
    service = MultiPortfolioService(session)
    try:
        return await service.update_group_status(group_id, GroupStatus.ACTIVE, actor_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{group_id}/suspend", response_model=PortfolioGroupResponse)
async def suspend_group(
    group_id: str,
    actor_id: str = "SYSTEM_ADMIN",
    session: AsyncSession = Depends(get_db),
):
    service = MultiPortfolioService(session)
    try:
        return await service.update_group_status(group_id, GroupStatus.SUSPENDED, actor_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{group_id}/close", response_model=PortfolioGroupResponse)
async def close_group(
    group_id: str,
    actor_id: str = "SYSTEM_ADMIN",
    session: AsyncSession = Depends(get_db),
):
    service = MultiPortfolioService(session)
    try:
        return await service.update_group_status(group_id, GroupStatus.CLOSED, actor_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{group_id}/archive", response_model=PortfolioGroupResponse)
async def archive_group(
    group_id: str,
    actor_id: str = "SYSTEM_ADMIN",
    session: AsyncSession = Depends(get_db),
):
    service = MultiPortfolioService(session)
    try:
        return await service.update_group_status(group_id, GroupStatus.ARCHIVED, actor_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ==========================================
# Membership Endpoints
# ==========================================

@router.post("/{group_id}/members", response_model=PortfolioGroupMembershipResponse, status_code=status.HTTP_201_CREATED)
async def add_portfolio_to_group(
    group_id: str,
    request: PortfolioGroupMembershipAddRequest,
    actor_id: str = "SYSTEM_ADMIN",
    session: AsyncSession = Depends(get_db),
):
    service = MultiPortfolioService(session)
    try:
        return await service.add_portfolio_to_group(group_id, request, actor_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{group_id}/members", response_model=List[PortfolioGroupMembershipResponse])
async def list_group_members(
    group_id: str,
    include_historical: bool = False,
    session: AsyncSession = Depends(get_db),
):
    service = MultiPortfolioService(session)
    mems = await service.repo.list_group_memberships(group_id, include_historical=include_historical)
    return [PortfolioGroupMembershipResponse.model_validate(m) for m in mems]


@router.post("/{group_id}/members/{portfolio_id}/remove", response_model=PortfolioGroupMembershipResponse)
async def remove_portfolio_from_group(
    group_id: str,
    portfolio_id: str,
    actor_id: str = "SYSTEM_ADMIN",
    session: AsyncSession = Depends(get_db),
):
    service = MultiPortfolioService(session)
    try:
        return await service.remove_portfolio_from_group(group_id, portfolio_id, actor_id=actor_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{group_id}/membership-history", response_model=List[PortfolioGroupMembershipEventResponse])
async def get_membership_history(
    group_id: str,
    session: AsyncSession = Depends(get_db),
):
    service = MultiPortfolioService(session)
    events = await service.repo.get_membership_history(group_id)
    return [PortfolioGroupMembershipEventResponse.model_validate(e) for e in events]


# ==========================================
# Shared Settings & Inheritance
# ==========================================

@router.get("/{group_id}/resolved-settings", response_model=ResolvedGroupSettingResponse)
async def resolve_setting(
    group_id: str,
    setting_key: str = Query(..., description="e.g. REPORTING_CURRENCY, BENCHMARK, RISK_CONVENTION"),
    portfolio_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
):
    service = MultiPortfolioService(session)
    return await service.resolve_setting(group_id, setting_key, portfolio_id)


# ==========================================
# Consolidation Runs & Exposures
# ==========================================

@router.post("/{group_id}/consolidations/run", response_model=ConsolidationRunResponse, status_code=status.HTTP_201_CREATED)
async def execute_consolidation(
    group_id: str,
    request: ConsolidationRunExecuteRequest,
    session: AsyncSession = Depends(get_db),
):
    service = MultiPortfolioService(session)
    try:
        return await service.execute_consolidation(group_id, request)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{group_id}/exposures", response_model=GroupExposureSummaryResponse)
async def get_group_exposure(
    group_id: str,
    session: AsyncSession = Depends(get_db),
):
    service = MultiPortfolioService(session)
    return await service.get_group_exposure(group_id)


@router.post("/compare", response_model=GroupComparisonResponse)
async def compare_groups(
    group_id_1: str = Query(...),
    group_id_2: str = Query(...),
    session: AsyncSession = Depends(get_db),
):
    service = MultiPortfolioService(session)
    return await service.compare_groups(group_id_1, group_id_2)


@router.get("/{group_id}/snapshots", response_model=List[PortfolioGroupSnapshotResponse])
async def list_snapshots(
    group_id: str,
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
):
    service = MultiPortfolioService(session)
    snaps = await service.repo.list_snapshots(group_id, limit=limit)
    return [PortfolioGroupSnapshotResponse.model_validate(s) for s in snaps]

