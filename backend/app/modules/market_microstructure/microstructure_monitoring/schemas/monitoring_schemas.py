"""
Microstructure Monitoring Pydantic Schemas (M09.09).
Strict validation using Pydantic 2.x and ConfigDict.
"""

from pydantic import BaseModel, ConfigDict, Field
from decimal import Decimal
from typing import List, Optional, Dict, Any
from datetime import datetime


class MonitoringConfigCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    config_name: str = Field(..., max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    market_scope: str = Field(default="ALL", max_length=50)
    venue_scope: str = Field(default="ALL", max_length=50)
    feed_scope: str = Field(default="ALL", max_length=50)
    instrument_scope: str = Field(default="ALL", max_length=50)
    monitoring_mode: str = Field(default="HYBRID", max_length=50)
    spread_window_seconds: int = Field(default=60, ge=1)
    depth_window_seconds: int = Field(default=60, ge=1)
    update_rate_window_seconds: int = Field(default=10, ge=1)
    maximum_spread_age_ms: int = Field(default=3000, ge=100)
    maximum_book_age_ms: int = Field(default=5000, ge=100)
    expected_update_cadence_ms: int = Field(default=1000, ge=50)
    minimum_sample_count: int = Field(default=5, ge=1)
    minimum_coverage: Decimal = Field(default=Decimal("0.80"), ge=0, le=1)
    version: str = Field(default="1.0.0", max_length=20)


class MonitoringConfigResponse(MonitoringConfigCreate):
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SpreadObservationInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    absolute_spread: Decimal = Field(..., ge=0)
    midpoint: Optional[Decimal] = Field(None, gt=0)
    quality_status: str = Field(default="VALID")


class SpreadMonitoringRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    listing_id: str
    venue_id: str
    source_feed_id: str
    observations: List[SpreadObservationInput] = Field(..., min_length=1)
    historical_baseline_spread: Optional[Decimal] = Field(None, gt=0)
    config_version: str = Field(default="1.0.0")


class SpreadMonitoringResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    instrument_id: str
    listing_id: str
    venue_id: str
    source_feed_id: str
    observation_timestamp: datetime
    calculation_timestamp: datetime
    absolute_spread: Decimal
    relative_spread: Optional[Decimal]
    spread_bps: Optional[Decimal]
    spread_change: Optional[Decimal]
    spread_change_percentage: Optional[Decimal]
    rolling_mean_spread: Optional[Decimal]
    rolling_stddev_spread: Optional[Decimal]
    spread_cv: Optional[Decimal]
    spread_range: Optional[Decimal]
    time_weighted_spread: Optional[Decimal]
    historical_percentile: Optional[Decimal]
    valid_observation_count: int
    coverage_ratio: Decimal
    quality_status: str
    spread_widening_flag: bool = False
    deterioration_severity: str = "INFO"


class DepthObservationInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    side: str = Field(..., pattern="^(BID|ASK|BOTH)$")
    displayed_depth: Decimal = Field(..., ge=0)
    baseline_depth: Optional[Decimal] = Field(None, ge=0)
    level_count: int = Field(default=5, ge=1)
    quality_status: str = Field(default="VALID")


class DepthMonitoringRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    listing_id: str
    venue_id: str
    source_feed_id: str
    observations: List[DepthObservationInput] = Field(..., min_length=1)
    config_version: str = Field(default="1.0.0")


class DepthMonitoringResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    instrument_id: str
    listing_id: str
    venue_id: str
    side: str
    event_timestamp: datetime
    calculation_timestamp: datetime
    current_depth: Decimal
    baseline_depth: Optional[Decimal]
    absolute_depth_change: Decimal
    relative_depth_change: Optional[Decimal]
    depletion_amount: Decimal
    depletion_rate: Optional[Decimal]
    replenishment_amount: Decimal
    recovery_ratio: Optional[Decimal]
    classification: str
    quality_status: str


class DepthEventInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_timestamp: datetime
    receive_timestamp: datetime
    sequence_number: Optional[int] = None
    event_type: str = Field(..., max_length=50) # ADD, MODIFY, CANCEL, EXECUTION, SNAPSHOT
    side: str = Field(..., pattern="^(BID|ASK)$")
    price: Optional[Decimal] = None
    quantity_change: Decimal
    notional_change: Optional[Decimal] = None
    order_reference: Optional[str] = None
    classification_source: str = Field(default="FEED_MESSAGE")
    classification_status: str = Field(default="EXPLICIT_EVENT")


class UpdateIntensityRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    listing_id: str
    venue_id: str
    source_feed_id: str
    interval_start: datetime
    interval_end: datetime
    source_mode: str = Field(default="STREAMING")
    total_message_count: int = Field(..., ge=0)
    valid_message_count: int = Field(..., ge=0)
    unique_event_count: Optional[int] = None
    book_update_count: int = Field(..., ge=0)
    trade_message_count: int = Field(default=0, ge=0)
    add_event_count: int = Field(default=0, ge=0)
    modify_event_count: int = Field(default=0, ge=0)
    cancel_event_count: int = Field(default=0, ge=0)
    snapshot_count: int = Field(default=0, ge=0)
    heartbeat_count: int = Field(default=0, ge=0)
    duplicate_message_count: int = Field(default=0, ge=0)
    invalid_message_count: int = Field(default=0, ge=0)
    baseline_message_rate: Optional[Decimal] = None


class UpdateIntensityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    instrument_id: str
    listing_id: str
    venue_id: str
    source_feed_id: str
    interval_start: datetime
    interval_end: datetime
    source_mode: str
    total_message_count: int
    valid_message_count: int
    book_update_count: int
    message_rate: Decimal
    book_change_rate: Decimal
    intensity_ratio: Optional[Decimal]
    burst_detected: bool = False
    burst_severity: str = "INFO"
    quality_status: str


class FeedFreshnessRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_feed_id: str
    instrument_id: str
    listing_id: str
    venue_id: str
    monitoring_timestamp: datetime
    last_source_event_timestamp: datetime
    last_receive_timestamp: datetime
    last_valid_book_timestamp: datetime
    expected_update_cadence_ms: int = Field(default=1000, ge=50)


class FeedFreshnessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_feed_id: str
    instrument_id: str
    listing_id: str
    venue_id: str
    monitoring_timestamp: datetime
    observation_age_ms: int
    receive_latency_ms: int
    expected_update_cadence_ms: int
    feed_status: str
    book_status: str
    sequence_status: str
    recovery_status: str
    quality_status: str


class AnomalyEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    instrument_id: str
    listing_id: str
    venue_id: str
    source_feed_id: str
    anomaly_category: str
    anomaly_description: str
    severity: str
    detected_metric: str
    observed_value: Decimal
    baseline_value: Optional[Decimal]
    threshold_value: Optional[Decimal]
    deviation_magnitude: Optional[Decimal]
    event_start_timestamp: datetime
    detection_timestamp: datetime
    last_observed_timestamp: datetime
    affected_side: Optional[str]
    detection_method: str
    lifecycle_status: str
    quality_status: str


class AnomalyAcknowledgeRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    actor_id: str = Field(..., max_length=50)
    notes: Optional[str] = None


class AnomalyResolveRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    actor_id: str = Field(..., max_length=50)
    resolution_reason: str = Field(..., max_length=255)
    notes: Optional[str] = None


class CurrentMonitoringOverviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    listing_id: str
    venue_id: str
    source_feed_id: str
    latest_spread: Optional[Decimal]
    spread_bps: Optional[Decimal]
    spread_volatility_cv: Optional[Decimal]
    latest_bid_depth: Optional[Decimal]
    latest_ask_depth: Optional[Decimal]
    depth_depletion_indicator: bool
    latest_message_rate: Optional[Decimal]
    book_change_rate: Optional[Decimal]
    feed_freshness_status: str
    active_anomaly_count: int
    highest_active_severity: str
    quality_status: str
