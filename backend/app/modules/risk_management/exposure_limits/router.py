"""
FastAPI Router for M06.08 Exposure Limits.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.risk_management.exposure_limits.models import (
    ExposureLimitCategory,
)
from backend.app.modules.risk_management.exposure_limits.schemas import (
    ExposureLimitConfigCreateRequest,
    ExposureLimitConfigResponse,
    ExposureLimitEvaluateRequest,
    ExposureLimitEvaluationSummaryResponse,
    ExposureLimitBreachHistoryItemResponse,
    ExposureLimitSimulateRequest,
    ExposureLimitSimulationResponse,
)
from backend.app.modules.risk_management.exposure_limits.services.service import (
    ExposureLimitService,
)

router = APIRouter(prefix="/risk/exposure-limits", tags=["M06.08 - Exposure Limits"])


@router.post("/configs", response_model=ExposureLimitConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_exposure_limit_config(
    req: ExposureLimitConfigCreateRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Create an effective-dated exposure limit configuration.
    """
    service = ExposureLimitService(session)
    return await service.create_limit_config(req)


@router.get("/configs", response_model=List[ExposureLimitConfigResponse], status_code=status.HTTP_200_OK)
async def list_exposure_limit_configs(
    portfolio_id: Optional[str] = None,
    portfolio_group_id: Optional[str] = None,
    limit_category: Optional[ExposureLimitCategory] = None,
    session: AsyncSession = Depends(get_db),
):
    """
    List active exposure limit configurations.
    """
    service = ExposureLimitService(session)
    configs = await service.repo.list_active_limit_configs(
        portfolio_id=portfolio_id,
        portfolio_group_id=portfolio_group_id,
        limit_category=limit_category,
    )
    return [ExposureLimitConfigResponse.model_validate(c) for c in configs]


@router.post("/evaluate", response_model=ExposureLimitEvaluationSummaryResponse, status_code=status.HTTP_200_OK)
async def evaluate_exposure_limits(
    req: ExposureLimitEvaluateRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Evaluate all active exposure limits against current authoritative exposures.
    """
    service = ExposureLimitService(session)
    return await service.evaluate_limits(req)


@router.get("/breaches", response_model=List[ExposureLimitBreachHistoryItemResponse], status_code=status.HTTP_200_OK)
async def list_breach_history(
    portfolio_id: Optional[str] = None,
    limit_id: Optional[str] = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_db),
):
    """
    Retrieve audit history of limit breach and warning transitions.
    """
    service = ExposureLimitService(session)
    history = await service.repo.list_breach_history(
        portfolio_id=portfolio_id,
        limit_id=limit_id,
        limit=limit,
    )
    return [ExposureLimitBreachHistoryItemResponse.model_validate(h) for h in history]


@router.post("/simulate", response_model=ExposureLimitSimulationResponse, status_code=status.HTTP_200_OK)
async def simulate_hypothetical_exposure(
    req: ExposureLimitSimulateRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Pre-trade / hypothetical limit evaluation without modifying portfolio positions.
    """
    service = ExposureLimitService(session)
    try:
        return await service.simulate_hypothetical_exposure(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
