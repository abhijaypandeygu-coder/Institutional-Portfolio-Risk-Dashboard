"""
FastAPI Router for M09.07 Position Liquidation.
Endpoints:
- POST /api/v1/market-microstructure/liquidation/plans (create versioned liquidation plan)
- GET /api/v1/market-microstructure/liquidation/plans/{plan_id} (retrieve plan)
- GET /api/v1/market-microstructure/liquidation/plans/{plan_id}/partial-comparison (partial target comparison)
- POST /api/v1/market-microstructure/liquidation/portfolio (portfolio concurrent / sequential analysis)
- POST /api/v1/market-microstructure/liquidation/calibrations (record model calibration)
- GET /api/v1/market-microstructure/liquidation/calibrations (list calibrations)
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.market_microstructure.position_liquidation.services.liquidation_service import (
    PositionLiquidationService,
)
from backend.app.modules.market_microstructure.position_liquidation.schemas.liquidation_schemas import (
    LiquidationPlanCreateRequest,
    LiquidationPlanResponse,
    PartialComparisonResponse,
    PortfolioLiquidationRequest,
    PortfolioLiquidationResponse,
    CalibrationRunCreateRequest,
    CalibrationRunResponse,
)

router = APIRouter(
    prefix="/api/v1/market-microstructure/liquidation",
    tags=["M09.07 - Position Liquidation"],
)


@router.post(
    "/plans",
    response_model=LiquidationPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a position liquidation plan",
)
async def create_liquidation_plan(
    req: LiquidationPlanCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    if req.starting_signed_quantity == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="NO_POSITION_TO_LIQUIDATE: Starting quantity cannot be zero.",
        )
    service = PositionLiquidationService(db)
    return await service.create_liquidation_plan(req)


@router.get(
    "/plans/{plan_id}",
    response_model=LiquidationPlanResponse,
    summary="Retrieve a liquidation plan by ID",
)
async def get_liquidation_plan(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = PositionLiquidationService(db)
    res = await service.get_plan(plan_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Liquidation plan {plan_id} not found.",
        )
    return res


@router.get(
    "/plans/{plan_id}/partial-comparison",
    response_model=PartialComparisonResponse,
    summary="Compare partial reduction targets for a liquidation plan",
)
async def get_partial_comparison(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = PositionLiquidationService(db)
    res = await service.get_partial_comparison(plan_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Liquidation plan {plan_id} not found.",
        )
    return res


@router.post(
    "/portfolio",
    response_model=PortfolioLiquidationResponse,
    summary="Run portfolio-level liquidation analysis across multiple positions",
)
async def run_portfolio_liquidation(
    req: PortfolioLiquidationRequest,
    db: AsyncSession = Depends(get_db),
):
    service = PositionLiquidationService(db)
    return await service.run_portfolio_liquidation(req)


@router.post(
    "/calibrations",
    response_model=CalibrationRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record historical model calibration run",
)
async def record_calibration(
    req: CalibrationRunCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    service = PositionLiquidationService(db)
    return await service.record_calibration_run(req)


@router.get(
    "/calibrations",
    response_model=List[CalibrationRunResponse],
    summary="List historical model calibration runs",
)
async def list_calibrations(
    db: AsyncSession = Depends(get_db),
):
    service = PositionLiquidationService(db)
    return await service.list_calibration_runs()

