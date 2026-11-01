"""SQLAlchemy 2.x Models for M05.04 - Cash Management."""
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, List
from sqlalchemy import (
    String,
    Boolean,
    Integer,
    Numeric,
    DateTime,
    Date,
    ForeignKey,
    Text,
    Enum as SAEnum,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


# ---------------------------------------------------------------------------
# ENUMS
# ---------------------------------------------------------------------------

class CashAccountType(str, Enum):
    TRADING = "TRADING"
    SETTLEMENT = "SETTLEMENT"
    COLLATERAL = "COLLATERAL"
    INCOME = "INCOME"
    SWEEP = "SWEEP"
    CUSTODY = "CUSTODY"
    GENERAL = "GENERAL"


class CashAccountStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RESTRICTED = "RESTRICTED"
    FROZEN = "FROZEN"
    CLOSED = "CLOSED"


class CashMovementType(str, Enum):
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    DIVIDEND = "DIVIDEND"
    INTEREST_INCOME = "INTEREST_INCOME"
    INTEREST_EXPENSE = "INTEREST_EXPENSE"
    TRANSACTION_FEE = "TRANSACTION_FEE"
    MANAGEMENT_FEE = "MANAGEMENT_FEE"
    TRADE_SETTLEMENT_DEBIT = "TRADE_SETTLEMENT_DEBIT"
    TRADE_SETTLEMENT_CREDIT = "TRADE_SETTLEMENT_CREDIT"
    TAX_WITHHOLDING = "TAX_WITHHOLDING"
    INTERNAL_TRANSFER_IN = "INTERNAL_TRANSFER_IN"
    INTERNAL_TRANSFER_OUT = "INTERNAL_TRANSFER_OUT"
    FX_BUY = "FX_BUY"
    FX_SELL = "FX_SELL"
    ADJUSTMENT = "ADJUSTMENT"
    REVERSAL = "REVERSAL"


class CashMovementStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    POSTED = "POSTED"
    SETTLED = "SETTLED"
    REJECTED = "REJECTED"
    REVERSED = "REVERSED"
    FAILED = "FAILED"


class CashReservationType(str, Enum):
    OPEN_ORDER = "OPEN_ORDER"
    EXECUTED_UNSETTLED_TRADE = "EXECUTED_UNSETTLED_TRADE"
    EXPECTED_TRANSACTION_FEE = "EXPECTED_TRANSACTION_FEE"
    SETTLEMENT_OBLIGATION = "SETTLEMENT_OBLIGATION"
    TAX_OR_WITHHOLDING = "TAX_OR_WITHHOLDING"
    MANUAL_COMMITMENT = "MANUAL_COMMITMENT"
    OTHER_APPROVED_COMMITMENT = "OTHER_APPROVED_COMMITMENT"


class CashReservationStatus(str, Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    PARTIALLY_RELEASED = "PARTIALLY_RELEASED"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    SETTLED = "SETTLED"
    FAILED = "FAILED"
    REVERSED = "REVERSED"


class CashRestrictionType(str, Enum):
    BLOCKED = "BLOCKED"
    PLEDGED = "PLEDGED"
    REGULATORY = "REGULATORY"
    BROKER_RESTRICTED = "BROKER_RESTRICTED"
    PURPOSE_SPECIFIC = "PURPOSE_SPECIFIC"
    OTHER = "OTHER"


class CashRestrictionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PARTIALLY_RELEASED = "PARTIALLY_RELEASED"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class CommitmentType(str, Enum):
    RECEIVABLE = "RECEIVABLE"
    PAYABLE = "PAYABLE"


class CommitmentStatus(str, Enum):
    EXPECTED = "EXPECTED"
    SCHEDULED = "SCHEDULED"
    DUE = "DUE"
    SETTLED = "SETTLED"
    FAILED = "FAILED"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"
    REVERSED = "REVERSED"


class TransferStatus(str, Enum):
    INITIATED = "INITIATED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    REVERSED = "REVERSED"


class ReconciliationStatus(str, Enum):
    MATCHED = "MATCHED"
    UNMATCHED_INTERNAL = "UNMATCHED_INTERNAL"
    UNMATCHED_EXTERNAL = "UNMATCHED_EXTERNAL"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    DATE_MISMATCH = "DATE_MISMATCH"
    DUPLICATE_SUSPECTED = "DUPLICATE_SUSPECTED"
    PENDING_REVIEW = "PENDING_REVIEW"


class AvailableCashStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    LOW_AVAILABLE_CASH = "LOW_AVAILABLE_CASH"
    NEGATIVE_AVAILABLE_CASH = "NEGATIVE_AVAILABLE_CASH"
    RESTRICTED = "RESTRICTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    POLICY_ERROR = "POLICY_ERROR"


# ---------------------------------------------------------------------------
# MODELS
# ---------------------------------------------------------------------------

class CashAccount(Base):
    """
    Subledger cash account representing funds held in a specific account and currency.
    """
    __tablename__ = "m05_cash_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cash_account_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_portfolios.portfolio_id"), nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, index=True)  # ISO-4217, e.g., 'INR', 'USD'
    cash_account_type: Mapped[CashAccountType] = mapped_column(
        SAEnum(CashAccountType, native_enum=False), default=CashAccountType.TRADING, nullable=False
    )
    status: Mapped[CashAccountStatus] = mapped_column(
        SAEnum(CashAccountStatus, native_enum=False), default=CashAccountStatus.ACTIVE, nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    movements: Mapped[List["CashMovement"]] = relationship("CashMovement", back_populates="cash_account")
    reservations: Mapped[List["CashReservation"]] = relationship("CashReservation", back_populates="cash_account")
    commitments: Mapped[List["CashCommitment"]] = relationship("CashCommitment", back_populates="cash_account")
    restrictions: Mapped[List["CashRestriction"]] = relationship("CashRestriction", back_populates="cash_account")
    snapshots: Mapped[List["CashBalanceSnapshot"]] = relationship("CashBalanceSnapshot", back_populates="cash_account")

    __table_args__ = (
        UniqueConstraint("portfolio_id", "account_id", "currency", "cash_account_type", name="uq_cash_account_identity"),
    )


class CashJournal(Base):
    """
    Double-entry cash journal header representing an atomic accounting transaction.
    """
    __tablename__ = "m05_cash_journals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    journal_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    journal_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    cash_account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    
    source_movement_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    source_event_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True, index=True)
    reversal_of_journal_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    effective_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    posted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="POSTED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    lines: Mapped[List["CashJournalLine"]] = relationship("CashJournalLine", back_populates="journal", cascade="all, delete-orphan")


