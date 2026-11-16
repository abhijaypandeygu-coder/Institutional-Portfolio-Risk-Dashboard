"""
FastAPI router for M10.07 Monte Carlo Scenarios.
Mounts endpoints for scenario authoring, configuration, stochastic execution, and risk reporting.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.scenario_analysis.monte_carlo.schemas.monte_carlo_schemas import (
    MonteCarloScenarioCreate,
    MonteCarloScenarioUpdate,
    MonteCarloScenarioResponse,
    SimulationExecutionRequest,
    SimulationRunResponse,
    SimulationSummaryResponse,
    RiskMetricResponse,
    InstrumentResultResponse,
)
from backend.app.modules.scenario_analysis.monte_carlo.services.monte_carlo_service import (
    MonteCarloService,
)

router = APIRouter(
    prefix="/api/v1/risk/scenarios/monte-carlo",
    tags=["M10.07 — Monte Carlo Scenarios"]
)


@router.post("/scenarios", response_model=MonteCarloScenarioResponse, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    payload: MonteCarloScenarioCreate,
    session: AsyncSession = Depends(get_db)
):
    """
    Creates a new Monte Carlo scenario specification.
    """
    service = MonteCarloService(session)
    try:
        scenario = await service.create_scenario(payload)
        await session.commit()
        return scenario
    except ValueError as ve:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create scenario: {str(e)}")


@router.get("/scenarios", response_model=List[MonteCarloScenarioResponse])
async def list_scenarios(
    active_only: bool = Query(True, description="Filter active scenarios"),
    session: AsyncSession = Depends(get_db)
):
    """
    Lists all configured Monte Carlo scenarios.
    """
    service = MonteCarloService(session)
    return await service.list_scenarios(active_only=active_only)


@router.get("/scenarios/{scenario_code}", response_model=MonteCarloScenarioResponse)
async def get_scenario(
    scenario_code: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Retrieves a Monte Carlo scenario by code or ID.
    """
    service = MonteCarloService(session)
    scenario = await service.get_scenario(scenario_code)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_code}' not found")
    return scenario


@router.put("/scenarios/{scenario_code}", response_model=MonteCarloScenarioResponse)
async def update_scenario(
    scenario_code: str,
    payload: MonteCarloScenarioUpdate,
    session: AsyncSession = Depends(get_db)
):
    """
    Updates an existing Monte Carlo scenario.
    """
    service = MonteCarloService(session)
    try:
        updated = await service.update_scenario(scenario_code, payload)
        await session.commit()
        return updated
    except ValueError as ve:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update scenario: {str(e)}")


@router.delete("/scenarios/{scenario_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scenario(
    scenario_code: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Deletes a Monte Carlo scenario.
    """
    service = MonteCarloService(session)
    try:
        await service.delete_scenario(scenario_code)
        await session.commit()
    except ValueError as ve:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete scenario: {str(e)}")


@router.post("/scenarios/{scenario_code}/run", response_model=SimulationRunResponse)
async def execute_simulation(
    scenario_code: str,
    payload: SimulationExecutionRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Executes a high-performance stochastic Monte Carlo simulation across portfolio holdings.
    Computes distribution moments, loss probabilities, and VaR/Expected Shortfall.
    """
    service = MonteCarloService(session)
    try:
        run = await service.run_simulation(scenario_code, payload)
        await session.commit()

        narrative = (
            f"Monte Carlo simulation '{run.run_code}' generated {run.n_paths} paths over a "
            f"{run.scenario.horizon_days}-day horizon with seed {run.random_seed}. "
            f"Mean P&L is ${run.summary.mean_pnl:,.2f} with {run.summary.loss_probability * 100:.1f}% probability of loss. "
            f"95% Monte Carlo VaR is ${run.risk_metrics[1].var_loss_amount:,.2f} ({run.risk_metrics[1].var_percent * 100:.2f}% of portfolio)."
        )

        return SimulationRunResponse(
            run_id=run.id,
            scenario_code=run.scenario.scenario_code,
            run_code=run.run_code,
            portfolio_id=run.portfolio_id,
            n_paths=run.n_paths,
            n_steps=run.n_steps,
            random_seed=run.random_seed,
            generator_algorithm=run.generator_algorithm,
            matrix_was_repaired=run.matrix_was_repaired,
            status=run.status,
            execution_duration_ms=run.execution_duration_ms,
            input_parameters_hash=run.input_parameters_hash,
            executed_at=run.executed_at,
            summary=SimulationSummaryResponse.model_validate(run.summary) if run.summary else None,
            risk_metrics=[RiskMetricResponse.model_validate(m) for m in run.risk_metrics],
            instrument_results=[InstrumentResultResponse.model_validate(i) for i in run.instrument_results],
            narrative=narrative
        )
    except ValueError as ve:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")


@router.get("/runs/{run_code}", response_model=SimulationRunResponse)
async def get_simulation_run(
    run_code: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Retrieves full simulation results by run code or ID.
    """
    service = MonteCarloService(session)
    run = await service.get_simulation_run(run_code)
    if not run:
        raise HTTPException(status_code=404, detail=f"Simulation run '{run_code}' not found")

    narrative = (
        f"Monte Carlo simulation '{run.run_code}' completed with {run.n_paths} paths. "
        f"Portfolio baseline value: ${run.summary.baseline_portfolio_value:,.2f}."
    ) if run.summary else None

    return SimulationRunResponse(
        run_id=run.id,
        scenario_code=run.scenario.scenario_code,
        run_code=run.run_code,
        portfolio_id=run.portfolio_id,
        n_paths=run.n_paths,
        n_steps=run.n_steps,
        random_seed=run.random_seed,
        generator_algorithm=run.generator_algorithm,
        matrix_was_repaired=run.matrix_was_repaired,
        status=run.status,
        execution_duration_ms=run.execution_duration_ms,
        input_parameters_hash=run.input_parameters_hash,
        executed_at=run.executed_at,
        summary=SimulationSummaryResponse.model_validate(run.summary) if run.summary else None,
        risk_metrics=[RiskMetricResponse.model_validate(m) for m in run.risk_metrics],
        instrument_results=[InstrumentResultResponse.model_validate(i) for i in run.instrument_results],
        narrative=narrative
    )

