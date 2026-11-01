"""
Module 03.01: Missing Data Detection - Database Models (SQLAlchemy 2.x).
Defines persistence models for:
1. ExpectedObservationPolicy: rules defining when observations are expected.
2. MissingDataIncident: detected gaps (ticks, candles, order-book updates, stale books).
3. MissingDataEvidence: supporting proof for incidents.
4. CoverageWindow: calculated data availability windows.
"""
from datetime import datetime, timezone
from enum import Enum
import uuid
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, JSON, Boolean, Text, Index, UniqueConstraint, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ExpectationStatus(str, Enum):
    EXPECTED = "EXPECTED"
    NOT_EXPECTED = "NOT_EXPECTED"
    UNKNOWN = "UNKNOWN"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    MARKET_CLOSED = "MARKET_CLOSED"
    POLICY_ERROR = "POLICY_ERROR"


class IssueType(str, Enum):
    MISSING_TICK = "MISSING_TICK"
    MISSING_TRADE = "MISSING_TRADE"
    MISSING_CANDLE = "MISSING_CANDLE"
    SEQUENCE_GAP = "SEQUENCE_GAP"
    STALE_ORDER_BOOK = "STALE_ORDER_BOOK"
    MISSING_ORDER_BOOK_UPDATE = "MISSING_ORDER_BOOK_UPDATE"


class IncidentStatus(str, Enum):
    PROVISIONAL = "PROVISIONAL"
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVING = "RESOLVING"
    RESOLVED = "RESOLVED"
    SUPPRESSED = "SUPPRESSED"


class IncidentSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CoverageStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_SUPPORTED = "NOT_SUPPORTED"


class ExpectedObservationPolicy(Base):
    """Configuration determining when an observation is expected."""
    __tablename__ = "expected_observation_policies"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_code = Column(String(64), unique=True, nullable=False, index=True)
    instrument_id = Column(String(64), nullable=True, index=True)
    exchange = Column(String(16), nullable=False)  # NSE, BSE, NYSE, NASDAQ, GLOBAL
    provider_id = Column(String(64), nullable=False)  # ALPHA_VANTAGE, SIMULATOR
    feed_id = Column(String(64), nullable=True)
    data_channel = Column(String(32), nullable=False)  # TICK, OHLCV, TRADE, ORDER_BOOK_L2
    observation_type = Column(String(32), nullable=False)
    expected_frequency = Column(String(16), nullable=False)  # 1m, 5m, 1d, REALTIME
    grace_period_seconds = Column(Integer, default=60, nullable=False)
    inactivity_threshold_seconds = Column(Integer, default=300, nullable=False)
    policy_parameters = Column(JSON, default=dict, nullable=False)
    priority = Column(Integer, default=10, nullable=False)  # Higher number = higher precedence
    effective_from = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    effective_until = Column(DateTime(timezone=True), nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class MissingDataIncident(Base):
    """Detected missing-data issues and gaps."""
    __tablename__ = "missing_data_incidents"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_key = Column(String(128), unique=True, nullable=False, index=True)  # Idempotent key
    instrument_id = Column(String(64), nullable=False, index=True)
    feed_id = Column(String(64), nullable=False, index=True)
    provider_id = Column(String(64), nullable=False)
    exchange = Column(String(16), nullable=False)
    data_type = Column(String(32), nullable=False)
    issue_type = Column(String(32), nullable=False, index=True)
    missing_start = Column(String(64), nullable=True)  # Timestamp or sequence
    missing_end = Column(String(64), nullable=True)
    missing_count = Column(Integer, default=1, nullable=False)
    first_detected_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_detected_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    issue_status = Column(String(32), default=IncidentStatus.OPEN.value, nullable=False, index=True)
    severity = Column(String(16), default=IncidentSeverity.WARNING.value, nullable=False)
    confidence = Column(Float, default=1.0, nullable=False)
    policy_id = Column(PG_UUID(as_uuid=True), nullable=True)
    evidence = Column(JSON, default=dict, nullable=False)
    resolution_reason = Column(String(256), nullable=True)


class MissingDataEvidence(Base):
    """Detailed evidence entries associated with a detected incident."""
    __tablename__ = "missing_data_evidence"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_key = Column(String(128), nullable=False, index=True)
    evidence_type = Column(String(64), nullable=False)
    expected_value = Column(String(128), nullable=True)
    observed_value = Column(String(128), nullable=True)
    provider_sequence = Column(Integer, nullable=True)
    event_timestamp = Column(DateTime(timezone=True), nullable=True)
    receive_timestamp = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    evidence_payload = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class CoverageWindow(Base):
    """Quantitative measurement of expected vs observed availability."""
    __tablename__ = "coverage_windows"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instrument_id = Column(String(64), nullable=False, index=True)
    feed_id = Column(String(64), nullable=False, index=True)
    provider_id = Column(String(64), nullable=False)
    exchange = Column(String(16), nullable=False)
    data_type = Column(String(32), nullable=False)
    interval_type = Column(String(16), nullable=False)  # 1m, 5m, 1d, REALTIME
    window_start = Column(DateTime(timezone=True), nullable=False, index=True)
    window_end = Column(DateTime(timezone=True), nullable=False, index=True)
    expected_units = Column(Integer, default=0, nullable=False)
    observed_units = Column(Integer, default=0, nullable=False)
    missing_units = Column(Integer, default=0, nullable=False)
    coverage_percentage = Column(Float, default=0.0, nullable=False)
    coverage_status = Column(String(32), default=CoverageStatus.COMPLETE.value, nullable=False)
    calculation_timestamp = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    policy_version = Column(String(32), default="1.0.0", nullable=False)
    calculation_metadata = Column(JSON, default=dict, nullable=False)

