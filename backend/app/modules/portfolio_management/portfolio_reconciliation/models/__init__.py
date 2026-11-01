"""SQLAlchemy 2.x Models for M05.06 - Portfolio Reconciliation."""
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

class ProviderType(str, Enum):
    BROKER = "BROKER"
    CUSTODIAN = "CUSTODIAN"
    FUND_ADMINISTRATOR = "FUND_ADMINISTRATOR"
    PORTFOLIO_ADMINISTRATOR = "PORTFOLIO_ADMINISTRATOR"
    OTHER = "OTHER"


class StatementType(str, Enum):
    POSITION = "POSITION"
    TRANSACTION = "TRANSACTION"
    CASH = "CASH"
    SETTLEMENT = "SETTLEMENT"
    VALUATION = "VALUATION"
    FULL_PORTFOLIO = "FULL_PORTFOLIO"


class ImportStatus(str, Enum):
    UPLOADED = "UPLOADED"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    NORMALIZING = "NORMALIZING"
    STAGED = "STAGED"
    READY_FOR_RECONCILIATION = "READY_FOR_RECONCILIATION"
    PARTIALLY_IMPORTED = "PARTIALLY_IMPORTED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    DUPLICATE = "DUPLICATE"
    SUPERSEDED = "SUPERSEDED"


class ReconciliationType(str, Enum):
    POSITION = "POSITION"
    TRANSACTION = "TRANSACTION"
    CASH = "CASH"
    PRICE_VALUATION = "PRICE_VALUATION"
    FULL_PORTFOLIO = "FULL_PORTFOLIO"


class ReconciliationRunStatus(str, Enum):
    CREATED = "CREATED"
    SNAPSHOTTING_INTERNAL_BOOK = "SNAPSHOTTING_INTERNAL_BOOK"
    MATCHING = "MATCHING"
    COMPARING = "COMPARING"
    GENERATING_BREAKS = "GENERATING_BREAKS"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_BREAKS = "COMPLETED_WITH_BREAKS"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class BreakCategory(str, Enum):
    # Position Breaks
    MISSING_INTERNAL_POSITION = "MISSING_INTERNAL_POSITION"
    MISSING_EXTERNAL_POSITION = "MISSING_EXTERNAL_POSITION"
    QUANTITY_MISMATCH = "QUANTITY_MISMATCH"
    LONG_SHORT_CLASSIFICATION_MISMATCH = "LONG_SHORT_CLASSIFICATION_MISMATCH"
    SETTLED_QUANTITY_MISMATCH = "SETTLED_QUANTITY_MISMATCH"
    UNSETTLED_QUANTITY_MISMATCH = "UNSETTLED_QUANTITY_MISMATCH"
    # Transaction Breaks
    MISSING_INTERNAL_TRANSACTION = "MISSING_INTERNAL_TRANSACTION"
    MISSING_EXTERNAL_TRANSACTION = "MISSING_EXTERNAL_TRANSACTION"
    TRANSACTION_PRICE_MISMATCH = "TRANSACTION_PRICE_MISMATCH"
    TRANSACTION_QUANTITY_MISMATCH = "TRANSACTION_QUANTITY_MISMATCH"
    TRANSACTION_FEE_MISMATCH = "TRANSACTION_FEE_MISMATCH"
    # Cash Breaks
    CASH_BALANCE_MISMATCH = "CASH_BALANCE_MISMATCH"
    MISSING_INTERNAL_CASH_MOVEMENT = "MISSING_INTERNAL_CASH_MOVEMENT"
    MISSING_EXTERNAL_CASH_MOVEMENT = "MISSING_EXTERNAL_CASH_MOVEMENT"
    # Mapping & Valuation Breaks
    INSTRUMENT_MAPPING_MISMATCH = "INSTRUMENT_MAPPING_MISMATCH"
    PRICE_MISMATCH = "PRICE_MISMATCH"
    MARKET_VALUE_MISMATCH = "MARKET_VALUE_MISMATCH"
    TIMING_DIFFERENCE = "TIMING_DIFFERENCE"


class BreakSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class BreakStatus(str, Enum):
    DETECTED = "DETECTED"
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    INVESTIGATING = "INVESTIGATING"
    PENDING_REVIEW = "PENDING_REVIEW"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"
    CANCELLED = "CANCELLED"


class ResolutionType(str, Enum):
    TIMING_DIFFERENCE = "TIMING_DIFFERENCE"
    PENDING_SETTLEMENT = "PENDING_SETTLEMENT"
    INTERNAL_RECORD_MISSING = "INTERNAL_RECORD_MISSING"
    EXTERNAL_RECORD_MISSING = "EXTERNAL_RECORD_MISSING"
    DUPLICATE_EXTERNAL_RECORD = "DUPLICATE_EXTERNAL_RECORD"
    POSITION_ADJUSTMENT_REQUIRED = "POSITION_ADJUSTMENT_REQUIRED"
    CASH_ADJUSTMENT_REQUIRED = "CASH_ADJUSTMENT_REQUIRED"
    TRANSACTION_CORRECTION_REQUIRED = "TRANSACTION_CORRECTION_REQUIRED"
    INSTRUMENT_MAPPING_CORRECTION = "INSTRUMENT_MAPPING_CORRECTION"
    ACCEPTED_WITH_EXPLANATION = "ACCEPTED_WITH_EXPLANATION"


# ---------------------------------------------------------------------------
# MODELS
# ---------------------------------------------------------------------------

