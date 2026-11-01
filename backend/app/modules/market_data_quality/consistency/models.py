"""
SQLAlchemy 2.x ORM models for M03.06 - Data Consistency.
Defines tables for comparison rules, comparison runs, comparison results,
field consistency outcomes, conflicts, source precedence policies, and resolution history.
Compatible with SQLite and PostgreSQL.
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


class ConsistencyComparisonRule(Base):
    """
    TABLE 1: consistency_comparison_rules
    Stores versioned comparison policies, tolerance thresholds, and alignment windows.
    """
    __tablename__ = "m03_consistency_comparison_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    rule_name: Mapped[str] = mapped_column(String(128), nullable=False)

    comparison_type: Mapped[str] = mapped_column(String(32), default="CROSS_FEED", nullable=False)  # CROSS_FEED, FIELD_CONSISTENCY, REFERENCE_COMPARE
    observation_type: Mapped[str] = mapped_column(String(32), default="TICK", nullable=False)  # TICK, TRADE, OHLCV, QUOTE, DEPTH

    exchange: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    provider_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    feed_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    # Tolerances
    tolerance_type: Mapped[str] = mapped_column(String(32), default="PERCENTAGE", nullable=False)  # PERCENTAGE, ABSOLUTE, HYBRID
    percentage_tolerance: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0.5000"), nullable=False)  # e.g. 0.5%
    absolute_tolerance: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)  # in instrument currency
    percentage_calculation_method: Mapped[str] = mapped_column(String(32), default="REFERENCE_PRICE", nullable=False)  # REFERENCE_PRICE, SYMMETRIC_AVERAGE

    timestamp_alignment_ms: Mapped[int] = mapped_column(Integer, default=5000, nullable=False)  # Max ms difference between observations
    source_independence_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="WARNING", nullable=False)  # INFO, WARNING, HIGH, CRITICAL

    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    effective_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[str] = mapped_column(String(16), default="1.0.0", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    rule_parameters: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), default="system", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class ConsistencyComparisonRun(Base):
    """
    TABLE 2: consistency_comparison_runs
    Tracks execution batches of consistency evaluations across feeds and instruments.
    """
    __tablename__ = "m03_consistency_comparison_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), default="NSE", nullable=False)
    comparison_type: Mapped[str] = mapped_column(String(32), default="CROSS_FEED", nullable=False)
    observation_type: Mapped[str] = mapped_column(String(32), default="TICK", nullable=False)

    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    sources_compared: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    observations_compared: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    consistent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    inconsistent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    comparison_status: Mapped[str] = mapped_column(String(32), default="COMPLETED", nullable=False)  # COMPLETED, FAILED, PARTIAL
    rule_version_summary: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ConsistencyComparisonResult(Base):
    """
    TABLE 3: consistency_comparison_results
    Stores pairwise source comparison evidence and calculated absolute / percentage discrepancies.
    """
    __tablename__ = "m03_consistency_comparison_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    result_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    comparison_run_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)

    instrument_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), default="NSE", nullable=False)
    observation_type: Mapped[str] = mapped_column(String(32), default="TICK", nullable=False)

    source_a_provider: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source_a_feed: Mapped[str] = mapped_column(String(64), nullable=False)
    observation_a_id: Mapped[str] = mapped_column(String(64), nullable=False)
    value_a: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    timestamp_a: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    source_b_provider: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source_b_feed: Mapped[str] = mapped_column(String(64), nullable=False)
    observation_b_id: Mapped[str] = mapped_column(String(64), nullable=False)
    value_b: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    timestamp_b: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    absolute_difference: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    percentage_difference: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    tolerance_applied: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)

    comparison_method: Mapped[str] = mapped_column(String(32), default="REFERENCE_PRICE", nullable=False)
    comparison_status: Mapped[str] = mapped_column(String(32), default="CONSISTENT", index=True, nullable=False)  # CONSISTENT, INCONSISTENT, UNCOMPARABLE, CURRENCY_MISMATCH, TIMESTAMP_MISMATCH
    severity: Mapped[str] = mapped_column(String(32), default="PASS", nullable=False)
    rule_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    evidence: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_cons_res_inst_time", "instrument_id", "created_at"),
    )


class FieldConsistencyResult(Base):
    """
    TABLE 4: field_consistency_results
    Stores intra-observation mathematical relationship outcomes (e.g. High >= Low, Open/Close in range, non-negative quantities).
    """
    __tablename__ = "m03_field_consistency_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    result_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    observation_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    observation_type: Mapped[str] = mapped_column(String(32), default="OHLCV", nullable=False)

    field_a: Mapped[str] = mapped_column(String(32), nullable=False)  # e.g. high_price
    field_b: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # e.g. low_price
    value_a: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    value_b: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)

    relationship_operator: Mapped[str] = mapped_column(String(32), nullable=False)  # GTE, LTE, EQUAL, BETWEEN, NON_NEGATIVE
    expected_relationship: Mapped[str] = mapped_column(String(128), nullable=False)
    actual_result: Mapped[str] = mapped_column(String(128), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(32), default="FIELD_CONSISTENT", index=True, nullable=False)  # FIELD_CONSISTENT, FIELD_INCONSISTENT

    evidence: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ConsistencyConflict(Base):
    """
    TABLE 5: consistency_conflicts
    Tracks detected cross-feed disagreements and intra-field violations requiring resolution.
    """
    __tablename__ = "m03_consistency_conflicts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conflict_key: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), default="NSE", nullable=False)
    conflict_type: Mapped[str] = mapped_column(String(64), default="CROSS_FEED_DISCREPANCY", nullable=False)  # CROSS_FEED_DISCREPANCY, FIELD_RELATIONSHIP_VIOLATION
    observation_type: Mapped[str] = mapped_column(String(32), default="TICK", nullable=False)

    comparison_result_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    severity: Mapped[str] = mapped_column(String(32), default="WARNING", nullable=False)
    conflict_status: Mapped[str] = mapped_column(String(32), default="DETECTED", index=True, nullable=False)  # DETECTED, AUTO_RESOLVED, PENDING_MANUAL_REVIEW, MANUALLY_RESOLVED, UNRESOLVED

    selected_observation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    selected_source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    resolution_method: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # SOURCE_PRECEDENCE, MANUAL_OVERRIDE, SUPPRESSED
    resolution_rule_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    resolution_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)


class SourcePrecedenceRule(Base):
    """
    TABLE 6: source_precedence_rules
    Stores source ranking and hierarchy rules for automated conflict resolution.
    """
    __tablename__ = "m03_source_precedence_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), default="NSE", nullable=False)
    market: Mapped[str] = mapped_column(String(32), default="IN", nullable=False)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    observation_type: Mapped[str] = mapped_column(String(32), default="ALL", nullable=False)

    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    feed_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)  # Lower number = higher priority (e.g. 1 = highest)

    eligibility_requirements: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    effective_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[str] = mapped_column(String(16), default="1.0.0", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_by: Mapped[str] = mapped_column(String(64), default="system", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ConsistencyResolutionHistory(Base):
    """
    TABLE 7: consistency_resolution_history
    Immutable audit trail of automatic and manual resolution actions.
    """
    __tablename__ = "m03_consistency_resolution_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    history_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    conflict_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    conflict_key: Mapped[str] = mapped_column(String(128), index=True, nullable=False)

    resolution_action: Mapped[str] = mapped_column(String(64), nullable=False)  # AUTO_RESOLVE_PRECEDENCE, ACCEPT_SOURCE_A, ACCEPT_SOURCE_B, REJECT_BOTH, REOPEN
    selected_source_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    selected_observation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    previous_status: Mapped[str] = mapped_column(String(32), nullable=False)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), default="SYSTEM", nullable=False)  # SYSTEM, OPERATOR, ADMIN
    actor_id: Mapped[str] = mapped_column(String(64), default="automated_engine", nullable=False)

    justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
