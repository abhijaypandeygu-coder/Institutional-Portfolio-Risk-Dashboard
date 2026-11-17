"""
FastAPI router for M13.01 — Portfolio Overview.
Endpoints:
- GET /api/v1/dashboard/portfolios/{portfolio_id}/overview
- GET /api/v1/dashboard/portfolios/{portfolio_id}/kpis
- GET /api/v1/dashboard/portfolios/{portfolio_id}/freshness
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.dashboard_visualization.portfolio_overview.services.portfolio_overview_service import (
    PortfolioOverviewService,
)
from backend.app.modules.dashboard_visualization.portfolio_overview.schemas.portfolio_overview_schemas import (
    PortfolioOverviewResponse,
    StandardMetricValue,
    DataFreshnessSummary,
)

router = APIRouter(prefix="/dashboard/portfolios", tags=["M13.01 Portfolio Overview"])


def get_service(session: AsyncSession = Depends(get_db)) -> PortfolioOverviewService:
    return PortfolioOverviewService(session)


@router.get("/{portfolio_id}/overview", response_model=PortfolioOverviewResponse)
async def get_portfolio_overview(
    portfolio_id: str,
    as_of: Optional[datetime] = Query(None),
    service: PortfolioOverviewService = Depends(get_service),
):
    """
    Returns the complete consolidated Portfolio Overview (NAV, P&L, Gross/Net Exposure, Freshness, and Trends).
    """
    try:
        return await service.get_portfolio_overview(portfolio_id=portfolio_id, as_of=as_of)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate overview: {str(e)}")


@router.get("/{portfolio_id}/kpis", response_model=List[StandardMetricValue])
async def get_portfolio_overview_kpis(
    portfolio_id: str,
    as_of: Optional[datetime] = Query(None),
    service: PortfolioOverviewService = Depends(get_service),
):
    """
    Returns the core summary table rows / KPI cards as standard metric contracts.
    """
    try:
        overview = await service.get_portfolio_overview(portfolio_id=portfolio_id, as_of=as_of)
        return overview.summary_table_rows
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{portfolio_id}/freshness", response_model=DataFreshnessSummary)
async def get_portfolio_freshness(
    portfolio_id: str,
    service: PortfolioOverviewService = Depends(get_service),
):
    """
    Returns the data freshness and valuation latency indicators.
    """
    try:
        overview = await service.get_portfolio_overview(portfolio_id=portfolio_id)
        return overview.freshness
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
