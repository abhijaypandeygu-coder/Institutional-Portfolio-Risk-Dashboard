"""
M06.05 Geographic Exposure - FastAPI Router.
Provides endpoints for calculating portfolio/group geographic exposures,
retrieving country/region exposure lists, unknown geography, and snapshot comparisons.
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.instrument_reference_data.geographic_classification.models import (
    GeographicAttributeType,
)
from backend.app.modules.risk_management.geographic_exposure.models import (
    GeographicLevel,
)
from backend.app.modules.risk_management.geographic_exposure.schemas import (
    GeographicExposureCalculateRequest,
    GeographicExposureSummaryResponse,
    CountryExposureItemResponse,
    RegionExposureItemResponse,
    UnknownGeographicItemResponse,
    GeographicComparisonResponse,
)
from backend.app.modules.risk_management.geographic_exposure.services.service import (
    GeographicExposureService,
)

router = APIRouter(tags=["M06.05 - Geographic Exposure"])


@router.post(
    "/portfolios/{portfolio_id}/risk/geographic-exposure/calculate",
    response_model=GeographicExposureSummaryResponse,
    summary="Calculate portfolio geographic exposure",
)
async def calculate_geographic_exposure(
    portfolio_id: str = Path(..., description="Target portfolio ID"),
    request: GeographicExposureCalculateRequest = None,
    db: AsyncSession = Depends(get_db),
):
    if request is None:
        request = GeographicExposureCalculateRequest(portfolio_id=portfolio_id)
    svc = GeographicExposureService(db)
    return await svc.calculate_portfolio_geographic_exposure(portfolio_id, request)


@router.post(
    "/portfolio-groups/{group_id}/risk/geographic-exposure/calculate",
    response_model=GeographicExposureSummaryResponse,
    summary="Calculate consolidated group geographic exposure",
)
async def calculate_group_geographic_exposure(
    group_id: str = Path(..., description="Target portfolio group ID"),
    request: GeographicExposureCalculateRequest = None,
    db: AsyncSession = Depends(get_db),
):
    if request is None:
        request = GeographicExposureCalculateRequest(portfolio_group_id=group_id)
    svc = GeographicExposureService(db)
    return await svc.calculate_group_geographic_exposure(group_id, request)


@router.get(
    "/portfolios/{portfolio_id}/risk/geographic-exposure/countries",
    response_model=List[CountryExposureItemResponse],
    summary="Get country-level geographic exposures",
)
async def get_country_exposures(
    portfolio_id: str = Path(..., description="Target portfolio ID"),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    svc = GeographicExposureService(db)
    run = await svc.repo.get_latest_run(portfolio_id)
    if not run:
        req = GeographicExposureCalculateRequest(portfolio_id=portfolio_id)
        summary = await svc.calculate_portfolio_geographic_exposure(portfolio_id, req)
        return summary.countries[:limit]

    results = await svc.repo.get_country_results(run.run_id)
    return [
        CountryExposureItemResponse(
            country_id=r.country_id,
            country_name=r.country_name,
            iso_alpha2=r.iso_alpha2,
            region_id=r.region_id,
            region_name=r.region_name,
            long_exposure=r.long_exposure,
            short_exposure=r.short_exposure,
            net_exposure=r.net_exposure,
            gross_exposure=r.gross_exposure,
            long_nav_weight=r.long_nav_weight,
            short_nav_weight=r.short_nav_weight,
            net_nav_weight=r.net_nav_weight,
            gross_nav_weight=r.gross_nav_weight,
            gross_contribution_weight=r.gross_contribution_weight,
            instrument_count=r.instrument_count,
            rank=r.rank,
        )
        for r in results[:limit]
    ]


@router.get(
    "/portfolios/{portfolio_id}/risk/geographic-exposure/regions",
    response_model=List[RegionExposureItemResponse],
    summary="Get regional geographic exposures",
)
async def get_region_exposures(
    portfolio_id: str = Path(..., description="Target portfolio ID"),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    svc = GeographicExposureService(db)
    run = await svc.repo.get_latest_run(portfolio_id)
    if not run:
        req = GeographicExposureCalculateRequest(portfolio_id=portfolio_id)
        summary = await svc.calculate_portfolio_geographic_exposure(portfolio_id, req)
        return summary.regions[:limit]

    results = await svc.repo.get_region_results(run.run_id)
    return [
        RegionExposureItemResponse(
            region_id=r.region_id,
            region_code=r.region_code,
            region_name=r.region_name,
            taxonomy_scheme_code=r.taxonomy_scheme_code,
            hierarchy_level=r.hierarchy_level,
            long_exposure=r.long_exposure,
            short_exposure=r.short_exposure,
            net_exposure=r.net_exposure,
            gross_exposure=r.gross_exposure,
            long_nav_weight=r.long_nav_weight,
            short_nav_weight=r.short_nav_weight,
            net_nav_weight=r.net_nav_weight,
            gross_nav_weight=r.gross_nav_weight,
            gross_contribution_weight=r.gross_contribution_weight,
            instrument_count=r.instrument_count,
            rank=r.rank,
        )
        for r in results[:limit]
    ]


@router.get(
    "/portfolios/{portfolio_id}/risk/geographic-exposure/unknown",
    response_model=List[UnknownGeographicItemResponse],
    summary="Get unmapped/unknown geographic holdings",
)
async def get_unknown_exposures(
    portfolio_id: str = Path(..., description="Target portfolio ID"),
    db: AsyncSession = Depends(get_db),
):
    svc = GeographicExposureService(db)
    run = await svc.repo.get_latest_run(portfolio_id)
    if not run:
        return []
    results = await svc.repo.get_unknown_results(run.run_id)
    return [
        UnknownGeographicItemResponse(
            instrument_id=r.instrument_id,
            reason_code=r.reason_code,
            unmapped_gross_exposure=r.unmapped_gross_exposure,
            unmapped_weight=r.unmapped_weight,
        )
        for r in results
    ]


@router.get(
    "/portfolios/{portfolio_id}/risk/geographic-exposure/comparison",
    response_model=GeographicComparisonResponse,
    summary="Compare geographic exposures across snapshots",
)
async def compare_geographic_exposures(
    portfolio_id: str = Path(..., description="Target portfolio ID"),
    current_snapshot_id: str = Query(..., description="Current snapshot ID"),
    prior_snapshot_id: str = Query(..., description="Prior snapshot ID"),
    level: GeographicLevel = Query(GeographicLevel.COUNTRY),
    db: AsyncSession = Depends(get_db),
):
    svc = GeographicExposureService(db)
    return await svc.compare_snapshots(portfolio_id, current_snapshot_id, prior_snapshot_id, level)
