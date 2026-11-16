"""
M10.06 Liquidity Stress Testing FastAPI Router.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.scenario_analysis.liquidity_stress.schemas import (
    LiquidityStressScenarioCreate,
    LiquidityStressScenarioResponse,
    ExecuteLiquidityStressRequest,
    LiquidityStressRunResponse,
)
from backend.app.modules.scenario_analysis.liquidity_stress.services import (
    LiquidityStressService,
)

router = APIRouter(
    prefix="/api/v1/risk/scenarios/liquidity-stress",
    tags=["M10.06 - Liquidity Stress Testing"],
)


@router.post("", response_model=LiquidityStressScenarioResponse, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    payload: LiquidityStressScenarioCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new liquidity stress scenario with versioned parameters and optional instrument overrides.
    """
    service = LiquidityStressService(db)
    return await service.create_scenario(payload)


@router.get("", response_model=List[LiquidityStressScenarioResponse])
async def list_scenarios(
    db: AsyncSession = Depends(get_db),
):
    """
    List all configured liquidity stress testing scenarios.
    """
    service = LiquidityStressService(db)
    return await service.list_scenarios()


@router.get("/{scenario_id}", response_model=LiquidityStressScenarioResponse)
async def get_scenario(
    scenario_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve scenario details by scenario ID.
    """
    service = LiquidityStressService(db)
    scenario = await service.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Liquidity stress scenario not found")
    return scenario


@router.post("/{scenario_id}/runs", response_model=LiquidityStressRunResponse, status_code=status.HTTP_201_CREATED)
async def execute_liquidity_stress_run(
    scenario_id: str,
    payload: ExecuteLiquidityStressRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Execute a liquidity stress simulation run against a portfolio.
    Calculates simultaneous spread, depth, and volume stress, stressed liquidation capacity,
    liquidation duration, cost decomposition without double counting, progressive horizon analysis,
    and residual exposure.
    """
    service = LiquidityStressService(db)
    try:
        return await service.execute_scenario(scenario_id, payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")
