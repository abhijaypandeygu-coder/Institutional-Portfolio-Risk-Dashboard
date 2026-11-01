"""SQLAlchemy 2.x Models for M05.02 - Position Management."""
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


class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


class PositionStatus(str, Enum):
    OPEN = "OPEN"
    ACTIVE = "ACTIVE"
    PARTIALLY_CLOSED = "PARTIALLY_CLOSED"
    CLOSED = "CLOSED"
    RESTRICTED = "RESTRICTED"
    UNDER_RECONCILIATION = "UNDER_RECONCILIATION"
    UNKNOWN = "UNKNOWN"


class PositionEventType(str, Enum):
    TRADE_BUY = "TRADE_BUY"
    TRADE_SELL = "TRADE_SELL"
    SHORT_OPEN = "SHORT_OPEN"
    SHORT_INCREASE = "SHORT_INCREASE"
    SHORT_COVER = "SHORT_COVER"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
    INTERNAL_TRANSFER = "INTERNAL_TRANSFER"
    SETTLEMENT = "SETTLEMENT"
    STOCK_SPLIT = "STOCK_SPLIT"
    REVERSE_SPLIT = "REVERSE_SPLIT"
    BONUS_ISSUE = "BONUS_ISSUE"
    MERGER_CONVERSION = "MERGER_CONVERSION"
    CORPORATE_ACTION_ADJUSTMENT = "CORPORATE_ACTION_ADJUSTMENT"
    POSITION_CORRECTION = "POSITION_CORRECTION"
    POSITION_REVERSAL = "POSITION_REVERSAL"
    RECONCILIATION_ADJUSTMENT = "RECONCILIATION_ADJUSTMENT"
    OTHER_APPROVED_EVENT = "OTHER_APPROVED_EVENT"


class PositionEventStatus(str, Enum):
    RECEIVED = "RECEIVED"
    VALIDATING = "VALIDATING"
    APPROVED = "APPROVED"
    PENDING_DEPENDENCY = "PENDING_DEPENDENCY"
    READY_FOR_PROCESSING = "READY_FOR_PROCESSING"
    PROCESSING = "PROCESSING"
    APPLIED = "APPLIED"
    PARTIALLY_APPLIED = "PARTIALLY_APPLIED"
    REJECTED = "REJECTED"
    QUARANTINED = "QUARANTINED"
    REVERSED = "REVERSED"
    SUPERSEDED = "SUPERSEDED"
    FAILED = "FAILED"


class TransferStatus(str, Enum):
    INITIATED = "INITIATED"
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    APPROVED = "APPROVED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    REVERSED = "REVERSED"


class BorrowStatus(str, Enum):
    VERIFIED = "VERIFIED"
    APPROVED = "APPROVED"
    PENDING = "PENDING"
    UNVERIFIED = "UNVERIFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    RESTRICTED = "RESTRICTED"
    RECALLED = "RECALLED"
    EXPIRED = "EXPIRED"


class ReconciliationStatus(str, Enum):
    MATCHED = "MATCHED"
    MATCHED_WITH_TOLERANCE = "MATCHED_WITH_TOLERANCE"
    DISCREPANCY = "DISCREPANCY"
    MISSING_INTERNAL_POSITION = "MISSING_INTERNAL_POSITION"
    MISSING_EXTERNAL_POSITION = "MISSING_EXTERNAL_POSITION"
    QUANTITY_MISMATCH = "QUANTITY_MISMATCH"
    SETTLEMENT_MISMATCH = "SETTLEMENT_MISMATCH"
    BORROW_MISMATCH = "BORROW_MISMATCH"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    PENDING_REVIEW = "PENDING_REVIEW"
    RESOLVED = "RESOLVED"


# ---------------------------------------------------------------------------
# 1. POSITION BOOK (Account-Level & Portfolio-Level Granularity)
# ---------------------------------------------------------------------------
class PositionBook(Base):
    """
    Authoritative position identity book per portfolio, account, and instrument/listing.
    """
    __tablename__ = "m05_position_books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    position_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_portfolios.portfolio_id"), nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m04_instruments.instrument_id"), nullable=False, index=True
    )
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    sleeve_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    
    position_side: Mapped[PositionSide] = mapped_column(
        SAEnum(PositionSide, native_enum=False), default=PositionSide.FLAT, nullable=False
    )
    position_status: Mapped[PositionStatus] = mapped_column(
        SAEnum(PositionStatus, native_enum=False), default=PositionStatus.OPEN, nullable=False
    )
    
    current_snapshot_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    events: Mapped[List["PositionEvent"]] = relationship(
        "PositionEvent", back_populates="position_book", cascade="all, delete-orphan"
    )
    snapshots: Mapped[List["PositionSnapshot"]] = relationship(
        "PositionSnapshot", back_populates="position_book", cascade="all, delete-orphan"
    )
    borrow_metadata: Mapped[List["PositionBorrowMetadata"]] = relationship(
        "PositionBorrowMetadata", back_populates="position_book", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("portfolio_id", "account_id", "instrument_id", "listing_id", name="uq_position_identity"),
    )


