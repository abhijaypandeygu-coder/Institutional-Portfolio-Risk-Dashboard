"""
Pydantic schemas for M03.04 - Order Book Validation.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class OrderBookLevelInput(BaseModel):
    price: Any = Field(..., description="Level price (Decimal, float, or string)")
    quantity: Any = Field(..., description="Level quantity (Decimal, float, or string)")
    level_position: Optional[int] = Field(None, description="Depth level index (1-based)")
    orders_count: Optional[int] = Field(None, description="Number of orders at this level")


class OrderBookDeltaInput(BaseModel):
    side: str = Field(..., description="BID or ASK")
    price: Any = Field(..., description="Price level")
    quantity: Any = Field(..., description="New quantity (0 for delete)")
    operation: str = Field("UPDATE", description="INSERT, UPDATE, DELETE")
    sequence_number: Optional[int] = Field(None, description="Event sequence number")


class OrderBookValidationInput(BaseModel):
    feed_id: str = Field(..., description="Identifier of the market data feed")
    symbol: str = Field(..., description="Ticker symbol (e.g. RELIANCE, INFY, AAPL)")
    venue: Optional[str] = Field(None, description="Exchange or trading venue code (e.g. NSE, BSE, NASDAQ)")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Observation timestamp")
    session_phase: str = Field("CONTINUOUS_TRADING", description="CONTINUOUS_TRADING, PRE_OPEN_AUCTION, CLOSING_AUCTION, POST_CLOSE, HALTED")
    data_origin: str = Field("SIMULATOR", description="SIMULATOR, ALPHA_VANTAGE, LIVE_EXCHANGE")

    sequence_number: Optional[int] = Field(None, description="Snapshot or delta sequence number")
    is_snapshot: bool = Field(True, description="True if full snapshot, False if incremental update")

    # Snapshot payloads
    bids: Optional[List[OrderBookLevelInput]] = Field(default=None, description="List of bid levels")
    asks: Optional[List[OrderBookLevelInput]] = Field(default=None, description="List of ask levels")

    # Incremental update payload (if not snapshot)
    delta: Optional[OrderBookDeltaInput] = Field(default=None, description="Incremental order book delta")

    # Observed previous state for continuity / duration
    expected_next_sequence: Optional[int] = Field(None, description="Expected sequence number for continuity check")
    last_locked_duration_ms: Optional[int] = Field(None, description="Elapsed locked duration if already locked")
    last_crossed_duration_ms: Optional[int] = Field(None, description="Elapsed crossed duration if already crossed")


class BookValidationRuleCreate(BaseModel):
    rule_code: str
    rule_name: str
    description: Optional[str] = None
    feed_id: Optional[str] = None
    symbol: Optional[str] = None
    venue: Optional[str] = None

    max_crossed_duration_ms: int = 50
    max_cross_amount: Optional[Decimal] = None
    allow_auction_cross: bool = True
    allow_auction_lock: bool = True
    max_locked_duration_ms: int = 100

    allow_fractional_shares: bool = False
    min_lot_size: Decimal = Decimal("1.0")
    max_order_quantity: Optional[Decimal] = None

    max_allowed_sequence_gap: int = 0
    auto_trigger_resync: bool = True
    is_enabled: bool = True


class BookValidationRuleResponse(BookValidationRuleCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ValidationResultResponse(BaseModel):
    validation_id: str
    feed_id: str
    symbol: str
    venue: Optional[str] = None
    timestamp: datetime
    session_phase: str
    sequence_number: Optional[int] = None
    is_snapshot: bool

    best_bid_price: Optional[Decimal] = None
    best_bid_quantity: Optional[Decimal] = None
    best_ask_price: Optional[Decimal] = None
    best_ask_quantity: Optional[Decimal] = None

    is_valid: bool
    is_crossed: bool
    is_locked: bool
    has_quantity_anomaly: bool
    has_continuity_break: bool
    has_structural_defect: bool

    crossed_classification: Optional[str] = None
    locked_classification: Optional[str] = None
    cross_amount: Optional[Decimal] = None

    spread_eligible: bool
    imbalance_eligible: bool
    depth_eligible: bool
    liquidity_eligible: bool
    execution_research_eligible: bool

    severity: str
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    resync_requested: bool = False


class ResyncRequestCreate(BaseModel):
    feed_id: str
    symbol: str
    venue: Optional[str] = None
    reason: str
    from_sequence: Optional[int] = None
    to_sequence: Optional[int] = None


class ResyncRequestResponse(BaseModel):
    request_id: str
    feed_id: str
    symbol: str
    venue: Optional[str] = None
    reason: str
    from_sequence: Optional[int] = None
    to_sequence: Optional[int] = None
    status: str
    requested_at: datetime
    completed_at: Optional[datetime] = None
    m02_acknowledgment: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class BookIntegrityIncidentResponse(BaseModel):
    id: int
    incident_key: str
    incident_type: str
    severity: str
    feed_id: str
    symbol: str
    venue: Optional[str] = None
    session_phase: str
    status: str
    details: Optional[Dict[str, Any]] = None
    started_at: datetime
    resolved_at: Optional[datetime] = None
    duration_ms: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class BookQualitySummary(BaseModel):
    feed_id: str
    symbol: str
    total_evaluations: int
    valid_count: int
    crossed_count: int
    locked_count: int
    quantity_defect_count: int
    continuity_break_count: int
    active_incidents: int
    spread_eligible_ratio: float
