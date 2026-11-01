"""
FastAPI Router for M06.06 Concentration Analytics.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.risk_management.concentration_analytics.models import (
    ConcentrationGroupingDimension,
    ConcentrationExposureBasis,
)
from backend.app.modules.risk_management.concentration_analytics.schemas import (
    ConcentrationCalculateRequest,
    ConcentrationSummaryResponse,
    ConcentrationContributorItemResponse,
    ConcentrationRatiosResponse,
    ConcentrationHHIResponse,
    ConcentrationCompareRequest,
    ConcentrationComparisonResponse,
    ConcentrationPolicyCreateRequest,
    ConcentrationPolicyResponse,
)
from backend.app.modules.risk_management.concentration_analytics.services.service import (
    ConcentrationAnalyticsService,
)

router = APIRouter(prefix="/risk/concentration", tags=["M06.06 - Concentration Analytics"])


@router.post("/calculate", response_model=ConcentrationSummaryResponse, status_code=status.HTTP_200_OK)
async def calculate_concentration(
    req: ConcentrationCalculateRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Calculate concentration ratios (CR1..CR20), HHI, and effective groups for a portfolio or group.
    """
    service = ConcentrationAnalyticsService(session)
    return await service.calculate_concentration(req)


@router.get("/results/{result_id}", response_model=ConcentrationSummaryResponse, status_code=status.HTTP_200_OK)
async def get_concentration_result(
    result_id: str,
    session: AsyncSession = Depends(get_db),
):
    """
    Retrieve an existing concentration calculation result by result_id.
    """
    service = ConcentrationAnalyticsService(session)
    res = await service.repo.get_result_by_id(result_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"Concentration result '{result_id}' not found.")
    policy = await service.repo.get_active_policy(
        portfolio_id=res.portfolio_id,
        portfolio_group_id=res.portfolio_group_id,
        grouping_dimension=res.grouping_dimension,
        exposure_basis=res.exposure_basis,
    )
    interp, flags = service._evaluate_policy(res, policy)
    resp = ConcentrationSummaryResponse.model_validate(res)
    resp.interpretation_level = interp
    resp.active_flags = flags
    resp.top_contributors = [
        ConcentrationContributorItemResponse.model_validate(c) for c in (res.contributors or [])[:20]
    ]
    return resp


@router.get("/ratios", response_model=ConcentrationRatiosResponse, status_code=status.HTTP_200_OK)
async def get_concentration_ratios(
    result_id: str = Query(..., description="Concentration calculation result ID"),
    session: AsyncSession = Depends(get_db),
):
    """
    Get concentration ratios (CR1, CR3, CR5, CR10, CR20) for a given run.
    """
    service = ConcentrationAnalyticsService(session)
    res = await service.repo.get_result_by_id(result_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"Concentration result '{result_id}' not found.")
    return ConcentrationRatiosResponse(
        result_id=res.result_id,
        grouping_dimension=res.grouping_dimension,
        exposure_basis=res.exposure_basis,
        ratios={
            "CR1": res.top_1_ratio,
            "CR3": res.top_3_ratio,
            "CR5": res.top_5_ratio,
            "CR10": res.top_10_ratio,
            "CR20": res.top_20_ratio,
        },
        eligible_group_count=res.eligible_group_count,
        calculation_status=res.calculation_status,
    )


@router.get("/hhi", response_model=ConcentrationHHIResponse, status_code=status.HTTP_200_OK)
async def get_concentration_hhi(
    result_id: str = Query(..., description="Concentration calculation result ID"),
    session: AsyncSession = Depends(get_db),
):
    """
    Get Herfindahl-Hirschman Index (decimal and 10,000-point scale) and effective number of groups.
    """
    service = ConcentrationAnalyticsService(session)
    res = await service.repo.get_result_by_id(result_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"Concentration result '{result_id}' not found.")
    scale_desc = "MODERATE"
    if res.hhi_10000 >= 2500:
        scale_desc = "HIGHLY_CONCENTRATED"
    elif res.hhi_10000 < 1500:
        scale_desc = "DIVERSIFIED"

    return ConcentrationHHIResponse(
        result_id=res.result_id,
        grouping_dimension=res.grouping_dimension,
        exposure_basis=res.exposure_basis,
        hhi_decimal=res.hhi_decimal,
        hhi_10000=res.hhi_10000,
        effective_number_of_groups=res.effective_number_of_groups,
        eligible_group_count=res.eligible_group_count,
        scale_interpretation=scale_desc,
        calculation_status=res.calculation_status,
    )


@router.post("/compare", response_model=ConcentrationComparisonResponse, status_code=status.HTTP_200_OK)
async def compare_concentrations(
    req: ConcentrationCompareRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Compare two concentration calculation results (e.g. historical T vs T-1).
    """
    service = ConcentrationAnalyticsService(session)
    try:
        return await service.compare_concentrations(req.base_result_id, req.comparison_result_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/policies", response_model=ConcentrationPolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_concentration_policy(
    req: ConcentrationPolicyCreateRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Create a configurable concentration threshold policy.
    """
    service = ConcentrationAnalyticsService(session)
    return await service.create_policy(req)
