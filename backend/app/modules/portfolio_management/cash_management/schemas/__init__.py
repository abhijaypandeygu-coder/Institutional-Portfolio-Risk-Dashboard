"""Pydantic 2.x Schemas for M05.04 - Cash Management."""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from backend.app.modules.portfolio_management.cash_management.models import (
    CashAccountType,
    CashAccountStatus,
    CashMovementType,
    CashMovementStatus,
    CashReservationType,
    CashReservationStatus,
    CashRestrictionType,
    CashRestrictionStatus,
    CommitmentType,
    CommitmentStatus,
    TransferStatus,
    ReconciliationStatus,
    AvailableCashStatus,
)


# ---------------------------------------------------------------------------
# CASH ACCOUNT SCHEMAS
# ---------------------------------------------------------------------------

class CashAccountCreate(BaseModel):
    portfolio_id: str = Field(..., max_length=64)
    account_id: str = Field(..., max_length=64)
    currency: str = Field(..., min_length=3, max_length=3, description="ISO-4217, e.g., 'INR', 'USD'")
    cash_account_type: CashAccountType = CashAccountType.TRADING
    description: Optional[str] = Field(None, max_length=255)


class CashAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cash_account_id: str
    portfolio_id: str
    account_id: str
    currency: str
    cash_account_type: CashAccountType
    status: CashAccountStatus
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# CASH BALANCES & AVAILABILITY
# ---------------------------------------------------------------------------

class CashBalanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cash_account_id: str
    portfolio_id: str
    account_id: str
    currency: str
    settled_balance: Decimal
    unsettled_receivables: Decimal
    unsettled_payables: Decimal
    reserved_cash: Decimal
    restricted_cash: Decimal
    eligible_credit: Decimal
    minimum_cash_buffer: Decimal
    available_cash: Decimal
    availability_status: AvailableCashStatus
    effective_at: datetime
    calculated_at: datetime
    policy_version: int


class AvailableCashExplanation(BaseModel):
    portfolio_id: str
    account_id: str
    currency: str
    settled_balance: Decimal
    eligible_unsettled_receivables: Decimal
    eligible_credit: Decimal
    active_reservations: Decimal
    restricted_cash: Decimal
    minimum_cash_buffer: Decimal
    unreserved_payable_deductions: Decimal
    final_available_cash: Decimal
    availability_status: AvailableCashStatus
    policy_version: int
    calculation_timestamp: datetime
    formula: str = (
        "Available Cash = Settled Cash + Eligible Receivables + Eligible Credit "
        "- Active Reservations - Restricted Cash - Minimum Buffer - Unreserved Payables"
    )
    reasons: List[str] = []


# ---------------------------------------------------------------------------
# CASH MOVEMENTS
# ---------------------------------------------------------------------------

class DepositCreate(BaseModel):
    portfolio_id: str
    account_id: str
    currency: str
    amount: Decimal = Field(..., gt=0)
    source_reference: Optional[str] = None
    idempotency_key: Optional[str] = None
    description: Optional[str] = None


class WithdrawalCreate(BaseModel):
    portfolio_id: str
    account_id: str
    currency: str
    amount: Decimal = Field(..., gt=0)
    destination_reference: Optional[str] = None
    idempotency_key: Optional[str] = None
    description: Optional[str] = None


class CashMovementCreate(BaseModel):
    portfolio_id: str
    account_id: str
    currency: str
    movement_type: CashMovementType
    signed_amount: Decimal  # Inflow > 0, Outflow < 0
    gross_amount: Decimal
    fees_amount: Decimal = Decimal("0.000000")
    tax_amount: Decimal = Decimal("0.000000")
    net_amount: Decimal
    effective_at: datetime
    settlement_at: Optional[datetime] = None
    source_system: str = "INTERNAL"
    source_event_id: Optional[str] = None
    external_reference: Optional[str] = None
    related_instrument_id: Optional[str] = None
    related_trade_id: Optional[str] = None
    related_corporate_action_id: Optional[str] = None
    idempotency_key: Optional[str] = None


class CashMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    movement_id: str
    cash_account_id: str
    portfolio_id: str
    account_id: str
    movement_type: CashMovementType
    signed_amount: Decimal
    currency: str
    gross_amount: Decimal
    fees_amount: Decimal
    tax_amount: Decimal
    net_amount: Decimal
    effective_at: datetime
    settlement_at: Optional[datetime]
    posted_at: Optional[datetime]
    status: CashMovementStatus
    source_system: str
    source_event_id: Optional[str]
    external_reference: Optional[str]
    related_instrument_id: Optional[str]
    related_trade_id: Optional[str]
    related_corporate_action_id: Optional[str]
    transfer_id: Optional[str]
    reversal_of_movement_id: Optional[str]
    idempotency_key: Optional[str]
    created_at: datetime


# ---------------------------------------------------------------------------
# CASH RESERVATIONS
# ---------------------------------------------------------------------------

class CashReservationCreate(BaseModel):
    portfolio_id: str
    account_id: str
    currency: str
    reservation_type: CashReservationType
    reserved_amount: Decimal = Field(..., gt=0)
    source_commitment_id: Optional[str] = None
    source_order_id: Optional[str] = None
    source_trade_id: Optional[str] = None
    reason: Optional[str] = None
    expires_at: Optional[datetime] = None
    idempotency_key: Optional[str] = None


class CashReservationRelease(BaseModel):
    release_amount: Optional[Decimal] = None  # If None, full release
    reason: Optional[str] = "Manual or automated release"


class CashReservationAdjust(BaseModel):
    new_reserved_amount: Decimal = Field(..., ge=0)
    reason: Optional[str] = "Adjustment based on fill or amended order"


class CashReservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reservation_id: str
    cash_account_id: str
    portfolio_id: str
    account_id: str
    currency: str
    reservation_type: CashReservationType
    reserved_amount: Decimal
    remaining_amount: Decimal
    source_commitment_id: Optional[str]
    source_order_id: Optional[str]
    source_trade_id: Optional[str]
    status: CashReservationStatus
    reason: Optional[str]
    policy_version: int
    created_at: datetime
    effective_at: datetime
    expires_at: Optional[datetime]
    released_at: Optional[datetime]


# ---------------------------------------------------------------------------
# TRANSFERS
# ---------------------------------------------------------------------------

class CashTransferCreate(BaseModel):
    source_portfolio_id: str
    source_account_id: str
    destination_portfolio_id: str
    destination_account_id: str
    source_currency: str
    destination_currency: str
    source_amount: Decimal = Field(..., gt=0)
    destination_amount: Optional[Decimal] = None  # Defaults to source_amount if same currency
    fx_rate: Optional[Decimal] = None
    fx_rate_reference: Optional[str] = None
    fee_amount: Decimal = Decimal("0.000000")
    source_reference: Optional[str] = None


class CashTransferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transfer_id: str
    source_cash_account_id: str
    destination_cash_account_id: str
    source_portfolio_id: str
    destination_portfolio_id: str
    source_currency: str
    destination_currency: str
    source_amount: Decimal
    destination_amount: Decimal
    fx_rate: Optional[Decimal]
    fx_rate_reference: Optional[str]
    fee_amount: Decimal
    status: TransferStatus
    source_reference: Optional[str]
    effective_at: datetime
    settlement_at: Optional[datetime]
    created_at: datetime


# ---------------------------------------------------------------------------
# RECONCILIATION
# ---------------------------------------------------------------------------

class CashReconciliationRunCreate(BaseModel):
    portfolio_id: str
    account_id: str
    currency: str
    statement_date: date
    external_closing_balance: Decimal
    source_statement_reference: Optional[str] = None


class CashReconciliationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    portfolio_id: str
    cash_account_id: str
    currency: str
    statement_date: date
    internal_closing_balance: Decimal
    external_closing_balance: Decimal
    difference: Decimal
    status: ReconciliationStatus
    source_statement_reference: Optional[str]
    exception_id: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    created_at: datetime

