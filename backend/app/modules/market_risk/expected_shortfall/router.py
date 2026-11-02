"""
Module M07.03: Expected Shortfall FastAPI Routes.
Mounted at:
- `/api/v1/portfolios/{portfolio_id}/risk/expected-shortfall`
- `/api/v1/portfolio-groups/{group_id}/risk/expected-shortfall`
- `/api/v1/risk/expected-shortfall`
"""
from datetime import date
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.market_risk.expected_shortfall.models import (
    ESMethodology,
    ESQuantileMethod,
    ESTailWeightingMethod,
)
from backend.app.modules.market_risk.expected_shortfall.schemas import (
    ESConfigCreateRequest,
    ESConfigResponse,
    ESCalculateRequest,
    ExpectedShortfallResultResponse,
    ESTailObservationResponse,
    ESContributionResponse,
    ESDiagnosticResponse,
    ESConfidenceComparisonResponse,
    ESMethodologyComparisonResponse,
    ESHistoricalTrendResponse,
)
from backend.app.modules.market_risk.expected_shortfall.services.service import ExpectedShortfallService

router = APIRouter(prefix="/api/v1/portfolios/{portfolio_id}/risk/expected-shortfall", tags=["M07.03 - Expected Shortfall"])
group_router = APIRouter(prefix="/api/v1/portfolio-groups/{group_id}/risk/expected-shortfall", tags=["M07.03 - Expected Shortfall Groups"])
config_router = APIRouter(prefix="/api/v1/risk/expected-shortfall", tags=["M07.03 - Expected Shortfall Global"])


@router.post("/calculate", response_model=ExpectedShortfallResultResponse)
async def calculate_expected_shortfall(
    portfolio_id: str = Path(...),
    req: ESCalculateRequest = ...,
    db: AsyncSession = Depends(get_db),
):
    """
    Calculate Expected Shortfall (CVaR) for a portfolio under Historical Portfolio Returns,
    Historical Simulation, or Monte Carlo methodologies with exact fractional tail weighting.
    """
    req.portfolio_id = portfolio_id
    svc = ExpectedShortfallService(db)
    return await svc.calculate_expected_shortfall(req)


@router.get("/summary", response_model=ExpectedShortfallResultResponse)
async def get_expected_shortfall_summary(
    portfolio_id: str = Path(...),
    methodology: ESMethodology = Query(default=ESMethodology.HISTORICAL_PORTFOLIO_RETURNS),
    confidence_level: Decimal = Query(default=Decimal("0.9750")),
    holding_horizon_days: int = Query(default=1),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve or compute the Expected Shortfall summary, VaR comparison, and tail metrics.
    """
    svc = ExpectedShortfallService(db)
    req = ESCalculateRequest(
        portfolio_id=portfolio_id,
        methodology=methodology,
        confidence_level=confidence_level,
        holding_horizon_days=holding_horizon_days,
    )
    return await svc.calculate_expected_shortfall(req)


@router.get("/confidence-comparison", response_model=ESConfidenceComparisonResponse)
async def compare_confidence_levels(
    portfolio_id: str = Path(...),
    methodology: ESMethodology = Query(default=ESMethodology.HISTORICAL_PORTFOLIO_RETURNS),
    holding_horizon_days: int = Query(default=1),
    as_of: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Evaluate Expected Shortfall sensitivity across confidence levels (90%, 95%, 97.5%, 99%, 99.5%).
    """
    svc = ExpectedShortfallService(db)
    return await svc.compare_confidence_levels(
        portfolio_id=portfolio_id,
        methodology=methodology,
        holding_horizon_days=holding_horizon_days,
        as_of=as_of,
    )


@router.get("/methodology-comparison", response_model=ESMethodologyComparisonResponse)
async def compare_methodologies(
    portfolio_id: str = Path(...),
    confidence_level: Decimal = Query(default=Decimal("0.9750")),
    holding_horizon_days: int = Query(default=1),
    as_of: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Side-by-side comparison of Historical Portfolio Returns, Historical Simulation, and Monte Carlo ES.
    """
    svc = ExpectedShortfallService(db)
    return await svc.compare_methodologies(
        portfolio_id=portfolio_id,
        confidence_level=confidence_level,
        holding_horizon_days=holding_horizon_days,
        as_of=as_of,
    )


@router.get("/history", response_model=ESHistoricalTrendResponse)
async def get_historical_trend(
    portfolio_id: str = Path(...),
    methodology: Optional[str] = Query(default=None),
    lookback_points: int = Query(default=30),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve historical Expected Shortfall time series for trend monitoring.
    """
    svc = ExpectedShortfallService(db)
    return await svc.get_historical_trend(
        portfolio_id=portfolio_id, methodology=methodology, lookback_points=lookback_points
    )


@router.get("/{result_id}/tail-scenarios", response_model=List[ESTailObservationResponse])
async def get_tail_scenarios(
    portfolio_id: str = Path(...),
    result_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Drill down into individual scenarios in the adverse tail with fractional weights.
    """
    svc = ExpectedShortfallService(db)
    obs = await svc.repo.get_tail_observations(result_id=result_id)
    return [ESTailObservationResponse.model_validate(o) for o in obs]


@router.get("/{result_id}/contributions", response_model=List[ESContributionResponse])
async def get_risk_contributions(
    portfolio_id: str = Path(...),
    result_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve constituent tail risk attributions for an Expected Shortfall calculation.
    """
    svc = ExpectedShortfallService(db)
    contribs = await svc.repo.get_contributions(result_id=result_id)
    return [ESContributionResponse.model_validate(c) for c in contribs]


@router.get("/{result_id}/tail-diagnostics", response_model=List[ESDiagnosticResponse])
async def get_tail_diagnostics(
    portfolio_id: str = Path(...),
    result_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve statistical diagnostics (sample size, effective mass, stability).
    """
    svc = ExpectedShortfallService(db)
    diags = await svc.repo.get_diagnostics(result_id=result_id)
    return [ESDiagnosticResponse.model_validate(d) for d in diags]


# Group Router
@group_router.post("/calculate", response_model=ExpectedShortfallResultResponse)
async def calculate_group_expected_shortfall(
    group_id: str = Path(...),
    req: ESCalculateRequest = ...,
    db: AsyncSession = Depends(get_db),
):
    """
    Consolidated Expected Shortfall calculation for a multi-portfolio group.
    """
    req.portfolio_id = group_id
    svc = ExpectedShortfallService(db)
    return await svc.calculate_expected_shortfall(req)


# Config Router
@config_router.post("/configs", response_model=ESConfigResponse)
async def create_es_config(
    req: ESConfigCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    svc = ExpectedShortfallService(db)
    return await svc.create_config(req)


@config_router.get("/configs", response_model=List[ESConfigResponse])
async def list_es_configs(
    portfolio_id: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    svc = ExpectedShortfallService(db)
    return await svc.list_configs(portfolio_id=portfolio_id)
