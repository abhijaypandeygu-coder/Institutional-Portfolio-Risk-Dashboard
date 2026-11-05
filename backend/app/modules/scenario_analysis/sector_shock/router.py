"""
Sector Shock Simulation FastAPI Router (M10.04).
Endpoints for:
- Sector shock scenario creation, versioning, and listing
- Sector & industry targets and spillovers
- Simulation execution & granular results (positions, groups, channels, attributions)
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from .services.sector_service import SectorShockService
from .schemas.sector_schemas import (
    SectorShockScenarioCreate,
    SectorShockScenarioResponse,
    SectorSimulationExecutionRequest,
    SectorSimulationSummaryResponse,
    SectorPositionResultResponse,
    SectorGroupResultResponse,
    SectorAttributionResultResponse,
    SectorWarningResponse
)

router = APIRouter(
    prefix="/api/v1/scenarios/sector-shock",
    tags=["M10.04 Sector Shock Simulation"]
)


@router.post("", response_model=SectorShockScenarioResponse, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    req: SectorShockScenarioCreate,
    db: AsyncSession = Depends(get_db)
):
    service = SectorShockService(db)
    return await service.create_scenario(req)


@router.get("", response_model=List[SectorShockScenarioResponse])
async def list_scenarios(
    category: Optional[str] = Query(None),
    portfolio_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    service = SectorShockService(db)
    scenarios = await service.repo.list_scenarios(category=category, portfolio_id=portfolio_id, status=status, limit=limit)
    return [SectorShockScenarioResponse.model_validate(s) for s in scenarios]


@router.get("/{scenario_id}", response_model=SectorShockScenarioResponse)
async def get_scenario(
    scenario_id: str,
    db: AsyncSession = Depends(get_db)
):
    service = SectorShockService(db)
    scenario = await service.repo.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Sector shock scenario '{scenario_id}' not found")
    return SectorShockScenarioResponse.model_validate(scenario)


@router.post("/runs", response_model=SectorSimulationSummaryResponse, status_code=status.HTTP_201_CREATED)
async def execute_simulation(
    req: SectorSimulationExecutionRequest,
    db: AsyncSession = Depends(get_db)
):
    service = SectorShockService(db)
    return await service.execute_simulation(req)


@router.get("/runs/{run_id}", response_model=SectorSimulationSummaryResponse)
async def get_simulation_run(
    run_id: str,
    db: AsyncSession = Depends(get_db)
):
    service = SectorShockService(db)
    run = await service.repo.get_simulation_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Sector simulation run '{run_id}' not found")
    
    return SectorSimulationSummaryResponse(
        simulation_id=run.id,
        simulation_code=run.simulation_code,
        scenario_id=run.scenario_id,
        portfolio_id=run.portfolio_id,
        base_currency=run.base_currency,
        run_status=run.run_status,
        baseline_nav=run.baseline_nav,
        scenario_nav=run.scenario_nav,
        scenario_pnl=run.scenario_pnl,
        scenario_loss=run.scenario_loss,
        scenario_return=run.scenario_return,
        gross_exposure=run.baseline_nav,
        net_exposure=run.baseline_nav,
        direct_exposure_coverage=run.direct_exposure_coverage,
        spillover_exposure_coverage=run.spillover_exposure_coverage,
        classification_coverage=run.classification_coverage,
        sensitivity_coverage=run.sensitivity_coverage,
        affected_positions=len(run.position_results) if run.position_results else 0,
        started_at=run.started_at,
        completed_at=run.completed_at,
        position_results=[SectorPositionResultResponse.model_validate(p) for p in (run.position_results or [])],
        group_results=[SectorGroupResultResponse.model_validate(g) for g in (run.group_results or [])],
        attribution_results=[SectorAttributionResultResponse.model_validate(a) for a in (run.attribution_results or [])],
        warnings=[SectorWarningResponse.model_validate(w) for w in (run.warnings or [])]
    )
