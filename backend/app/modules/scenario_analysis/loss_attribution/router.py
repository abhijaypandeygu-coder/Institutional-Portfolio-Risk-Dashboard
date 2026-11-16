"""
FastAPI router for M10.09 Stress Loss Attribution.
Mounts endpoints for attribution configuration CRUD, execution, position/sector/industry/factor/interaction reporting.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.scenario_analysis.loss_attribution.schemas.attribution_schemas import (
    AttributionCreate,
    AttributionResponse,
    AttributionExecutionRequest,
    AttributionRunResponse,
    PositionContributionResponse,
    SectorContributionResponse,
    IndustryContributionResponse,
    FactorContributionResponse,
    InteractionEffectResponse,
)
from backend.app.modules.scenario_analysis.loss_attribution.services.attribution_service import (
    StressLossAttributionService,
)

router = APIRouter(
    prefix="/api/v1/stress-loss-attributions",
    tags=["M10.09 — Stress Loss Attribution"]
)


@router.post("/", response_model=AttributionResponse, status_code=status.HTTP_201_CREATED)
async def create_attribution(
    payload: AttributionCreate,
    session: AsyncSession = Depends(get_db)
):
    """
    Creates a new stress loss attribution configuration.
    """
    service = StressLossAttributionService(session)
    try:
        created = await service.create_attribution(payload)
        await session.commit()
        return created
    except ValueError as ve:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create attribution: {str(e)}")


@router.get("/", response_model=List[AttributionResponse])
async def list_attributions(
    portfolio_id: Optional[str] = Query(None, description="Filter by portfolio ID"),
    session: AsyncSession = Depends(get_db)
):
    """
    Lists saved stress loss attribution configurations.
    """
    service = StressLossAttributionService(session)
    return await service.list_attributions(portfolio_id=portfolio_id)


@router.get("/{attribution_code}", response_model=AttributionResponse)
async def get_attribution(
    attribution_code: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Retrieves an attribution configuration by code or ID.
    """
    service = StressLossAttributionService(session)
    attr = await service.get_attribution(attribution_code)
    if not attr:
        raise HTTPException(status_code=404, detail=f"Attribution '{attribution_code}' not found")
    return attr


@router.post("/{attribution_code}/execute", response_model=AttributionRunResponse)
async def execute_attribution(
    attribution_code: str,
    payload: AttributionExecutionRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Executes stress loss attribution across position, sector, industry, factor, and interaction dimensions.
    """
    service = StressLossAttributionService(session)
    try:
        run = await service.execute_attribution(attribution_code, payload)
        await session.commit()

        narrative = (
            f"Stress Loss Attribution '{run.run_code}' decomposed total stressed P&L of "
            f"${run.authoritative_total_pnl:,.2f} across {len(run.position_contributions)} positions. "
            f"Loss HHI is {run.loss_hhi:.4f} with {run.effective_contributor_count:.1f} effective loss drivers. "
            f"Reconciliation status: {'RECONCILED' if run.is_reconciled else 'UNRECONCILED'} (residual: ${run.residual_amount:,.2f})."
        )

        return AttributionRunResponse(
            id=run.id,
            attribution_id=run.attribution_id,
            run_code=run.run_code,
            scenario_run_id=run.scenario_run_id,
            execution_status=run.execution_status,
            attribution_completeness=run.attribution_completeness,
            started_at=run.started_at,
            completed_at=run.completed_at,
            duration_ms=run.duration_ms,
            authoritative_total_pnl=run.authoritative_total_pnl,
            explained_pnl=run.explained_pnl,
            residual_amount=run.residual_amount,
            is_reconciled=run.is_reconciled,
            loss_hhi=run.loss_hhi,
            effective_contributor_count=run.effective_contributor_count,
            position_contributions=[PositionContributionResponse.model_validate(p) for p in run.position_contributions],
            sector_contributions=[SectorContributionResponse.model_validate(s) for s in run.sector_contributions],
            industry_contributions=[IndustryContributionResponse.model_validate(i) for i in run.industry_contributions],
            factor_contributions=[FactorContributionResponse.model_validate(f) for f in run.factor_contributions],
            interaction_effects=[InteractionEffectResponse.model_validate(x) for x in run.interaction_effects],
            narrative=narrative
        )
    except ValueError as ve:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Attribution execution failed: {str(e)}")


@router.get("/runs/{run_code}", response_model=AttributionRunResponse)
async def get_attribution_run(
    run_code: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Retrieves full attribution execution results by run code or ID.
    """
    service = StressLossAttributionService(session)
    run = await service.get_run(run_code)
    if not run:
        raise HTTPException(status_code=404, detail=f"Attribution run '{run_code}' not found")

    narrative = (
        f"Attribution '{run.run_code}' completed with {len(run.position_contributions)} positions. "
        f"Residual: ${run.residual_amount:,.2f}."
    )

    return AttributionRunResponse(
        id=run.id,
        attribution_id=run.attribution_id,
        run_code=run.run_code,
        scenario_run_id=run.scenario_run_id,
        execution_status=run.execution_status,
        attribution_completeness=run.attribution_completeness,
        started_at=run.started_at,
        completed_at=run.completed_at,
        duration_ms=run.duration_ms,
        authoritative_total_pnl=run.authoritative_total_pnl,
        explained_pnl=run.explained_pnl,
        residual_amount=run.residual_amount,
        is_reconciled=run.is_reconciled,
        loss_hhi=run.loss_hhi,
        effective_contributor_count=run.effective_contributor_count,
        position_contributions=[PositionContributionResponse.model_validate(p) for p in run.position_contributions],
        sector_contributions=[SectorContributionResponse.model_validate(s) for s in run.sector_contributions],
        industry_contributions=[IndustryContributionResponse.model_validate(i) for i in run.industry_contributions],
        factor_contributions=[FactorContributionResponse.model_validate(f) for f in run.factor_contributions],
        interaction_effects=[InteractionEffectResponse.model_validate(x) for x in run.interaction_effects],
        narrative=narrative
    )


@router.get("/runs/{run_code}/positions", response_model=List[PositionContributionResponse])
async def get_run_positions(
    run_code: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Retrieves position-level loss contributions from an execution run.
    """
    service = StressLossAttributionService(session)
    run = await service.get_run(run_code)
    if not run:
        raise HTTPException(status_code=404, detail=f"Attribution run '{run_code}' not found")
    return [PositionContributionResponse.model_validate(p) for p in run.position_contributions]


@router.get("/runs/{run_code}/sectors", response_model=List[SectorContributionResponse])
async def get_run_sectors(
    run_code: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Retrieves sector-level loss contributions from an execution run.
    """
    service = StressLossAttributionService(session)
    run = await service.get_run(run_code)
    if not run:
        raise HTTPException(status_code=404, detail=f"Attribution run '{run_code}' not found")
    return [SectorContributionResponse.model_validate(s) for s in run.sector_contributions]


@router.get("/runs/{run_code}/factors", response_model=List[FactorContributionResponse])
async def get_run_factors(
    run_code: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Retrieves economic factor shock contributions from an execution run.
    """
    service = StressLossAttributionService(session)
    run = await service.get_run(run_code)
    if not run:
        raise HTTPException(status_code=404, detail=f"Attribution run '{run_code}' not found")
    return [FactorContributionResponse.model_validate(f) for f in run.factor_contributions]

