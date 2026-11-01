"""
Module 02: Market Data Ingestion Engine - Database Models (SQLAlchemy 2.x).
Defines persistence models for raw events, normalized ticks, OHLCV, trades,
order book snapshots/deltas, checkpoints, and backfill jobs.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import (
    Column, String, Integer, BigInteger, DateTime, Numeric, JSON, Boolean, Text, Index, UniqueConstraint, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RawMarketEvent(Base):
    """Immutable log of raw received messages with full source provenance."""
    __tablename__ = "raw_market_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    feed_id = Column(String(64), nullable=False, index=True)
    provider_id = Column(String(64), nullable=False)
    event_type = Column(String(32), nullable=False, index=True)  # TICK, OHLCV, TRADE, SNAPSHOT, DELTA
    provider_event_id = Column(String(128), nullable=True)
    provider_sequence = Column(BigInteger, nullable=True)
    instrument_reference = Column(String(64), nullable=False, index=True)
    event_timestamp = Column(DateTime(timezone=True), nullable=False)
    receive_timestamp = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    raw_payload = Column(JSON, nullable=False)
    schema_version = Column(String(16), default="1.0.0", nullable=False)
    processing_status = Column(String(32), default="PROCESSED", nullable=False)


class NormalizedMarketTick(Base):
    """Normalized real-time market ticks / Level 1 updates."""
    __tablename__ = "normalized_market_ticks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(64), unique=True, nullable=False, index=True)
    feed_id = Column(String(64), nullable=False, index=True)
    instrument_id = Column(String(64), nullable=False, index=True)
    exchange = Column(String(16), default="NSE", nullable=False)
    symbol = Column(String(32), nullable=False)
    price = Column(Numeric(18, 4), nullable=False)
    quantity = Column(Numeric(18, 4), nullable=False)
    best_bid_price = Column(Numeric(18, 4), nullable=True)
    best_bid_quantity = Column(Numeric(18, 4), nullable=True)
    best_ask_price = Column(Numeric(18, 4), nullable=True)
    best_ask_quantity = Column(Numeric(18, 4), nullable=True)
    event_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    receive_timestamp = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    provider_sequence = Column(BigInteger, nullable=True)
    provider_event_id = Column(String(128), nullable=True)

    __table_args__ = (
        Index("ix_tick_inst_time", "instrument_id", "event_timestamp"),
    )


class MarketOHLCV(Base):
    """Aggregated / streaming OHLCV candle records."""
    __tablename__ = "market_ohlcv"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(64), unique=True, nullable=False, index=True)
    feed_id = Column(String(64), nullable=False, index=True)
    instrument_id = Column(String(64), nullable=False, index=True)
    interval = Column(String(16), nullable=False)  # 1m, 5m, 1h, 1d
    open_price = Column(Numeric(18, 4), nullable=False)
    high_price = Column(Numeric(18, 4), nullable=False)
    low_price = Column(Numeric(18, 4), nullable=False)
    close_price = Column(Numeric(18, 4), nullable=False)
    volume = Column(Numeric(22, 4), nullable=False)
    candle_start = Column(DateTime(timezone=True), nullable=False, index=True)
    candle_end = Column(DateTime(timezone=True), nullable=False)
    source_provider = Column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint("feed_id", "instrument_id", "interval", "candle_start", name="uq_ohlcv_candle"),
        Index("ix_ohlcv_inst_interval", "instrument_id", "interval", "candle_start"),
    )


class MarketTradeEvent(Base):
    """Executed trade tick records."""
    __tablename__ = "market_trade_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(64), unique=True, nullable=False, index=True)
    feed_id = Column(String(64), nullable=False, index=True)
    instrument_id = Column(String(64), nullable=False, index=True)
    exchange = Column(String(16), default="NSE", nullable=False)
    provider_trade_id = Column(String(128), nullable=True)
    price = Column(Numeric(18, 4), nullable=False)
    quantity = Column(Numeric(18, 4), nullable=False)
    trade_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    receive_timestamp = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    aggressor_side = Column(String(8), nullable=True)  # BID, ASK
    sequence_number = Column(BigInteger, nullable=True)

    __table_args__ = (
        Index("ix_trade_inst_time", "instrument_id", "trade_timestamp"),
    )


class OrderBookSnapshotRecord(Base):
    """Full Level 2 order book snapshot storage."""
    __tablename__ = "order_book_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(64), unique=True, nullable=False, index=True)
    feed_id = Column(String(64), nullable=False, index=True)
    instrument_id = Column(String(64), nullable=False, index=True)
    exchange = Column(String(16), default="NSE", nullable=False)
    sequence_number = Column(BigInteger, nullable=False, index=True)
    snapshot_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    bid_levels = Column(JSON, nullable=False)
    ask_levels = Column(JSON, nullable=False)
    receive_timestamp = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class OrderBookDeltaRecord(Base):
    """Incremental Level 2 order book modifications."""
    __tablename__ = "order_book_deltas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(64), unique=True, nullable=False, index=True)
    feed_id = Column(String(64), nullable=False, index=True)
    instrument_id = Column(String(64), nullable=False, index=True)
    sequence_number = Column(BigInteger, nullable=False, index=True)
    previous_sequence_number = Column(BigInteger, nullable=True)
    event_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    side = Column(String(8), nullable=False)  # BID, ASK
    price = Column(Numeric(18, 4), nullable=False)
    quantity = Column(Numeric(18, 4), nullable=False)
    operation = Column(String(16), nullable=False)  # INSERT, UPDATE, DELETE
    order_count = Column(Integer, nullable=True)
    receive_timestamp = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class IngestionCheckpoint(Base):
    """Stream processing checkpoints for sequence tracking and recovery."""
    __tablename__ = "ingestion_checkpoints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    feed_id = Column(String(64), nullable=False)
    instrument_id = Column(String(64), nullable=False)
    channel = Column(String(32), nullable=False)
    last_processed_sequence = Column(BigInteger, default=0, nullable=False)
    last_processed_timestamp = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("feed_id", "instrument_id", "channel", name="uq_checkpoint_feed_inst_channel"),
    )


class HistoricalBackfillJob(Base):
    """Backfill job tracking metadata."""
    __tablename__ = "historical_backfill_jobs"

    id = Column(String(64), primary_key=True)
    feed_id = Column(String(64), nullable=False, index=True)
    instrument_id = Column(String(64), nullable=False, index=True)
    data_type = Column(String(32), nullable=False)  # OHLCV, TRADES
    requested_start = Column(DateTime(timezone=True), nullable=False)
    requested_end = Column(DateTime(timezone=True), nullable=False)
    job_status = Column(String(32), default="PENDING", nullable=False)  # PENDING, RUNNING, COMPLETED, FAILED
    records_received = Column(Integer, default=0, nullable=False)
    error_summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
