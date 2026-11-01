"""SQLAlchemy 2.x Models for M05.05 - Transaction Management."""
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any
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
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


# ---------------------------------------------------------------------------
# ENUMS
# ---------------------------------------------------------------------------

class TransactionType(str, Enum):
    TRADE = "TRADE"
    SECURITY_TRANSFER = "SECURITY_TRANSFER"
    CASH_TRANSFER = "CASH_TRANSFER"
    CORPORATE_ACTION = "CORPORATE_ACTION"
    ADJUSTMENT = "ADJUSTMENT"


class TradeSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class PositionEffect(str, Enum):
    OPEN_LONG = "OPEN_LONG"
    CLOSE_LONG = "CLOSE_LONG"
    OPEN_SHORT = "OPEN_SHORT"
    CLOSE_SHORT = "CLOSE_SHORT"
    UNSPECIFIED = "UNSPECIFIED"


class TransactionStatus(str, Enum):
    PENDING = "PENDING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    PARTIALLY_FILLED_CANCELLED = "PARTIALLY_FILLED_CANCELLED"
    CORRECTED = "CORRECTED"
    REVERSED = "REVERSED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


class ExecutionStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    CORRECTED = "CORRECTED"
    BUSTED = "BUSTED"
    REVERSED = "REVERSED"


class TransferDirection(str, Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"
    INTERNAL = "INTERNAL"


class TransferStatus(str, Enum):
    INITIATED = "INITIATED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    IN_PROGRESS = "IN_PROGRESS"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    REVERSED = "REVERSED"


class AdjustmentCategory(str, Enum):
    SECURITY_QUANTITY = "SECURITY_QUANTITY"
    CASH_BALANCE = "CASH_BALANCE"
    TRADE_CORRECTION = "TRADE_CORRECTION"
    FEE_CORRECTION = "FEE_CORRECTION"
    SETTLEMENT_REFERENCE = "SETTLEMENT_REFERENCE"
    RECONCILIATION_ADJUSTMENT = "RECONCILIATION_ADJUSTMENT"
    OTHER = "OTHER"


class AdjustmentApprovalStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    POSTED = "POSTED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    REVERSED = "REVERSED"


class SettlementStatus(str, Enum):
    NOT_SCHEDULED = "NOT_SCHEDULED"
    EXPECTED = "EXPECTED"
    SCHEDULED = "SCHEDULED"
    DUE = "DUE"
    SETTLED = "SETTLED"
    PARTIALLY_SETTLED = "PARTIALLY_SETTLED"
    FAILED = "FAILED"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"
    REVERSED = "REVERSED"


class OutboxDeliveryStatus(str, Enum):
    PENDING = "PENDING"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    RETRIED = "RETRIED"


# ---------------------------------------------------------------------------
# MODELS
# ---------------------------------------------------------------------------

class Transaction(Base):
    """
    Authoritative logical transaction record (parent of individual executions).
    """
    __tablename__ = "m05_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_portfolios.portfolio_id"), nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("m04_instruments.instrument_id"), nullable=True, index=True
    )
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    
    transaction_type: Mapped[TransactionType] = mapped_column(
        SAEnum(TransactionType, native_enum=False), default=TransactionType.TRADE, nullable=False, index=True
    )
    trade_side: Mapped[Optional[TradeSide]] = mapped_column(
        SAEnum(TradeSide, native_enum=False), nullable=True, index=True
    )
    position_effect: Mapped[PositionEffect] = mapped_column(
        SAEnum(PositionEffect, native_enum=False), default=PositionEffect.UNSPECIFIED, nullable=False
    )
    transaction_currency: Mapped[str] = mapped_column(String(3), nullable=False, index=True)  # ISO-4217
    
    requested_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    executed_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    remaining_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    cancelled_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    
    average_execution_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    aggregate_gross_consideration: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    aggregate_fees: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    aggregate_net_consideration: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    
    trade_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False, index=True)
    first_execution_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_execution_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expected_settlement_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    
    status: Mapped[TransactionStatus] = mapped_column(
        SAEnum(TransactionStatus, native_enum=False), default=TransactionStatus.PENDING, nullable=False, index=True
    )
    source_system: Mapped[str] = mapped_column(String(64), default="MANUAL", nullable=False)
    external_order_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    external_trade_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    executions: Mapped[List["TradeExecution"]] = relationship("TradeExecution", back_populates="transaction", cascade="all, delete-orphan")
    lifecycle_events: Mapped[List["TransactionLifecycleEvent"]] = relationship("TransactionLifecycleEvent", back_populates="transaction", cascade="all, delete-orphan")
    fees: Mapped[List["TransactionFee"]] = relationship("TransactionFee", back_populates="transaction", cascade="all, delete-orphan")
    settlement: Mapped[Optional["TransactionSettlement"]] = relationship("TransactionSettlement", back_populates="transaction", uselist=False, cascade="all, delete-orphan")


class TradeExecution(Base):
    """
    Individual fill or confirmed execution leg of a logical trade.
    """
    __tablename__ = "m05_trade_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    transaction_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_transactions.transaction_id"), nullable=False, index=True
    )
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    trade_side: Mapped[TradeSide] = mapped_column(SAEnum(TradeSide, native_enum=False), nullable=False)
    position_effect: Mapped[PositionEffect] = mapped_column(
        SAEnum(PositionEffect, native_enum=False), default=PositionEffect.UNSPECIFIED, nullable=False
    )
    executed_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    execution_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    execution_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    gross_consideration: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    
    execution_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    trade_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    source_system: Mapped[str] = mapped_column(String(64), default="MANUAL", nullable=False)
    external_execution_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    broker_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    source_sequence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    execution_status: Mapped[ExecutionStatus] = mapped_column(
        SAEnum(ExecutionStatus, native_enum=False), default=ExecutionStatus.CONFIRMED, nullable=False
    )
    correction_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    supersedes_execution_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="executions")

    __table_args__ = (
        UniqueConstraint("source_system", "external_execution_id", name="uq_source_external_exec_id"),
    )


