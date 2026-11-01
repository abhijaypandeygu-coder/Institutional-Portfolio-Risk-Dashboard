"""
M03.05 - Duplicate Detection Models (SQLAlchemy 2.x).
Cross-compatible with PostgreSQL and SQLite.
Enforces unique event identity constraints, tracks duplicate receipts,
records identity conflicts, versioned detection rules, and aggregate metrics.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any
from sqlalchemy import (
    String, Integer, BigInteger, DateTime, Numeric, Boolean, Text, JSON, Index, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EventIdentityRegistry(Base):
    """
    TABLE 1: event_identity_registry
    Records canonical identity mappings with an authoritative uniqueness constraint.
    Guarantees exactly-once business record registration within its identity scope.
    """
    __tablename__ = "m03_event_identity_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    feed_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), default="NSE", nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)  # TRADE, QUOTE, SNAPSHOT, DELTA, OHLCV

    identity_strategy: Mapped[str] = mapped_column(String(64), nullable=False)  # PROVIDER_EVENT_ID, EXCHANGE_TRADE_ID, SEQUENCE_ID, COMPOSITE_FINGERPRINT
    identity_scope: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    payload_fingerprint: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # SHA-256 hash of business payload

    canonical_event_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    canonical_record_table: Mapped[str] = mapped_column(String(64), nullable=False)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    delivery_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    record_status: Mapped[str] = mapped_column(String(32), default="NEW_EVENT_ACCEPTED", nullable=False)  # NEW_EVENT_ACCEPTED, IDENTITY_CONFLICT, REVISION_PENDING

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_ev_id_scope_inst", "instrument_id", "event_type", "provider_id"),
    )


class DuplicateEventReceipt(Base):
    """
    TABLE 2: duplicate_event_receipts
    Records repeated deliveries of confirmed or suspected duplicate events.
    Auditable without creating duplicate business records or inflating volume.
    """
    __tablename__ = "m03_duplicate_event_receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    receipt_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    identity_registry_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    canonical_event_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    provider_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    feed_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)

    duplicate_reason: Mapped[str] = mapped_column(String(64), nullable=False)
    identity_strategy: Mapped[str] = mapped_column(String(64), nullable=False)

    incoming_provider_event_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    incoming_sequence: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    incoming_payload_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    original_receive_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duplicate_receive_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    processing_outcome: Mapped[str] = mapped_column(String(32), default="IGNORED_REPLAY", nullable=False)  # IGNORED_REPLAY, SUSPECTED_DUPLICATE
    evidence: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class EventIdentityConflict(Base):
    """
    TABLE 3: event_identity_conflicts
    Tracks occurrences where an incoming message matches an existing identity key
    but contains materially conflicting business content.
    """
    __tablename__ = "m03_event_identity_conflicts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conflict_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    identity_registry_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    canonical_event_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    incoming_event_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    original_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    incoming_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    conflict_type: Mapped[str] = mapped_column(String(64), default="PAYLOAD_MISMATCH", nullable=False)  # PAYLOAD_MISMATCH, TRADE_VALUE_MISMATCH, REVISION_PROPOSED
    conflict_status: Mapped[str] = mapped_column(String(32), default="OPEN", index=True, nullable=False)  # OPEN, RESOLVED, SUPPRESSED

    evidence: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class DuplicateDetectionRule(Base):
    """
    TABLE 4: duplicate_detection_rules
    Stores versioned detection policies for providers, feeds, instruments, and event types.
    """
    __tablename__ = "m03_duplicate_detection_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    rule_name: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)  # ALL, TRADE, QUOTE, SNAPSHOT, DELTA, OHLCV

    provider_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    feed_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    identity_strategy: Mapped[str] = mapped_column(String(64), default="AUTO_HIERARCHICAL", nullable=False)
    rule_parameters: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    confidence_policy: Mapped[str] = mapped_column(String(32), default="CONSERVATIVE", nullable=False)
    retention_policy: Mapped[str] = mapped_column(String(32), default="STANDARD_DURABLE", nullable=False)

    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    effective_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[str] = mapped_column(String(16), default="1.0.0", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_by: Mapped[str] = mapped_column(String(64), default="system", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class DuplicateDetectionMetrics(Base):
    """
    TABLE 5: duplicate_detection_metrics
    Stores aggregated duplicate counts, duplicate rates, and prevented volume/turnover.
    """
    __tablename__ = "m03_duplicate_detection_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    feed_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    duplicate_reason: Mapped[str] = mapped_column(String(64), default="ALL", nullable=False)

    interval_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    interval_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    total_deliveries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unique_canonical_events: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confirmed_duplicates: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    suspected_duplicates: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    identity_conflicts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    prevented_business_inserts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    prevented_volume: Mapped[Decimal] = mapped_column(Numeric(24, 4), default=Decimal("0.0"), nullable=False)
    prevented_turnover: Mapped[Decimal] = mapped_column(Numeric(24, 4), default=Decimal("0.0"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_dup_metrics_inst_time", "instrument_id", "interval_start"),
    )
