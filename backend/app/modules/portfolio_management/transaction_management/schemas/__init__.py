"""Pydantic 2.x Schemas for M05.05 - Transaction Management."""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from backend.app.modules.portfolio_management.transaction_management.models import (
    TransactionType,
    TradeSide,
    PositionEffect,
    TransactionStatus,
    ExecutionStatus,
    TransferDirection,
    TransferStatus,
    AdjustmentCategory,
    AdjustmentApprovalStatus,
    SettlementStatus,
    OutboxDeliveryStatus,
)


# ---------------------------------------------------------------------------
# TRANSACTIONS
# ---------------------------------------------------------------------------

class TransactionCreate(BaseModel):
    portfolio_id: str = Field(..., max_length=64)
    account_id: str = Field(..., max_length=64)
    instrument_id: Optional[str] = Field(None, max_length=64)
    listing_id: Optional[str] = Field(None, max_length=64)
    transaction_type: TransactionType = TransactionType.TRADE
    trade_side: Optional[TradeSide] = None
    position_effect: PositionEffect = PositionEffect.UNSPECIFIED
    transaction_currency: str = Field(..., min_length=3, max_length=3)
    requested_quantity: Decimal = Field(..., ge=0)
    expected_settlement_date: Optional[date] = None
    source_system: str = "MANUAL"
    external_order_reference: Optional[str] = None
    external_trade_reference: Optional[str] = None


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transaction_id: str
    portfolio_id: str
    account_id: str
    instrument_id: Optional[str]
    listing_id: Optional[str]
    transaction_type: TransactionType
    trade_side: Optional[TradeSide]
    position_effect: PositionEffect
    transaction_currency: str
    requested_quantity: Decimal
    executed_quantity: Decimal
    remaining_quantity: Decimal
    cancelled_quantity: Decimal
    average_execution_price: Optional[Decimal]
    aggregate_gross_consideration: Decimal
    aggregate_fees: Decimal
    aggregate_net_consideration: Decimal
    trade_date: date
    first_execution_at: Optional[datetime]
    last_execution_at: Optional[datetime]
    expected_settlement_date: Optional[date]
    status: TransactionStatus
    source_system: str
    external_order_reference: Optional[str]
    external_trade_reference: Optional[str]
    current_version: int
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# EXECUTIONS
# ---------------------------------------------------------------------------

class TradeExecutionCreate(BaseModel):
    executed_quantity: Decimal = Field(..., gt=0)
    execution_price: Decimal = Field(..., gt=0)
    execution_currency: str = Field(..., min_length=3, max_length=3)
    execution_timestamp: Optional[datetime] = None
    source_system: str = "MANUAL"
    external_execution_id: Optional[str] = None
    broker_reference: Optional[str] = None
    source_sequence: Optional[int] = None
    idempotency_key: Optional[str] = None


class TradeExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    execution_id: str
    transaction_id: str
    portfolio_id: str
    account_id: str
    instrument_id: str
    listing_id: Optional[str]
    trade_side: TradeSide
    position_effect: PositionEffect
    executed_quantity: Decimal
    execution_price: Decimal
    execution_currency: str
    gross_consideration: Decimal
    execution_timestamp: datetime
    trade_date: date
    source_system: str
    external_execution_id: Optional[str]
    broker_reference: Optional[str]
    execution_status: ExecutionStatus
    created_at: datetime


# ---------------------------------------------------------------------------
# FEES
# ---------------------------------------------------------------------------

class TransactionFeeCreate(BaseModel):
    execution_id: Optional[str] = None
    fee_category: str = Field(..., max_length=64)
    fee_amount: Decimal = Field(..., gt=0)
    fee_currency: str = Field(..., min_length=3, max_length=3)
    fee_source: str = "ESTIMATED"
    external_fee_reference: Optional[str] = None


class TransactionFeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fee_id: str
    transaction_id: str
    execution_id: Optional[str]
    fee_category: str
    fee_amount: Decimal
    fee_currency: str
    fee_source: str
    external_fee_reference: Optional[str]
    estimated_or_actual: str
    effective_at: datetime
    created_at: datetime


# ---------------------------------------------------------------------------
# TRANSFERS
# ---------------------------------------------------------------------------

class SecurityTransferCreate(BaseModel):
    source_portfolio_id: str
    source_account_id: str
    destination_portfolio_id: str
    destination_account_id: str
    instrument_id: str
    listing_id: Optional[str] = None
    quantity: Decimal = Field(..., gt=0)
    transfer_direction: TransferDirection = TransferDirection.INTERNAL
    external_transfer_reference: Optional[str] = None
    reason: Optional[str] = None


class CashTransferCreate(BaseModel):
    source_portfolio_id: str
    source_account_id: str
    destination_portfolio_id: str
    destination_account_id: str
    source_currency: str
    destination_currency: str
    source_amount: Decimal = Field(..., gt=0)
    destination_amount: Optional[Decimal] = None
    fx_rate: Optional[Decimal] = None
    external_transfer_reference: Optional[str] = None
    reason: Optional[str] = None


class TransferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transfer_id: str
    portfolio_id: str
    source_account_id: str
    destination_account_id: str
    transfer_type: str
    transfer_direction: TransferDirection
    instrument_id: Optional[str]
    listing_id: Optional[str]
    source_currency: Optional[str]
    destination_currency: Optional[str]
    quantity: Decimal
    source_amount: Decimal
    destination_amount: Decimal
    fx_rate: Optional[Decimal]
    fees_amount: Decimal
    status: TransferStatus
    external_transfer_reference: Optional[str]
    reason: Optional[str]
    effective_at: datetime
    completed_at: Optional[datetime]
    created_at: datetime


# ---------------------------------------------------------------------------
# ADJUSTMENTS
# ---------------------------------------------------------------------------

class AdjustmentCreate(BaseModel):
    portfolio_id: str
    account_id: str
    instrument_id: Optional[str] = None
    transaction_id: Optional[str] = None
    adjustment_type: AdjustmentCategory
    reason: str = Field(..., min_length=3, max_length=255)
    original_value: str
    proposed_value: str
    adjustment_amount: Decimal
    currency: Optional[str] = None
    supporting_evidence_reference: Optional[str] = None
    requested_by: str = "SYSTEM_USER"


class AdjustmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    adjustment_id: str
    portfolio_id: str
    account_id: str
    instrument_id: Optional[str]
    transaction_id: Optional[str]
    adjustment_type: AdjustmentCategory
    reason: str
    original_value: str
    proposed_value: str
    adjustment_amount: Decimal
    currency: Optional[str]
    supporting_evidence_reference: Optional[str]
    requested_by: str
    requested_at: datetime
    approval_status: AdjustmentApprovalStatus
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    rejection_reason: Optional[str]
    downstream_posting_status: str
    created_at: datetime


# ---------------------------------------------------------------------------
# CORRECTIONS
# ---------------------------------------------------------------------------

class ExecutionCorrectionCreate(BaseModel):
    execution_id: str
    new_quantity: Optional[Decimal] = None
    new_price: Optional[Decimal] = None
    reason: str = Field(..., min_length=3)
    source_system: str = "MANUAL"


# ---------------------------------------------------------------------------
# LIFECYCLE & OUTBOX
# ---------------------------------------------------------------------------

class LifecycleEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transaction_id: str
    previous_status: str
    new_status: str
    event_type: str
    source_system: str
    source_event_id: Optional[str]
    reason: Optional[str]
    effective_at: datetime
    recorded_at: datetime


class OutboxDeliveryStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    outbox_id: str
    aggregate_id: str
    event_type: str
    destination_module: str
    delivery_status: OutboxDeliveryStatus
    attempt_count: int
    last_error: Optional[str]
    delivered_at: Optional[datetime]
    created_at: datetime

