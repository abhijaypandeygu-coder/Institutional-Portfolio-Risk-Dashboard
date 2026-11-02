"""
M07.06 Covariance Analysis FastAPI Router.
Mounted under:
- /api/v1/market-risk/covariance
- /api/v1/portfolios/{portfolio_id}/risk/covariance
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.market_risk.covariance.services.service import CovarianceService
from backend.app.modules.market_risk.covariance.repositories.repository import CovarianceRepository
from backend.app.modules.market_risk.covariance.models import (
    CovarianceConfiguration,
    WeightBasis,
)
from backend.app.modules.market_risk.covariance.schemas import (
    PairwiseCovarianceRequest,
    PairwiseCovarianceResponse,
    MatrixCovarianceRequest,
    CovarianceMatrixResponse,
    RollingCovarianceRequest,
    RollingCovarianceResponse,
    PortfolioCovarianceRequest,
    PortfolioCovarianceResponse,
    PortfolioPairCovarianceRequest,
    PortfolioPairCovarianceResponse,
    CovarianceConfigCreate,
    CovarianceConfigResponse,
)

router = APIRouter()
portfolio_router = APIRouter()


@router.post("/pairwise", response_model=PairwiseCovarianceResponse, summary="Calculate Pairwise Covariance")
async def calculate_pairwise(
    request: PairwiseCovarianceRequest,
    session: AsyncSession = Depends(get_db),
):
    service = CovarianceService(session)
    return await service.calculate_pairwise(request)


@router.post("/matrix", response_model=CovarianceMatrixResponse, summary="Generate Covariance Matrix with PSD Diagnostics")
async def calculate_matrix(
    request: MatrixCovarianceRequest,
    session: AsyncSession = Depends(get_db),
):
    service = CovarianceService(session)
    return await service.calculate_matrix(request)


@router.post("/rolling", response_model=RollingCovarianceResponse, summary="Compute Rolling Covariance Series")
async def calculate_rolling(
    request: RollingCovarianceRequest,
    session: AsyncSession = Depends(get_db),
):
    service = CovarianceService(session)
    return await service.calculate_rolling(request)


@router.post("/portfolio", response_model=PortfolioCovarianceResponse, summary="Calculate Portfolio Variance and Risk Contributions")
async def calculate_portfolio_covariance(
    request: PortfolioCovarianceRequest,
    session: AsyncSession = Depends(get_db),
):
    service = CovarianceService(session)
    return await service.calculate_portfolio_covariance(request)


@router.post("/portfolio-pair", response_model=PortfolioPairCovarianceResponse, summary="Calculate Cross-Portfolio Covariance")
async def calculate_portfolio_pair_covariance(
    request: PortfolioPairCovarianceRequest,
    session: AsyncSession = Depends(get_db),
):
    service = CovarianceService(session)
    return await service.calculate_portfolio_pair_covariance(request)


@router.post("/configs", response_model=CovarianceConfigResponse, summary="Create Covariance Configuration")
async def create_config(
    request: CovarianceConfigCreate,
    session: AsyncSession = Depends(get_db),
):
    repo = CovarianceRepository(session)
    config = CovarianceConfiguration(**request.model_dump())
    return await repo.create_config(config)


@router.get("/configs", response_model=List[CovarianceConfigResponse], summary="List Active Covariance Configurations")
async def list_configs(
    session: AsyncSession = Depends(get_db),
):
    repo = CovarianceRepository(session)
    return await repo.list_active_configs()


# Portfolio Specific Endpoints
@portfolio_router.get("/{portfolio_id}/risk/covariance/matrix", response_model=CovarianceMatrixResponse, summary="Portfolio Covariance Matrix")
async def get_portfolio_covariance_matrix(
    portfolio_id: str = Path(..., description="Portfolio ID"),
    lookback_days: int = Query(60, ge=5, le=2520),
    annualize: bool = Query(False, description="Annualize matrix entries"),
    session: AsyncSession = Depends(get_db),
):
    service = CovarianceService(session)
    return await service.calculate_matrix(
        MatrixCovarianceRequest(
            portfolio_id=portfolio_id,
            lookback_days=lookback_days,
            annualize=annualize,
        )
    )


@portfolio_router.get("/{portfolio_id}/risk/covariance/contributions", response_model=PortfolioCovarianceResponse, summary="Portfolio Risk Contributions")
async def get_portfolio_risk_contributions(
    portfolio_id: str = Path(..., description="Portfolio ID"),
    lookback_days: int = Query(60, ge=5, le=2520),
    weight_basis: WeightBasis = Query(WeightBasis.PORTFOLIO_NAV, description="Weight calculation basis"),
    session: AsyncSession = Depends(get_db),
):
    service = CovarianceService(session)
    return await service.calculate_portfolio_covariance(
        PortfolioCovarianceRequest(
            portfolio_id=portfolio_id,
            lookback_days=lookback_days,
            weight_basis=weight_basis,
        )
    )
