"""
M09.03 Liquidity Estimation - Database Models (SQLAlchemy 2.x).
Defines institutional relational tables for:
- liquidity_metric_configs (m09_03_liquidity_metric_configs)
- liquidity_volume_aggregates (m09_03_liquidity_volume_aggregates)
- liquidity_turnover_aggregates (m09_03_liquidity_turnover_aggregates)
- liquidity_rolling_statistics (m09_03_liquidity_rolling_statistics)
- liquidity_score_configs (m09_03_liquidity_score_configs)
- liquidity_score_snapshots (m09_03_liquidity_score_snapshots)
- liquidity_bucket_policies (m09_03_liquidity_bucket_policies)
- liquidity_bucket_snapshots (m09_03_liquidity_bucket_snapshots)
- liquidity_bucket_transitions (m09_03_liquidity_bucket_transitions)
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String,
    Integer,
    BigInteger,
    DateTime,
    Numeric,
    JSON,
    Boolean,
    Text,
    Index,
    UniqueConstraint,
    Float,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LiquidityMetricConfig(Base):
    """
    Versioned calculation configurations for volume and turnover aggregation.
    """
    __tablename__ = "m09_03_liquidity_metric_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    config_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    market: Mapped[str] = mapped_column(String(32), default="ALL", nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)

    volume_aggregation_interval: Mapped[str] = mapped_column(String(16), default="1d", nullable=False)
    turnover_aggregation_interval: Mapped[str] = mapped_column(String(16), default="1d", nullable=False)
    volume_lookback_sessions: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    turnover_lookback_sessions: Mapped[int] = mapped_column(Integer, default=20, nullable=False)

    spread_measure: Mapped[str] = mapped_column(String(32), default="TIME_WEIGHTED_BPS", nullable=False)
    depth_measure: Mapped[str] = mapped_column(String(32), default="TIME_WEIGHTED_NOTIONAL", nullable=False)
    depth_level_count: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    session_policy: Mapped[str] = mapped_column(String(32), default="COMPLETED_ONLY", nullable=False)
    minimum_coverage: Mapped[float] = mapped_column(Float, default=0.50, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)

    __table_args__ = (
        UniqueConstraint("config_code", "version", name="uq_m09_03_metric_cfg_code_ver"),
    )


class LiquidityVolumeAggregate(Base):
    """
    Executed traded quantity aggregates over discrete intervals (e.g. 5m, 1h, 1d session).
    """
    __tablename__ = "m09_03_liquidity_volume_aggregates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    aggregate_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    exchange: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    venue: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    aggregation_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    aggregation_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    aggregation_interval: Mapped[str] = mapped_column(String(16), default="1d", nullable=False)

    traded_volume: Mapped[Decimal] = mapped_column(Numeric(24, 4), nullable=False)
    eligible_trade_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_coverage_ratio: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    source_scope: Mapped[str] = mapped_column(String(32), default="VENUE_SPECIFIC", nullable=False)
    quality_status: Mapped[str] = mapped_column(String(32), default="ELIGIBLE", nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_m09_03_vol_inst_time", "instrument_id", "aggregation_start", "aggregation_end"),
    )


class LiquidityTurnoverAggregate(Base):
    """
    Executed monetary turnover aggregates over discrete intervals.
    """
    __tablename__ = "m09_03_liquidity_turnover_aggregates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    aggregate_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    exchange: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    venue: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    aggregation_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    aggregation_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    aggregation_interval: Mapped[str] = mapped_column(String(16), default="1d", nullable=False)

    turnover_amount: Mapped[Decimal] = mapped_column(Numeric(26, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    eligible_trade_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_coverage_ratio: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    source_scope: Mapped[str] = mapped_column(String(32), default="VENUE_SPECIFIC", nullable=False)
    quality_status: Mapped[str] = mapped_column(String(32), default="ELIGIBLE", nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_m09_03_tov_inst_time", "instrument_id", "aggregation_start", "aggregation_end"),
    )


class LiquidityRollingStatistics(Base):
    """
    Rolling statistical aggregates (ADV, ADTV, standard deviation, CV, percentiles, intraday pace).
    """
    __tablename__ = "m09_03_liquidity_rolling_statistics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stat_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    venue: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    as_of_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    lookback_sessions: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    eligible_session_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    coverage_ratio: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    average_daily_volume: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 4), nullable=True)
    median_daily_volume: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 4), nullable=True)
    volume_stddev: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 4), nullable=True)
    volume_cv: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume_percentiles: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    average_daily_turnover: Mapped[Optional[Decimal]] = mapped_column(Numeric(26, 4), nullable=True)
    median_daily_turnover: Mapped[Optional[Decimal]] = mapped_column(Numeric(26, 4), nullable=True)
    turnover_stddev: Mapped[Optional[Decimal]] = mapped_column(Numeric(26, 4), nullable=True)
    turnover_cv: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    turnover_percentiles: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)

    intraday_volume_pace: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    intraday_turnover_pace: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    quality_status: Mapped[str] = mapped_column(String(32), default="NORMAL", nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_m09_03_roll_inst_asof", "instrument_id", "as_of_timestamp"),
    )


class LiquidityScoreConfig(Base):
    """
    Scoring methodology, component weighting, and normalization parameters.
    """
    __tablename__ = "m09_03_liquidity_score_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    profile_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    market_scope: Mapped[str] = mapped_column(String(32), default="ALL", nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    peer_group_definition: Mapped[str] = mapped_column(String(64), default="MARKET_CAP_SECTOR", nullable=False)

    spread_weight: Mapped[float] = mapped_column(Float, default=0.25, nullable=False)
    depth_weight: Mapped[float] = mapped_column(Float, default=0.30, nullable=False)
    turnover_weight: Mapped[float] = mapped_column(Float, default=0.30, nullable=False)
    availability_weight: Mapped[float] = mapped_column(Float, default=0.15, nullable=False)

    minimum_spread_coverage: Mapped[float] = mapped_column(Float, default=0.50, nullable=False)
    minimum_depth_coverage: Mapped[float] = mapped_column(Float, default=0.50, nullable=False)
    minimum_turnover_coverage: Mapped[float] = mapped_column(Float, default=0.50, nullable=False)
    minimum_reference_sample_size: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    winsorization_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    winsor_lower_percentile: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    winsor_upper_percentile: Mapped[float] = mapped_column(Float, default=99.0, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)

    __table_args__ = (
        UniqueConstraint("profile_code", "version", name="uq_m09_03_score_cfg_code_ver"),
    )


class LiquidityScoreSnapshot(Base):
    """
    Point-in-time composite liquidity score and component subscores with full audit lineage.
    """
    __tablename__ = "m09_03_liquidity_score_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    exchange: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    venue: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)

    as_of_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    score_config_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    score_config_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    peer_group_id: Mapped[str] = mapped_column(String(64), default="DEFAULT_PEERS", nullable=False)

    # Raw metrics
    spread_raw_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # bps
    depth_raw_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 4), nullable=True)  # notional
    turnover_raw_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(26, 4), nullable=True)  # ADTV or session

    # Subscores (0.0 to 100.0)
    spread_subscore: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    depth_subscore: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    turnover_subscore: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    availability_subscore: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Contributions
    spread_contribution: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    depth_contribution: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    turnover_contribution: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    availability_contribution: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Coverage
    spread_coverage: Mapped[Optional[float]] = mapped_column(Float, default=1.0, nullable=True)
    depth_coverage: Mapped[Optional[float]] = mapped_column(Float, default=1.0, nullable=True)
    turnover_coverage: Mapped[Optional[float]] = mapped_column(Float, default=1.0, nullable=True)

    composite_liquidity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True, index=True)
    scoring_status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)  # ACTIVE, INSUFFICIENT_DATA
    status_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    calculation_version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_m09_03_score_inst_asof", "instrument_id", "as_of_timestamp"),
    )


class LiquidityBucketPolicy(Base):
    """
    Versioned classification policies defining bucket boundaries and methodologies.
    """
    __tablename__ = "m09_03_liquidity_bucket_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    policy_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    classification_method: Mapped[str] = mapped_column(String(32), default="SCORE_THRESHOLD", nullable=False)
    market_scope: Mapped[str] = mapped_column(String(32), default="ALL", nullable=False)

    # JSON representation of threshold boundaries
    threshold_definitions: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)

    __table_args__ = (
        UniqueConstraint("policy_code", "version", name="uq_m09_03_bucket_pol_code_ver"),
    )


class LiquidityBucketSnapshot(Base):
    """
    Point-in-time liquidity bucket classification record.
    """
    __tablename__ = "m09_03_liquidity_bucket_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    venue: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    as_of_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    liquidity_score_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    bucket_policy_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    bucket_policy_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    bucket_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    bucket_rank: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    underlying_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    peer_group_percentile: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    classification_status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    classification_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_m09_03_bucket_inst_asof", "instrument_id", "as_of_timestamp"),
    )


class LiquidityBucketTransition(Base):
    """
    Tracks transitions between liquidity buckets over time.
    """
    __tablename__ = "m09_03_liquidity_bucket_transitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transition_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    previous_bucket: Mapped[str] = mapped_column(String(64), nullable=False)
    new_bucket: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    new_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    previous_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    new_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    bucket_policy_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    transition_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    transition_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_m09_03_trans_inst_time", "instrument_id", "transition_timestamp"),
    )
