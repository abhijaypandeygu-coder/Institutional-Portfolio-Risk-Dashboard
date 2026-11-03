"""
M09.01 Bid-Ask Spread - Database Models (SQLAlchemy 2.x).
Defines institutional relational tables for:
- spread_calculation_configs (M09_01_spread_calculation_configs)
- spread_observations (M09_01_spread_observations)
- spread_quality_results (M09_01_spread_quality_results)
- spread_interval_aggregates (M09_01_spread_interval_aggregates)
- spread_session_summaries (M09_01_spread_session_summaries)
- spread_quality_summaries (M09_01_spread_quality_summaries)
"""

from datetime import datetime, timezone, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String,
    Integer,
    BigInteger,
    DateTime,
    Date,
    Numeric,
    JSON,
    Boolean,
    Text,
    Index,
    UniqueConstraint,
    ForeignKey,
    Float,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SpreadCalculationConfig(Base):
    """
    Immutable versioned spread calculation policies and thresholds.
    """
    __tablename__ = "m09_01_spread_calculation_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    config_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    book_scope: Mapped[str] = mapped_column(String(32), default="VENUE_SPECIFIC", nullable=False)  # VENUE_SPECIFIC, CONSOLIDATED
    relative_spread_method: Mapped[str] = mapped_column(String(32), default="MIDPOINT_NORMALIZED", nullable=False)  # MIDPOINT_NORMALIZED, BID_NORMALIZED, ASK_NORMALIZED, REFERENCE_PRICE_NORMALIZED
    locked_book_policy: Mapped[str] = mapped_column(String(32), default="INCLUDE_AS_ZERO", nullable=False)  # INCLUDE_AS_ZERO, EXCLUDE, FLAG_ANOMALY
    
    maximum_quote_age_seconds: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    maximum_quote_skew_seconds: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    
    session_policy: Mapped[str] = mapped_column(String(32), default="CONTINUOUS_ONLY", nullable=False)  # CONTINUOUS_ONLY, ALL_SESSIONS, EXCLUDE_AUCTION
    minimum_source_quality: Mapped[str] = mapped_column(String(32), default="NORMAL", nullable=False)
    tick_validation_policy: Mapped[str] = mapped_column(String(32), default="STRICT_ALIGNMENT", nullable=False)  # STRICT_ALIGNMENT, WARN_ONLY, IGNORE
    outlier_warning_policy: Mapped[str] = mapped_column(String(32), default="FLAG_ONLY", nullable=False)

    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint("config_code", "version", name="uq_m09_01_config_code_version"),
    )


class SpreadObservation(Base):
    """
    Stores top-of-book absolute and relative bid-ask spread observations linked to source quote states.
    """
    __tablename__ = "m09_01_spread_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    observation_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    exchange: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # NSE, BSE, NYSE, NASDAQ
    venue: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    book_scope: Mapped[str] = mapped_column(String(32), default="VENUE_SPECIFIC", nullable=False)
    source_feed_id: Mapped[str] = mapped_column(String(64), nullable=False)

    source_quote_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    book_snapshot_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    bid_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    ask_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    bid_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    ask_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)

    bid_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ask_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    book_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    receive_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    quote_skew_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quote_age_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    absolute_spread: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    midpoint_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    relative_spread_decimal: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    relative_spread_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    relative_spread_bps: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)

    spread_ticks: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    tick_size_reference: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)

    session_type: Mapped[str] = mapped_column(String(32), default="REGULAR_TRADING", nullable=False)
    quality_status: Mapped[str] = mapped_column(String(32), default="VALID", nullable=False, index=True)
    quality_reason_codes: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    calculation_config_id: Mapped[str] = mapped_column(String(64), nullable=False)
    calculation_config_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_m09_obs_inst_time", "instrument_id", "book_timestamp"),
        Index("ix_m09_obs_venue_time", "venue", "book_timestamp"),
    )


