"""
M03.07 - Quality Scoring Models (SQLAlchemy 2.x).
Cross-compatible with SQLite and PostgreSQL.
Tables for scoring policies, scoring execution runs, feed reliability,
completeness, freshness, composite quality snapshots, and use eligibility decisions.
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


class QualityScoringPolicy(Base):
    """
    TABLE 1: quality_scoring_policies
    Versioned scoring parameters, component weights, and rolling-window configurations.
    """
    __tablename__ = "m03_quality_scoring_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    policy_name: Mapped[str] = mapped_column(String(128), nullable=False)

    score_type: Mapped[str] = mapped_column(String(32), default="COMPOSITE", nullable=False)  # RELIABILITY, COMPLETENESS, FRESHNESS, COMPOSITE
    provider_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    feed_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    data_type: Mapped[str] = mapped_column(String(32), default="ALL", nullable=False)  # ALL, TICK, OHLCV, TRADE, DEPTH
    rolling_window: Mapped[str] = mapped_column(String(32), default="24h", nullable=False)  # 1h, 6h, 24h, 7d, 30d

    # Reliability Weights (Availability + Timeliness + Error = 1.0)
    availability_weight: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.4000"), nullable=False)
    timeliness_weight: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.3500"), nullable=False)
    error_weight: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.2500"), nullable=False)

    # Composite Weights (Reliability + Completeness + Freshness = 1.0)
    reliability_weight: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.3500"), nullable=False)
    completeness_weight: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.3500"), nullable=False)
    freshness_weight: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.3000"), nullable=False)

    threshold_config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    missing_component_policy: Mapped[str] = mapped_column(String(32), default="PARTIAL_SCORE", nullable=False)  # PARTIAL_SCORE, REJECT, UNKNOWN

    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    effective_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[str] = mapped_column(String(16), default="1.0.0", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_by: Mapped[str] = mapped_column(String(64), default="system", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class QualityScoreRun(Base):
    """
    TABLE 2: quality_score_runs
    Tracks execution batches of quality scoring calculations.
    """
    __tablename__ = "m03_quality_score_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    run_type: Mapped[str] = mapped_column(String(32), default="SCHEDULED", nullable=False)  # SCHEDULED, AD_HOC, RECALCULATION
    scoring_scope: Mapped[str] = mapped_column(String(32), default="FEED", nullable=False)  # FEED, PROVIDER, INSTRUMENT, DATASET

    provider_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    feed_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    calculation_context: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    run_status: Mapped[str] = mapped_column(String(32), default="COMPLETED", nullable=False)  # COMPLETED, FAILED, PARTIAL

    policy_version_summary: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class FeedReliabilityScore(Base):
    """
    TABLE 3: feed_reliability_scores
    Operational reliability scores based on availability, timeliness, and error rates.
    """
    __tablename__ = "m03_feed_reliability_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    score_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    score_run_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)

    provider_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    feed_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    data_type: Mapped[str] = mapped_column(String(32), default="ALL", nullable=False)

    availability_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    timeliness_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    error_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    reliability_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    reliability_classification: Mapped[str] = mapped_column(String(32), nullable=False)  # EXCELLENT, GOOD, ACCEPTABLE, POOR, UNRELIABLE

    # Raw telemetry details
    expected_duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unavailable_duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    eligible_operations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_operations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    timely_observations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    late_observations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    calculation_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_feed_rel_feed_time", "feed_id", "calculated_at"),
    )


class CompletenessScore(Base):
    """
    TABLE 4: completeness_scores
    Evaluates expected vs observed records and field-level completeness.
    """
    __tablename__ = "m03_completeness_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    score_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    score_run_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)

    provider_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    feed_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    data_type: Mapped[str] = mapped_column(String(32), default="OHLCV", nullable=False)

    expected_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    observed_unique_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    missing_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invalid_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_receipts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    field_completeness_ratio: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("1.0000"), nullable=False)
    completeness_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    completeness_classification: Mapped[str] = mapped_column(String(32), nullable=False)  # COMPLETE, MOSTLY_COMPLETE, PARTIALLY_COMPLETE, INCOMPLETE

    calculation_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class FreshnessScore(Base):
    """
    TABLE 5: freshness_scores
    Evaluates observation ages against cadence SLAs and assigns piecewise scores.
    """
    __tablename__ = "m03_freshness_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    score_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    score_run_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)

    provider_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    feed_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    data_type: Mapped[str] = mapped_column(String(32), default="TICK", nullable=False)
    calculation_context: Mapped[str] = mapped_column(String(64), default="LIVE_MONITORING", nullable=False)

    target_age_ms: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    maximum_age_ms: Mapped[int] = mapped_column(Integer, default=10000, nullable=False)
    observed_age_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    freshness_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    freshness_classification: Mapped[str] = mapped_column(String(32), nullable=False)  # FRESH, AGING, STALE, CRITICALLY_STALE, HISTORICAL, MARKET_CLOSED

    calculation_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class DataQualitySnapshot(Base):
    """
    TABLE 6: data_quality_snapshots
    Composite quality score summary across reliability, completeness, and freshness.
    """
    __tablename__ = "m03_data_quality_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    score_run_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)

    provider_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    feed_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    data_type: Mapped[str] = mapped_column(String(32), default="ALL", nullable=False)

    reliability_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    completeness_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    freshness_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    composite_quality_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    score_status: Mapped[str] = mapped_column(String(32), default="SCORE_AVAILABLE", nullable=False)
    data_origin: Mapped[str] = mapped_column(String(32), default="SIMULATED", nullable=False)  # REAL, SIMULATED

    policy_version_summary: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class UseEligibilityProfile(Base):
    """
    TABLE 7: use_eligibility_profiles
    Defines downstream calculation criteria (e.g. Daily VaR, Spread, Depth Imbalance).
    """
    __tablename__ = "m03_use_eligibility_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)  # DAILY_VALUATION, HISTORICAL_VAR, SPREAD_CALCULATION, ORDER_BOOK_IMBALANCE
    calculation_name: Mapped[str] = mapped_column(String(128), nullable=False)

    required_data_types: Mapped[str] = mapped_column(String(128), default="TICK", nullable=False)  # comma separated
    minimum_reliability: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("70.00"), nullable=False)
    minimum_completeness: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("90.00"), nullable=False)
    minimum_freshness: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("50.00"), nullable=False)

    hard_gate_config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    data_origin_policy: Mapped[str] = mapped_column(String(32), default="ANY", nullable=False)  # ANY, REAL_ONLY, SIMULATED_ALLOWED

    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    effective_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[str] = mapped_column(String(16), default="1.0.0", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_by: Mapped[str] = mapped_column(String(64), default="system", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class UseEligibilityDecision(Base):
    """
    TABLE 8: use_eligibility_decisions
    Formal decision gating data for downstream financial calculations.
    """
    __tablename__ = "m03_use_eligibility_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    decision_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    profile_code: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    provider_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    feed_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    calculation_context: Mapped[str] = mapped_column(String(64), nullable=False)

    eligibility_status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)  # ACCEPTED, ACCEPTED_WITH_WARNING, RESTRICTED, REJECTED, NOT_SUPPORTED, UNKNOWN
    reliability_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    completeness_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    freshness_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)

    hard_gate_results: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    restriction_reasons: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    warning_reasons: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    decision_explanation: Mapped[str] = mapped_column(Text, nullable=False)

    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

