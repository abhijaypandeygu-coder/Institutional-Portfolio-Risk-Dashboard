"""
M07.09 Risk Contribution API Router.
Endpoints:
- POST /api/v1/market-risk/risk-contribution/calculate
- GET  /api/v1/market-risk/risk-contribution/portfolio/{portfolio_id}
- GET  /api/v1/market-risk/risk-contribution/portfolio/{portfolio_id}/holdings
- GET  /api/v1/market-risk/risk-contribution/portfolio/{portfolio_id}/groups
- GET  /api/v1/market-risk/risk-contribution/reconciliation/{calculation_id}
- POST /api/v1/market-risk/risk-contribution/scenario
- GET  /api/v1/portfolios/{portfolio_id}/risk/contribution
"""
from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Path, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.market_risk.risk_contribution.models import (
    GroupingDimension,
    WeightBasis,
)
from backend.app.modules.market_risk.risk_contribution.schemas import (
    RiskContributionCalculateRequest,
    RiskContributionResponse,
    HoldingContributionItem,
    GroupContributionItem,
    GroupBreakdownResponse,
    ReconciliationDetails,
    ScenarioPerturbationRequest,
    ScenarioPerturbationResponse,
)
from backend.app.modules.market_risk.risk_contribution.services.service import (
    RiskContributionService,
)

router = APIRouter(prefix="/api/v1/market-risk/risk-contribution", tags=["Market Risk - Risk Contribution"])
portfolio_nested_router = APIRouter(prefix="/api/v1/portfolios", tags=["Portfolio Risk Attribution"])


@router.post("/calculate", response_model=RiskContributionResponse)
async def calculate_risk_contribution(
    request: RiskContributionCalculateRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Calculate and persist portfolio risk decomposition into marginal and component contributions.
    """
    service = RiskContributionService(session)
    return await service.calculate_risk_contribution(request)


@router.get("/portfolio/{portfolio_id}", response_model=RiskContributionResponse)
async def get_portfolio_risk_contribution(
    portfolio_id: str = Path(..., description="Portfolio identifier"),
    as_of: Optional[date] = Query(None, description="Observation as-of date"),
    session: AsyncSession = Depends(get_db),
):
    """
    Retrieve latest risk contribution decomposition for a portfolio.
    """
    service = RiskContributionService(session)
    return await service.get_latest_risk_contribution(portfolio_id, as_of=as_of)


@router.get("/portfolio/{portfolio_id}/holdings", response_model=List[HoldingContributionItem])
async def get_portfolio_holding_contributions(
    portfolio_id: str = Path(..., description="Portfolio identifier"),
    as_of: Optional[date] = Query(None, description="Observation as-of date"),
    session: AsyncSession = Depends(get_db),
):
    """
    Retrieve holding-level marginal and component risk contributions.
    """
    service = RiskContributionService(session)
    resp = await service.get_latest_risk_contribution(portfolio_id, as_of=as_of)
    return resp.holdings


@router.get("/portfolio/{portfolio_id}/groups", response_model=GroupBreakdownResponse)
async def get_portfolio_group_contributions(
    portfolio_id: str = Path(..., description="Portfolio identifier"),
    dimension: GroupingDimension = Query(GroupingDimension.SECTOR, description="Classification dimension"),
    as_of: Optional[date] = Query(None, description="Observation as-of date"),
    session: AsyncSession = Depends(get_db),
):
    """
    Retrieve group-level risk attribution across sectors, industries, geography, or strategy sleeves.
    """
    service = RiskContributionService(session)
    return await service.get_group_breakdown(portfolio_id, dimension=dimension, as_of=as_of)


@router.get("/reconciliation/{calculation_id}", response_model=ReconciliationDetails)
async def get_reconciliation_details(
    calculation_id: str = Path(..., description="Calculation identifier"),
    session: AsyncSession = Depends(get_db),
):
    """
    Retrieve Euler additivity reconciliation diagnostics for a specific calculation run.
    """
    service = RiskContributionService(session)
    run = await service.repo.get_calculation_run(calculation_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Calculation run {calculation_id} not found")

    return ReconciliationDetails(
        reconciliation_status=run.reconciliation_status,
        portfolio_variance=run.portfolio_variance,
        sum_component_variance=run.sum_component_variance,
        variance_residual=run.variance_residual,
        portfolio_volatility=run.portfolio_volatility,
        sum_component_volatility=run.sum_component_volatility,
        volatility_residual=run.volatility_residual,
        relative_residual=run.relative_residual,
        finite_difference_max_error=run.finite_difference_max_error,
    )


@router.post("/scenario", response_model=ScenarioPerturbationResponse)
async def evaluate_weight_perturbation_scenario(
    request: ScenarioPerturbationRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Evaluate what-if weight perturbation scenario comparing linear Taylor prediction to exact non-linear recalculation.
    """
    service = RiskContributionService(session)
    return await service.evaluate_scenario_perturbation(request)


# Nested portfolio endpoint
@portfolio_nested_router.get("/{portfolio_id}/risk/contribution", response_model=RiskContributionResponse)
async def get_nested_portfolio_risk_contribution(
    portfolio_id: str = Path(..., description="Portfolio identifier"),
    as_of: Optional[date] = Query(None, description="Observation as-of date"),
    session: AsyncSession = Depends(get_db),
):
    """
    Portfolio-scoped endpoint for complete risk contribution decomposition.
    """
    service = RiskContributionService(session)
    return await service.get_latest_risk_contribution(portfolio_id, as_of=as_of)