class CashJournalLine(Base):
    """
    Balanced debit or credit entry in a double-entry cash journal.
    For Cash asset accounts: Debit increases cash, Credit decreases cash.
    """
    __tablename__ = "m05_cash_journal_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    journal_id: Mapped[str] = mapped_column(String(64), ForeignKey("m05_cash_journals.journal_id"), nullable=False, index=True)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    ledger_account_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    debit_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    credit_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    journal: Mapped["CashJournal"] = relationship("CashJournal", back_populates="lines")


class CashMovement(Base):
    """
    Immutable economic cash movement record.
    """
    __tablename__ = "m05_cash_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    movement_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    cash_account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_cash_accounts.cash_account_id"), nullable=False, index=True
    )
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    
    movement_type: Mapped[CashMovementType] = mapped_column(
        SAEnum(CashMovementType, native_enum=False), nullable=False, index=True
    )
    signed_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)  # Inflow > 0, Outflow < 0
    currency: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    fees_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    
    effective_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    settlement_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    status: Mapped[CashMovementStatus] = mapped_column(
        SAEnum(CashMovementStatus, native_enum=False), default=CashMovementStatus.PENDING, nullable=False, index=True
    )
    
    source_system: Mapped[str] = mapped_column(String(64), default="INTERNAL", nullable=False)
    source_event_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    external_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    related_instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    related_trade_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    related_corporate_action_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    transfer_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    reversal_of_movement_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True, index=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    cash_account: Mapped["CashAccount"] = relationship("CashAccount", back_populates="movements")


class CashReservation(Base):
    """
    Cash reservation earmarked for an active commitment (orders, trades, fees).
    """
    __tablename__ = "m05_cash_reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reservation_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    cash_account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_cash_accounts.cash_account_id"), nullable=False, index=True
    )
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    
    reservation_type: Mapped[CashReservationType] = mapped_column(
        SAEnum(CashReservationType, native_enum=False), nullable=False, index=True
    )
    reserved_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    remaining_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    
    source_commitment_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    source_order_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    source_trade_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    
    status: Mapped[CashReservationStatus] = mapped_column(
        SAEnum(CashReservationStatus, native_enum=False), default=CashReservationStatus.ACTIVE, nullable=False, index=True
    )
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    policy_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True, index=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    cash_account: Mapped["CashAccount"] = relationship("CashAccount", back_populates="reservations")
    events: Mapped[List["CashReservationEvent"]] = relationship("CashReservationEvent", back_populates="reservation", cascade="all, delete-orphan")


