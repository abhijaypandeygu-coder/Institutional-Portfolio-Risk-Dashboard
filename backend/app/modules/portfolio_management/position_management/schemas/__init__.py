"""Pydantic 2.x Schemas for M05.02 - Position Management."""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

from backend.app.modules.portfolio_management.position_management.models import (
    PositionSide,
    PositionStatus,
    PositionEventType,
    PositionEventStatus,
    TransferStatus,
    BorrowStatus,
    ReconciliationStatus,
)


# ---------------------------------------------------------------------------
# POSITION BOOK SCHEMAS
# ---------------------------------------------------------------------------
class PositionBookRegisterRequest(BaseModel):
    portfolio_id: str = Field(..., min_length=3, max_length=64)
    account_id: str = Field(..., min_length=2, max_length=64)
    instrument_id: str = Field(..., min_length=3, max_length=64)
    listing_id: Optional[str] = None
    sleeve_id: Optional[str] = None


class PositionBookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position_id: str
    portfolio_id: str
    account_id: str
    instrument_id: str
    listing_id: Optional[str] = None
    sleeve_id: Optional[str] = None
    position_side: PositionSide
    position_status: PositionStatus
    current_snapshot_version: int
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# POSITION EVENT SCHEMAS
# ---------------------------------------------------------------------------
class PositionEventRegisterRequest(BaseModel):
    portfolio_id: str = Field(..., min_length=3, max_length=64)
    account_id: str = Field(..., min_length=2, max_length=64)
    instrument_id: str = Field(..., min_length=3, max_length=64)
    listing_id: Optional[str] = None
    event_type: PositionEventType
    signed_quantity_delta: Decimal = Field(..., description="Positive for long / buy, negative for short / sell")
    settled_quantity_delta: Optional[Decimal] = Decimal("0.0")
    unsettled_quantity_delta: Optional[Decimal] = Decimal("0.0")
    effective_timestamp: Optional[datetime] = None
    source_system: str = "MANUAL"
    source_event_id: Optional[str] = None
    transaction_reference: Optional[str] = None
    corporate_action_reference: Optional[str] = None
    transfer_reference: Optional[str] = None
    idempotency_key: str = Field(..., min_length=3, max_length=128)
    reason: Optional[str] = None


class PositionEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position_event_id: str
    position_id: str
    portfolio_id: str
    account_id: str
    instrument_id: str
    listing_id: Optional[str] = None
    event_type: PositionEventType
    event_status: PositionEventStatus
    signed_quantity_delta: Decimal
    settled_quantity_delta: Decimal
    unsettled_quantity_delta: Decimal
    effective_timestamp: datetime
    recorded_at: datetime
    source_system: str
    transaction_reference: Optional[str] = None
    corporate_action_reference: Optional[str] = None
    transfer_reference: Optional[str] = None
    idempotency_key: str
    event_sequence: int
    reversal_of_event_id: Optional[str] = None
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# POSITION SNAPSHOT SCHEMAS
# ---------------------------------------------------------------------------
class PositionSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    snapshot_id: str
    position_id: str
    portfolio_id: str
    account_id: str
    instrument_id: str
    listing_id: Optional[str] = None
    position_side: PositionSide
    gross_long_quantity: Decimal
    gross_short_quantity: Decimal
    net_signed_quantity: Decimal
    settled_quantity: Decimal
    unsettled_quantity: Decimal
    economic_quantity: Decimal
    available_quantity: Decimal
    reserved_quantity: Decimal
    restricted_quantity: Decimal
    borrowed_quantity: Decimal
    effective_timestamp: datetime
    recorded_at: datetime
    last_applied_event_id: Optional[str] = None
    snapshot_version: int


# ---------------------------------------------------------------------------
# PORTFOLIO AGGREGATE SCHEMAS
# ---------------------------------------------------------------------------
class PortfolioPositionAggregateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    aggregate_id: str
    portfolio_id: str
    instrument_id: str
    listing_id: Optional[str] = None
    gross_long_quantity: Decimal
    gross_short_quantity: Decimal
    net_signed_quantity: Decimal
    settled_quantity: Decimal
    unsettled_quantity: Decimal
    available_quantity: Decimal
    contributing_account_count: int
    effective_timestamp: datetime
    snapshot_version: int
    generated_at: datetime


# ---------------------------------------------------------------------------
# BORROW METADATA SCHEMAS
# ---------------------------------------------------------------------------
class PositionBorrowRegisterRequest(BaseModel):
    lender_reference: Optional[str] = None
    locate_reference: Optional[str] = None
    borrowed_quantity: Decimal = Field(..., gt=0)
    borrow_rate_annual_pct: Optional[Decimal] = None
    borrow_status: BorrowStatus = BorrowStatus.APPROVED
    effective_date: date
    recall_date: Optional[date] = None


class PositionBorrowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    borrow_id: str
    position_id: str
    lender_reference: Optional[str] = None
    locate_reference: Optional[str] = None
    borrowed_quantity: Decimal
    borrow_rate_annual_pct: Optional[Decimal] = None
    borrow_status: BorrowStatus
    effective_date: date
    recall_date: Optional[date] = None
    recorded_at: datetime


# ---------------------------------------------------------------------------
# TRANSFER SCHEMAS
# ---------------------------------------------------------------------------
class PositionTransferCreateRequest(BaseModel):
    source_portfolio_id: str = Field(..., min_length=3, max_length=64)
    source_account_id: str = Field(..., min_length=2, max_length=64)
    destination_portfolio_id: str = Field(..., min_length=3, max_length=64)
    destination_account_id: str = Field(..., min_length=2, max_length=64)
    instrument_id: str = Field(..., min_length=3, max_length=64)
    listing_id: Optional[str] = None
    quantity: Decimal = Field(..., gt=0)
    effective_timestamp: Optional[datetime] = None
    transfer_reason: Optional[str] = None


class PositionTransferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transfer_id: str
    source_portfolio_id: str
    source_account_id: str
    destination_portfolio_id: str
    destination_account_id: str
    instrument_id: str
    listing_id: Optional[str] = None
    quantity: Decimal
    transfer_status: TransferStatus
    source_confirmed: bool
    destination_confirmed: bool
    effective_timestamp: datetime
    transfer_reason: Optional[str] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# RECONCILIATION SCHEMAS
# ---------------------------------------------------------------------------
class PositionReconciliationSubmitRequest(BaseModel):
    portfolio_id: str = Field(..., min_length=3, max_length=64)
    account_id: str = Field(..., min_length=2, max_length=64)
    instrument_id: str = Field(..., min_length=3, max_length=64)
    external_quantity: Decimal
    source_name: str = "BROKER"
    as_of_date: date


class PositionReconciliationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reconciliation_id: str
    position_id: str
    portfolio_id: str
    account_id: str
    instrument_id: str
    internal_quantity: Decimal
    external_quantity: Decimal
    difference_quantity: Decimal
    reconciliation_status: ReconciliationStatus
    source_name: str
    as_of_date: date
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
