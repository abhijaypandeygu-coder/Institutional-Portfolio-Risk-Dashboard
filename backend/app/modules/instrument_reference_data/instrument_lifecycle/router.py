from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.instrument_reference_data.instrument_lifecycle.schemas import (
    RegisterListingLifecycleRequest,
    ListingLifecycleResponse,
    RegisterSuspensionRequest,
    RegisterResumptionRequest,
    RegisterDelistingRequest,
    LifecycleEventResponse,
    InstrumentLifecycleSummary
)
from backend.app.modules.instrument_reference_data.instrument_lifecycle.services.service import InstrumentLifecycleService
from backend.app.modules.instrument_reference_data.instrument_lifecycle.state_machine.transitions import ListingLifecycleStatus

router = APIRouter(prefix="/instrument-lifecycle", tags=["Instrument Lifecycle"])


@router.post("/listings", response_model=ListingLifecycleResponse, status_code=status.HTTP_201_CREATED)
async def register_listing_lifecycle(
    req: RegisterListingLifecycleRequest,
    db: AsyncSession = Depends(get_db)
):
    service = InstrumentLifecycleService(db)
    try:
        rec = await service.register_listing_lifecycle(req)
        return rec
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/listings/{listing_id}", response_model=ListingLifecycleResponse)
async def get_listing_lifecycle(
    listing_id: str,
    db: AsyncSession = Depends(get_db)
):
    service = InstrumentLifecycleService(db)
    rec = await service.repo.get_listing_record(listing_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Listing '{listing_id}' not found.")
    return rec


@router.get("/listings/{listing_id}/history", response_model=List[LifecycleEventResponse])
async def get_listing_event_history(
    listing_id: str,
    db: AsyncSession = Depends(get_db)
):
    service = InstrumentLifecycleService(db)
    return await service.repo.list_events_by_listing(listing_id)


@router.get("/listings/{listing_id}/status/as-of")
async def get_listing_status_as_of(
    listing_id: str,
    as_of_date: date = Query(..., description="Query date in YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db)
):
    service = InstrumentLifecycleService(db)
    status_val = await service.repo.get_historical_status_as_of(listing_id, as_of_date)
    return {
        "listing_id": listing_id,
        "as_of_date": as_of_date,
        "historical_status": status_val.value if status_val else "UNKNOWN"
    }


@router.post("/suspensions", status_code=status.HTTP_201_CREATED)
async def register_suspension(
    req: RegisterSuspensionRequest,
    db: AsyncSession = Depends(get_db)
):
    service = InstrumentLifecycleService(db)
    try:
        return await service.register_suspension(req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/resumptions", status_code=status.HTTP_201_CREATED)
async def register_resumption(
    req: RegisterResumptionRequest,
    db: AsyncSession = Depends(get_db)
):
    service = InstrumentLifecycleService(db)
    try:
        return await service.register_resumption(req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/delistings", status_code=status.HTTP_201_CREATED)
async def register_delisting(
    req: RegisterDelistingRequest,
    db: AsyncSession = Depends(get_db)
):
    service = InstrumentLifecycleService(db)
    try:
        return await service.register_delisting(req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/instruments/{instrument_id}/summary", response_model=InstrumentLifecycleSummary)
async def get_instrument_summary(
    instrument_id: str,
    db: AsyncSession = Depends(get_db)
):
    service = InstrumentLifecycleService(db)
    return await service.get_instrument_summary(instrument_id)
