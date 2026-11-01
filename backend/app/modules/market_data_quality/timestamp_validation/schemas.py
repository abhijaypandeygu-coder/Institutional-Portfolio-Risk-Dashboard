"""
Module 03.03: Timestamp Validation - Pydantic 2.x Schemas.
Request, response, and canonical inspection contracts for:
- Single & Batch timestamp validation
- Rule management
- Anomaly incidents & lifecycle resolution
- Freshness, Ordering, and Clock Status inquiries
- Quality summary metrics
"""
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field

from backend.app.modules.market_data_quality.timestamp_validation.models import (
    ClockStatus,
    FinalTimestampStatus,
    FreshnessStatus,
    OrderingStatus,
    SessionStatus,
    TimestampAnomalyStatus,
    TimestampRuleCategory,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampObservationInput(BaseModel):
    """Canonical observation input for timestamp quality evaluation."""
    observation_id: str = Field(default_factory=lambda: str(uuid4()))
    instrument_id: str
    feed_id: str
    provider_id: str = "SIMULATOR"
    exchange: str = "NSE"
    event_type: str = "TICK"              # TICK, OHLCV, TRADE, ORDER_BOOK_L2
    processing_context: str = "REALTIME"  # REALTIME, EOD, HISTORICAL
    
    source_timestamp: Any                # May be string, int epoch, datetime, or date-only
    provider_receive_timestamp: Optional[Any] = None
    local_receive_timestamp: Optional[datetime] = None
    sequence_number: Optional[int] = None
    connection_epoch: int = 1
    
    is_orderbook_synchronized: bool = True
    allow_extended_hours: bool = True
    source_metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class BatchTimestampObservationInput(BaseModel):
    observations: List[TimestampObservationInput]


class TimestampRuleCreate(BaseModel):
    rule_code: str
    rule_name: str
    rule_category: TimestampRuleCategory
    provider_id: Optional[str] = None
    feed_id: Optional[str] = None
    instrument_id: Optional[str] = None
    exchange: str = "ALL"
    event_type: str = "ALL"
    processing_context: str = "REALTIME"
    rule_parameters: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 100
    description: Optional[str] = None


class TimestampRuleUpdate(BaseModel):
    rule_name: Optional[str] = None
    rule_parameters: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None


class TimestampRuleResponse(BaseModel):
    id: UUID
    rule_code: str
    rule_name: str
    rule_category: TimestampRuleCategory
    provider_id: Optional[str]
    feed_id: Optional[str]
    instrument_id: Optional[str]
    exchange: str
    event_type: str
    processing_context: str
    rule_parameters: Dict[str, Any]
    priority: int
    version: int
    effective_from: datetime
    effective_until: Optional[datetime]
    enabled: bool
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TimestampEvidenceItem(BaseModel):
    rule_code: str
    evidence_type: str
    previous_value: Optional[str] = None
    current_value: Optional[str] = None
    calculated_value: Optional[float] = None
    threshold_value: Optional[float] = None
    source_reference: Optional[str] = None
    status: FinalTimestampStatus
    evidence_payload: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class TimestampValidationResultResponse(BaseModel):
    id: UUID
    observation_id: str
    instrument_id: str
    feed_id: str
    provider_id: str
    exchange: str
    event_type: str
    source_timestamp: Optional[str]
    normalized_event_timestamp: datetime
    provider_receive_timestamp: Optional[datetime]
    local_receive_timestamp: datetime
    processing_timestamp: datetime
    validation_timestamp: datetime
    ordering_status: OrderingStatus
    clock_status: ClockStatus
    freshness_status: FreshnessStatus
    session_status: SessionStatus
    final_status: FinalTimestampStatus
    is_downstream_eligible: bool
    rule_version_summary: Dict[str, Any]
    evidence_summary: Dict[str, Any]
    evidence_items: List[TimestampEvidenceItem] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class TimestampAnomalyIncidentResponse(BaseModel):
    id: UUID
    incident_key: str
    instrument_id: str
    feed_id: str
    provider_id: str
    exchange: str
    anomaly_type: str
    event_timestamp: datetime
    previous_event_timestamp: Optional[datetime]
    local_receive_timestamp: datetime
    calculated_difference_ms: Optional[float]
    threshold_ms: Optional[float]
    severity: str
    incident_status: TimestampAnomalyStatus
    first_detected_at: datetime
    last_detected_at: datetime
    resolved_at: Optional[datetime]
    resolved_by: Optional[str]
    resolution_reason: Optional[str]
    evidence: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class TimestampAnomalyResolutionRequest(BaseModel):
    status: TimestampAnomalyStatus
    resolution_reason: str


class SessionCheckRequest(BaseModel):
    exchange: str = "NSE"
    timestamp: datetime
    allow_extended_hours: bool = True


class SessionCheckResponse(BaseModel):
    exchange: str
    normalized_utc_timestamp: datetime
    exchange_local_time: str
    trading_date: date
    session_status: SessionStatus
    is_auction: bool
    session_name: str
    is_valid: bool
    reason: str


class ClockStatusResponse(BaseModel):
    provider_id: str
    feed_id: str
    status: ClockStatus
    apparent_offset_ms: float
    estimated_offset_ms: Optional[float]
    drift_rate_ms_per_min: Optional[float]
    uncertainty_ms: float
    last_evaluated: datetime


class TimestampQualitySummary(BaseModel):
    total_observations_validated: int
    valid_count: int
    warning_count: int
    rejected_count: int
    quarantined_count: int
    ordering_anomalies_count: int
    clock_anomalies_count: int
    stale_observations_count: int
    session_misalignments_count: int
    open_incidents_count: int
    downstream_eligibility_rate_percentage: float
