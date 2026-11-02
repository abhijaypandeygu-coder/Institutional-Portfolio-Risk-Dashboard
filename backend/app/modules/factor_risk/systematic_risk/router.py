"""
FastAPI Router for M08.05 Systematic Risk Analytics.
Exposes endpoints for:
- Systematic risk configuration management
- Factor covariance estimation and diagnostics
- Instrument systematic risk calculation
- Portfolio systematic risk calculation (cross-security covariance)
- Factor shock scenario creation and simulation
- Holding-level and portfolio-level model coverage inspection
"""
from datetime import date
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.factor_risk.systematic_risk.models import (
    CovarianceMethod,
    SystematicTargetType,
)
from backend.app.modules.factor_risk.systematic_risk.schemas import (
    CreateRiskConfigRequest,
    FactorRiskConfigResponse,
    EstimateFactorCovarianceRequest,
    FactorCovarianceSnapshotResponse,
    RunInstrumentSystematicRiskRequest,
    InstrumentSystematicRiskResponse,
    RunPortfolioSystematicRiskRequest,
    PortfolioSystematicRiskResponse,
    CreateFactorScenarioRequest,
    FactorScenarioConfigResponse,
    RunFactorScenarioRequest,
    FactorScenarioRunResponse,
    PortfolioCoverageSummaryResponse,
)
from backend.app.modules.factor_risk.systematic_risk.services.service import SystematicRiskService

router = APIRouter(prefix="/api/v1/systematic-risk", tags=["M08.05 - Systematic Risk"])


# ============================================================================
# 1. RISK CONFIGURATIONS
# ============================================================================

@router.post("/configs", response_model=FactorRiskConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_risk_config(
    payload: CreateRiskConfigRequest, db: AsyncSession = Depends(get_db)
):
    """Register an immutable versioned systematic risk calculation configuration."""
    service = SystematicRiskService(db)
    return await service.create_risk_config(payload)


@router.get("/configs", response_model=List[FactorRiskConfigResponse])
async def list_risk_configs(db: AsyncSession = Depends(get_db)):
    """List all registered systematic risk configurations."""
    service = SystematicRiskService(db)
    return await service.list_configs()


@router.get("/configs/{config_id}", response_model=FactorRiskConfigResponse)
async def get_risk_config(config_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve systematic risk configuration details."""
    service = SystematicRiskService(db)
    cfg = await service.get_config(config_id)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Configuration '{config_id}' not found")
    return cfg


# ============================================================================
# 2. FACTOR COVARIANCE ESTIMATION & DIAGNOSTICS
# ============================================================================

@router.post("/covariance/estimate", response_model=FactorCovarianceSnapshotResponse, status_code=status.HTTP_200_OK)
async def estimate_factor_covariance(
    payload: EstimateFactorCovarianceRequest, db: AsyncSession = Depends(get_db)
):
    """Estimate or retrieve cached factor covariance matrix with PSD & condition number validation."""
    service = SystematicRiskService(db)
    try:
        return await service.get_or_create_factor_covariance(
            factor_model_version_id=payload.factor_model_version_id,
            as_of_date=payload.as_of_date,
            lookback_days=payload.lookback_days,
            covariance_method=payload.covariance_method,
            decay_factor=payload.decay_factor or 0.94,
            annualization_factor=payload.annualization_factor,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/covariance/{snapshot_id}", response_model=FactorCovarianceSnapshotResponse)
async def get_covariance_snapshot(snapshot_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve factor covariance matrix and diagnostics by snapshot ID."""
    service = SystematicRiskService(db)
    snap = await service.repo.get_covariance_snapshot_by_id(snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail=f"Covariance snapshot '{snapshot_id}' not found")
    return snap


# ============================================================================
# 3. INSTRUMENT & PORTFOLIO SYSTEMATIC RISK
# ============================================================================

@router.post("/instruments/calculate", response_model=InstrumentSystematicRiskResponse)
async def calculate_instrument_systematic_risk(
    payload: RunInstrumentSystematicRiskRequest, db: AsyncSession = Depends(get_db)
):
    """Calculate instrument common-factor variance and systematic volatility."""
    service = SystematicRiskService(db)
    try:
        return await service.calculate_instrument_systematic_risk(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/portfolios/calculate", response_model=PortfolioSystematicRiskResponse)
async def calculate_portfolio_systematic_risk(
    payload: RunPortfolioSystematicRiskRequest, db: AsyncSession = Depends(get_db)
):
    """Calculate portfolio common-factor variance, cross-security covariance, and coverage."""
    service = SystematicRiskService(db)
    try:
        return await service.calculate_portfolio_systematic_risk(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/runs/{run_id}")
async def get_systematic_risk_run(run_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve execution header and details for a systematic risk run."""
    service = SystematicRiskService(db)
    run = await service.repo.get_run_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Risk run '{run_id}' not found")

    if run.target_type == SystematicTargetType.PORTFOLIO:
        detail = await service.repo.get_portfolio_risk_by_run_id(run_id)
    else:
        detail = await service.repo.get_instrument_risk_by_run_id(run_id)
    return {"header": run, "detail": detail}


# ============================================================================
# 4. SCENARIO SENSITIVITY SHOCKS
# ============================================================================

@router.post("/scenarios", response_model=FactorScenarioConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_factor_scenario(
    payload: CreateFactorScenarioRequest, db: AsyncSession = Depends(get_db)
):
    """Define a versioned factor shock scenario."""
    service = SystematicRiskService(db)
    return await service.create_scenario_config(payload)


@router.get("/scenarios", response_model=List[FactorScenarioConfigResponse])
async def list_factor_scenarios(db: AsyncSession = Depends(get_db)):
    """List all registered factor shock scenarios."""
    service = SystematicRiskService(db)
    return await service.repo.list_scenario_configs()


@router.post("/scenarios/run", response_model=FactorScenarioRunResponse)
async def run_factor_scenario(
    payload: RunFactorScenarioRequest, db: AsyncSession = Depends(get_db)
):
    """Simulate return and dollar impact of factor shocks on a portfolio or instrument."""
    service = SystematicRiskService(db)
    try:
        run = await service.run_factor_scenario(payload)
        return await service.repo.get_scenario_run_by_id(run.run_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# 5. MODEL COVERAGE DIAGNOSTICS
# ============================================================================

@router.get("/portfolios/{portfolio_id}/coverage", response_model=PortfolioCoverageSummaryResponse)
async def get_portfolio_model_coverage(
    portfolio_id: str,
    as_of_date: date = Query(default=date.today),
    db: AsyncSession = Depends(get_db),
):
    """Inspect holding-level model coverage, absolute weights, and missing factor diagnostics."""
    service = SystematicRiskService(db)
    return await service.get_portfolio_coverage_summary(portfolio_id, as_of_date)

