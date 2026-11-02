"""
FastAPI router for M08.06 Idiosyncratic Risk.
Provides RESTful endpoints for:
- Residual configuration lifecycle
- Instrument-level residual volatility estimation
- Residual covariance snapshot creation & retrieval
- Portfolio idiosyncratic risk & Euler risk contributions
- Residual diagnostics, moments, and specification tests
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.factor_risk.idiosyncratic_risk.schemas import (
    ResidualConfigCreate,
    ResidualConfigResponse,
    InstrumentResidualVolRequest,
    InstrumentResidualVolResponse,
    ResidualCovarianceRequest,
    ResidualCovarianceResponse,
    PortfolioIdiosyncraticRiskRequest,
    PortfolioIdiosyncraticRiskResponse,
    ResidualDiagnosticRequest,
    ResidualDiagnosticResponse,
)
from backend.app.modules.factor_risk.idiosyncratic_risk.services.service import IdiosyncraticRiskService

router = APIRouter(prefix="/api/v1/idiosyncratic-risk", tags=["M08.06 - Idiosyncratic Risk"])


# ---------------------------------------------------------
# Configuration Endpoints
# ---------------------------------------------------------

@router.post(
    "/configs",
    response_model=ResidualConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or get residual risk calculation configuration",
)
async def create_residual_config(
    req: ResidualConfigCreate,
    db: AsyncSession = Depends(get_db),
):
    service = IdiosyncraticRiskService(db)
    cfg = await service.create_or_get_config(req)
    return cfg


@router.get(
    "/configs",
    response_model=List[ResidualConfigResponse],
    summary="List residual risk calculation configurations",
)
async def list_residual_configs(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    service = IdiosyncraticRiskService(db)
    return await service.list_configs(limit=limit)


# ---------------------------------------------------------
# Instrument Residual Volatility
# ---------------------------------------------------------

@router.post(
    "/instruments/calculate",
    response_model=InstrumentResidualVolResponse,
    status_code=status.HTTP_200_OK,
    summary="Estimate security residual volatility and variance",
)
async def calculate_instrument_residual_volatility(
    req: InstrumentResidualVolRequest,
    db: AsyncSession = Depends(get_db),
):
    service = IdiosyncraticRiskService(db)
    try:
        run = await service.calculate_instrument_residual_volatility(req)
        return run
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------
# Residual Covariance Matrix
# ---------------------------------------------------------

@router.post(
    "/covariance/estimate",
    response_model=ResidualCovarianceResponse,
    status_code=status.HTTP_200_OK,
    summary="Estimate residual covariance matrix snapshot",
)
async def estimate_residual_covariance(
    req: ResidualCovarianceRequest,
    db: AsyncSession = Depends(get_db),
):
    service = IdiosyncraticRiskService(db)
    try:
        snapshot = await service.get_or_create_residual_covariance(req)
        return snapshot
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------
# Portfolio Idiosyncratic Risk & Risk Contributions
# ---------------------------------------------------------

@router.post(
    "/portfolios/calculate",
    response_model=PortfolioIdiosyncraticRiskResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate portfolio idiosyncratic risk, Euler contributions, and diversification metrics",
)
async def calculate_portfolio_idiosyncratic_risk(
    req: PortfolioIdiosyncraticRiskRequest,
    db: AsyncSession = Depends(get_db),
):
    service = IdiosyncraticRiskService(db)
    try:
        port_run = await service.calculate_portfolio_idiosyncratic_risk(req)
        return port_run
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------
# Residual Diagnostics & Specification Tests
# ---------------------------------------------------------

@router.post(
    "/diagnostics/run",
    response_model=ResidualDiagnosticResponse,
    status_code=status.HTTP_200_OK,
    summary="Run econometric diagnostics on security factor residuals",
)
async def run_residual_diagnostics(
    req: ResidualDiagnosticRequest,
    db: AsyncSession = Depends(get_db),
):
    service = IdiosyncraticRiskService(db)
    try:
        diag = await service.run_residual_diagnostics(req)
        return diag
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

