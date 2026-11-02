"""
M07.05 Correlation Analysis FastAPI Router.
Endpoints mounted under /api/v1/market-risk/correlation and /api/v1/portfolios/{portfolio_id}/risk/correlation.
"""
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.market_risk.correlation.services.service import CorrelationService
from backend.app.modules.market_risk.correlation.repositories.repository import CorrelationRepository
from backend.app.modules.market_risk.correlation.models import (
    CorrelationConfiguration,
    CorrelationRegimeStatus,
)
from backend.app.modules.market_risk.correlation.schemas import (
    PairwiseCorrelationRequest,
    PairwiseCorrelationResponse,
    MatrixCorrelationRequest,
    CorrelationMatrixResponse,
    RollingCorrelationRequest,
    RollingCorrelationResponse,
    CorrelationRankingsResponse,
    CorrelationRegimeEventResponse,
    MultiHorizonCorrelationResponse,
    CorrelationConfigCreate,
    CorrelationConfigResponse,
)

router = APIRouter()
portfolio_router = APIRouter()


@router.post("/pairwise", response_model=PairwiseCorrelationResponse, summary="Calculate Pairwise Correlation")
async def calculate_pairwise(
    request: PairwiseCorrelationRequest,
    session: AsyncSession = Depends(get_db),
):
    service = CorrelationService(session)
    return await service.calculate_pairwise(request)


@router.post("/matrix", response_model=CorrelationMatrixResponse, summary="Generate Correlation Matrix with PSD Diagnostics")
async def calculate_matrix(
    request: MatrixCorrelationRequest,
    session: AsyncSession = Depends(get_db),
):
    service = CorrelationService(session)
    return await service.calculate_matrix(request)


@router.post("/rolling", response_model=RollingCorrelationResponse, summary="Compute Rolling Correlation Series")
async def calculate_rolling(
    request: RollingCorrelationRequest,
    session: AsyncSession = Depends(get_db),
):
    service = CorrelationService(session)
    return await service.calculate_rolling(request)


@router.get("/multi-horizon", response_model=MultiHorizonCorrelationResponse, summary="Multi-Horizon Lookback Comparison")
async def get_multi_horizon(
    asset_a_id: str = Query(..., description="First asset ID"),
    asset_b_id: str = Query(..., description="Second asset ID"),
    as_of: Optional[date] = Query(None, description="Observation anchor date"),
    session: AsyncSession = Depends(get_db),
):
    service = CorrelationService(session)
    return await service.get_multi_horizon(asset_a_id, asset_b_id, as_of=as_of)


@router.get("/regimes", response_model=List[CorrelationRegimeEventResponse], summary="List Detected Regime Events")
async def list_regime_events(
    portfolio_id: Optional[str] = Query(None, description="Filter by portfolio ID"),
    status: Optional[CorrelationRegimeStatus] = Query(None, description="Event status filter"),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
):
    repo = CorrelationRepository(session)
    events = await repo.list_regime_events(portfolio_id=portfolio_id, status=status, limit=limit)
    return events


@router.post("/configs", response_model=CorrelationConfigResponse, summary="Create Correlation Configuration")
async def create_config(
    request: CorrelationConfigCreate,
    session: AsyncSession = Depends(get_db),
):
    repo = CorrelationRepository(session)
    config = CorrelationConfiguration(**request.model_dump())
    return await repo.create_config(config)


@router.get("/configs", response_model=List[CorrelationConfigResponse], summary="List Active Correlation Configurations")
async def list_configs(
    session: AsyncSession = Depends(get_db),
):
    repo = CorrelationRepository(session)
    return await repo.list_active_configs()


# Portfolio specific endpoints
@portfolio_router.get("/{portfolio_id}/risk/correlation/rankings", response_model=CorrelationRankingsResponse, summary="Portfolio Correlation Rankings")
async def get_portfolio_correlation_rankings(
    portfolio_id: str = Path(..., description="Portfolio ID"),
    lookback_days: int = Query(60, ge=5, le=2520),
    as_of: Optional[date] = Query(None, description="Calculation date"),
    top_n: int = Query(5, ge=1, le=20),
    session: AsyncSession = Depends(get_db),
):
    service = CorrelationService(session)
    return await service.get_rankings(portfolio_id=portfolio_id, lookback_days=lookback_days, as_of=as_of, top_n=top_n)


@portfolio_router.get("/{portfolio_id}/risk/correlation/matrix", response_model=CorrelationMatrixResponse, summary="Latest Portfolio Correlation Matrix")
async def get_portfolio_matrix(
    portfolio_id: str = Path(..., description="Portfolio ID"),
    lookback_days: int = Query(60, ge=5, le=2520),
    as_of: Optional[date] = Query(None, description="Calculation date"),
    repair_psd: bool = Query(False, description="Attempt PSD matrix repair if non-PSD"),
    session: AsyncSession = Depends(get_db),
):
    service = CorrelationService(session)
    return await service.calculate_matrix(
        MatrixCorrelationRequest(
            portfolio_id=portfolio_id,
            lookback_days=lookback_days,
            as_of=as_of,
            repair_psd=repair_psd,
        )
    )