class TransactionLifecycleEvent(Base):
    """
    Immutable audit history of state machine transitions for transactions.
    """
    __tablename__ = "m05_transaction_lifecycle_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_transactions.transaction_id"), nullable=False, index=True
    )
    previous_status: Mapped[str] = mapped_column(String(32), nullable=False)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_system: Mapped[str] = mapped_column(String(64), default="INTERNAL", nullable=False)
    source_event_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="lifecycle_events")


class TransactionFee(Base):
    """
    Itemized execution or transaction fee record.
    """
    __tablename__ = "m05_transaction_fees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fee_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    transaction_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_transactions.transaction_id"), nullable=False, index=True
    )
    execution_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    transfer_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    
    fee_category: Mapped[str] = mapped_column(String(64), nullable=False)  # BROKERAGE, EXCHANGE, TAX, STAMP_DUTY
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    fee_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    fee_source: Mapped[str] = mapped_column(String(64), default="ESTIMATED", nullable=False)
    external_fee_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    estimated_or_actual: Mapped[str] = mapped_column(String(16), default="ACTUAL", nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="fees")


class TransactionTransfer(Base):
    """
    Inbound, outbound, or internal security and cash transfer master record.
    """
    __tablename__ = "m05_transaction_transfers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transfer_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    destination_account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    
    transfer_type: Mapped[str] = mapped_column(String(32), default="SECURITY", nullable=False)  # SECURITY, CASH
    transfer_direction: Mapped[TransferDirection] = mapped_column(
        SAEnum(TransferDirection, native_enum=False), default=TransferDirection.INTERNAL, nullable=False
    )
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    destination_currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    source_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    destination_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    fx_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    fees_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    
    status: Mapped[TransferStatus] = mapped_column(
        SAEnum(TransferStatus, native_enum=False), default=TransferStatus.INITIATED, nullable=False, index=True
    )
    external_transfer_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    legs: Mapped[List["TransactionTransferLeg"]] = relationship("TransactionTransferLeg", back_populates="transfer", cascade="all, delete-orphan")


class TransactionTransferLeg(Base):
    """
    Individual debit or credit leg of an internal or linked transfer.
    """
    __tablename__ = "m05_transaction_transfer_legs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transfer_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_transaction_transfers.transfer_id"), nullable=False, index=True
    )
    leg_type: Mapped[str] = mapped_column(String(32), nullable=False)  # SECURITY, CASH
    direction: Mapped[str] = mapped_column(String(16), nullable=False)  # DEBIT, CREDIT
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    transfer: Mapped["TransactionTransfer"] = relationship("TransactionTransfer", back_populates="legs")


class TransactionAdjustment(Base):
    """
    Controlled manual adjustment request requiring authorization and auditable approval.
    """
    __tablename__ = "m05_transaction_adjustments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    adjustment_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    transaction_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    
    adjustment_type: Mapped[AdjustmentCategory] = mapped_column(
        SAEnum(AdjustmentCategory, native_enum=False), default=AdjustmentCategory.SECURITY_QUANTITY, nullable=False
    )
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    original_value: Mapped[str] = mapped_column(String(128), nullable=False)
    proposed_value: Mapped[str] = mapped_column(String(128), nullable=False)
    adjustment_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    supporting_evidence_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    requested_by: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    approval_status: Mapped[AdjustmentApprovalStatus] = mapped_column(
        SAEnum(AdjustmentApprovalStatus, native_enum=False), default=AdjustmentApprovalStatus.PENDING_APPROVAL, nullable=False, index=True
    )
    approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    downstream_posting_status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class TransactionCorrection(Base):
    """
    Audit log preserving old and new values for trade corrections, bust, and reversals.
    """
    __tablename__ = "m05_transaction_corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    correction_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    original_transaction_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    original_execution_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    correction_type: Mapped[str] = mapped_column(String(32), nullable=False)  # QUANTITY, PRICE, FEE, BUST, REVERSAL
    correction_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    
    old_values: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    new_values: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    source_system: Mapped[str] = mapped_column(String(64), default="MANUAL", nullable=False)
    source_event_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class TransactionSettlement(Base):
    """
    Transaction-level settlement references and tracking.
    """
    __tablename__ = "m05_transaction_settlements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_transactions.transaction_id"), unique=True, nullable=False, index=True
    )
    expected_settlement_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_settlement_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    settlement_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    settlement_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    settled_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    settled_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    outstanding_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    outstanding_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    settlement_status: Mapped[SettlementStatus] = mapped_column(
        SAEnum(SettlementStatus, native_enum=False), default=SettlementStatus.SCHEDULED, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="settlement")


class TransactionOutbox(Base):
    """
    Transactional outbox for reliable downstream event publication to Position (M05.02) and Cash (M05.04).
    """
    __tablename__ = "m05_transaction_outbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    outbox_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    aggregate_type: Mapped[str] = mapped_column(String(32), default="TRANSACTION", nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)  # POSITION_EFFECT, CASH_EFFECT
    destination_module: Mapped[str] = mapped_column(String(64), nullable=False)  # M05.02_POSITION, M05.04_CASH
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    delivery_status: Mapped[OutboxDeliveryStatus] = mapped_column(
        SAEnum(OutboxDeliveryStatus, native_enum=False), default=OutboxDeliveryStatus.PENDING, nullable=False, index=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
