"""
FastAPI router for M13.03 — Exposure Dashboard.

Exposes REST endpoints under:
/api/v1/dashboard/portfolios/{portfolio_id}/exposure-dashboard
/api/v1/dashboard/portfolios/{portfolio_id}/exposure-dashboard/sectors
/api/v1/dashboard/portfolios/{portfolio_id}/exposure-dashboard/instruments
/api/v1/dashboard/portfolios/{portfolio_id}/exposure-dashboard/allocation
/api/v1/dashboard/portfolios/{portfolio_id}/exposure-dashboard/drilldown
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.dashboard_visualization.exposure_dashboard.schemas.exposure_dashboard_schemas import (
    ConsolidatedExposureDashboardResponse,
    SectorAllocationSummary,
    InstrumentAllocationSummary,
    PortfolioAllocationSummary,
    ExposureDrillDownResponse,
    PositionSideFilter,
    HierarchyLevel,
)
from backend.app.modules.dashboard_visualization.exposure_dashboard.services.exposure_dashboard_service import (
    ExposureDashboardService,
    SectorAllocationPresentationService,
    InstrumentAllocationPresentationService,
    PortfolioAllocationPresentationService,
    ExposureDrilldownService,
)

router = APIRouter(tags=["M13.03 — Exposure Dashboard"])


@router.get(
    "/{portfolio_id}/exposure-dashboard",
    response_model=ConsolidatedExposureDashboardResponse,
    summary="Consolidated Exposure Dashboard",
    description="Returns consolidated view of capital allocation, sector weights, ranked long/short holdings, and data quality notes.",
)
async def get_consolidated_exposure_dashboard(
    portfolio_id: str,
    position_side: PositionSideFilter = Query(PositionSideFilter.ALL, description="Filter: ALL, LONG, SHORT"),
    as_of: Optional[datetime] = Query(None, description="Valuation timestamp filter"),
    session: AsyncSession = Depends(get_db),
):
    service = ExposureDashboardService(session)
    try:
        return await service.get_consolidated_dashboard(
            portfolio_id=portfolio_id,
            side_filter=position_side,
            as_of_dt=as_of,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve exposure dashboard: {exc}")


@router.get(
    "/{portfolio_id}/exposure-dashboard/sectors",
    response_model=SectorAllocationSummary,
    summary="Sector Allocation Overview",
    description="Returns authoritative M06.03 sector exposures, NAV weights, long/short breakdowns, and instrument counts.",
)
async def get_sector_allocation(
    portfolio_id: str,
    as_of: Optional[datetime] = Query(None, description="Valuation timestamp"),
    session: AsyncSession = Depends(get_db),
):
    service = SectorAllocationPresentationService(session)
    try:
        return await service.get_sector_allocation(
            portfolio_id=portfolio_id,
            as_of_dt=as_of,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve sector allocation: {exc}")


@router.get(
    "/{portfolio_id}/exposure-dashboard/instruments",
    response_model=InstrumentAllocationSummary,
    summary="Ranked Instrument Holdings",
    description="Returns ranked instrument exposures with long vs. short separation, market prices, and NAV weights.",
)
async def get_instrument_allocation(
    portfolio_id: str,
    position_side: PositionSideFilter = Query(PositionSideFilter.ALL, description="Side filter: ALL, LONG, SHORT"),
    as_of: Optional[datetime] = Query(None, description="Valuation timestamp"),
    session: AsyncSession = Depends(get_db),
):
    service = InstrumentAllocationPresentationService(session)
    try:
        return await service.get_instrument_allocation(
            portfolio_id=portfolio_id,
            side_filter=position_side,
            as_of_dt=as_of,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve instrument allocation: {exc}")


@router.get(
    "/{portfolio_id}/exposure-dashboard/allocation",
    response_model=PortfolioAllocationSummary,
    summary="Portfolio Capital Allocation & Cash",
    description="Returns complete view of NAV distribution between positions, cash accounts, and reconciliation status.",
)
async def get_portfolio_allocation(
    portfolio_id: str,
    as_of: Optional[datetime] = Query(None, description="Valuation timestamp"),
    session: AsyncSession = Depends(get_db),
):
    service = PortfolioAllocationPresentationService(session)
    try:
        return await service.get_portfolio_allocation(
            portfolio_id=portfolio_id,
            as_of_dt=as_of,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve portfolio allocation: {exc}")


@router.get(
    "/{portfolio_id}/exposure-dashboard/drilldown",
    response_model=ExposureDrillDownResponse,
    summary="Hierarchical Exposure Drill-Down",
    description="Navigates hierarchically across Portfolio -> Sector -> Industry -> Security with breadcrumb trail.",
)
async def get_exposure_drilldown(
    portfolio_id: str,
    level: HierarchyLevel = Query(HierarchyLevel.PORTFOLIO, description="Level: PORTFOLIO, SECTOR, INDUSTRY, INSTRUMENT"),
    sector_id: Optional[str] = Query(None, description="Sector ID for SECTOR drill-down"),
    industry_id: Optional[str] = Query(None, description="Industry ID for INDUSTRY drill-down"),
    instrument_id: Optional[str] = Query(None, description="Instrument ID for INSTRUMENT drill-down"),
    as_of: Optional[datetime] = Query(None, description="Valuation timestamp"),
    session: AsyncSession = Depends(get_db),
):
    service = ExposureDrilldownService(session)
    try:
        return await service.drill_down(
            portfolio_id=portfolio_id,
            level=level,
            sector_id=sector_id,
            industry_id=industry_id,
            instrument_id=instrument_id,
            as_of_dt=as_of,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to drill down: {exc}")
