"""
M06.01 Gross Exposure Router.
FastAPI endpoints for portfolio and group gross exposure, details, ratios, and breakdowns.
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.risk_management.gross_exposure.schemas import (
    ExposureCalculationExecuteRequest,
    GrossExposureSummaryResponse,
    DenominatorType,
)
from backend.app.modules.risk_management.gross_exposure.services.service import (
    GrossExposureService,
)

router = APIRouter(
    tags=["Risk Management - Gross Exposure (M06.01)"],
)


@router.get("/api/v1/portfolios/{portfolio_id}/risk/gross-exposure", response_model=GrossExposureSummaryResponse)
async def get_portfolio_gross_exposure(
    portfolio_id: str,
    as_of: Optional[datetime] = None,
    reporting_currency: Optional[str] = None,
    denominator_type: DenominatorType = DenominatorType.NAV,
    custom_denominator_value: Optional[float] = None,
    session: AsyncSession = Depends(get_db),
):
    service = GrossExposureService(session)
    req = ExposureCalculationExecuteRequest(
        as_of=as_of,
        reporting_currency=reporting_currency,
        denominator_type=denominator_type,
        custom_denominator_value=custom_denominator_value,
    )
    return await service.calculate_portfolio_exposure(portfolio_id, req)


@router.post("/api/v1/portfolios/{portfolio_id}/risk/gross-exposure/calculate", response_model=GrossExposureSummaryResponse, status_code=status.HTTP_201_CREATED)
async def calculate_portfolio_gross_exposure(
    portfolio_id: str,
    request: ExposureCalculationExecuteRequest,
    session: AsyncSession = Depends(get_db),
):
    service = GrossExposureService(session)
    return await service.calculate_portfolio_exposure(portfolio_id, request)


@router.get("/api/v1/portfolio-groups/{group_id}/risk/gross-exposure", response_model=GrossExposureSummaryResponse)
async def get_group_gross_exposure(
    group_id: str,
    as_of: Optional[datetime] = None,
    reporting_currency: Optional[str] = None,
    denominator_type: DenominatorType = DenominatorType.NAV,
    custom_denominator_value: Optional[float] = None,
    session: AsyncSession = Depends(get_db),
):
    service = GrossExposureService(session)
    req = ExposureCalculationExecuteRequest(
        as_of=as_of,
        reporting_currency=reporting_currency,
        denominator_type=denominator_type,
        custom_denominator_value=custom_denominator_value,
    )
    try:
        return await service.calculate_group_exposure(group_id, req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

