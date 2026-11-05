"""
Market Crash Simulation FastAPI Router (M10.03).
Endpoints for:
- Scenario creation & versioning
- Listing and retrieving scenario configurations
- Executing market crash simulations
- Retrieving granular position results, attributions, warnings, and comparisons
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from .services.crash_service import MarketCrashService
from .schemas.crash_schemas import (
    MarketCrashScenarioCreate,
    MarketCrashScenarioResponse,
    SimulationExecutionRequest,
    SimulationSummaryResponse,
    PositionResultResponse,
    AttributionResultResponse,
    WarningResponse
)

router = APIRouter(
    prefix="/api/v1/scenarios/market-crash",
    tags=["M10.03 Market Crash Simulation"]
)


@router.post("", response_model=MarketCrashScenarioResponse, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    req: MarketCrashScenarioCreate,
    db: AsyncSession = Depends(get_db)
):
    service = MarketCrashService(db)
    return await service.create_scenario(req)


@router.get("", response_model=List[MarketCrashScenarioResponse])
async def list_scenarios(
    category: Optional[str] = Query(None),
    portfolio_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    service = MarketCrashService(db)
    scenarios = await service.repo.list_scenarios(category=category, portfolio_id=portfolio_id, status=status, limit=limit)
    return [MarketCrashScenarioResponse.model_validate(s) for s in scenarios]


@router.get("/{scenario_id}", response_model=MarketCrashScenarioResponse)
async def get_scenario(
    scenario_id: str,
    db: AsyncSession = Depends(get_db)
):
    service = MarketCrashService(db)
    scenario = await service.repo.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Market crash scenario '{scenario_id}' not found")
    return MarketCrashScenarioResponse.model_validate(scenario)


@router.post("/runs", response_model=SimulationSummaryResponse, status_code=status.HTTP_201_CREATED)
async def execute_simulation(
    req: SimulationExecutionRequest,
    db: AsyncSession = Depends(get_db)
):
    service = MarketCrashService(db)
    return await service.execute_simulation(req)


@router.get("/runs/{run_id}", response_model=SimulationSummaryResponse)
async def get_simulation_run(
    run_id: str,
    db: AsyncSession = Depends(get_db)
):
    service = MarketCrashService(db)
    run = await service.repo.get_simulation_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Simulation run '{run_id}' not found")
    
    return SimulationSummaryResponse(
        simulation_id=run.id,
        simulation_code=run.simulation_code,
        scenario_id=run.scenario_id,
        portfolio_id=run.portfolio_id,
        base_currency=run.base_currency,
        response_model=run.response_model,
        run_status=run.run_status,
        baseline_nav=run.baseline_nav,
        scenario_nav=run.scenario_nav,
        scenario_pnl=run.scenario_pnl,
        scenario_loss=run.scenario_loss,
        scenario_return=run.scenario_return,
        gross_exposure=run.summary_results.gross_exposure if run.summary_results else run.baseline_nav,
        net_exposure=run.summary_results.net_exposure if run.summary_results else run.baseline_nav,
        mapped_coverage=run.mapped_coverage,
        beta_coverage=run.beta_coverage,
        nonlinear_coverage=run.nonlinear_coverage,
        affected_positions=len(run.position_results) if run.position_results else 0,
        started_at=run.started_at,
        completed_at=run.completed_at,
        position_results=[PositionResultResponse.model_validate(p) for p in (run.position_results or [])],
        attribution_results=[AttributionResultResponse.model_validate(a) for a in (run.attribution_results or [])],
        warnings=[WarningResponse.model_validate(w) for w in (run.warnings or [])]
    )
