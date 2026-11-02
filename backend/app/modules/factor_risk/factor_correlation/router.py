"""
FastAPI Router for M08.07 Factor Correlation & Covariance Analytics.
Provides RESTful endpoints for:
- Factor correlation configuration management
- Inter-factor correlation matrix execution
- Retrieval of correlation matrix snapshots
- Authoritative factor covariance matrix calculation (consumed by M08.05 Systematic Risk)
- Retrieval of authoritative factor covariance snapshots
- Rolling factor correlation & relationship time series
- Correlation regime evaluation & active alert queries
"""

from datetime import date
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.factor_risk.factor_correlation.schemas import (
    FactorCorrelationConfigCreate,
    FactorCorrelationConfigResponse,
    FactorCorrelationCalculateRequest,
    FactorCorrelationRunResponse,
    FactorCorrelationMatrixSnapshotResponse,
    FactorCovarianceCalculateRequest,
    FactorCovarianceSnapshotResponse,
    RollingFactorCorrelationRequest,
    RollingFactorCorrelationResponse,
    FactorRegimeEvaluateRequest,
    FactorRegimeEvaluationResponse,
    FactorRegimeAlertResponse,
)
from backend.app.modules.factor_risk.factor_correlation.services.service import FactorCorrelationService

router = APIRouter(prefix="/api/v1/factor-correlation", tags=["M08.07 - Factor Correlation"])


# ---------------------------------------------------------
# Configuration Endpoints
# ---------------------------------------------------------

@router.post(
    "/configs",
    response_model=FactorCorrelationConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or retrieve a factor correlation configuration",
)
async def create_correlation_config(
    req: FactorCorrelationConfigCreate,
    db: AsyncSession = Depends(get_db),
):
    service = FactorCorrelationService(db)
    return await service.create_or_get_correlation_config(req)


@router.get(
    "/configs",
    response_model=List[FactorCorrelationConfigResponse],
    summary="List factor correlation configurations",
)
async def list_correlation_configs(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    service = FactorCorrelationService(db)
    return await service.list_correlation_configs(limit=limit)


# ---------------------------------------------------------
# Correlation Matrix Execution & Retrieval
# ---------------------------------------------------------

@router.post(
    "/calculate",
    response_model=FactorCorrelationRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate full inter-factor correlation matrix",
)
async def calculate_factor_correlation(
    req: FactorCorrelationCalculateRequest,
    db: AsyncSession = Depends(get_db),
):
    service = FactorCorrelationService(db)
    try:
        return await service.calculate_inter_factor_correlation(req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/matrices/{matrix_id}",
    response_model=FactorCorrelationMatrixSnapshotResponse,
    summary="Retrieve pinned correlation matrix snapshot",
)
async def get_correlation_matrix(
    matrix_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = FactorCorrelationService(db)
    snap = await service.get_matrix_snapshot(matrix_id)
    if not snap:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Matrix '{matrix_id}' not found")
    return snap


# ---------------------------------------------------------
# Authoritative Factor Covariance (M08.05 Contract)
# ---------------------------------------------------------

@router.post(
    "/covariance/calculate",
    response_model=FactorCovarianceSnapshotResponse,
    status_code=status.HTTP_200_OK,
    summary="Estimate authoritative factor covariance matrix for M08.05 Systematic Risk",
)
async def calculate_factor_covariance(
    req: FactorCovarianceCalculateRequest,
    db: AsyncSession = Depends(get_db),
):
    service = FactorCorrelationService(db)
    try:
        return await service.calculate_factor_covariance(req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/covariance/{snapshot_id}",
    response_model=FactorCovarianceSnapshotResponse,
    summary="Retrieve authoritative factor covariance snapshot",
)
async def get_factor_covariance(
    snapshot_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = FactorCorrelationService(db)
    snap = await service.get_covariance_snapshot(snapshot_id)
    if not snap:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Covariance snapshot '{snapshot_id}' not found")
    return snap


# ---------------------------------------------------------
# Rolling Relationships
# ---------------------------------------------------------

@router.post(
    "/rolling",
    response_model=RollingFactorCorrelationResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate rolling correlation & covariance between two factors",
)
async def compute_rolling_relationships(
    req: RollingFactorCorrelationRequest,
    db: AsyncSession = Depends(get_db),
):
    service = FactorCorrelationService(db)
    try:
        return await service.compute_rolling_relationships(req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------
# Correlation Regime Detection & Alerts
# ---------------------------------------------------------

@router.post(
    "/regimes/evaluate",
    response_model=FactorRegimeEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate correlation regimes, sign reversals, and structural breaks",
)
async def evaluate_correlation_regimes(
    req: FactorRegimeEvaluateRequest,
    db: AsyncSession = Depends(get_db),
):
    service = FactorCorrelationService(db)
    try:
        return await service.evaluate_regimes(req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/regimes/alerts",
    response_model=List[FactorRegimeAlertResponse],
    summary="Retrieve active regime alerts for a factor model",
)
async def get_active_regime_alerts(
    factor_model_version_id: str,
    as_of_date: date,
    db: AsyncSession = Depends(get_db),
):
    service = FactorCorrelationService(db)
    return await service.get_active_alerts(
        factor_model_version_id=factor_model_version_id, as_of_date=as_of_date
    )
