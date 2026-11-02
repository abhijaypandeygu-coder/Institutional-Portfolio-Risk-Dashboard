"""
M08.03 Factor Sensitivity API Router.
Exposes endpoints for:
1. POST /api/v1/factor-sensitivity/configs - Create sensitivity regression model configuration
2. GET /api/v1/factor-sensitivity/configs - List model configurations
3. GET /api/v1/factor-sensitivity/configs/{config_id} - Retrieve config detail
4. POST /api/v1/factor-sensitivity/estimate - Execute sensitivity estimation for instrument or portfolio
5. GET /api/v1/factor-sensitivity/runs/{run_id} - Retrieve run details with coefficients & diagnostics
6. GET /api/v1/factor-sensitivity/{target_type}/{target_id}/coefficients - Get historical coefficients
7. GET /api/v1/factor-sensitivity/{target_type}/{target_id}/stability - Evaluate coefficient stability
8. POST /api/v1/factor-sensitivity/stability/break-test - Run formal structural break test
9. GET /api/v1/portfolios/{portfolio_id}/factor-sensitivity/reconciliation - Reconcile direct regression vs. bottom-up exposure
"""
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.factor_risk.factor_sensitivity.models import TargetType
from backend.app.modules.factor_risk.factor_sensitivity.services.service import (
    FactorSensitivityService,
)
from backend.app.modules.factor_risk.factor_sensitivity.schemas import (
    CreateModelConfigRequest,
    ModelConfigResponse,
    RunSensitivityRequest,
    SensitivityRunResponse,
    SensitivityCoefficientResponse,
    SensitivityStabilityResponse,
    StructuralBreakTestResponse,
    RunBreakTestRequest,
    PortfolioSensitivityReconciliationResponse,
)

router = APIRouter(prefix="", tags=["M08.03 - Factor Sensitivity"])


# ============================================================================
# 1. MODEL CONFIGURATION
# ============================================================================

@router.post("/api/v1/factor-sensitivity/configs", response_model=ModelConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_sensitivity_config(
    req: CreateModelConfigRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register an immutable factor sensitivity regression configuration."""
    service = FactorSensitivityService(db)
    try:
        config = await service.create_model_config(req)
        return config
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/api/v1/factor-sensitivity/configs", response_model=List[ModelConfigResponse])
async def list_sensitivity_configs(
    db: AsyncSession = Depends(get_db),
):
    """List all available factor sensitivity model configurations."""
    service = FactorSensitivityService(db)
    return await service.list_configs()


@router.get("/api/v1/factor-sensitivity/configs/{config_id}", response_model=ModelConfigResponse)
async def get_sensitivity_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve factor sensitivity model configuration by ID."""
    service = FactorSensitivityService(db)
    config = await service.get_config(config_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Config {config_id} not found")
    return config


# ============================================================================
# 2. SENSITIVITY ESTIMATION
# ============================================================================

@router.post("/api/v1/factor-sensitivity/estimate", response_model=SensitivityRunResponse)
async def estimate_factor_sensitivity(
    req: RunSensitivityRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Execute multi-factor regression sensitivity estimation for an instrument or direct portfolio.
    Calculates factor betas, HC3 standard errors, t-statistics, p-values, FDR corrections, and model diagnostics.
    """
    service = FactorSensitivityService(db)
    try:
        run = await service.run_sensitivity_estimation(req)
        return run
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/api/v1/factor-sensitivity/runs/{run_id}", response_model=SensitivityRunResponse)
async def get_sensitivity_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve details of a sensitivity estimation run including coefficients and diagnostics."""
    service = FactorSensitivityService(db)
    run = await service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run {run_id} not found")
    return run


@router.get("/api/v1/factor-sensitivity/{target_type}/{target_id}/coefficients", response_model=List[SensitivityCoefficientResponse])
async def get_coefficient_history(
    target_type: TargetType,
    target_id: str,
    factor_code: Optional[str] = Query(None, description="Optional factor code filter"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve point-in-time factor sensitivity coefficients over an observation horizon."""
    service = FactorSensitivityService(db)
    coeffs = await service.repo.get_coefficients_history(
        target_type=target_type,
        target_id=target_id,
        factor_code=factor_code,
        start_date=start_date,
        end_date=end_date,
    )
    return coeffs


# ============================================================================
# 3. STABILITY & STRUCTURAL BREAKS
# ============================================================================

@router.get("/api/v1/factor-sensitivity/{target_type}/{target_id}/stability", response_model=Optional[SensitivityStabilityResponse])
async def get_or_compute_coefficient_stability(
    target_type: TargetType,
    target_id: str,
    factor_code: str = Query(..., description="Factor code to evaluate (e.g., MKT_RF, SMB, HML)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Compute rolling stability diagnostics, drift metrics, and volatility for a factor coefficient.
    """
    service = FactorSensitivityService(db)
    stability = await service.compute_target_stability(
        target_type=target_type,
        target_id=target_id,
        factor_code=factor_code,
    )
    if not stability:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Insufficient coefficient history to compute stability for {target_type} {target_id} factor {factor_code}",
        )
    return stability


@router.post("/api/v1/factor-sensitivity/stability/break-test", response_model=StructuralBreakTestResponse)
async def run_structural_break_test(
    req: RunBreakTestRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Execute formal structural break test (Chow F-test) around candidate split date.
    """
    service = FactorSensitivityService(db)
    try:
        test_res = await service.run_break_test(req)
        return test_res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============================================================================
# 4. DIRECT SENSITIVITY VS. WEIGHTED EXPOSURE RECONCILIATION
# ============================================================================

@router.get(
    "/api/v1/portfolios/{portfolio_id}/factor-sensitivity/reconciliation",
    response_model=PortfolioSensitivityReconciliationResponse,
)
async def reconcile_portfolio_factor_sensitivity(
    portfolio_id: str,
    as_of_date: Optional[date] = Query(None, description="Anchor date for reconciliation"),
    config_id: Optional[str] = Query(None, description="Model configuration ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Reconcile direct portfolio time-series regression sensitivity against
    bottom-up holdings-weighted factor exposure (from M08.02).
    """
    service = FactorSensitivityService(db)
    try:
        recon = await service.reconcile_portfolio_sensitivity(
            portfolio_id=portfolio_id,
            as_of_date=as_of_date,
            config_id=config_id,
        )
        return recon
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