class SpreadQualityResult(Base):
    """
    Granular diagnostic check results per observation or rejected quote state.
    """
    __tablename__ = "m09_01_spread_quality_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    result_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    observation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    source_quote_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    quality_check_type: Mapped[str] = mapped_column(String(64), nullable=False)  # PRICE_VALIDITY, SYNCHRONIZATION, STALENESS, CROSSED_BOOK, etc.
    quality_status: Mapped[str] = mapped_column(String(32), nullable=False)  # PASS, WARNING, FAIL
    severity: Mapped[str] = mapped_column(String(16), default="INFO", nullable=False)  # INFO, WARNING, ERROR, HARD_GATE
    measured_value: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    threshold_value: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    diagnostic_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class SpreadIntervalAggregate(Base):
    """
    Aggregated spread statistics across configurable intervals (1s, 5s, 1m, 5m, 15m, 1h).
    """
    __tablename__ = "m09_01_spread_interval_aggregates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    aggregate_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    exchange: Mapped[str] = mapped_column(String(16), nullable=False)
    venue: Mapped[str] = mapped_column(String(32), nullable=False)
    book_scope: Mapped[str] = mapped_column(String(32), default="VENUE_SPECIFIC", nullable=False)

    aggregation_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    aggregation_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    aggregation_frequency: Mapped[str] = mapped_column(String(16), nullable=False)  # 1s, 5s, 1m, 5m, 15m, 1h
    aggregation_method: Mapped[str] = mapped_column(String(32), default="HYBRID_OBS_TIME", nullable=False)

    mean_absolute_spread: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    median_absolute_spread: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    minimum_absolute_spread: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    maximum_absolute_spread: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    p90_absolute_spread: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    p95_absolute_spread: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    p99_absolute_spread: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)

    mean_relative_spread: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    median_relative_spread: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    p90_relative_spread: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    p95_relative_spread: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)

    mean_relative_spread_bps: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    median_relative_spread_bps: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)

    mean_time_weighted_spread: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    mean_time_weighted_relative_spread: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)

    valid_observation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invalid_observation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stale_observation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_book_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    crossed_book_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    valid_time_coverage_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    expected_time_coverage_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    coverage_percentage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    data_watermark: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    calculation_config_id: Mapped[str] = mapped_column(String(64), nullable=False)
    calculation_config_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    result_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_m09_agg_inst_freq", "instrument_id", "aggregation_frequency", "aggregation_start"),
    )


class SpreadSessionSummary(Base):
    """
    Daily or trading-session spread summary.
    """
    __tablename__ = "m09_01_spread_session_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    summary_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    exchange: Mapped[str] = mapped_column(String(16), nullable=False)
    venue: Mapped[str] = mapped_column(String(32), nullable=False)
    trading_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    session_type: Mapped[str] = mapped_column(String(32), default="REGULAR_TRADING", nullable=False)

    mean_absolute_spread: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    median_absolute_spread: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    p90_absolute_spread: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    p95_absolute_spread: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)

    mean_relative_spread: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    median_relative_spread: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    p90_relative_spread: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)

    time_weighted_spread: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    time_weighted_relative_spread: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)

    valid_observation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_time_coverage_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    coverage_percentage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    excluded_observation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    quality_status: Mapped[str] = mapped_column(String(32), default="SUFFICIENT", nullable=False)
    calculation_config_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    result_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("instrument_id", "exchange", "venue", "trading_date", "session_type", "result_version", name="uq_m09_sess_summary"),
    )


class SpreadQualitySummary(Base):
    """
    Aggregated quality health summary tracking invalid/stale/crossed/locked quote frequencies.
    """
    __tablename__ = "m09_01_spread_quality_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    summary_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    exchange: Mapped[str] = mapped_column(String(16), nullable=False)
    venue: Mapped[str] = mapped_column(String(32), nullable=False)

    aggregation_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    aggregation_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    valid_quote_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stale_quote_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    crossed_book_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_book_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    missing_bid_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    missing_ask_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unsynchronized_quote_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sequence_error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invalid_price_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    out_of_session_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    quality_coverage_percentage: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    summary_status: Mapped[str] = mapped_column(String(32), default="HEALTHY", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

