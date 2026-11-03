"""
M09.02 Order Book Depth - Database Models (SQLAlchemy 2.x).
Defines institutional relational tables:
1. m09_02_depth_calculation_configs
2. m09_02_order_book_depth_snapshots
3. m09_02_order_book_depth_levels
4. m09_02_order_book_depth_bands
5. m09_02_order_book_depth_persistence
6. m09_02_order_book_depth_history_aggregates
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
    ForeignKey,
    Float,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DepthCalculationConfig(Base):
    """
    Immutable versioned depth calculation configurations and policies.
    """
    __tablename__ = "m09_02_depth_calculation_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    config_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    venue: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # NSE, BSE, NYSE, NASDAQ, or NULL for global
    aggregation_mode: Mapped[str] = mapped_column(String(32), default="LEVEL_BASED", nullable=False)  # LEVEL_BASED, TICK_DISTANCE, BPS_DISTANCE
    level_count: Mapped[int] = mapped_column(Integer, default=5, nullable=False)  # e.g. 5, 10, 20
    distance_unit: Mapped[str] = mapped_column(String(16), default="BPS", nullable=False)
    distance_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reference_price_method: Mapped[str] = mapped_column(String(32), default="MIDPOINT", nullable=False)
    measure_type: Mapped[str] = mapped_column(String(32), default="QUANTITY_AND_NOTIONAL", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    contract_multiplier: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("1.0"), nullable=False)

    weighting_method: Mapped[str] = mapped_column(String(32), default="EXPONENTIAL_DECAY", nullable=False)
    weighting_parameter: Mapped[float] = mapped_column(Float, default=0.05, nullable=False)
    minimum_depth_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    maximum_state_age_seconds: Mapped[float] = mapped_column(Float, default=10.0, nullable=False)

    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)

    __table_args__ = (
        UniqueConstraint("config_code", "version", name="uq_m09_02_cfg_code_ver"),
    )


class OrderBookDepthSnapshot(Base):
    """
    Stores top-level derived depth summary from an eligible reconstructed book state.
    """
    __tablename__ = "m09_02_order_book_depth_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    depth_snapshot_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    exchange: Mapped[str] = mapped_column(String(16), nullable=False)
    venue: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    book_scope: Mapped[str] = mapped_column(String(32), default="VENUE_SPECIFIC", nullable=False)

    source_feed_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_book_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    sequence_number: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    received_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    calculation_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    best_bid_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    best_ask_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    midpoint_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)

    bid_level_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ask_level_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    bid_total_quantity: Mapped[Decimal] = mapped_column(Numeric(22, 4), default=Decimal("0"), nullable=False)
    ask_total_quantity: Mapped[Decimal] = mapped_column(Numeric(22, 4), default=Decimal("0"), nullable=False)
    bid_total_notional: Mapped[Decimal] = mapped_column(Numeric(24, 4), default=Decimal("0"), nullable=False)
    ask_total_notional: Mapped[Decimal] = mapped_column(Numeric(24, 4), default=Decimal("0"), nullable=False)

    quantity_imbalance: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    notional_imbalance: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    weighted_imbalance: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)

    depth_quality_status: Mapped[str] = mapped_column(String(32), default="VALID", nullable=False, index=True)
    quality_reasons: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    calculation_config_id: Mapped[str] = mapped_column(String(64), nullable=False)
    calculation_config_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        Index("ix_m09_depth_inst_time", "instrument_id", "event_timestamp"),
        Index("ix_m09_depth_venue_time", "venue", "event_timestamp"),
    )


class OrderBookDepthLevel(Base):
    """
    Stores individual price-level derived depth records (Level 1 to N for Bid and Ask).
    """
    __tablename__ = "m09_02_order_book_depth_levels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    level_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    depth_snapshot_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m09_02_order_book_depth_snapshots.depth_snapshot_id", ondelete="CASCADE"), nullable=False, index=True
    )
    side: Mapped[str] = mapped_column(String(8), nullable=False)  # BID, ASK
    level_index: Mapped[int] = mapped_column(Integer, nullable=False)  # 1, 2, 3...
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    displayed_quantity: Mapped[Decimal] = mapped_column(Numeric(22, 4), nullable=False)
    displayed_notional: Mapped[Decimal] = mapped_column(Numeric(24, 4), nullable=False)
    cumulative_quantity: Mapped[Decimal] = mapped_column(Numeric(22, 4), nullable=False)
    cumulative_notional: Mapped[Decimal] = mapped_column(Numeric(24, 4), nullable=False)

    distance_from_midpoint: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    distance_bps: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    distance_ticks: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    order_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_m09_depth_lvl_snap_side", "depth_snapshot_id", "side", "level_index"),
    )


class OrderBookDepthBand(Base):
    """
    Stores liquidity aggregated across defined distance bands from midpoint.
    """
    __tablename__ = "m09_02_order_book_depth_bands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    band_record_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    depth_snapshot_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m09_02_order_book_depth_snapshots.depth_snapshot_id", ondelete="CASCADE"), nullable=False, index=True
    )
    band_id: Mapped[str] = mapped_column(String(32), nullable=False)  # e.g. BAND_0_5_BPS
    band_lower_bound: Mapped[float] = mapped_column(Float, nullable=False)
    band_upper_bound: Mapped[float] = mapped_column(Float, nullable=False)
    distance_unit: Mapped[str] = mapped_column(String(16), default="BPS", nullable=False)

    bid_quantity: Mapped[Decimal] = mapped_column(Numeric(22, 4), default=Decimal("0"), nullable=False)
    ask_quantity: Mapped[Decimal] = mapped_column(Numeric(22, 4), default=Decimal("0"), nullable=False)
    bid_notional: Mapped[Decimal] = mapped_column(Numeric(24, 4), default=Decimal("0"), nullable=False)
    ask_notional: Mapped[Decimal] = mapped_column(Numeric(24, 4), default=Decimal("0"), nullable=False)
    bid_level_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ask_level_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    quantity_imbalance: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    notional_imbalance: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class OrderBookDepthPersistence(Base):
    """
    Time-weighted depth persistence and stability records across analysis windows (1m, 5m, 15m, 1h).
    """
    __tablename__ = "m09_02_order_book_depth_persistence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    persistence_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    venue: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    config_id: Mapped[str] = mapped_column(String(64), nullable=False)
    config_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)

    bid_time_weighted_mean: Mapped[Optional[Decimal]] = mapped_column(Numeric(22, 4), nullable=True)
    ask_time_weighted_mean: Mapped[Optional[Decimal]] = mapped_column(Numeric(22, 4), nullable=True)
    bid_time_weighted_stddev: Mapped[Optional[Decimal]] = mapped_column(Numeric(22, 4), nullable=True)
    ask_time_weighted_stddev: Mapped[Optional[Decimal]] = mapped_column(Numeric(22, 4), nullable=True)

    bid_depth_cv: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ask_depth_cv: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    bid_threshold_persistence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ask_threshold_persistence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_level_persistence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    depth_stability_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    valid_duration_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    expected_duration_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    coverage_percentage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    valid_state_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    quality_status: Mapped[str] = mapped_column(String(32), default="SUFFICIENT", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class OrderBookDepthHistoryAggregate(Base):
    """
    Aggregated historical depth interval summaries.
    """
    __tablename__ = "m09_02_order_book_depth_history_aggregates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    aggregate_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    venue: Mapped[str] = mapped_column(String(32), nullable=False)
    aggregation_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    aggregation_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    aggregation_interval: Mapped[str] = mapped_column(String(16), nullable=False)  # 1m, 5m, 15m, 1h, 1d

    average_bid_depth: Mapped[Optional[Decimal]] = mapped_column(Numeric(22, 4), nullable=True)
    average_ask_depth: Mapped[Optional[Decimal]] = mapped_column(Numeric(22, 4), nullable=True)
    average_bid_notional: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 4), nullable=True)
    average_ask_notional: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 4), nullable=True)

    average_quantity_imbalance: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    average_notional_imbalance: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)

    maximum_bid_depth: Mapped[Optional[Decimal]] = mapped_column(Numeric(22, 4), nullable=True)
    maximum_ask_depth: Mapped[Optional[Decimal]] = mapped_column(Numeric(22, 4), nullable=True)
    minimum_bid_depth: Mapped[Optional[Decimal]] = mapped_column(Numeric(22, 4), nullable=True)
    minimum_ask_depth: Mapped[Optional[Decimal]] = mapped_column(Numeric(22, 4), nullable=True)

    coverage_percentage: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    valid_observation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quality_status: Mapped[str] = mapped_column(String(32), default="VALID", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
