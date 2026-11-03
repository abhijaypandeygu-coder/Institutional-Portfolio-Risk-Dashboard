"""
Microstructure Monitoring FastAPI Router (M09.09).
Endpoints for short-horizon spread surveillance, depth fluctuation & depletion,
message update intensity, feed staleness, active anomaly lifecycle, and current overview.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from .services.monitoring_service import MicrostructureMonitoringService
from .schemas.monitoring_schemas import (
    MonitoringConfigCreate,
    MonitoringConfigResponse,
    SpreadMonitoringRequest,
    SpreadMonitoringResponse,
    DepthMonitoringRequest,
    DepthMonitoringResponse,
    DepthEventInput,
    UpdateIntensityRequest,
    UpdateIntensityResponse,
    FeedFreshnessRequest,
    FeedFreshnessResponse,
    AnomalyEventResponse,
    AnomalyAcknowledgeRequest,
    AnomalyResolveRequest,
    CurrentMonitoringOverviewResponse
)

router = APIRouter(
    prefix="/api/v1/market-microstructure/monitoring",
    tags=["M09.09 Microstructure Monitoring"]
)


@router.post("/configs", response_model=MonitoringConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_monitoring_config(
    req: MonitoringConfigCreate,
    db: AsyncSession = Depends(get_db)
):
    service = MicrostructureMonitoringService(db)
    return await service.create_monitoring_config(req)


@router.post("/spread", response_model=SpreadMonitoringResponse)
async def monitor_spread(
    req: SpreadMonitoringRequest,
    db: AsyncSession = Depends(get_db)
):
    service = MicrostructureMonitoringService(db)
    return await service.monitor_spread(req)


@router.get("/{instrument_id}/spread", response_model=List[SpreadMonitoringResponse])
async def get_spread_history(
    instrument_id: str,
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db)
):
    service = MicrostructureMonitoringService(db)
    records = await service.repo.get_spread_history(instrument_id, limit=limit)
    return [
        SpreadMonitoringResponse(
            id=r.id,
            instrument_id=r.instrument_id,
            listing_id=r.listing_id,
            venue_id=r.venue_id,
            source_feed_id=r.source_feed_id,
            observation_timestamp=r.observation_timestamp,
            calculation_timestamp=r.calculation_timestamp,
            absolute_spread=r.absolute_spread,
            relative_spread=r.relative_spread,
            spread_bps=r.spread_bps,
            spread_change=r.spread_change,
            spread_change_percentage=r.spread_change_percentage,
            rolling_mean_spread=r.rolling_mean_spread,
            rolling_stddev_spread=r.rolling_stddev_spread,
            spread_cv=r.spread_cv,
            spread_range=r.spread_range,
            time_weighted_spread=r.time_weighted_spread,
            historical_percentile=r.historical_percentile,
            valid_observation_count=r.valid_observation_count,
            coverage_ratio=r.coverage_ratio,
            quality_status=r.quality_status,
            spread_widening_flag=False,
            deterioration_severity="INFO"
        )
        for r in records
    ]


@router.post("/depth", response_model=DepthMonitoringResponse)
async def monitor_depth(
    req: DepthMonitoringRequest,
    db: AsyncSession = Depends(get_db)
):
    service = MicrostructureMonitoringService(db)
    return await service.monitor_depth(req)


@router.get("/{instrument_id}/depth", response_model=List[DepthMonitoringResponse])
async def get_depth_history(
    instrument_id: str,
    side: Optional[str] = Query(None, pattern="^(BID|ASK|BOTH)$"),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db)
):
    service = MicrostructureMonitoringService(db)
    records = await service.repo.get_depth_history(instrument_id, side=side, limit=limit)
    return [
        DepthMonitoringResponse(
            id=r.id,
            instrument_id=r.instrument_id,
            listing_id=r.listing_id,
            venue_id=r.venue_id,
            side=r.side,
            event_timestamp=r.event_timestamp,
            calculation_timestamp=r.calculation_timestamp,
            current_depth=r.current_depth,
            baseline_depth=r.baseline_depth,
            absolute_depth_change=r.absolute_depth_change,
            relative_depth_change=r.relative_depth_change,
            depletion_amount=r.depletion_amount,
            depletion_rate=r.depletion_rate,
            replenishment_amount=r.replenishment_amount,
            recovery_ratio=r.recovery_ratio,
            classification="DEPTH_OBSERVATION",
            quality_status=r.quality_status
        )
        for r in records
    ]


@router.post("/update-intensity", response_model=UpdateIntensityResponse)
async def monitor_update_intensity(
    req: UpdateIntensityRequest,
    db: AsyncSession = Depends(get_db)
):
    service = MicrostructureMonitoringService(db)
    return await service.monitor_update_intensity(req)


@router.post("/freshness", response_model=FeedFreshnessResponse)
async def monitor_feed_freshness(
    req: FeedFreshnessRequest,
    db: AsyncSession = Depends(get_db)
):
    service = MicrostructureMonitoringService(db)
    return await service.monitor_feed_freshness(req)


@router.get("/anomalies", response_model=List[AnomalyEventResponse])
async def get_anomalies(
    instrument_id: Optional[str] = None,
    severity: Optional[str] = None,
    lifecycle_status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db)
):
    service = MicrostructureMonitoringService(db)
    records = await service.repo.get_anomalies(
        instrument_id=instrument_id,
        severity=severity,
        lifecycle_status=lifecycle_status,
        limit=limit
    )
    return [AnomalyEventResponse.model_validate(r) for r in records]


@router.post("/anomalies/{anomaly_id}/acknowledge", response_model=AnomalyEventResponse)
async def acknowledge_anomaly(
    anomaly_id: str,
    req: AnomalyAcknowledgeRequest,
    db: AsyncSession = Depends(get_db)
):
    service = MicrostructureMonitoringService(db)
    try:
        return await service.acknowledge_anomaly(anomaly_id, req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/anomalies/{anomaly_id}/resolve", response_model=AnomalyEventResponse)
async def resolve_anomaly(
    anomaly_id: str,
    req: AnomalyResolveRequest,
    db: AsyncSession = Depends(get_db)
):
    service = MicrostructureMonitoringService(db)
    try:
        return await service.resolve_anomaly(anomaly_id, req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{instrument_id}/current", response_model=CurrentMonitoringOverviewResponse)
async def get_current_monitoring_overview(
    instrument_id: str,
    db: AsyncSession = Depends(get_db)
):
    service = MicrostructureMonitoringService(db)
    return await service.get_current_overview(instrument_id)