class ReconciliationProvider(Base):
    """External statement provider (Broker, Custodian, Fund Admin)."""
    __tablename__ = "m05_reconciliation_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    provider_name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_type: Mapped[ProviderType] = mapped_column(
        SAEnum(ProviderType, native_enum=False), default=ProviderType.BROKER, nullable=False
    )
    provider_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class StatementImport(Base):
    """External statement intake and processing record."""
    __tablename__ = "m05_statement_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    statement_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    provider_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    statement_type: Mapped[StatementType] = mapped_column(
        SAEnum(StatementType, native_enum=False), default=StatementType.POSITION, nullable=False, index=True
    )
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    import_status: Mapped[ImportStatus] = mapped_column(
        SAEnum(ImportStatus, native_enum=False), default=ImportStatus.UPLOADED, nullable=False, index=True
    )
    total_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invalid_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    positions: Mapped[List["ExternalPositionRecord"]] = relationship("ExternalPositionRecord", back_populates="statement", cascade="all, delete-orphan")
    transactions: Mapped[List["ExternalTransactionRecord"]] = relationship("ExternalTransactionRecord", back_populates="statement", cascade="all, delete-orphan")
    cash_records: Mapped[List["ExternalCashRecord"]] = relationship("ExternalCashRecord", back_populates="statement", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("provider_code", "portfolio_id", "account_id", "statement_type", "as_of_date", "file_hash", name="uq_statement_import_identity"),
    )


class ExternalPositionRecord(Base):
    """Normalized external position row."""
    __tablename__ = "m05_external_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    statement_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_statement_imports.statement_id"), nullable=False, index=True
    )
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    external_symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resolved_instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    position_side: Mapped[str] = mapped_column(String(16), default="LONG", nullable=False)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    market_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    statement: Mapped["StatementImport"] = relationship("StatementImport", back_populates="positions")


class ExternalTransactionRecord(Base):
    """Normalized external trade/execution row."""
    __tablename__ = "m05_external_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    statement_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_statement_imports.statement_id"), nullable=False, index=True
    )
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    external_trade_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    external_symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resolved_instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    trade_side: Mapped[str] = mapped_column(String(16), nullable=False)  # BUY, SELL
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    fees: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    settlement_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    statement: Mapped["StatementImport"] = relationship("StatementImport", back_populates="transactions")


class ExternalCashRecord(Base):
    """Normalized external cash balance or movement row."""
    __tablename__ = "m05_external_cash_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    statement_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_statement_imports.statement_id"), nullable=False, index=True
    )
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    closing_balance: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    statement: Mapped["StatementImport"] = relationship("StatementImport", back_populates="cash_records")


class ReconciliationRun(Base):
    """Reconciliation run execution metadata and high-level results."""
    __tablename__ = "m05_reconciliation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider_code: Mapped[str] = mapped_column(String(32), nullable=False)
    reconciliation_type: Mapped[ReconciliationType] = mapped_column(
        SAEnum(ReconciliationType, native_enum=False), default=ReconciliationType.POSITION, nullable=False
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    statement_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    status: Mapped[ReconciliationRunStatus] = mapped_column(
        SAEnum(ReconciliationRunStatus, native_enum=False), default=ReconciliationRunStatus.CREATED, nullable=False, index=True
    )
    total_external_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_internal_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    matched_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unmatched_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    break_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    critical_break_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    breaks: Mapped[List["ReconciliationBreak"]] = relationship("ReconciliationBreak", back_populates="run", cascade="all, delete-orphan")


class ReconciliationBreak(Base):
    """Discrepancy record requiring investigation and resolution."""
    __tablename__ = "m05_reconciliation_breaks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    break_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_reconciliation_runs.run_id"), nullable=False, index=True
    )
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    
    break_category: Mapped[BreakCategory] = mapped_column(
        SAEnum(BreakCategory, native_enum=False), nullable=False, index=True
    )
    severity: Mapped[BreakSeverity] = mapped_column(
        SAEnum(BreakSeverity, native_enum=False), default=BreakSeverity.MEDIUM, nullable=False, index=True
    )
    break_status: Mapped[BreakStatus] = mapped_column(
        SAEnum(BreakStatus, native_enum=False), default=BreakStatus.OPEN, nullable=False, index=True
    )
    
    internal_value: Mapped[str] = mapped_column(String(128), nullable=False)
    external_value: Mapped[str] = mapped_column(String(128), nullable=False)
    difference_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    difference_unit: Mapped[str] = mapped_column(String(32), default="SHARES", nullable=False)
    
    assigned_to: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    root_cause: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    resolution_type: Mapped[Optional[ResolutionType]] = mapped_column(
        SAEnum(ResolutionType, native_enum=False), nullable=True
    )
    resolution_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    run: Mapped["ReconciliationRun"] = relationship("ReconciliationRun", back_populates="breaks")
    notes: Mapped[List["ReconciliationNote"]] = relationship("ReconciliationNote", back_populates="reconciliation_break", cascade="all, delete-orphan")


class ReconciliationNote(Base):
    """Investigation notes attached to a reconciliation break."""
    __tablename__ = "m05_reconciliation_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    note_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    break_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m05_reconciliation_breaks.break_id"), nullable=False, index=True
    )
    author_id: Mapped[str] = mapped_column(String(64), nullable=False)
    note_content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    reconciliation_break: Mapped["ReconciliationBreak"] = relationship("ReconciliationBreak", back_populates="notes")
