"""
Module M07.02: Value at Risk API Router.
Mounted at /api/v1/portfolios and /api/v1/risk/var.
"""
from datetime import date
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.market_risk.value_at_risk.models import (
    VaRMethodology,
    VaRValuationBaseType,
    VaRDistributionAssumption,
    VaRQuantileMethod,
)
from backend.app.modules.market_risk.value_at_risk.schemas import (
    VaRModelConfigCreateRequest,
    VaRModelConfigResponse,
    VaRCalculateRequest,
    VaRResultResponse,
    VaRRiskContributionItem,
    VaRModelComparisonResponse,
    VaRHistoricalTrendResponse,
    VaRDiagnosticItemResponse,
)
from backend.app.modules.market_risk.value_at_risk.services.service import VaRService

router = APIRouter(
    prefix="/portfolios",
    tags=["M07.02 - Value at Risk (VaR)"],
)

config_router = APIRouter(
    prefix="/risk/var",
    tags=["M07.02 - VaR Model Governance & Configurations"],
)


# 1. Configuration & Governance
@config_router.post(
    "/configurations",
    response_model=VaRModelConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create VaR model configuration",
)
async def create_var_config(
    req: VaRModelConfigCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    svc = VaRService(db)
    cfg = await svc.create_config(req)
    return VaRModelConfigResponse.model_validate(cfg)


@config_router.get(
    "/configurations",
    response_model=List[VaRModelConfigResponse],
    summary="List VaR model configurations",
)
async def list_var_configs(
    portfolio_id: Optional[str] = Query(None, description="Filter by portfolio"),
    db: AsyncSession = Depends(get_db),
):
    svc = VaRService(db)
    items = await svc.repo.list_configs(portfolio_id=portfolio_id)
    return [VaRModelConfigResponse.model_validate(c) for c in items]


# 2. Portfolio VaR Execution Endpoints
@router.post(
    "/{portfolio_id}/risk/var/calculate",
    response_model=VaRResultResponse,
    summary="Calculate portfolio VaR across selected methodology",
)
async def calculate_portfolio_var(
    portfolio_id: str,
    req: VaRCalculateRequest,
    db: AsyncSession = Depends(get_db),
):
    req.portfolio_id = portfolio_id
    svc = VaRService(db)
    return await svc.calculate_var(req)


@router.post(
    "/{portfolio_id}/risk/var/historical",
    response_model=VaRResultResponse,
    summary="Calculate Historical VaR using empirical returns",
)
async def calculate_historical_var(
    portfolio_id: str,
    confidence_level: Decimal = Query(Decimal("0.9900"), description="Confidence level (e.g. 0.95, 0.99)"),
    holding_horizon_days: int = Query(1, description="Holding horizon in days"),
    lookback_period_days: int = Query(252, description="Lookback window in days"),
    quantile_method: VaRQuantileMethod = Query(VaRQuantileMethod.LINEAR_INTERPOLATION, description="Quantile method"),
    as_of: Optional[date] = Query(None, description="As-of date"),
    db: AsyncSession = Depends(get_db),
):
    req = VaRCalculateRequest(
        portfolio_id=portfolio_id,
        methodology=VaRMethodology.HISTORICAL,
        confidence_level=confidence_level,
        holding_horizon_days=holding_horizon_days,
        lookback_period_days=lookback_period_days,
        quantile_method=quantile_method,
        as_of=as_of,
    )
    svc = VaRService(db)
    return await svc.calculate_var(req)


@router.post(
    "/{portfolio_id}/risk/var/parametric",
    response_model=VaRResultResponse,
    summary="Calculate Parametric VaR with Euler component risk attribution",
)
async def calculate_parametric_var(
    portfolio_id: str,
    confidence_level: Decimal = Query(Decimal("0.9900"), description="Confidence level (e.g. 0.95, 0.99)"),
    holding_horizon_days: int = Query(1, description="Holding horizon in days"),
    distribution_assumption: VaRDistributionAssumption = Query(VaRDistributionAssumption.NORMAL, description="Distribution"),
    lookback_period_days: int = Query(252, description="Lookback window in days"),
    as_of: Optional[date] = Query(None, description="As-of date"),
    db: AsyncSession = Depends(get_db),
):
    req = VaRCalculateRequest(
        portfolio_id=portfolio_id,
        methodology=VaRMethodology.PARAMETRIC,
        confidence_level=confidence_level,
        holding_horizon_days=holding_horizon_days,
        distribution_assumption=distribution_assumption,
        lookback_period_days=lookback_period_days,
        as_of=as_of,
    )
    svc = VaRService(db)
    return await svc.calculate_var(req)


@router.post(
    "/{portfolio_id}/risk/var/monte-carlo",
    response_model=VaRResultResponse,
    summary="Calculate Monte Carlo VaR with Cholesky correlated simulation",
)
async def calculate_monte_carlo_var(
    portfolio_id: str,
    confidence_level: Decimal = Query(Decimal("0.9900"), description="Confidence level (e.g. 0.95, 0.99)"),
    holding_horizon_days: int = Query(1, description="Holding horizon in days"),
    simulation_count: int = Query(10000, description="Simulation count"),
    random_seed: Optional[int] = Query(42, description="Random seed for reproducibility"),
    as_of: Optional[date] = Query(None, description="As-of date"),
    db: AsyncSession = Depends(get_db),
):
    req = VaRCalculateRequest(
        portfolio_id=portfolio_id,
        methodology=VaRMethodology.MONTE_CARLO,
        confidence_level=confidence_level,
        holding_horizon_days=holding_horizon_days,
        simulation_count=simulation_count,
        random_seed=random_seed,
        as_of=as_of,
    )
    svc = VaRService(db)
    return await svc.calculate_var(req)


@router.get(
    "/{portfolio_id}/risk/var/summary",
    response_model=VaRResultResponse,
    summary="Get latest summary VaR result for a portfolio",
)
async def get_var_summary(
    portfolio_id: str,
    methodology: Optional[VaRMethodology] = Query(None, description="Filter methodology"),
    db: AsyncSession = Depends(get_db),
):
    svc = VaRService(db)
    res = await svc.repo.get_latest_var_result(portfolio_id=portfolio_id, methodology=methodology)
    if not res:
        # On-demand calculate default 99% 1-day Historical VaR
        req = VaRCalculateRequest(portfolio_id=portfolio_id)
        return await svc.calculate_var(req)

    contribs = await svc.repo.get_contributions_for_result(res.result_id)
    resp = VaRResultResponse.model_validate(res)
    if contribs:
        resp.contributions = [
            VaRRiskContributionItem(
                grouping_dimension=c.grouping_dimension,
                entity_id=c.entity_id,
                entity_name=c.entity_name,
                weight_percentage=c.weight_percentage,
                marginal_var=c.marginal_var,
                component_var_amount=c.component_var_amount,
                percentage_of_total_var=c.percentage_of_total_var,
                is_additive=c.is_additive,
            )
            for c in contribs
        ]
    return resp


@router.get(
    "/{portfolio_id}/risk/var/model-comparison",
    response_model=VaRModelComparisonResponse,
    summary="Compare Historical, Parametric, and Monte Carlo VaR side-by-side",
)
async def get_var_model_comparison(
    portfolio_id: str,
    confidence_level: Decimal = Query(Decimal("0.9900"), description="Confidence level"),
    holding_horizon_days: int = Query(1, description="Holding horizon in days"),
    as_of: Optional[date] = Query(None, description="As-of date"),
    db: AsyncSession = Depends(get_db),
):
    svc = VaRService(db)
    return await svc.compare_var_models(
        portfolio_id=portfolio_id,
        confidence_level=confidence_level,
        holding_horizon_days=holding_horizon_days,
        as_of=as_of,
    )


@router.get(
    "/{portfolio_id}/risk/var/history",
    response_model=VaRHistoricalTrendResponse,
    summary="Get historical VaR trend and period-over-period changes",
)
async def get_var_history(
    portfolio_id: str,
    methodology: VaRMethodology = Query(VaRMethodology.HISTORICAL, description="Methodology"),
    from_date: Optional[date] = Query(None, description="Start date"),
    to_date: Optional[date] = Query(None, description="End date"),
    db: AsyncSession = Depends(get_db),
):
    svc = VaRService(db)
    return await svc.get_var_history_trend(
        portfolio_id=portfolio_id,
        methodology=methodology,
        from_date=from_date,
        to_date=to_date,
    )


@router.get(
    "/{portfolio_id}/risk/var/contributions",
    response_model=List[VaRRiskContributionItem],
    summary="Get component risk contributions for a specific VaR result",
)
async def get_var_contributions(
    portfolio_id: str,
    result_id: str = Query(..., description="VaR Result ID"),
    db: AsyncSession = Depends(get_db),
):
    svc = VaRService(db)
    contribs = await svc.repo.get_contributions_for_result(result_id)
    return [
        VaRRiskContributionItem(
            grouping_dimension=c.grouping_dimension,
            entity_id=c.entity_id,
            entity_name=c.entity_name,
            weight_percentage=c.weight_percentage,
            marginal_var=c.marginal_var,
            component_var_amount=c.component_var_amount,
            percentage_of_total_var=c.percentage_of_total_var,
            is_additive=c.is_additive,
        )
        for c in contribs
    ]


@router.get(
    "/{portfolio_id}/risk/var/{result_id}/diagnostics",
    response_model=List[VaRDiagnosticItemResponse],
    summary="Get calculation diagnostics for a VaR result",
)
async def get_var_diagnostics(
    portfolio_id: str,
    result_id: str,
    db: AsyncSession = Depends(get_db),
):
    svc = VaRService(db)
    diags = await svc.repo.list_diagnostics(result_id=result_id, portfolio_id=portfolio_id)
    return [VaRDiagnosticItemResponse.model_validate(d) for d in diags]

