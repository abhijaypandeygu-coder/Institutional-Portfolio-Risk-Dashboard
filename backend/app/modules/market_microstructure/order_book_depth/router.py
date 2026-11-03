"""
M09.02 Order Book Depth - FastAPI REST Router.
Endpoints:
- POST /api/v1/market-microstructure/depth/configurations
- GET  /api/v1/market-microstructure/depth/configurations/{config_code}
- POST /api/v1/market-microstructure/depth/calculate
- GET  /api/v1/market-microstructure/depth/{instrument_id}/current
- GET  /api/v1/market-microstructure/depth/{instrument_id}/levels
- GET  /api/v1/market-microstructure/depth/{instrument_id}/cumulative
- GET  /api/v1/market-microstructure/depth/{instrument_id}/imbalance
- GET  /api/v1/market-microstructure/depth/{instrument_id}/bands
- GET  /api/v1/market-microstructure/depth/{instrument_id}/persistence
- GET  /api/v1/market-microstructure/depth/{instrument_id}/history
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.market_microstructure.order_book_depth.services.service import OrderBookDepthService
from backend.app.modules.market_microstructure.order_book_depth.schemas import (
    DepthCalculationConfigCreate,
    DepthCalculationConfigResponse,
    DirectDepthCalculationRequest,
    OrderBookDepthSnapshotResponse,
    OrderBookDepthLevelResponse,
    OrderBookDepthBandResponse,
    CumulativeDepthResponse,
    DepthImbalanceResponse,
    DepthPersistenceResponse,
    DepthAggregationMode,
)

router = APIRouter(tags=["M09.02 - Order Book Depth Analytics"])


# =============================================================================
# 1. Configuration Endpoints
# =============================================================================

@router.post(
    "/api/v1/market-microstructure/depth/configurations",
    response_model=DepthCalculationConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or version an order book depth calculation policy",
)
async def create_depth_configuration(
    req: DepthCalculationConfigCreate,
    db: AsyncSession = Depends(get_db),
):
    service = OrderBookDepthService(db)
    cfg = await service.create_config(req)
    return cfg


@router.get(
    "/api/v1/market-microstructure/depth/configurations/{config_code}",
    response_model=DepthCalculationConfigResponse,
    summary="Get depth calculation configuration by code",
)
async def get_depth_configuration(
    config_code: str,
    db: AsyncSession = Depends(get_db),
):
    service = OrderBookDepthService(db)
    cfg = await service.repo.get_config_by_code(config_code)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Depth configuration '{config_code}' not found")
    return cfg


# =============================================================================
# 2. Direct Calculation Endpoint
# =============================================================================

@router.post(
    "/api/v1/market-microstructure/depth/calculate",
    response_model=OrderBookDepthSnapshotResponse,
    summary="Directly calculate order book depth from input level ladder",
)
async def calculate_order_book_depth(
    req: DirectDepthCalculationRequest,
    db: AsyncSession = Depends(get_db),
):
    service = OrderBookDepthService(db)
    snap, levels, bands = await service.calculate_depth(req)

    # Convert to schema response
    lvl_responses = [OrderBookDepthLevelResponse.model_validate(l) for l in levels]
    band_responses = [OrderBookDepthBandResponse.model_validate(b) for b in bands]

    res = OrderBookDepthSnapshotResponse.model_validate(snap)
    res.levels = lvl_responses
    res.bands = band_responses
    return res


# =============================================================================
# 3. Depth Query Endpoints
# =============================================================================

@router.get(
    "/api/v1/market-microstructure/depth/{instrument_id}/current",
    response_model=OrderBookDepthSnapshotResponse,
    summary="Get latest order book depth summary for an instrument",
)
async def get_current_depth(
    instrument_id: str,
    venue: Optional[str] = Query(None, description="Trading venue (e.g. NSE, BSE, NASDAQ)"),
    db: AsyncSession = Depends(get_db),
):
    service = OrderBookDepthService(db)
    latest = await service.repo.get_latest_snapshot(instrument_id=instrument_id, venue=venue)

    if not latest:
        # Fallback to M02 OrderBookSnapshotRecord
        resolved = await service.resolve_from_m02_and_calculate(
            instrument_id=instrument_id,
            venue=venue or "NSE",
        )
        if resolved:
            latest, _, _ = resolved

    if not latest:
        raise HTTPException(status_code=404, detail=f"No order book depth snapshot found for instrument '{instrument_id}'")

    levels = await service.repo.get_snapshot_levels(latest.depth_snapshot_id)
    bands = await service.repo.get_snapshot_bands(latest.depth_snapshot_id)

    res = OrderBookDepthSnapshotResponse.model_validate(latest)
    res.levels = [OrderBookDepthLevelResponse.model_validate(l) for l in levels]
    res.bands = [OrderBookDepthBandResponse.model_validate(b) for b in bands]
    return res


@router.get(
    "/api/v1/market-microstructure/depth/{instrument_id}/levels",
    response_model=List[OrderBookDepthLevelResponse],
    summary="Get displayed depth by individual price levels",
)
async def get_depth_by_level(
    instrument_id: str,
    side: Optional[str] = Query(None, description="BID or ASK"),
    venue: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    service = OrderBookDepthService(db)
    latest = await service.repo.get_latest_snapshot(instrument_id=instrument_id, venue=venue)
    if not latest:
        raise HTTPException(status_code=404, detail=f"No depth snapshot found for instrument '{instrument_id}'")

    levels = await service.repo.get_snapshot_levels(latest.depth_snapshot_id)
    if side:
        levels = [l for l in levels if l.side.upper() == side.upper()]

    return [OrderBookDepthLevelResponse.model_validate(l) for l in levels]


@router.get(
    "/api/v1/market-microstructure/depth/{instrument_id}/cumulative",
    response_model=CumulativeDepthResponse,
    summary="Get cumulative displayed depth across configurable levels",
)
async def get_cumulative_depth(
    instrument_id: str,
    venue: Optional[str] = Query(None),
    level_count: int = Query(5, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    service = OrderBookDepthService(db)
    latest = await service.repo.get_latest_snapshot(instrument_id=instrument_id, venue=venue)
    if not latest:
        raise HTTPException(status_code=404, detail=f"No depth snapshot found for instrument '{instrument_id}'")

    levels = await service.repo.get_snapshot_levels(latest.depth_snapshot_id)
    bids = [l for l in levels if l.side == "BID" and l.level_index <= level_count]
    asks = [l for l in levels if l.side == "ASK" and l.level_index <= level_count]

    bid_cum_q = bids[-1].cumulative_quantity if bids else Decimal("0")
    bid_cum_n = bids[-1].cumulative_notional if bids else Decimal("0")
    ask_cum_q = asks[-1].cumulative_quantity if asks else Decimal("0")
    ask_cum_n = asks[-1].cumulative_notional if asks else Decimal("0")

    q_denom = bid_cum_q + ask_cum_q
    n_denom = bid_cum_n + ask_cum_n
    q_imb = (bid_cum_q - ask_cum_q) / q_denom if q_denom > Decimal("0") else None
    n_imb = (bid_cum_n - ask_cum_n) / n_denom if n_denom > Decimal("0") else None

    return CumulativeDepthResponse(
        instrument_id=instrument_id,
        venue=latest.venue,
        levels_requested=level_count,
        midpoint=latest.midpoint_price,
        bid_cumulative_quantity=bid_cum_q,
        bid_cumulative_notional=bid_cum_n,
        ask_cumulative_quantity=ask_cum_q,
        ask_cumulative_notional=ask_cum_n,
        quantity_imbalance=q_imb,
        notional_imbalance=n_imb,
        bids=[OrderBookDepthLevelResponse.model_validate(b) for b in bids],
        asks=[OrderBookDepthLevelResponse.model_validate(a) for a in asks],
    )


@router.get(
    "/api/v1/market-microstructure/depth/{instrument_id}/imbalance",
    response_model=DepthImbalanceResponse,
    summary="Get quantity, notional, and weighted depth imbalance",
)
async def get_depth_imbalance(
    instrument_id: str,
    venue: Optional[str] = Query(None),
    levels: int = Query(5, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    service = OrderBookDepthService(db)
    latest = await service.repo.get_latest_snapshot(instrument_id=instrument_id, venue=venue)
    if not latest:
        raise HTTPException(status_code=404, detail=f"No depth snapshot found for instrument '{instrument_id}'")

    q_imb_pct = latest.quantity_imbalance * Decimal("100") if latest.quantity_imbalance is not None else None
    n_imb_pct = latest.notional_imbalance * Decimal("100") if latest.notional_imbalance is not None else None
    w_imb_pct = latest.weighted_imbalance * Decimal("100") if latest.weighted_imbalance is not None else None

    return DepthImbalanceResponse(
        instrument_id=instrument_id,
        venue=latest.venue,
        levels_considered=latest.bid_level_count,
        bid_quantity=latest.bid_total_quantity,
        ask_quantity=latest.ask_total_quantity,
        bid_notional=latest.bid_total_notional,
        ask_notional=latest.ask_total_notional,
        quantity_imbalance=latest.quantity_imbalance,
        quantity_imbalance_percentage=q_imb_pct,
        notional_imbalance=latest.notional_imbalance,
        notional_imbalance_percentage=n_imb_pct,
        weighted_imbalance=latest.weighted_imbalance,
        weighted_imbalance_percentage=w_imb_pct,
    )


@router.get(
    "/api/v1/market-microstructure/depth/{instrument_id}/bands",
    response_model=List[OrderBookDepthBandResponse],
    summary="Get displayed liquidity aggregated by price-distance bands",
)
async def get_price_band_depth(
    instrument_id: str,
    venue: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    service = OrderBookDepthService(db)
    latest = await service.repo.get_latest_snapshot(instrument_id=instrument_id, venue=venue)
    if not latest:
        raise HTTPException(status_code=404, detail=f"No depth snapshot found for instrument '{instrument_id}'")

    bands = await service.repo.get_snapshot_bands(latest.depth_snapshot_id)
    return [OrderBookDepthBandResponse.model_validate(b) for b in bands]


@router.get(
    "/api/v1/market-microstructure/depth/{instrument_id}/persistence",
    response_model=DepthPersistenceResponse,
    summary="Get time-weighted depth persistence, CV, and stability statistics",
)
async def get_depth_persistence(
    instrument_id: str,
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    venue: Optional[str] = Query(None),
    minimum_depth_threshold: Optional[Decimal] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    service = OrderBookDepthService(db)
    persistence = await service.compute_persistence_window(
        instrument_id=instrument_id,
        start_time=start_time,
        end_time=end_time,
        venue=venue,
        minimum_depth_threshold=minimum_depth_threshold,
    )
    return DepthPersistenceResponse.model_validate(persistence)


@router.get(
    "/api/v1/market-microstructure/depth/{instrument_id}/history",
    response_model=List[OrderBookDepthSnapshotResponse],
    summary="Get historical depth snapshots",
)
async def get_depth_history(
    instrument_id: str,
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    venue: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    service = OrderBookDepthService(db)
    snapshots = await service.repo.query_snapshots(
        instrument_id=instrument_id,
        start_time=start_time,
        end_time=end_time,
        venue=venue,
        limit=limit,
        offset=offset,
    )
    return [OrderBookDepthSnapshotResponse.model_validate(s) for s in snapshots]

