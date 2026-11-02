"""
FastAPI Router for M08.08 Factor Monitoring & Control.
Exposes REST endpoints for:
- Factor monitoring configuration profiles
- Factor exposure target profiles & components
- Factor threshold policy management
- Execution of factor monitoring pipeline
- Portfolio factor monitoring summaries, exposure drifts, and concentrations
- Breach lifecycle management (active query, acknowledgement)
- Factor monitoring history & trends
"""

from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.factor_risk.factor_monitoring.schemas import (
    FactorMonitoringConfigCreate,
    FactorMonitoringConfigResponse,
    FactorExposureTargetCreate,
    FactorExposureTargetResponse,
    FactorThresholdPolicyCreate,
    FactorThresholdPolicyResponse,
    FactorMonitoringRunRequest,
    FactorMonitoringRunResponse,
    FactorExposureDriftResponse,
    FactorConcentrationResponse,
    FactorMonitoringBreachResponse,
    BreachAcknowledgeRequest,
)
from backend.app.modules.factor_risk.factor_monitoring.services.service import FactorMonitoringService
from backend.app.modules.factor_risk.factor_monitoring.models import (
    BreachSeverity,
    BreachStatus,
)

router = APIRouter(prefix="/api/v1/factor-monitoring", tags=["M08.08 - Factor Monitoring"])
portfolio_router = APIRouter(prefix="/api/v1/portfolios/{portfolio_id}/factor-monitoring", tags=["M08.08 - Portfolio Factor Monitoring"])


# =============================================================================
# 1. Configuration & Target Profiles
# =============================================================================

