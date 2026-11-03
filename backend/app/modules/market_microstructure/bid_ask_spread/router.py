"""
M09.01 Bid-Ask Spread - FastAPI REST Router.
Endpoints:
- POST /api/v1/spreads/configurations
- GET  /api/v1/spreads/configurations/{config_code}
- POST /api/v1/spreads/calculate
- GET  /api/v1/instruments/{instrument_id}/spread/current
- GET  /api/v1/instruments/{instrument_id}/spread/history
- GET  /api/v1/instruments/{instrument_id}/spread/statistics
- GET  /api/v1/instruments/{instrument_id}/spread/quality
- GET  /api/v1/instruments/{instrument_id}/spread/venues
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.market_microstructure.bid_ask_spread.services.service import SpreadCalculationOrchestrator
from backend.app.modules.market_microstructure.bid_ask_spread.schemas import (
    SpreadCalculationConfigCreate,
    SpreadCalculationConfigResponse,
    DirectSpreadCalculationRequest,
    SpreadObservationResponse,
    SpreadIntervalAggregateResponse,
    SpreadStatisticsResponse,
    SpreadQualitySummaryResponse,
    VenueSpreadComparisonItem,
    SpreadQualityResultResponse,
    BookScope,
    RelativeSpreadMethod,
)

router = APIRouter(tags=["M09.01 - Bid-Ask Spread Analytics"])


# =============================================================================
# 1. Configuration Endpoints
# =============================================================================

@router.post(
    "/api/v1/spreads/configurations",
    response_model=SpreadCalculationConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or version a spread calculation configuration",
)
async def create_spread_configuration(
    req: SpreadCalculationConfigCreate,
    db: AsyncSession = Depends(get_db),
):
    orchestrator = SpreadCalculationOrchestrator(db)
    cfg = await orchestrator.create_config(req)
    return cfg


@router.get(
    "/api/v1/spreads/configurations/{config_code}",
    response_model=SpreadCalculationConfigResponse,
    summary="Get spread calculation configuration by code",
)
async def get_spread_configuration(
    config_code: str,
    db: AsyncSession = Depends(get_db),
):
    orchestrator = SpreadCalculationOrchestrator(db)
    cfg = await orchestrator.repo.get_config_by_code(config_code)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Spread configuration '{config_code}' not found")
    return cfg


# =============================================================================
# 2. Calculation Endpoint
# =============================================================================

@router.post(
    "/api/v1/spreads/calculate",
    response_model=SpreadObservationResponse,
    summary="Directly calculate and record bid-ask spread from quote state",
)
async def calculate_spread(
    req: DirectSpreadCalculationRequest,
    db: AsyncSession = Depends(get_db),
):
    orchestrator = SpreadCalculationOrchestrator(db)
    obs = await orchestrator.calculate_spread(req)
    return obs


# =============================================================================
# 3. Instrument Spread Endpoints
# =============================================================================

@router.get(
    "/api/v1/instruments/{instrument_id}/spread/current",
    response_model=SpreadObservationResponse,
    summary="Get current or latest displayed bid-ask spread for an instrument",
)
async def get_current_spread(
    instrument_id: str,
    venue: Optional[str] = Query(None, description="Trading venue code (e.g. NSE, BSE, NYSE, NASDAQ)"),
    book_scope: Optional[BookScope] = Query(None, description="VENUE_SPECIFIC or CONSOLIDATED"),
    db: AsyncSession = Depends(get_db),
):
    orchestrator = SpreadCalculationOrchestrator(db)
    latest = await orchestrator.repo.get_latest_observation(
        instrument_id=instrument_id,
        venue=venue,
        book_scope=book_scope.value if book_scope else None,
    )
    if not latest:
        # Fallback: Attempt to resolve from latest M02 tick
        latest = await orchestrator.resolve_from_m02_tick_and_calculate(
            instrument_id=instrument_id,
            venue=venue or "NSE",
        )

    if not latest:
        raise HTTPException(status_code=404, detail=f"No quote or spread observation found for instrument '{instrument_id}'")
    return latest


@router.get(
    "/api/v1/instruments/{instrument_id}/spread/history",
    response_model=List[SpreadObservationResponse],
    summary="Get historical quote-level spread observations",
)
async def get_spread_history(
    instrument_id: str,
    start_time: Optional[datetime] = Query(None, description="Start timestamp in UTC"),
    end_time: Optional[datetime] = Query(None, description="End timestamp in UTC"),
    venue: Optional[str] = Query(None, description="Trading venue code"),
    quality_status: Optional[str] = Query(None, description="Filter by quality status (e.g. VALID, STALE_QUOTE)"),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    orchestrator = SpreadCalculationOrchestrator(db)
    observations = await orchestrator.repo.query_observations(
        instrument_id=instrument_id,
        start_time=start_time,
        end_time=end_time,
        venue=venue,
        quality_status=quality_status,
        limit=limit,
        offset=offset,
    )
    return observations


@router.get(
    "/api/v1/instruments/{instrument_id}/spread/statistics",
    response_model=SpreadStatisticsResponse,
    summary="Get observation-weighted and time-weighted summary statistics",
)
async def get_spread_statistics(
    instrument_id: str,
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    venue: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    orchestrator = SpreadCalculationOrchestrator(db)
    stats = await orchestrator.compute_historical_statistics(
        instrument_id=instrument_id,
        start_time=start_time,
        end_time=end_time,
        venue=venue,
    )
    return stats


@router.get(
    "/api/v1/instruments/{instrument_id}/spread/quality",
    response_model=List[SpreadQualityResultResponse],
    summary="Get quote quality diagnostic checks and exclusion reasons",
)
async def get_spread_quality_diagnostics(
    instrument_id: str,
    observation_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    orchestrator = SpreadCalculationOrchestrator(db)
    results = await orchestrator.repo.query_quality_results(
        observation_id=observation_id,
        limit=limit,
    )
    return results


@router.get(
    "/api/v1/instruments/{instrument_id}/spread/venues",
    response_model=List[VenueSpreadComparisonItem],
    summary="Compare venue-specific displayed spreads across exchanges",
)
async def get_venue_comparison(
    instrument_id: str,
    db: AsyncSession = Depends(get_db),
):
    orchestrator = SpreadCalculationOrchestrator(db)
    return await orchestrator.get_venue_comparison(instrument_id)