# ---------------------------------------------------------------------------
# 2. POSITION EVENT LEDGER (Authoritative & Immutable)
# ---------------------------------------------------------------------------
class PositionEvent(Base):
    """
    Immutable event ledger representing every quantity-impacting transaction, corporate action, transfer, or settlement.
    """
    __tablename__ = "m05_position_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    position_event_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    position_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_position_books.position_id", ondelete="CASCADE"), nullable=False, index=True
    )
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    event_type: Mapped[PositionEventType] = mapped_column(
        SAEnum(PositionEventType, native_enum=False), nullable=False, index=True
    )
    event_status: Mapped[PositionEventStatus] = mapped_column(
        SAEnum(PositionEventStatus, native_enum=False), default=PositionEventStatus.APPLIED, nullable=False
    )

    # Signed quantity deltas: Longs are positive, Shorts are negative
    signed_quantity_delta: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    settled_quantity_delta: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    unsettled_quantity_delta: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)

    effective_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    source_system: Mapped[str] = mapped_column(String(64), default="MANUAL", nullable=False)
    source_event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    transaction_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    corporate_action_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    transfer_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    event_sequence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    reversal_of_event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    position_book: Mapped["PositionBook"] = relationship("PositionBook", back_populates="events")


# ---------------------------------------------------------------------------
# 3. POSITION SNAPSHOTS (Projections & Historical Point-in-Time)
# ---------------------------------------------------------------------------
class PositionSnapshot(Base):
    """
    Derived projection snapshot representing exact signed position quantities and components.
    """
    __tablename__ = "m05_position_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    position_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_position_books.position_id", ondelete="CASCADE"), nullable=False, index=True
    )
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    position_side: Mapped[PositionSide] = mapped_column(
        SAEnum(PositionSide, native_enum=False), default=PositionSide.FLAT, nullable=False
    )
    
    # Quantities
    gross_long_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    gross_short_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False) # Positive magnitude
    net_signed_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)  # + for Long, - for Short
    
    settled_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    unsettled_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    economic_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    
    available_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    reserved_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    restricted_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    borrowed_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)

    effective_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_applied_event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    snapshot_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    position_book: Mapped["PositionBook"] = relationship("PositionBook", back_populates="snapshots")


# ---------------------------------------------------------------------------
# 4. PORTFOLIO-LEVEL POSITION AGGREGATES
# ---------------------------------------------------------------------------
class PortfolioPositionAggregate(Base):
    """
    Derived portfolio-level position aggregated across contributing accounts.
    Preserves gross long and gross short quantities independently.
    """
    __tablename__ = "m05_portfolio_position_aggregates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    aggregate_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    gross_long_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    gross_short_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    net_signed_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    
    settled_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    unsettled_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    available_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    
    contributing_account_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    effective_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    snapshot_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


# ---------------------------------------------------------------------------
# 5. BORROW METADATA FOR SHORT POSITIONS
# ---------------------------------------------------------------------------
class PositionBorrowMetadata(Base):
    """
    Tracks borrow locates, lenders, borrow rates, and recall dates for short positions.
    """
    __tablename__ = "m05_position_borrow_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    borrow_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    position_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_position_books.position_id", ondelete="CASCADE"), nullable=False, index=True
    )
    lender_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    locate_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    borrowed_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    borrow_rate_annual_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4), nullable=True)
    borrow_status: Mapped[BorrowStatus] = mapped_column(
        SAEnum(BorrowStatus, native_enum=False), default=BorrowStatus.APPROVED, nullable=False
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    recall_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    position_book: Mapped["PositionBook"] = relationship("PositionBook", back_populates="borrow_metadata")


# ---------------------------------------------------------------------------
# 6. POSITION TRANSFERS
# ---------------------------------------------------------------------------
class PositionTransfer(Base):
    """
    Internal and external transfers linking source and destination accounts.
    """
    __tablename__ = "m05_position_transfers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transfer_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    source_portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    destination_portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False)
    destination_account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    transfer_status: Mapped[TransferStatus] = mapped_column(
        SAEnum(TransferStatus, native_enum=False), default=TransferStatus.INITIATED, nullable=False
    )
    source_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    destination_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    effective_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    transfer_reason: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


# ---------------------------------------------------------------------------
# 7. POSITION RECONCILIATION RECORDS
# ---------------------------------------------------------------------------
class PositionReconciliationRecord(Base):
    """
    Discrepancy detection between internal positions and external broker/custodian records.
    """
    __tablename__ = "m05_position_reconciliations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reconciliation_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    position_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False)
    
    internal_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    external_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    difference_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    
    reconciliation_status: Mapped[ReconciliationStatus] = mapped_column(
        SAEnum(ReconciliationStatus, native_enum=False), default=ReconciliationStatus.DISCREPANCY, nullable=False
    )
    source_name: Mapped[str] = mapped_column(String(64), default="BROKER", nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
