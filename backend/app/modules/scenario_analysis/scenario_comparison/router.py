"""
FastAPI router for M10.08 Scenario Comparison.
Mounts endpoints for comparison CRUD, scenario membership, compatibility validation,
execution, ranking retrieval, sensitivity analysis, attribution, and export.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.scenario_analysis.scenario_comparison.schemas.comparison_schemas import (
    ComparisonCreate,
    ComparisonUpdate,
    ComparisonResponse,
    ScenarioMemberCreate,
    ScenarioMemberResponse,
    ComparisonExecutionRequest,
    ComparisonRunResponse,
    RankingResponse,
    SensitivityResponse,
    AttributionResponse,
    MetricResultResponse,
)
from backend.app.modules.scenario_analysis.scenario_comparison.services.comparison_service import (
    ScenarioComparisonService,
)

router = APIRouter(
    prefix="/api/v1/scenario-comparisons",
    tags=["M10.08 — Scenario Comparison"]
)


@router.post("/", response_model=ComparisonResponse, status_code=status.HTTP_201_CREATED)
async def create_comparison(
    payload: ComparisonCreate,
    session: AsyncSession = Depends(get_db)
):
    """
    Creates a new scenario comparison definition with optional initial scenario members.
    """
    service = ScenarioComparisonService(session)
    try:
        created = await service.create_comparison(payload)
        await session.commit()
        return created
    except ValueError as ve:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create comparison: {str(e)}")


@router.get("/", response_model=List[ComparisonResponse])
async def list_comparisons(
    portfolio_id: Optional[str] = Query(None, description="Filter by portfolio ID"),
    session: AsyncSession = Depends(get_db)
):
    """
    Lists saved scenario comparisons.
    """
    service = ScenarioComparisonService(session)
    return await service.list_comparisons(portfolio_id=portfolio_id)


@router.get("/{comparison_code}", response_model=ComparisonResponse)
async def get_comparison(
    comparison_code: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Retrieves comparison configuration by code or ID.
    """
    service = ScenarioComparisonService(session)
    comp = await service.get_comparison(comparison_code)
    if not comp:
        raise HTTPException(status_code=404, detail=f"Comparison '{comparison_code}' not found")
    return comp


@router.post("/{comparison_code}/members", response_model=ScenarioMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_member(
    comparison_code: str,
    member_in: ScenarioMemberCreate,
    session: AsyncSession = Depends(get_db)
):
    """
    Adds a scenario execution run to the comparison set.
    """
    service = ScenarioComparisonService(session)
    try:
        member = await service.add_member(comparison_code, member_in)
        await session.commit()
        return member
    except ValueError as ve:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to add member: {str(e)}")


@router.delete("/{comparison_code}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    comparison_code: str,
    member_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Removes a scenario run from the comparison set.
    """
    service = ScenarioComparisonService(session)
    try:
        await service.remove_member(comparison_code, member_id)
        await session.commit()
    except ValueError as ve:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to remove member: {str(e)}")


@router.post("/{comparison_code}/validate")
async def validate_comparison(
    comparison_code: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Validates scenario compatibility before execution.
    """
    service = ScenarioComparisonService(session)
    try:
        return await service.validate_comparison(comparison_code)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))


@router.post("/{comparison_code}/execute", response_model=ComparisonRunResponse)
async def execute_comparison(
    comparison_code: str,
    payload: ComparisonExecutionRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Executes comparative analysis across selected scenarios and baseline.
    Computes performance differences, rankings, assumption sensitivity, and attribution.
    """
    service = ScenarioComparisonService(session)
    try:
        run = await service.execute_comparison(comparison_code, payload)
        await session.commit()

        narrative = (
            f"Scenario comparison '{run.run_code}' executed across {len(run.metric_results)} scenarios. "
            f"Top ranked scenario is '{run.rankings[0].scenario_name}' by {run.rankings[0].ranking_metric} "
            f"with raw value {run.rankings[0].raw_metric_value:,.2f}."
        ) if run.rankings else None

        return ComparisonRunResponse(
            id=run.id,
            comparison_id=run.comparison_id,
            run_code=run.run_code,
            configuration_version=run.configuration_version,
            baseline_snapshot_id=run.baseline_snapshot_id,
            execution_status=run.execution_status,
            started_at=run.started_at,
            completed_at=run.completed_at,
            duration_ms=run.duration_ms,
            application_version=run.application_version,
            calculation_engine_version=run.calculation_engine_version,
            validation_summary=run.validation_summary,
            metric_results=[MetricResultResponse.model_validate(m) for m in run.metric_results],
            rankings=[RankingResponse.model_validate(r) for r in run.rankings],
            sensitivities=[SensitivityResponse.model_validate(s) for s in run.sensitivities],
            attributions=[AttributionResponse.model_validate(a) for a in run.attributions],
            narrative=narrative
        )
    except ValueError as ve:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Comparison execution failed: {str(e)}")


@router.get("/runs/{run_code}", response_model=ComparisonRunResponse)
async def get_comparison_run(
    run_code: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Retrieves saved immutable comparison execution results by run code or ID.
    """
    service = ScenarioComparisonService(session)
    run = await service.get_run(run_code)
    if not run:
        raise HTTPException(status_code=404, detail=f"Comparison run '{run_code}' not found")

    narrative = (
        f"Saved comparison '{run.run_code}' contains {len(run.metric_results)} scenarios."
    )

    return ComparisonRunResponse(
        id=run.id,
        comparison_id=run.comparison_id,
        run_code=run.run_code,
        configuration_version=run.configuration_version,
        baseline_snapshot_id=run.baseline_snapshot_id,
        execution_status=run.execution_status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        duration_ms=run.duration_ms,
        application_version=run.application_version,
        calculation_engine_version=run.calculation_engine_version,
        validation_summary=run.validation_summary,
        metric_results=[MetricResultResponse.model_validate(m) for m in run.metric_results],
        rankings=[RankingResponse.model_validate(r) for r in run.rankings],
        sensitivities=[SensitivityResponse.model_validate(s) for s in run.sensitivities],
        attributions=[AttributionResponse.model_validate(a) for a in run.attributions],
        narrative=narrative
    )


@router.get("/runs/{run_code}/rankings", response_model=List[RankingResponse])
async def get_run_rankings(
    run_code: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Retrieves scenario rankings from a comparison run.
    """
    service = ScenarioComparisonService(session)
    run = await service.get_run(run_code)
    if not run:
        raise HTTPException(status_code=404, detail=f"Comparison run '{run_code}' not found")
    return [RankingResponse.model_validate(r) for r in run.rankings]


@router.get("/runs/{run_code}/sensitivities", response_model=List[SensitivityResponse])
async def get_run_sensitivities(
    run_code: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Retrieves assumption sensitivities from a comparison run.
    """
    service = ScenarioComparisonService(session)
    run = await service.get_run(run_code)
    if not run:
        raise HTTPException(status_code=404, detail=f"Comparison run '{run_code}' not found")
    return [SensitivityResponse.model_validate(s) for s in run.sensitivities]


@router.get("/runs/{run_code}/attribution", response_model=List[AttributionResponse])
async def get_run_attributions(
    run_code: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Retrieves difference attribution from a comparison run.
    """
    service = ScenarioComparisonService(session)
    run = await service.get_run(run_code)
    if not run:
        raise HTTPException(status_code=404, detail=f"Comparison run '{run_code}' not found")
    return [AttributionResponse.model_validate(a) for a in run.attributions]

