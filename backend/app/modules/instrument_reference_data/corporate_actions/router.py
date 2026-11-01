from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.instrument_reference_data.corporate_actions.schemas import (
    CorporateActionCreate,
    CorporateActionUpdate,
    CorporateActionResponse,
    CalculateAdjustmentRequest,
    AdjustmentResultResponse
)
from backend.app.modules.instrument_reference_data.corporate_actions.services.service import CorporateActionService

router = APIRouter(prefix="/corporate-actions", tags=["Corporate Actions"])


@router.post("", response_model=CorporateActionResponse, status_code=status.HTTP_201_CREATED)
async def create_corporate_action(
    payload: CorporateActionCreate,
    db: AsyncSession = Depends(get_db)
):
    service = CorporateActionService(db)
    try:
        action = await service.create_corporate_action(payload)
        return action
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{event_id}", response_model=CorporateActionResponse)
async def get_corporate_action(
    event_id: str,
    db: AsyncSession = Depends(get_db)
):
    service = CorporateActionService(db)
    action = await service.repo.get_by_id(event_id)
    if not action:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Corporate action '{event_id}' not found.")
    return action


@router.put("/{event_id}", response_model=CorporateActionResponse)
async def update_corporate_action(
    event_id: str,
    payload: CorporateActionUpdate,
    db: AsyncSession = Depends(get_db)
):
    service = CorporateActionService(db)
    try:
        updated = await service.update_corporate_action(event_id, payload)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/instrument/{instrument_id}", response_model=List[CorporateActionResponse])
async def list_actions_by_instrument(
    instrument_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    service = CorporateActionService(db)
    return await service.repo.list_by_instrument(instrument_id, limit=limit, offset=offset)


@router.post("/calculate-adjustments", response_model=AdjustmentResultResponse)
async def calculate_adjustments(
    req: CalculateAdjustmentRequest,
    db: AsyncSession = Depends(get_db)
):
    service = CorporateActionService(db)
    try:
        return await service.calculate_adjustments(req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

