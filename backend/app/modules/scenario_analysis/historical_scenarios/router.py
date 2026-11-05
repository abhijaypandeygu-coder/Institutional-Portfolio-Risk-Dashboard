"""
Historical Scenarios FastAPI Router (M10.01).
Endpoints for maintaining historical events library, adding validated observations,
executing portfolio replays, retrieving positions, warnings, paths, and difference reports.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from .services.scenario_service import HistoricalScenariosService
from .schemas.scenario_schemas import (
    HistoricalEventCreate,
    HistoricalEventResponse,
    HistoricalObservationInput,
    ReplayExecutionRequest,
    ReplayRunSummaryResponse,
    HistoricalDifferenceReport
)

router = APIRouter(
    prefix="/api/v1/scenarios/historical",
    tags=["M10.01 Historical Scenarios"]
)


@router.post("/events", response_model=HistoricalEventResponse, status_code=status.HTTP_201_CREATED)
async def create_historical_event(
    req: HistoricalEventCreate,
    db: AsyncSession = Depends(get_db)
):
    service = HistoricalScenariosService(db)
    return await service.create_event(req)


@router.get("/events", response_model=List[HistoricalEventResponse])
async def list_historical_events(
    category: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    service = HistoricalScenariosService(db)
    events = await service.repo.list_events(category=category, region=region, status=status, limit=limit)
    return [HistoricalEventResponse.model_validate(e) for e in events]


@router.get("/events/{event_id}", response_model=HistoricalEventResponse)
async def get_historical_event(
    event_id: str,
    db: AsyncSession = Depends(get_db)
):
    service = HistoricalScenariosService(db)
    event = await service.repo.get_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    return HistoricalEventResponse.model_validate(event)


@router.post("/events/{event_id}/observations", status_code=status.HTTP_201_CREATED)
async def add_event_observations(
    event_id: str,
    observations: List[HistoricalObservationInput],
    db: AsyncSession = Depends(get_db)
):
    service = HistoricalScenariosService(db)
    count = await service.add_observations(event_id, observations)
    return {"message": f"Successfully ingested {count} observations for event {event_id}"}


@router.post("/replays", response_model=ReplayRunSummaryResponse, status_code=status.HTTP_200_OK)
async def execute_replay(
    req: ReplayExecutionRequest,
    db: AsyncSession = Depends(get_db)
):
    service = HistoricalScenariosService(db)
    try:
        return await service.execute_replay(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/replays/{replay_id}/comparison", response_model=HistoricalDifferenceReport)
async def get_replay_difference_report(
    replay_id: str,
    db: AsyncSession = Depends(get_db)
):
    service = HistoricalScenariosService(db)
    try:
        return await service.get_historical_difference_report(replay_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

