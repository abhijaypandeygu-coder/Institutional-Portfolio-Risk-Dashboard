"""
SQLAlchemy 2.x Declarative Models for M09.08 Order Book Imbalance.
Tables:
- m09_order_book_imbalance_configs
- m09_order_book_imbalance_snapshots
- m09_order_book_imbalance_persistence
- m09_order_book_imbalance_reversals
- m09_order_book_imbalance_monitoring
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import (
    String,
    Integer,
    Numeric,
    DateTime,
    Boolean,
    ForeignKey,
    Text,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class OrderBookImbalanceConfig(Base):
    """Stores versioned calculation configurations for order book imbalance."""

    __tablename__ = "m09_order_book_imbalance_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    config_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    depth_level_count: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    weighting_method: Mapped[str] = mapped_column(String(32), default="EQUAL", nullable=False)  # EQUAL, EXPONENTIAL_LEVEL, LINEAR_LEVEL, DISTANCE_DECAY, CUSTOM
    decay_parameter: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.5000"), nullable=False)
    distance_unit: Mapped[str] = mapped_column(String(16), default="PRICE", nullable=False)  # PRICE, TICK, BPS
    custom_weights_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    persistence_threshold: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.2000"), nullable=False)
    reversal_entry_threshold: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.2000"), nullable=False)
    reversal_exit_threshold: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.0500"), nullable=False)

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    snapshots: Mapped[List["OrderBookImbalanceSnapshot"]] = relationship(
        "OrderBookImbalanceSnapshot", back_populates="config", cascade="all, delete-orphan"
    )


class OrderBookImbalanceSnapshot(Base):
    """Stores point-in-time calculated imbalance indicators for an order book snapshot."""

    __tablename__ = "m09_order_book_imbalance_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    venue_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    source_book_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    event_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    calculation_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    best_level_imbalance: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    multi_level_quantity_imbalance: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    multi_level_notional_imbalance: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    weighted_quantity_imbalance: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    weighted_notional_imbalance: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)

    bid_share: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4), nullable=True)
    ask_share: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4), nullable=True)

    total_bid_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    total_ask_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    total_bid_notional: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    total_ask_notional: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)

    microprice: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    midpoint: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    microprice_deviation_bps: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)

    actual_level_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    regime: Mapped[str] = mapped_column(String(32), default="NEUTRAL", nullable=False)

    config_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m09_order_book_imbalance_configs.config_id", ondelete="CASCADE"), nullable=False
    )
    quality_status: Mapped[str] = mapped_column(String(32), default="ELIGIBLE", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    config: Mapped["OrderBookImbalanceConfig"] = relationship("OrderBookImbalanceConfig", back_populates="snapshots")


class OrderBookImbalancePersistenceResult(Base):
    """Stores calculated persistence metrics over a specified historical window."""

    __tablename__ = "m09_order_book_imbalance_persistence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    persistence_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    venue_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    bid_persistence_ratio: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    ask_persistence_ratio: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    neutral_persistence_ratio: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)

    current_state: Mapped[str] = mapped_column(String(32), default="NEUTRAL", nullable=False)
    current_run_duration_seconds: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0"), nullable=False)
    max_bid_run_seconds: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0"), nullable=False)
    max_ask_run_seconds: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0"), nullable=False)
    average_bid_run_seconds: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0"), nullable=False)
    average_ask_run_seconds: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0"), nullable=False)

    total_valid_duration_seconds: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class OrderBookImbalanceReversalEvent(Base):
    """Stores state and sign transition events."""

    __tablename__ = "m09_order_book_imbalance_reversals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reversal_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    venue_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    reversal_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    previous_state: Mapped[str] = mapped_column(String(32), nullable=False)
    new_state: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_imbalance: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    current_imbalance: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    reversal_magnitude: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    reversal_rate_per_sec: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0.0"), nullable=False)
    duration_seconds: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("1.0"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class OrderBookImbalanceMonitoringSnapshot(Base):
    """Stores ongoing monitoring status and alert tracking."""

    __tablename__ = "m09_order_book_imbalance_monitoring"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    venue_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    monitoring_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    latest_imbalance: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    rolling_mean_imbalance: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    bid_persistence_ratio: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    ask_persistence_ratio: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    reversal_count_24h: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    regime: Mapped[str] = mapped_column(String(32), default="NEUTRAL", nullable=False)
    monitoring_status: Mapped[str] = mapped_column(String(32), default="NORMAL", nullable=False)  # NORMAL, WARNING, BREACH
    alert_message: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

