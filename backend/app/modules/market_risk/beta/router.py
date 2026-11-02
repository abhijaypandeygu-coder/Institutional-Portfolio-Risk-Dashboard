"""
M07.07 Portfolio Beta FastAPI Router.
Mounted under:
- /api/v1/market-risk/beta
- /api/v1/portfolios/{portfolio_id}/risk/beta
"""
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.market_risk.beta.services.service import BetaService
from backend.app.modules.market_risk.beta.repositories.repository import BetaRepository
from backend.app.modules.market_risk.beta.models import (
    BetaConfiguration,
    BetaCalculationMethod,
)
from backend.app.modules.market_risk.beta.schemas import (
    SecurityBetaRequest,
    SecurityBetaResponse,
    PortfolioBetaRequest,
    PortfolioBetaResponse,
    AssetBetaContribution,
    DirectVsWeightedBetaReconciliation,
    BenchmarkReferenceCreate,
    BenchmarkReferenceResponse,
    BetaConfigCreate,
    BetaConfigResponse,
)

router = APIRouter()
portfolio_router = APIRouter()


# ---------------------------------------------------------
# Security & Portfolio Beta Endpoints
# ---------------------------------------------------------
@router.post("/security", response_model=SecurityBetaResponse, summary="Calculate Individual Security Beta")
async def calculate_security_beta(
    request: SecurityBetaRequest,
    session: AsyncSession = Depends(get_db),
):
    service = BetaService(session)
    return await service.calculate_security_beta(request)


@router.post("/portfolio", response_model=PortfolioBetaResponse, summary="Calculate Portfolio Beta (Direct or Weighted)")
async def calculate_portfolio_beta(
    request: PortfolioBetaRequest,
    session: AsyncSession = Depends(get_db),
):
    service = BetaService(session)
    return await service.calculate_portfolio_beta(request)


@router.get("/reconciliation", response_model=DirectVsWeightedBetaReconciliation, summary="Reconcile Direct vs Weighted Portfolio Beta")
async def reconcile_direct_vs_weighted(
    portfolio_id: str = Query(..., description="Target portfolio UUID"),
    benchmark_code: Optional[str] = Query(None, description="Benchmark code (default: NIFTY_50)"),
    lookback_days: int = Query(60, description="Lookback window in days"),
    as_of: Optional[date] = Query(None, description="Evaluation as of date"),
    session: AsyncSession = Depends(get_db),
):
    service = BetaService(session)
    return await service.reconcile_direct_vs_weighted(
        portfolio_id=portfolio_id,
        benchmark_code=benchmark_code,
        lookback_days=lookback_days,
        as_of=as_of,
    )


# ---------------------------------------------------------
# Benchmark Reference Management
# ---------------------------------------------------------
@router.post("/benchmarks", response_model=BenchmarkReferenceResponse, summary="Register Benchmark Reference")
async def register_benchmark(
    payload: BenchmarkReferenceCreate,
    session: AsyncSession = Depends(get_db),
):
    repo = BetaRepository(session)
    bench = BenchmarkReference(
        benchmark_code=payload.benchmark_code,
        benchmark_name=payload.benchmark_name,
        market=payload.market,
        currency=payload.currency,
        instrument_id=payload.instrument_id,
        provider=payload.provider,
        return_basis=payload.return_basis,
        time_zone=payload.time_zone,
        is_active=payload.is_active,
    )
    return await repo.create_benchmark(bench)


@router.get("/benchmarks", response_model=List[BenchmarkReferenceResponse], summary="List Active Benchmarks")
async def list_benchmarks(
    market: Optional[str] = Query(None, description="Filter by market"),
    session: AsyncSession = Depends(get_db),
):
    repo = BetaRepository(session)
    return await repo.list_benchmarks(market=market, active_only=True)


# ---------------------------------------------------------
# Beta Configuration Profiles
# ---------------------------------------------------------
@router.post("/configs", response_model=BetaConfigResponse, summary="Create Beta Calculation Configuration Profile")
async def create_config(
    payload: BetaConfigCreate,
    session: AsyncSession = Depends(get_db),
):
    repo = BetaRepository(session)
    config = BetaConfiguration(
        config_name=payload.config_name,
        benchmark_id=payload.benchmark_id,
        model_type=payload.model_type,
        calculation_method=payload.calculation_method,
        lookback_days=payload.lookback_days,
        min_observations=payload.min_observations,
        weight_basis=payload.weight_basis,
        include_intercept=payload.include_intercept,
        confidence_level=payload.confidence_level,
        description=payload.description,
    )
    return await repo.save_config(config)


@router.get("/configs", response_model=List[BetaConfigResponse], summary="List Beta Configurations")
async def list_configs(
    session: AsyncSession = Depends(get_db),
):
    repo = BetaRepository(session)
    return await repo.list_configs()


# ---------------------------------------------------------
# Portfolio Nested Endpoints: /api/v1/portfolios/{portfolio_id}/risk/beta
# ---------------------------------------------------------
@portfolio_router.get(
    "/{portfolio_id}/risk/beta",
    response_model=PortfolioBetaResponse,
    summary="Get Portfolio Beta Analysis",
)
async def get_portfolio_beta(
    portfolio_id: str = Path(..., description="Target portfolio UUID"),
    benchmark_code: Optional[str] = Query(None, description="Benchmark code"),
    method: BetaCalculationMethod = Query(BetaCalculationMethod.CURRENT_WEIGHT_IMPLIED, description="Calculation method"),
    lookback_days: int = Query(60, description="Lookback window in days"),
    as_of: Optional[date] = Query(None, description="Evaluation date"),
    session: AsyncSession = Depends(get_db),
):
    service = BetaService(session)
    bench = await service.get_or_resolve_benchmark(benchmark_code=benchmark_code)
    req = PortfolioBetaRequest(
        portfolio_id=portfolio_id,
        benchmark_id=bench.id,
        method=method,
        lookback_days=lookback_days,
        as_of=as_of,
    )
    return await service.calculate_portfolio_beta(req)


@portfolio_router.get(
    "/{portfolio_id}/risk/beta/contributions",
    response_model=List[AssetBetaContribution],
    summary="Get Portfolio Constituent Beta Contributions",
)
async def get_portfolio_beta_contributions(
    portfolio_id: str = Path(..., description="Target portfolio UUID"),
    benchmark_code: Optional[str] = Query(None, description="Benchmark code"),
    lookback_days: int = Query(60, description="Lookback window in days"),
    as_of: Optional[date] = Query(None, description="Evaluation date"),
    session: AsyncSession = Depends(get_db),
):
    service = BetaService(session)
    bench = await service.get_or_resolve_benchmark(benchmark_code=benchmark_code)
    req = PortfolioBetaRequest(
        portfolio_id=portfolio_id,
        benchmark_id=bench.id,
        method=BetaCalculationMethod.CURRENT_WEIGHT_IMPLIED,
        lookback_days=lookback_days,
        as_of=as_of,
    )
    res = await service.calculate_portfolio_beta(req)
    return res.contributions
