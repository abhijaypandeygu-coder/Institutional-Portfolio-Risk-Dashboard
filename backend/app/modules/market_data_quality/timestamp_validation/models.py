"""
Module 03.03: Timestamp Validation - SQLAlchemy 2.x Database Models.
Tables:
- timestamp_validation_rules: Versioned policies controlling latency, drift, staleness, and sessions.
- timestamp_validation_results: Granular validation outcomes across all four subfeatures.
- timestamp_anomaly_incidents: Material anomalies with deduplication keys and resolution lifecycle.
- clock_offset_samples: Telemetry records of apparent and estimated clock offsets and drift rates.
- timestamp_validation_evidence: Granular evidence payload supporting each rule evaluation.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampRuleCategory(str, Enum):
    ORDERING = "ORDERING"
    CLOCK_DRIFT = "CLOCK_DRIFT"
    FRESHNESS = "FRESHNESS"
    SESSION_ALIGNMENT = "SESSION_ALIGNMENT"


class OrderingStatus(str, Enum):
    IN_ORDER = "IN_ORDER"
    EVENT_TIME_REGRESSION = "EVENT_TIME_REGRESSION"
    SEQUENCE_REGRESSION = "SEQUENCE_REGRESSION"
    LATE_ARRIVAL = "LATE_ARRIVAL"
    ARRIVAL_ORDER_WARNING = "ARRIVAL_ORDER_WARNING"
    FUTURE_TIMESTAMP = "FUTURE_TIMESTAMP"
    UNKNOWN_ORDERING = "UNKNOWN_ORDERING"


class ClockStatus(str, Enum):
    CLOCK_NORMAL = "CLOCK_NORMAL"
    APPARENT_CLOCK_DIVERGENCE = "APPARENT_CLOCK_DIVERGENCE"
    SOURCE_CLOCK_OFFSET = "SOURCE_CLOCK_OFFSET"
    LOCAL_CLOCK_OFFSET = "LOCAL_CLOCK_OFFSET"
    CLOCK_DRIFT_DETECTED = "CLOCK_DRIFT_DETECTED"
    CLOCK_SYNC_LOST = "CLOCK_SYNC_LOST"
    CLOCK_UNCERTAIN = "CLOCK_UNCERTAIN"
    INSUFFICIENT_CLOCK_EVIDENCE = "INSUFFICIENT_CLOCK_EVIDENCE"


class FreshnessStatus(str, Enum):
    FRESH = "FRESH"
    AGING = "AGING"
    STALE = "STALE"
    CRITICALLY_STALE = "CRITICALLY_STALE"
    FUTURE_DATED = "FUTURE_DATED"
    HISTORICAL = "HISTORICAL"
    MARKET_CLOSED = "MARKET_CLOSED"
    UNKNOWN = "UNKNOWN"


class SessionStatus(str, Enum):
    REGULAR_SESSION = "REGULAR_SESSION"
    PRE_MARKET = "PRE_MARKET"
    POST_MARKET = "POST_MARKET"
    OPENING_AUCTION = "OPENING_AUCTION"
    CLOSING_AUCTION = "CLOSING_AUCTION"
    SPECIAL_SESSION = "SPECIAL_SESSION"
    EXCHANGE_BREAK = "EXCHANGE_BREAK"
    MARKET_CLOSED = "MARKET_CLOSED"
    OUT_OF_SESSION = "OUT_OF_SESSION"
    UNKNOWN_SESSION = "UNKNOWN_SESSION"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class FinalTimestampStatus(str, Enum):
    VALID = "VALID"
    VALID_WITH_WARNING = "VALID_WITH_WARNING"
    REJECTED = "REJECTED"
    QUARANTINED = "QUARANTINED"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class TimestampAnomalyStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    SUPPRESSED = "SUPPRESSED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class TimestampValidationRule(Base):
    """Stores configurable, versioned timestamp-validation policies."""
    __tablename__ = "timestamp_validation_rules"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    rule_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    rule_name: Mapped[str] = mapped_column(String(128))
    rule_category: Mapped[TimestampRuleCategory] = mapped_column(
        SQLEnum(TimestampRuleCategory), index=True
    )
    provider_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    feed_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    exchange: Mapped[str] = mapped_column(String(32), default="ALL", index=True)
    event_type: Mapped[str] = mapped_column(String(32), default="ALL")
    processing_context: Mapped[str] = mapped_column(String(32), default="REALTIME")

    # Threshold parameters stored as JSON for flexible policies
    rule_parameters: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    version: Mapped[int] = mapped_column(Integer, default=1)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    effective_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class TimestampValidationResult(Base):
    """Stores the granular and aggregated validation outcome for an observation."""
    __tablename__ = "timestamp_validation_results"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    observation_id: Mapped[str] = mapped_column(String(64), index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), index=True)
    feed_id: Mapped[str] = mapped_column(String(64), index=True)
    provider_id: Mapped[str] = mapped_column(String(64), index=True)
    exchange: Mapped[str] = mapped_column(String(32), index=True)
    event_type: Mapped[str] = mapped_column(String(32))

    source_timestamp: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    normalized_event_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )
    provider_receive_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    local_receive_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    processing_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    validation_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    ordering_status: Mapped[OrderingStatus] = mapped_column(SQLEnum(OrderingStatus))
    clock_status: Mapped[ClockStatus] = mapped_column(SQLEnum(ClockStatus))
    freshness_status: Mapped[FreshnessStatus] = mapped_column(SQLEnum(FreshnessStatus))
    session_status: Mapped[SessionStatus] = mapped_column(SQLEnum(SessionStatus))
    final_status: Mapped[FinalTimestampStatus] = mapped_column(
        SQLEnum(FinalTimestampStatus), index=True
    )

    is_downstream_eligible: Mapped[bool] = mapped_column(Boolean, default=True)
    rule_version_summary: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_summary: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)

    # Relationships
    evidence_items: Mapped[List["TimestampValidationEvidence"]] = relationship(
        "TimestampValidationEvidence", back_populates="validation_result", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_tvr_inst_event_time", "instrument_id", "normalized_event_timestamp"),
        Index("ix_tvr_feed_status", "feed_id", "final_status"),
    )


class TimestampValidationEvidence(Base):
    """Detailed evidence supporting every subfeature rule evaluation."""
    __tablename__ = "timestamp_validation_evidence"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    validation_result_id: Mapped[UUID] = mapped_column(
        ForeignKey("timestamp_validation_results.id", ondelete="CASCADE"), index=True
    )
    rule_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("timestamp_validation_rules.id"), nullable=True
    )
    rule_code: Mapped[str] = mapped_column(String(64))
    evidence_type: Mapped[str] = mapped_column(String(64))

    previous_value: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    current_value: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    calculated_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    threshold_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    source_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[FinalTimestampStatus] = mapped_column(SQLEnum(FinalTimestampStatus))
    evidence_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    validation_result: Mapped["TimestampValidationResult"] = relationship(
        "TimestampValidationResult", back_populates="evidence_items"
    )


class TimestampAnomalyIncident(Base):
    """Tracks material timestamp anomalies with resolution lifecycle."""
    __tablename__ = "timestamp_anomaly_incidents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    incident_key: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), index=True)
    feed_id: Mapped[str] = mapped_column(String(64), index=True)
    provider_id: Mapped[str] = mapped_column(String(64), index=True)
    exchange: Mapped[str] = mapped_column(String(32), index=True)
    anomaly_type: Mapped[str] = mapped_column(String(64), index=True)

    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    previous_event_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    local_receive_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    calculated_difference_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    threshold_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    severity: Mapped[str] = mapped_column(String(32), default="HIGH")
    incident_status: Mapped[TimestampAnomalyStatus] = mapped_column(
        SQLEnum(TimestampAnomalyStatus), default=TimestampAnomalyStatus.OPEN, index=True
    )

    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    resolution_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)


class ClockOffsetSample(Base):
    """Telemetry records of apparent/estimated clock offsets and drift rates."""
    __tablename__ = "clock_offset_samples"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider_id: Mapped[str] = mapped_column(String(64), index=True)
    feed_id: Mapped[str] = mapped_column(String(64), index=True)
    clock_source: Mapped[str] = mapped_column(String(64), default="PROVIDER_TIMESTAMP")
    source_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    local_reference_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    apparent_offset_ms: Mapped[float] = mapped_column(Float)
    estimated_offset_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    transport_latency_estimate_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    uncertainty_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    synchronization_status: Mapped[str] = mapped_column(String(32), default="SYNCHRONIZED")
    sampling_method: Mapped[str] = mapped_column(String(64), default="ONE_WAY_DELAY")
    sampled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
