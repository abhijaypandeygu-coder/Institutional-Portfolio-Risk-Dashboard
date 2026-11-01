from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.instrument_reference_data.price_reference.schemas import (
    PriceReferenceObservationCreate,
    PriceReferenceObservationResponse,
    ResolvePreviousCloseRequest,
    PreviousCloseResolutionResponse,
    RegisterCurrencyConversionRequest,
    CurrencyConversionResponse
)
from backend.app.modules.instrument_reference_data.price_reference.services.service import PriceReferenceService

router = APIRouter(prefix="/price-references", tags=["Price Reference"])


@router.post("/observations", response_model=PriceReferenceObservationResponse, status_code=status.HTTP_201_CREATED)
async def register_observation(
    payload: PriceReferenceObservationCreate,
    db: AsyncSession = Depends(get_db)
):
    service = PriceReferenceService(db)
    try:
        return await service.register_observation(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/observations/{reference_id}", response_model=PriceReferenceObservationResponse)
async def get_observation(
    reference_id: str,
    db: AsyncSession = Depends(get_db)
):
    service = PriceReferenceService(db)
    obs = await service.repo.get_observation_by_id(reference_id)
    if not obs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Observation '{reference_id}' not found.")
    return obs


@router.get("/instrument/{instrument_id}", response_model=List[PriceReferenceObservationResponse])
async def list_observations_by_instrument(
    instrument_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    service = PriceReferenceService(db)
    return await service.repo.list_observations_by_instrument(instrument_id, limit=limit, offset=offset)


@router.post("/previous-close/resolve", response_model=PreviousCloseResolutionResponse)
async def resolve_previous_close(
    req: ResolvePreviousCloseRequest,
    db: AsyncSession = Depends(get_db)
):
    service = PriceReferenceService(db)
    try:
        return await service.resolve_previous_close(req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/currency-conversions/register", response_model=CurrencyConversionResponse, status_code=status.HTTP_201_CREATED)
async def register_currency_conversion(
    payload: RegisterCurrencyConversionRequest,
    db: AsyncSession = Depends(get_db)
):
    service = PriceReferenceService(db)
    try:
        conv = await service.register_currency_conversion(payload)
        return conv
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

