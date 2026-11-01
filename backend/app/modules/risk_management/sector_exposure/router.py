"""
M06.03 Sector Exposure FastAPI Router.
Endpoints for calculating, querying, and analyzing sector and industry exposure,
coverage, unclassified holdings, and benchmark-relative active weights.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.risk_management.sector_exposure.models import (
    SectorWeightBasis,
    BenchmarkSectorComposition,
)
from backend.app.modules.risk_management.sector_exposure.schemas import (
    SectorExposureCalculateRequest,
    SectorExposureSummaryResponse,
    BenchmarkSectorCompositionCreateRequest,
    BenchmarkSectorCompositionResponse,
)
from backend.app.modules.risk_management.sector_exposure.services.service import (
    SectorExposureService,
)

router = APIRouter(
    tags=["Risk Management - Sector Exposure (M06.03)"],
)


@router.get("/api/v1/portfolios/{portfolio_id}/risk/sector-exposure", response_model=SectorExposureSummaryResponse)
async def get_portfolio_sector_exposure(
    portfolio_id: str,
    as_of: Optional[datetime] = None,
    reporting_currency: Optional[str] = None,
    weight_basis: SectorWeightBasis = SectorWeightBasis.NAV,
    custom_denominator_value: Optional[Decimal] = None,
    classification_scheme_code: Optional[str] = "GICS",
    benchmark_id: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
):
    service = SectorExposureService(session)
    req = SectorExposureCalculateRequest(
        as_of=as_of,
        reporting_currency=reporting_currency,
        weight_basis=weight_basis,
        custom_denominator_value=custom_denominator_value,
        classification_scheme_code=classification_scheme_code,
        benchmark_id=benchmark_id,
    )
    return await service.calculate_portfolio_sector_exposure(portfolio_id, req)


@router.post(
    "/api/v1/portfolios/{portfolio_id}/risk/sector-exposure/calculate",
    response_model=SectorExposureSummaryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def calculate_portfolio_sector_exposure_endpoint(
    portfolio_id: str,
    request: SectorExposureCalculateRequest,
    session: AsyncSession = Depends(get_db),
):
    service = SectorExposureService(session)
    return await service.calculate_portfolio_sector_exposure(portfolio_id, request)


@router.get("/api/v1/portfolio-groups/{group_id}/risk/sector-exposure", response_model=SectorExposureSummaryResponse)
async def get_group_sector_exposure(
    group_id: str,
    as_of: Optional[datetime] = None,
    reporting_currency: Optional[str] = None,
    weight_basis: SectorWeightBasis = SectorWeightBasis.NAV,
    custom_denominator_value: Optional[Decimal] = None,
    classification_scheme_code: Optional[str] = "GICS",
    benchmark_id: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
):
    service = SectorExposureService(session)
    req = SectorExposureCalculateRequest(
        as_of=as_of,
        reporting_currency=reporting_currency,
        weight_basis=weight_basis,
        custom_denominator_value=custom_denominator_value,
        classification_scheme_code=classification_scheme_code,
        benchmark_id=benchmark_id,
    )
    return await service.calculate_group_sector_exposure(group_id, req)


@router.post(
    "/api/v1/portfolio-groups/{group_id}/risk/sector-exposure/calculate",
    response_model=SectorExposureSummaryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def calculate_group_sector_exposure_endpoint(
    group_id: str,
    request: SectorExposureCalculateRequest,
    session: AsyncSession = Depends(get_db),
):
    service = SectorExposureService(session)
    return await service.calculate_group_sector_exposure(group_id, request)


@router.post(
    "/api/v1/benchmarks/{benchmark_id}/sectors",
    response_model=BenchmarkSectorCompositionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_benchmark_sector_composition(
    benchmark_id: str,
    payload: BenchmarkSectorCompositionCreateRequest,
    session: AsyncSession = Depends(get_db),
):
    service = SectorExposureService(session)
    import uuid
    comp = BenchmarkSectorComposition(
        id=f"BM-SEC-{uuid.uuid4().hex[:10].upper()}",
        benchmark_id=benchmark_id,
        benchmark_name=payload.benchmark_name,
        sector_id=payload.sector_id,
        sector_name=payload.sector_name,
        classification_scheme_code=payload.classification_scheme_code,
        benchmark_weight=payload.benchmark_weight,
        effective_date=payload.effective_date or datetime.utcnow(),
        source_reference=payload.source_reference or "AUTHORITATIVE_INDEX_PROVIDER",
    )
    saved = await service.repo.save_benchmark_composition(comp)
    return saved

