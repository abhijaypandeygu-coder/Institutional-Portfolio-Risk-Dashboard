"""
SQLAlchemy ORM models for M03.04 - Order Book Validation.
Supports PostgreSQL (JSON) and SQLite compatible structures.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Any, Dict
from sqlalchemy import String, Integer, DateTime, Numeric, Boolean, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class BookValidationRule(Base):
    """
    Validation rules governing order book cross, lock, quantity, continuity, and structure checks.
    """
    __tablename__ = "m03_book_validation_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    rule_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Scope
    feed_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    symbol: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    venue: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)

    # Thresholds & Parameters
    max_crossed_duration_ms: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    max_cross_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    allow_auction_cross: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_auction_lock: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_locked_duration_ms: Mapped[int] = mapped_column(Integer, default=100, nullable=False)

    # Quantity Rules
    allow_fractional_shares: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    min_lot_size: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1.0"), nullable=False)
    max_order_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)

    # Continuity Rules
    max_allowed_sequence_gap: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0 = strict gapless
    auto_trigger_resync: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class BookValidationResult(Base):
    """
    Validation results for order book evaluations (snapshots or incremental deltas).
    """
    __tablename__ = "m03_book_validation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    validation_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    feed_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    venue: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    session_phase: Mapped[str] = mapped_column(String(32), default="CONTINUOUS_TRADING", nullable=False)
    data_origin: Mapped[str] = mapped_column(String(32), default="SIMULATOR", nullable=False)

    # Observation details
    sequence_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_snapshot: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Best prices & quantities
    best_bid_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    best_bid_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    best_ask_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    best_ask_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)

    # Validation Flags
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_crossed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_quantity_anomaly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_continuity_break: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_structural_defect: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Classifications
    crossed_classification: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    locked_classification: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    cross_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)

    # Metric Eligibility Gates
    spread_eligible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    imbalance_eligible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    depth_eligible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    liquidity_eligible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    execution_research_eligible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Diagnostics
    severity: Mapped[str] = mapped_column(String(32), default="INFO", nullable=False)
    diagnostics: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)


class BookIntegrityIncident(Base):
    """
    Tracks persistent, severe, or suspicious order book anomalies requiring operator intervention or resync.
    """
    __tablename__ = "m03_book_integrity_incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_key: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    incident_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # CROSSED_BOOK, LOCKED_BOOK, QUANTITY_ANOMALY, CONTINUITY_BREAK
    severity: Mapped[str] = mapped_column(String(32), default="WARNING", nullable=False)

    feed_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    venue: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    session_phase: Mapped[str] = mapped_column(String(32), default="CONTINUOUS_TRADING", nullable=False)

    status: Mapped[str] = mapped_column(String(32), default="OPEN", index=True, nullable=False)  # OPEN, RESOLVED, SUPPRESSED
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class BookResynchronizationRequest(Base):
    """
    Tracks automated or manual requests sent to M02 Market Data Ingestion to resynchronize an order book.
    """
    __tablename__ = "m03_book_resync_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    feed_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    venue: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    reason: Mapped[str] = mapped_column(String(64), nullable=False)  # SEQUENCE_GAP, SNAPSHOT_CORRUPT, PERSISTENT_CROSS, RESTORATION_TIMEOUT
    from_sequence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    to_sequence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="INITIATED", index=True, nullable=False)  # INITIATED, DISPATCHED, COMPLETED, FAILED

    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    m02_acknowledgment: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)


class BookValidationEvidence(Base):
    """
    Audit log of raw and normalized order book payloads alongside validation outcomes.
    """
    __tablename__ = "m03_book_validation_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    validation_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    raw_payload_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parsed_levels: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    rule_evaluations: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
