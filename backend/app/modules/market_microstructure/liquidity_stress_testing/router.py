"""
FastAPI router for M09.06 Liquidity Stress Testing & Stressed Execution Cost Estimation.
"""

from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.market_microstructure.liquidity_stress_testing.schemas.stress_schemas import (
    StressConfigCreate,
    StressConfigResponse,
    StressRunRequest,
    StressRunResponse,
    ReverseStressRequest,
    ReverseStressResponse,
    PortfolioStressRequest,
    PortfolioStressResponse,
)
from backend.app.modules.market_microstructure.liquidity_stress_testing.services.stress_service import (
    LiquidityStressService,
)

router = APIRouter(
    prefix="/api/v1/market-microstructure/liquidity-stress",
    tags=["M09.06 - Liquidity Stress Testing"],
)


@router.post(
    "/scenarios",
    response_model=StressConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or retrieve a versioned liquidity stress scenario configuration",
)
async def create_stress_scenario(
    config: StressConfigCreate,
    session: AsyncSession = Depends(get_db),
):
    """
    Creates or returns an active liquidity stress testing scenario configuration
    defining spread widening multipliers, depth reductions, and volume contraction ratios.
    """
    service = LiquidityStressService(session)
    return await service.get_or_create_config(config)


@router.get(
    "/scenarios",
    response_model=List[StressConfigResponse],
    summary="List all active liquidity stress scenario configurations",
)
async def list_stress_scenarios(
    session: AsyncSession = Depends(get_db),
):
    """
    Lists all available active liquidity stress configurations.
    """
    service = LiquidityStressService(session)
    configs = await service.repo.list_configs()
    return [StressConfigResponse.model_validate(c) for c in configs]


@router.post(
    "/run",
    response_model=StressRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute comprehensive instrument liquidity stress test and cost escalation",
)
async def run_liquidity_stress(
    request: StressRunRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Applies spread widening, depth reduction, and volume contraction shocks to baseline market data.
    Generates synthetic stressed order book, calculates liquidation duration across volume profiles,
    and recalculates execution costs (spread crossing, depth-walk concession, impact, fees, opportunity cost).
    """
    service = LiquidityStressService(session)
    return await service.run_liquidity_stress_test(request)


@router.post(
    "/reverse-stress",
    response_model=ReverseStressResponse,
    status_code=status.HTTP_200_OK,
    summary="Reverse stress testing to identify critical parameter breach thresholds",
)
async def run_reverse_stress(
    request: ReverseStressRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Calculates the critical volume contraction percentage or spread multiplier
    that triggers a breach of maximum acceptable liquidation duration or cost.
    """
    service = LiquidityStressService(session)
    return await service.execute_reverse_stress(request)


@router.post(
    "/portfolio",
    response_model=PortfolioStressResponse,
    status_code=status.HTTP_200_OK,
    summary="Run portfolio-level liquidity stress testing and critical-path liquidation duration",
)
async def run_portfolio_stress(
    request: PortfolioStressRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Aggregates liquidity stress across multiple portfolio positions under concurrent liquidation schedules,
    determining portfolio-level cost escalation and critical-path liquidation duration.
    """
    service = LiquidityStressService(session)
    return await service.execute_portfolio_stress(request)

