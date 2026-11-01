"""
FastAPI Router for M06.07 Portfolio Allocation.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.risk_management.portfolio_allocation.models import (
    AllocationGroupingDimension,
    AllocationViewType,
)
from backend.app.modules.risk_management.portfolio_allocation.schemas import (
    PortfolioAllocationCalculateRequest,
    PortfolioAllocationSummaryResponse,
    PortfolioAllocationComponentItemResponse,
    PortfolioAllocationTargetCreateRequest,
    PortfolioAllocationTargetResponse,
    PortfolioAllocationDriftResponse,
    PortfolioAllocationCompareRequest,
    PortfolioAllocationComparisonResponse,
)
from backend.app.modules.risk_management.portfolio_allocation.services.service import (
    PortfolioAllocationService,
)

router = APIRouter(prefix="/risk/portfolio-allocation", tags=["M06.07 - Portfolio Allocation"])


@router.post("/calculate", response_model=PortfolioAllocationSummaryResponse, status_code=status.HTTP_200_OK)
async def calculate_portfolio_allocation(
    req: PortfolioAllocationCalculateRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Calculate portfolio capital allocation across securities, cash, sectors, and geographies with NAV reconciliation.
    """
    service = PortfolioAllocationService(session)
    return await service.calculate_portfolio_allocation(req)


@router.get("/results/{result_id}", response_model=PortfolioAllocationSummaryResponse, status_code=status.HTTP_200_OK)
async def get_allocation_result(
    result_id: str,
    session: AsyncSession = Depends(get_db),
):
    """
    Retrieve an existing allocation calculation run by result_id.
    """
    service = PortfolioAllocationService(session)
    res = await service.repo.get_result_by_id(result_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"Allocation result '{result_id}' not found.")
    resp = PortfolioAllocationSummaryResponse.model_validate(res)
    resp.invested_nav_weight = (res.net_security_market_value / res.nav_value) if res.nav_value > 0 else 0
    resp.cash_nav_weight = (res.cash_nav_value / res.nav_value) if res.nav_value > 0 else 0
    resp.gross_exposure_to_nav = (res.gross_security_exposure / res.nav_value) if res.nav_value > 0 else 0
    resp.components = [
        PortfolioAllocationComponentItemResponse.model_validate(c) for c in (res.components or [])
    ]
    return resp


@router.post("/targets", response_model=PortfolioAllocationTargetResponse, status_code=status.HTTP_201_CREATED)
async def create_allocation_target(
    req: PortfolioAllocationTargetCreateRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Configure an effective-dated target weight for an entity/dimension.
    """
    service = PortfolioAllocationService(session)
    return await service.create_allocation_target(req)


@router.get("/drift", response_model=PortfolioAllocationDriftResponse, status_code=status.HTTP_200_OK)
async def get_allocation_drift(
    result_id: str = Query(..., description="Allocation calculation result ID"),
    session: AsyncSession = Depends(get_db),
):
    """
    Calculate allocation drift against active configured targets.
    """
    service = PortfolioAllocationService(session)
    try:
        return await service.calculate_allocation_drift(result_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/compare", response_model=PortfolioAllocationComparisonResponse, status_code=status.HTTP_200_OK)
async def compare_allocations(
    req: PortfolioAllocationCompareRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Compare two allocation runs (e.g. historical T vs T-1).
    """
    service = PortfolioAllocationService(session)
    try:
        return await service.compare_allocations(req.base_result_id, req.comparison_result_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
