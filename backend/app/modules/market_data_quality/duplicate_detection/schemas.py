"""
M03.05 - Duplicate Detection Pydantic Schemas.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


class EventDetectionInput(BaseModel):
    provider_id: str = Field(..., description="Provider identifier (e.g. SIMULATOR, ALPHA_VANTAGE)")
    feed_id: str = Field(..., description="Feed identifier")
    instrument_id: str = Field(..., description="Canonical instrument identifier (e.g. RELIANCE, INFY, AAPL)")
    exchange: str = Field("NSE", description="Exchange code (e.g. NSE, BSE, NASDAQ, NYSE)")
    event_type: str = Field(..., description="Event type: TRADE, QUOTE, SNAPSHOT, DELTA, OHLCV")

    # Identifiers
    provider_event_id: Optional[str] = Field(None, description="Provider assigned event ID")
    exchange_trade_id: Optional[str] = Field(None, description="Exchange issued trade ID")
    sequence_number: Optional[int] = Field(None, description="Sequence identifier")
    connection_epoch: Optional[int] = Field(None, description="Connection session epoch")

    # Core observation attributes (for trade, quote, ohlcv, deltas)
    event_timestamp: datetime = Field(..., description="Source observation timestamp")
    price: Optional[Any] = Field(None, description="Observation price or trade price")
    quantity: Optional[Any] = Field(None, description="Observation quantity or trade size")
    side: Optional[str] = Field(None, description="Side: BID, ASK, or aggressor side")
    trade_condition: Optional[str] = Field(None, description="Trade execution condition")
    interval: Optional[str] = Field(None, description="OHLCV interval e.g. 1d, 1h")

    # Payload or level data
    raw_payload: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Original event data payload")


class DuplicateDetectionResult(BaseModel):
    classification: str = Field(..., description="NEW_EVENT, DUPLICATE_EVENT, SUSPECTED_DUPLICATE, IDENTITY_CONFLICT, REVISION")
    is_duplicate: bool
    is_new: bool
    is_conflict: bool
    identity_strategy: str
    idempotency_key: str
    payload_fingerprint: str
    canonical_event_id: str
    canonical_record_table: str
    duplicate_reason: Optional[str] = None
    existing_delivery_count: int = 1
    evidence: Dict[str, Any] = Field(default_factory=dict)


class DuplicateDetectionRuleCreate(BaseModel):
    rule_code: str
    rule_name: str
    event_type: str = "ALL"
    provider_id: Optional[str] = None
    feed_id: Optional[str] = None
    instrument_id: Optional[str] = None
    identity_strategy: str = "AUTO_HIERARCHICAL"
    rule_parameters: Optional[Dict[str, Any]] = None
    confidence_policy: str = "CONSERVATIVE"
    retention_policy: str = "STANDARD_DURABLE"
    enabled: bool = True


class DuplicateDetectionRuleResponse(DuplicateDetectionRuleCreate):
    id: int
    version: str
    effective_from: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DuplicateReceiptResponse(BaseModel):
    receipt_id: str
    canonical_event_id: str
    provider_id: str
    feed_id: str
    instrument_id: str
    exchange: str
    event_type: str
    duplicate_reason: str
    identity_strategy: str
    incoming_provider_event_id: Optional[str] = None
    incoming_sequence: Optional[int] = None
    incoming_payload_fingerprint: str
    original_receive_timestamp: datetime
    duplicate_receive_timestamp: datetime
    processing_outcome: str
    evidence: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class IdentityConflictResponse(BaseModel):
    conflict_id: str
    canonical_event_id: str
    incoming_event_reference: str
    original_fingerprint: str
    incoming_fingerprint: str
    conflict_type: str
    conflict_status: str
    evidence: Optional[Dict[str, Any]] = None
    first_detected_at: datetime
    last_detected_at: datetime
    resolved_at: Optional[datetime] = None
    resolution_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ConflictResolutionRequest(BaseModel):
    resolution_action: str = Field(..., description="ACCEPT_REVISION, OVERWRITE_CANONICAL, REJECT_INCOMING")
    resolution_reason: str


class DuplicateAuditSummary(BaseModel):
    total_deliveries: int
    unique_canonical_events: int
    confirmed_duplicates: int
    suspected_duplicates: int
    identity_conflicts: int
    prevented_business_inserts: int
    prevented_volume: Decimal
    prevented_turnover: Decimal
    duplicate_rate_percentage: Optional[float] = None
