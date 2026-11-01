"""
Module 02: Market Data Ingestion Engine - FastAPI REST Router.
Provides endpoints for ingestion control, health, order book inspection,
historical backfill, and operational telemetry.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import AuthenticatedUser, UserRole, require_role
from backend.app.modules.market_data_ingestion.adapters.registry import ProviderAdapterRegistry
from backend.app.modules.market_data_ingestion.normalization.schemas import MarketDataChannel
from backend.app.modules.market_data_ingestion.service import IngestionService

router = APIRouter(prefix="/market-data", tags=["Market Data Ingestion Engine"])


# ============================================================================
# Schemas for Router Endpoints
# ============================================================================

class StartIngestionRequest(BaseModel):
    feed_id: str
    instruments: List[str] = Field(default=["RELIANCE", "TCS"])
    channels: List[MarketDataChannel] = Field(default=[MarketDataChannel.TICK, MarketDataChannel.ORDER_BOOK_L2])
    provider_type: str = "SIMULATOR"


class BackfillRequest(BaseModel):
    feed_id: str
    instrument_id: str
    start_time: datetime
    end_time: datetime
    interval: str = "1m"


# ============================================================================
# Ingestion Control & State Endpoints
# ============================================================================

@router.post(
    "/start",
    summary="Start market data ingestion for configured instruments and channels",
)
async def start_ingestion(
    payload: StartIngestionRequest,
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    service = IngestionService(db)
    connected = await service.start_feed_ingestion(
        feed_id=payload.feed_id,
        instruments=payload.instruments,
        channels=payload.channels,
        provider_type=payload.provider_type,
    )
    return {"feed_id": payload.feed_id, "status": "CONNECTED" if connected else "FAILED"}


@router.post(
    "/stop/{feed_id}",
    summary="Stop market data ingestion for a feed",
)
async def stop_ingestion(
    feed_id: str,
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    service = IngestionService(db)
    await service.stop_feed_ingestion(feed_id)
    return {"feed_id": feed_id, "status": "STOPPED"}


# ============================================================================
# Order Book Inspection Endpoints
# ============================================================================

@router.get(
    "/order-book/{instrument_id}",
    summary="Inspect current reconstructed Level 2 order book state",
)
async def get_order_book(
    instrument_id: str,
    depth: int = Query(default=5, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    service = IngestionService(db)
    book = service.order_book_manager.get_or_create_book(instrument_id)
    return book.get_depth_snapshot(depth=depth)


# ============================================================================
# Historical Data & Backfill Endpoints
# ============================================================================

@router.post(
    "/backfill",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Execute historical backfill job",
)
async def trigger_backfill(
    payload: BackfillRequest,
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    service = IngestionService(db)
    job = await service.execute_historical_backfill(
        feed_id=payload.feed_id,
        instrument_id=payload.instrument_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
        interval=payload.interval,
    )
    return {
        "job_id": job.id,
        "status": job.job_status,
        "records_received": job.records_received,
        "completed_at": job.completed_at,
    }


# ============================================================================
# Operational Telemetry Endpoints
# ============================================================================

@router.get(
    "/telemetry",
    summary="Retrieve operational metrics, throughput, error rates, and queue health",
)
async def get_telemetry(
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    service = IngestionService(db)
    return {
        "metrics": service.metrics,
        "timestamp": datetime.now(timezone.utc),
    }