@router.post("/configs", response_model=FactorMonitoringConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_monitoring_config(
    req: FactorMonitoringConfigCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a versioned factor monitoring profile."""
    svc = FactorMonitoringService(db)
    return await svc.create_monitoring_config(req)


@router.get("/configs", response_model=List[FactorMonitoringConfigResponse])
async def list_monitoring_configs(
    db: AsyncSession = Depends(get_db),
):
    """List registered factor monitoring configuration profiles."""
    svc = FactorMonitoringService(db)
    return await svc.repo.list_monitoring_configs()


@router.post("/targets", response_model=FactorExposureTargetResponse, status_code=status.HTTP_201_CREATED)
async def create_exposure_target(
    req: FactorExposureTargetCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create an approved factor exposure target profile."""
    svc = FactorMonitoringService(db)
    return await svc.create_exposure_target(req)


@router.get("/targets", response_model=List[FactorExposureTargetResponse])
async def list_exposure_targets(
    portfolio_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List factor exposure targets filtered by portfolio."""
    svc = FactorMonitoringService(db)
    return await svc.repo.list_exposure_targets(portfolio_id)


# =============================================================================
# 2. Threshold Policies
# =============================================================================

@router.post("/threshold-policies", response_model=FactorThresholdPolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_threshold_policy(
    req: FactorThresholdPolicyCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create an immutable threshold policy version."""
    svc = FactorMonitoringService(db)
    return await svc.create_threshold_policy(req)


@router.get("/threshold-policies", response_model=List[FactorThresholdPolicyResponse])
async def list_threshold_policies(
    db: AsyncSession = Depends(get_db),
):
    """List all configured threshold policies."""
    svc = FactorMonitoringService(db)
    return await svc.repo.list_all_threshold_policies()


# =============================================================================
# 3. Execution & Run Management
# =============================================================================

@portfolio_router.post("/run", response_model=FactorMonitoringRunResponse)
async def run_factor_monitoring(
    portfolio_id: str,
    req: FactorMonitoringRunRequest,
    db: AsyncSession = Depends(get_db),
):
    """Execute complete factor monitoring pipeline for a portfolio."""
    if req.portfolio_id != portfolio_id:
        raise HTTPException(status_code=400, detail="Portfolio ID in URL path does not match request body")
    svc = FactorMonitoringService(db)
    try:
        run = await svc.run_factor_monitoring(req)
        # Fetch concentration result to embed in response
        conc = await svc.repo.get_concentration_result_by_run_id(run.run_id)
        resp_dict = {
            "id": run.id,
            "run_id": run.run_id,
            "portfolio_id": run.portfolio_id,
            "factor_model_version_id": run.factor_model_version_id,
            "config_id": run.config_id,
            "target_id": run.target_id,
            "as_of_date": run.as_of_date,
            "status": run.status,
            "drift_status": run.drift_status,
            "concentration_status": run.concentration_status,
            "has_active_breaches": run.has_active_breaches,
            "active_breach_count": run.active_breach_count,
            "warning_count": run.warning_count,
            "critical_breach_count": run.critical_breach_count,
            "input_freshness": run.input_freshness,
            "result_hash": run.result_hash,
            "drifts": run.drifts,
            "concentration": conc,
            "evaluations": run.evaluations,
            "created_at": run.created_at,
        }
        return FactorMonitoringRunResponse.model_validate(resp_dict)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@portfolio_router.get("", response_model=Optional[FactorMonitoringRunResponse])
async def get_latest_monitoring_summary(
    portfolio_id: str,
    as_of_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the latest factor monitoring summary for a portfolio."""
    svc = FactorMonitoringService(db)
    run = await svc.repo.get_latest_monitoring_run(portfolio_id, as_of_date)
    if not run:
        return None
    conc = await svc.repo.get_concentration_result_by_run_id(run.run_id)
    resp_dict = {
        "id": run.id,
        "run_id": run.run_id,
        "portfolio_id": run.portfolio_id,
        "factor_model_version_id": run.factor_model_version_id,
        "config_id": run.config_id,
        "target_id": run.target_id,
        "as_of_date": run.as_of_date,
        "status": run.status,
        "drift_status": run.drift_status,
        "concentration_status": run.concentration_status,
        "has_active_breaches": run.has_active_breaches,
        "active_breach_count": run.active_breach_count,
        "warning_count": run.warning_count,
        "critical_breach_count": run.critical_breach_count,
        "input_freshness": run.input_freshness,
        "result_hash": run.result_hash,
        "drifts": run.drifts,
        "concentration": conc,
        "evaluations": run.evaluations,
        "created_at": run.created_at,
    }
    return FactorMonitoringRunResponse.model_validate(resp_dict)


@portfolio_router.get("/drift", response_model=List[FactorExposureDriftResponse])
async def get_latest_exposure_drift(
    portfolio_id: str,
    as_of_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve latest factor exposure drift metrics."""
    svc = FactorMonitoringService(db)
    run = await svc.repo.get_latest_monitoring_run(portfolio_id, as_of_date)
    if not run:
        return []
    return run.drifts


@portfolio_router.get("/concentration", response_model=Optional[FactorConcentrationResponse])
async def get_latest_concentration(
    portfolio_id: str,
    as_of_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve latest factor concentration metrics."""
    svc = FactorMonitoringService(db)
    run = await svc.repo.get_latest_monitoring_run(portfolio_id, as_of_date)
    if not run:
        return None
    return await svc.repo.get_concentration_result_by_run_id(run.run_id)


# =============================================================================
# 4. Breach Management & Acknowledgment
# =============================================================================

@router.get("/breaches", response_model=List[FactorMonitoringBreachResponse])
async def list_active_breaches(
    portfolio_id: Optional[str] = Query(None),
    severity: Optional[BreachSeverity] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Query active or pending factor monitoring breaches."""
    svc = FactorMonitoringService(db)
    return await svc.repo.list_active_breaches(portfolio_id, severity)


@router.post("/breaches/{breach_id}/acknowledge", response_model=FactorMonitoringBreachResponse)
async def acknowledge_breach(
    breach_id: str,
    req: BreachAcknowledgeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Acknowledge an active breach without clearing its underlying risk state."""
    svc = FactorMonitoringService(db)
    try:
        return await svc.acknowledge_breach(breach_id, req.user_id, req.note)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

