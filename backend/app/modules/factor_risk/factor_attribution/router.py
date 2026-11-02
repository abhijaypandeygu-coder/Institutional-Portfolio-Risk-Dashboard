"""
M08.04 Factor Attribution API Router.
Exposes endpoints for:
1. POST /api/v1/factor-attribution/configs - Create attribution configuration profile
2. GET  /api/v1/factor-attribution/configs - List attribution configurations
3. GET  /api/v1/factor-attribution/configs/{config_id} - Retrieve config detail
4. POST /api/v1/portfolios/{portfolio_id}/factor-attribution/returns - Execute return attribution
5. GET  /api/v1/portfolios/{portfolio_id}/factor-attribution/returns/history - Return attribution history
6. POST /api/v1/portfolios/{portfolio_id}/factor-attribution/risk - Execute risk attribution
7. GET  /api/v1/portfolios/{portfolio_id}/factor-attribution/risk/history - Risk attribution history
8. GET  /api/v1/factor-attribution/runs/{run_id} - Retrieve return or risk run detail
9. GET  /api/v1/factor-attribution/runs/{run_id}/reconciliation - Attribution reconciliation report
10. POST /api/v1/factor-attribution/compare - Compare attribution runs (Period/Portfolio)
"""
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.factor_risk.factor_attribution.services.service import (
    FactorAttributionService,
)
from backend.app.modules.factor_risk.factor_attribution.schemas import (
    CreateAttributionConfigRequest,
    AttributionConfigResponse,
    RunReturnAttributionRequest,
    ReturnAttributionRunResponse,
    RunRiskAttributionRequest,
    RiskAttributionRunResponse,
    AttributionReconciliationResponse,
    AttributionComparisonRequest,
    AttributionComparisonResponse,
)

router = APIRouter(prefix="", tags=["M08.04 - Factor Attribution"])


# ============================================================================
# 1. ATTRIBUTION CONFIGURATION
# ============================================================================

@router.post("/api/v1/factor-attribution/configs", response_model=AttributionConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_attribution_config(
    req: CreateAttributionConfigRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register an immutable factor attribution configuration profile."""
    service = FactorAttributionService(db)
    try:
        config = await service.create_attribution_config(req)
        return config
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/api/v1/factor-attribution/configs", response_model=List[AttributionConfigResponse])
async def list_attribution_configs(
    db: AsyncSession = Depends(get_db),
):
    """List all available factor attribution configurations."""
    service = FactorAttributionService(db)
    return await service.list_configs()


@router.get("/api/v1/factor-attribution/configs/{config_id}", response_model=AttributionConfigResponse)
async def get_attribution_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve factor attribution configuration by ID."""
    service = FactorAttributionService(db)
    config = await service.get_config(config_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Config {config_id} not found")
    return config


# ============================================================================
# 2. RETURN ATTRIBUTION
# ============================================================================

@router.post(
    "/api/v1/portfolios/{portfolio_id}/factor-attribution/returns",
    response_model=ReturnAttributionRunResponse,
)
async def run_portfolio_return_attribution(
    portfolio_id: str,
    req: RunReturnAttributionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Execute factor return attribution explaining realized portfolio returns
    via systematic factors, risk-free rate, alpha intercept, and model residual.
    """
    if req.portfolio_id != portfolio_id:
        req.portfolio_id = portfolio_id

    service = FactorAttributionService(db)
    try:
        run = await service.run_return_attribution(req)
        return run
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/api/v1/portfolios/{portfolio_id}/factor-attribution/returns/history",
    response_model=List[ReturnAttributionRunResponse],
)
async def list_portfolio_return_attribution_history(
    portfolio_id: str,
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve historical return attribution runs for a portfolio."""
    service = FactorAttributionService(db)
    return await service.repo.list_return_runs_for_portfolio(
        portfolio_id=portfolio_id, start_date=start_date, end_date=end_date
    )


# ============================================================================
# 3. RISK ATTRIBUTION
# ============================================================================

@router.post(
    "/api/v1/portfolios/{portfolio_id}/factor-attribution/risk",
    response_model=RiskAttributionRunResponse,
)
async def run_portfolio_risk_attribution(
    portfolio_id: str,
    req: RunRiskAttributionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Execute factor risk attribution decomposing portfolio variance and volatility
    into systematic factor Euler contributions, marginal risk, and residual risk.
    """
    if req.portfolio_id != portfolio_id:
        req.portfolio_id = portfolio_id

    service = FactorAttributionService(db)
    try:
        run = await service.run_risk_attribution(req)
        return run
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/api/v1/portfolios/{portfolio_id}/factor-attribution/risk/history",
    response_model=List[RiskAttributionRunResponse],
)
async def list_portfolio_risk_attribution_history(
    portfolio_id: str,
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve historical factor risk attribution runs for a portfolio."""
    service = FactorAttributionService(db)
    return await service.repo.list_risk_runs_for_portfolio(
        portfolio_id=portfolio_id, start_date=start_date, end_date=end_date
    )


# ============================================================================
# 4. RUN RETRIEVAL & RECONCILIATION
# ============================================================================

@router.get("/api/v1/factor-attribution/runs/{run_id}")
async def get_attribution_run_detail(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve return or risk attribution run detail with full components and provenance."""
    service = FactorAttributionService(db)
    return_run = await service.repo.get_return_run_by_id(run_id)
    if return_run:
        return return_run
    risk_run = await service.repo.get_risk_run_by_id(run_id)
    if risk_run:
        return risk_run
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Attribution run {run_id} not found")


@router.get(
    "/api/v1/factor-attribution/runs/{run_id}/reconciliation",
    response_model=AttributionReconciliationResponse,
)
async def get_attribution_reconciliation_detail(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve formal return or risk attribution reconciliation bridge."""
    service = FactorAttributionService(db)
    recon = await service.repo.get_reconciliation_by_run_id(run_id)
    if not recon:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No reconciliation found for run {run_id}")
    return recon


# ============================================================================
# 5. ATTRIBUTION COMPARISON
# ============================================================================

@router.post(
    "/api/v1/factor-attribution/compare",
    response_model=AttributionComparisonResponse,
)
async def compare_attributions(
    req: AttributionComparisonRequest,
    db: AsyncSession = Depends(get_db),
):
    """Compare two attribution runs across periods or portfolios."""
    service = FactorAttributionService(db)
    try:
        return await service.compare_attributions(req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

