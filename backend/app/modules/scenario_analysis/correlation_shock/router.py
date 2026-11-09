"""
M10.05 Correlation Shock FastAPI Router.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.scenario_analysis.correlation_shock.schemas import (
    CorrelationShockScenarioCreate,
    CorrelationShockScenarioResponse,
    MatrixValidateRequest,
    MatrixValidateResponse,
    ExecuteScenarioRequest,
    ExecutionResponse,
    PairRuleCreate,
    ScopeMemberCreate,
)
from backend.app.modules.scenario_analysis.correlation_shock.services import (
    CorrelationShockService,
)

router = APIRouter(
    prefix="/api/v1/scenarios/correlation-shock",
    tags=["M10.05 - Correlation Shock"],
)


@router.post("", response_model=CorrelationShockScenarioResponse, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    payload: CorrelationShockScenarioCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new correlation shock scenario with version 1 and optional scope/pair rules.
    """
    service = CorrelationShockService(db)
    scenario = await service.create_scenario(payload)
    latest_ver = scenario.versions[-1].version_number if scenario.versions else 1
    return CorrelationShockScenarioResponse(
        id=scenario.id,
        scenario_code=scenario.scenario_code,
        name=scenario.name,
        description=scenario.description,
        scenario_scope=scenario.scenario_scope,
        portfolio_id=scenario.portfolio_id,
        scenario_category=scenario.scenario_category,
        status=scenario.status,
        created_by=scenario.created_by,
        created_at=scenario.created_at,
        updated_at=scenario.updated_at,
        latest_version_number=latest_ver,
    )


@router.get("", response_model=List[CorrelationShockScenarioResponse])
async def list_scenarios(
    portfolio_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    List configured correlation shock scenarios.
    """
    service = CorrelationShockService(db)
    scenarios = await service.list_scenarios(portfolio_id=portfolio_id)
    return [
        CorrelationShockScenarioResponse(
            id=s.id,
            scenario_code=s.scenario_code,
            name=s.name,
            description=s.description,
            scenario_scope=s.scenario_scope,
            portfolio_id=s.portfolio_id,
            scenario_category=s.scenario_category,
            status=s.status,
            created_by=s.created_by,
            created_at=s.created_at,
            updated_at=s.updated_at,
            latest_version_number=s.versions[-1].version_number if s.versions else 1,
        )
        for s in scenarios
    ]


@router.get("/{scenario_id}", response_model=CorrelationShockScenarioResponse)
async def get_scenario(
    scenario_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve details of a correlation shock scenario by ID.
    """
    service = CorrelationShockService(db)
    scenario = await service.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return CorrelationShockScenarioResponse(
        id=scenario.id,
        scenario_code=scenario.scenario_code,
        name=scenario.name,
        description=scenario.description,
        scenario_scope=scenario.scenario_scope,
        portfolio_id=scenario.portfolio_id,
        scenario_category=scenario.scenario_category,
        status=scenario.status,
        created_by=scenario.created_by,
        created_at=scenario.created_at,
        updated_at=scenario.updated_at,
        latest_version_number=scenario.versions[-1].version_number if scenario.versions else 1,
    )


@router.post("/validate-matrix", response_model=MatrixValidateResponse)
async def validate_matrix(
    payload: MatrixValidateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Validate correlation matrix properties (symmetry, diagonal, bounds, eigenvalues, rank, condition number).
    """
    service = CorrelationShockService(db)
    return service.validate_matrix(
        matrix_data=payload.matrix_data,
        symmetry_tol=payload.symmetry_tol,
        psd_tol=payload.psd_tol,
    )


@router.post("/{scenario_id}/execute", response_model=ExecutionResponse)
async def execute_scenario(
    scenario_id: str,
    payload: ExecuteScenarioRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Execute a correlation shock scenario against a portfolio snapshot or custom holding inputs.
    Calculates raw transformations, matrix validation, controlled repair, stressed covariance,
    recalculated portfolio risk, and exact Euler risk contributions.
    """
    service = CorrelationShockService(db)
    try:
        return await service.execute_scenario(scenario_id, payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")
