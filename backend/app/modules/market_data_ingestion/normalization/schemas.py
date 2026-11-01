"""
Module 02: Market Data Ingestion Engine - Canonical Schemas (Pydantic 2.x).
Defines institutional typed schemas for ticks, OHLCV, trades, order book snapshots/deltas,
heartbeats, errors, backfill requests, and Alpha Vantage data freshness.
"""
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OrderBookSide(str, Enum):
    BID = "BID"
    ASK = "ASK"


class OrderBookOperation(str, Enum):
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class MarketDataChannel(str, Enum):
    TICK = "TICK"
    OHLCV = "OHLCV"
    TRADE = "TRADE"
    ORDER_BOOK_L1 = "ORDER_BOOK_L1"
    ORDER_BOOK_L2 = "ORDER_BOOK_L2"


class BackfillJobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DataFreshness(str, Enum):
    END_OF_DAY = "END_OF_DAY"
    HISTORICAL = "HISTORICAL"
    SIMULATED_REALTIME = "SIMULATED_REALTIME"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


class AlphaVantageErrorType(str, Enum):
    INVALID_API_KEY = "INVALID_API_KEY"
    UNSUPPORTED_SYMBOL = "UNSUPPORTED_SYMBOL"
    UNSUPPORTED_ENDPOINT = "UNSUPPORTED_ENDPOINT"
    PREMIUM_ENTITLEMENT_REQUIRED = "PREMIUM_ENTITLEMENT_REQUIRED"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    DAILY_QUOTA_EXHAUSTED = "DAILY_QUOTA_EXHAUSTED"
    EMPTY_RESPONSE = "EMPTY_RESPONSE"
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    SERVER_ERROR = "SERVER_ERROR"


# ============================================================================
# Canonical Event Schemas
# ============================================================================

class MarketTick(BaseModel):
    """Canonical Level 1 / Top-of-Book / LTP event."""
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    provider_event_id: Optional[str] = None
    feed_id: str
    instrument_id: str
    exchange: str = "NSE"
    symbol: str
    last_traded_price: Decimal
    last_traded_quantity: Decimal
    best_bid_price: Optional[Decimal] = None
    best_bid_quantity: Optional[Decimal] = None
    best_ask_price: Optional[Decimal] = None
    best_ask_quantity: Optional[Decimal] = None
    event_timestamp: datetime
    exchange_timestamp: Optional[datetime] = None
    receive_timestamp: datetime = Field(default_factory=utc_now)
    normalization_timestamp: datetime = Field(default_factory=utc_now)
    provider_sequence: Optional[int] = None
    source_metadata: Dict[str, Any] = Field(default_factory=dict)
    data_freshness: DataFreshness = DataFreshness.SIMULATED_REALTIME

    model_config = ConfigDict(from_attributes=True)


class OHLCVCandle(BaseModel):
    """Canonical OHLCV historical or streaming candle."""
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    feed_id: str
    instrument_id: str
    exchange: str = "NSE"
    interval: str = "1m"  # 1m, 5m, 15m, 1h, 1d, 1w, 1M
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    candle_start: datetime
    candle_end: datetime
    source_provider: str
    receive_timestamp: datetime = Field(default_factory=utc_now)
    data_freshness: DataFreshness = DataFreshness.HISTORICAL
    is_adjusted: bool = False
    currency: str = "INR"

    model_config = ConfigDict(from_attributes=True)


class TradeEvent(BaseModel):
    """Canonical executed trade event."""
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    provider_trade_id: Optional[str] = None
    feed_id: str
    instrument_id: str
    exchange: str = "NSE"
    price: Decimal
    quantity: Decimal
    trade_timestamp: datetime
    receive_timestamp: datetime = Field(default_factory=utc_now)
    aggressor_side: Optional[OrderBookSide] = None
    sequence_number: Optional[int] = None
    trade_type: Optional[str] = None
    source_metadata: Dict[str, Any] = Field(default_factory=dict)
    data_freshness: DataFreshness = DataFreshness.SIMULATED_REALTIME

    model_config = ConfigDict(from_attributes=True)


class OrderBookLevel(BaseModel):
    """Single price-level entry within an order-book snapshot."""
    price: Decimal
    quantity: Decimal
    order_count: Optional[int] = None
    level_position: int = Field(ge=1, le=50)

    model_config = ConfigDict(from_attributes=True)


class OrderBookSnapshot(BaseModel):
    """Canonical Level 2 full order-book snapshot."""
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    feed_id: str
    instrument_id: str
    exchange: str = "NSE"
    snapshot_sequence: int
    snapshot_timestamp: datetime
    bids: List[OrderBookLevel] = Field(default_factory=list)
    asks: List[OrderBookLevel] = Field(default_factory=list)
    receive_timestamp: datetime = Field(default_factory=utc_now)
    source_metadata: Dict[str, Any] = Field(default_factory=dict)
    data_freshness: DataFreshness = DataFreshness.SIMULATED_REALTIME

    model_config = ConfigDict(from_attributes=True)


class OrderBookDelta(BaseModel):
    """Canonical Level 2 incremental order-book modification."""
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    feed_id: str
    instrument_id: str
    exchange: str = "NSE"
    sequence_number: int
    previous_sequence_number: Optional[int] = None
    event_timestamp: datetime
    side: OrderBookSide
    price: Decimal
    quantity: Decimal
    operation: OrderBookOperation
    order_count: Optional[int] = None
    receive_timestamp: datetime = Field(default_factory=utc_now)
    data_freshness: DataFreshness = DataFreshness.SIMULATED_REALTIME

    model_config = ConfigDict(from_attributes=True)


class ProviderHeartbeat(BaseModel):
    """Canonical heartbeat event."""
    feed_id: str
    provider_id: str
    heartbeat_timestamp: datetime
    receive_timestamp: datetime = Field(default_factory=utc_now)
    connection_id: Optional[str] = None


class IngestionError(BaseModel):
    """Canonical structured ingestion error."""
    error_id: str = Field(default_factory=lambda: str(uuid4()))
    feed_id: str
    provider_id: str
    instrument_id: Optional[str] = None
    error_code: str
    error_type: str
    sanitized_message: str
    event_timestamp: datetime
    occurrence_timestamp: datetime = Field(default_factory=utc_now)
    recovery_status: str = "PENDING"
