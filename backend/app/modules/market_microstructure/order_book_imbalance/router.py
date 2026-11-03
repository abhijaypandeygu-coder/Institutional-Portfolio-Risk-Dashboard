"""
FastAPI Router for M09.08 Order Book Imbalance.
Endpoints:
- POST /api/v1/market-microstructure/order-book-imbalance/calculate
- GET /api/v1/market-microstructure/order-book-imbalance/{instrument_id}/current
- POST /api/v1/market-microstructure/order-book-imbalance/configs
- POST /api/v1/market-microstructure/order-book-imbalance/persistence
- POST /api/v1/market-microstructure/order-book-imbalance/reversals
- POST /api/v1/market-microstructure/order-book-imbalance/venues
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.market_microstructure.order_book_imbalance.services.imbalance_service import (
    OrderBookImbalanceService,
)
from backend.app.modules.market_microstructure.order_book_imbalance.schemas.imbalance_schemas import (
    ImbalanceConfigCreateRequest,
    ImbalanceConfigResponse,
    ImbalanceCalculateRequest,
    ImbalanceSnapshotResponse,
    PersistenceAnalysisRequest,
    PersistenceResponse,
    ReversalDetectionRequest,
    ReversalDetectionResponse,
    VenueComparisonRequest,
    VenueComparisonResponse,
)

router = APIRouter(
    prefix="/api/v1/market-microstructure/order-book-imbalance",
    tags=["M09.08 - Order Book Imbalance Analytics"],
)


@router.post(
    "/calculate",
    response_model=ImbalanceSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Calculate and persist order book imbalance snapshot",
)
async def calculate_imbalance(
    req: ImbalanceCalculateRequest,
    db: AsyncSession = Depends(get_db),
):
    if not req.levels:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order book levels cannot be empty.",
        )
    service = OrderBookImbalanceService(db)
    return await service.calculate_and_save_imbalance(req)


@router.get(
    "/{instrument_id}/current",
    response_model=ImbalanceSnapshotResponse,
    summary="Get latest order book imbalance snapshot for an instrument",
)
async def get_current_imbalance(
    instrument_id: str,
    venue_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    service = OrderBookImbalanceService(db)
    snap = await service.get_latest_imbalance(instrument_id, venue_id)
    if not snap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No imbalance snapshot found for instrument {instrument_id}.",
        )
    return snap


@router.post(
    "/configs",
    response_model=ImbalanceConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create custom order book imbalance configuration",
)
async def create_imbalance_config(
    req: ImbalanceConfigCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    service = OrderBookImbalanceService(db)
    return await service.create_config(req)


@router.post(
    "/persistence",
    response_model=PersistenceResponse,
    summary="Analyze state persistence over an observation series",
)
async def analyze_persistence(
    req: PersistenceAnalysisRequest,
    db: AsyncSession = Depends(get_db),
):
    service = OrderBookImbalanceService(db)
    return await service.analyze_persistence(req)


@router.post(
    "/reversals",
    response_model=ReversalDetectionResponse,
    summary="Detect state reversals and transitions with hysteresis",
)
async def detect_reversals(
    req: ReversalDetectionRequest,
    db: AsyncSession = Depends(get_db),
):
    service = OrderBookImbalanceService(db)
    return await service.detect_reversals(req)


@router.post(
    "/venues",
    response_model=VenueComparisonResponse,
    summary="Compare order book imbalance across multiple venues",
)
async def compare_venues(
    req: VenueComparisonRequest,
    db: AsyncSession = Depends(get_db),
):
    service = OrderBookImbalanceService(db)
    return await service.compare_venues(req)