class CashReservationEvent(Base):
    """
    Lifecycle event log for cash reservations (adjustments, partial releases, expiries).
    """
    __tablename__ = "m05_cash_reservation_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reservation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_cash_reservations.reservation_id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)  # CREATED, ADJUSTED, PARTIALLY_RELEASED, RELEASED, EXPIRED, SETTLED
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    previous_remaining_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    new_remaining_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    source_event_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    reservation: Mapped["CashReservation"] = relationship("CashReservation", back_populates="events")


class CashCommitment(Base):
    """
    Pending or unsettled cash commitment (receivable from sale/dividend, or payable from buy/fee).
    """
    __tablename__ = "m05_cash_commitments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    commitment_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    cash_account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_cash_accounts.cash_account_id"), nullable=False, index=True
    )
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    
    commitment_type: Mapped[CommitmentType] = mapped_column(
        SAEnum(CommitmentType, native_enum=False), nullable=False, index=True
    )
    expected_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    outstanding_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    expected_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    actual_settlement_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    source_event_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    reservation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[CommitmentStatus] = mapped_column(
        SAEnum(CommitmentStatus, native_enum=False), default=CommitmentStatus.EXPECTED, nullable=False, index=True
    )
    
    effective_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    cash_account: Mapped["CashAccount"] = relationship("CashAccount", back_populates="commitments")


class CashRestriction(Base):
    """
    Restricted cash amount (blocked, pledged, or regulatory hold).
    """
    __tablename__ = "m05_cash_restrictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    restriction_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    cash_account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_cash_accounts.cash_account_id"), nullable=False, index=True
    )
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    
    restricted_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    restriction_type: Mapped[CashRestrictionType] = mapped_column(
        SAEnum(CashRestrictionType, native_enum=False), default=CashRestrictionType.BLOCKED, nullable=False
    )
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    source_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    
    status: Mapped[CashRestrictionStatus] = mapped_column(
        SAEnum(CashRestrictionStatus, native_enum=False), default=CashRestrictionStatus.ACTIVE, nullable=False, index=True
    )
    effective_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    cash_account: Mapped["CashAccount"] = relationship("CashAccount", back_populates="restrictions")


class CashBalanceSnapshot(Base):
    """
    Point-in-time materialized cash balance snapshot. Disposable and rebuildable from ledger.
    """
    __tablename__ = "m05_cash_balance_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    cash_account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_cash_accounts.cash_account_id"), nullable=False, index=True
    )
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    
    settled_balance: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    unsettled_receivables: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    unsettled_payables: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    reserved_cash: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    restricted_cash: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    eligible_credit: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    minimum_cash_buffer: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    available_cash: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    
    availability_status: Mapped[AvailableCashStatus] = mapped_column(
        SAEnum(AvailableCashStatus, native_enum=False), default=AvailableCashStatus.AVAILABLE, nullable=False
    )
    effective_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    cash_account: Mapped["CashAccount"] = relationship("CashAccount", back_populates="snapshots")


class CashTransferGroup(Base):
    """
    Linked transfer record connecting source debit and destination credit legs.
    """
    __tablename__ = "m05_cash_transfer_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transfer_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    source_cash_account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    destination_cash_account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    destination_portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    
    source_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    destination_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    source_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    destination_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    
    fx_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    fx_rate_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    
    status: Mapped[TransferStatus] = mapped_column(
        SAEnum(TransferStatus, native_enum=False), default=TransferStatus.INITIATED, nullable=False
    )
    source_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    settlement_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class CashReconciliationRun(Base):
    """
    Reconciliation record between internal cash balance and external broker/custody statement.
    """
    __tablename__ = "m05_cash_reconciliation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    cash_account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    statement_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    internal_closing_balance: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    external_closing_balance: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    difference: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    
    status: Mapped[ReconciliationStatus] = mapped_column(
        SAEnum(ReconciliationStatus, native_enum=False), default=ReconciliationStatus.PENDING_REVIEW, nullable=False
    )
    source_statement_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    exception_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class CashPolicy(Base):
    """
    Configurable cash availability and accounting policy per portfolio.
    """
    __tablename__ = "m05_cash_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    policy_name: Mapped[str] = mapped_column(String(128), nullable=False)
    
    allow_unsettled_receivables: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allow_sale_proceeds_reuse: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allow_credit_facility: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    credit_facility_limit: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    minimum_cash_buffer: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    allow_account_pooling: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
