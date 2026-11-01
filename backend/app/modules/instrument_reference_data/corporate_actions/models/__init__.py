import enum
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    Boolean,
    DateTime,
    Date,
    ForeignKey,
    Text,
    Enum as SAEnum,
    Index
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from backend.app.core.database import Base


class CorporateActionType(str, enum.Enum):
    CASH_DIVIDEND = "CASH_DIVIDEND"
    STOCK_DIVIDEND = "STOCK_DIVIDEND"
    STOCK_SPLIT = "STOCK_SPLIT"
    REVERSE_SPLIT = "REVERSE_SPLIT"
    BONUS_ISSUE = "BONUS_ISSUE"
    MERGER = "MERGER"
    SPINOFF = "SPINOFF"
    CONVERSION = "CONVERSION"
    CANCELLATION = "CANCELLATION"


class LifecycleStatus(str, enum.Enum):
    ANNOUNCED = "ANNOUNCED"
    CONFIRMED = "CONFIRMED"
    EFFECTIVE = "EFFECTIVE"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"


class InstrumentRole(str, enum.Enum):
    ORIGINAL_SECURITY = "ORIGINAL_SECURITY"
    SUCCESSOR_SECURITY = "SUCCESSOR_SECURITY"
    ACQUIRING_SECURITY = "ACQUIRING_SECURITY"
    CANCELLED_SECURITY = "CANCELLED_SECURITY"
    SPUNOFF_SECURITY = "SPUNOFF_SECURITY"


class ConsiderationType(str, enum.Enum):
    STOCK = "STOCK"
    CASH = "CASH"
    MIXED = "MIXED"


class GrossNetBasis(str, enum.Enum):
    GROSS = "GROSS"
    NET = "NET"


class CorporateAction(Base):
    """
    Authoritative canonical registry entity for corporate actions.
    Supports bitemporal/versioned event definitions.
    """
    __tablename__ = "corporate_actions"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    corporate_action_type: Mapped[CorporateActionType] = mapped_column(
        SAEnum(CorporateActionType, native_enum=False), nullable=False, index=True
    )
    lifecycle_status: Mapped[LifecycleStatus] = mapped_column(
        SAEnum(LifecycleStatus, native_enum=False), nullable=False, default=LifecycleStatus.ANNOUNCED, index=True
    )
    primary_instrument_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m04_instruments.instrument_id"), nullable=False, index=True
    )
    
    # Event dates
    declaration_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    ex_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    record_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    payment_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Versioning & Audit
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    source_name: Mapped[str] = mapped_column(String(64), nullable=False, default="MANUAL")
    source_reference_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    instruments: Mapped[List["CorporateActionInstrument"]] = relationship(
        "CorporateActionInstrument", back_populates="corporate_action", cascade="all, delete-orphan"
    )
    versions: Mapped[List["CorporateActionVersion"]] = relationship(
        "CorporateActionVersion", back_populates="corporate_action", cascade="all, delete-orphan"
    )
    dividend_detail: Mapped[Optional["CorporateActionDividend"]] = relationship(
        "CorporateActionDividend", back_populates="corporate_action", uselist=False, cascade="all, delete-orphan"
    )
    ratio_detail: Mapped[Optional["CorporateActionRatio"]] = relationship(
        "CorporateActionRatio", back_populates="corporate_action", uselist=False, cascade="all, delete-orphan"
    )
    merger_detail: Mapped[Optional["CorporateActionMerger"]] = relationship(
        "CorporateActionMerger", back_populates="corporate_action", uselist=False, cascade="all, delete-orphan"
    )


class CorporateActionInstrument(Base):
    """
    Associates an event with involved instruments (e.g., target, acquirer, successor).
    """
    __tablename__ = "corporate_action_instruments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("corporate_actions.event_id", ondelete="CASCADE"), nullable=False, index=True
    )
    instrument_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m04_instruments.instrument_id"), nullable=False, index=True
    )
    role: Mapped[InstrumentRole] = mapped_column(
        SAEnum(InstrumentRole, native_enum=False), nullable=False, default=InstrumentRole.ORIGINAL_SECURITY
    )

    corporate_action: Mapped["CorporateAction"] = relationship("CorporateAction", back_populates="instruments")


class CorporateActionVersion(Base):
    """
    Immutable version snapshot preserving full event history across updates/amendments.
    """
    __tablename__ = "corporate_action_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("corporate_actions.event_id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_payload: Mapped[str] = mapped_column(Text, nullable=False)  # JSON dump of terms
    reason: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    corporate_action: Mapped["CorporateAction"] = relationship("CorporateAction", back_populates="versions")


class CorporateActionDividend(Base):
    """
    Stores cash and stock dividend specifics.
    """
    __tablename__ = "corporate_action_dividends"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("corporate_actions.event_id", ondelete="CASCADE"), unique=True, nullable=False
    )
    gross_amount: Mapped[Numeric] = mapped_column(Numeric(18, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    gross_net_basis: Mapped[GrossNetBasis] = mapped_column(
        SAEnum(GrossNetBasis, native_enum=False), default=GrossNetBasis.GROSS, nullable=False
    )
    withholding_tax_rate: Mapped[Optional[Numeric]] = mapped_column(Numeric(8, 6), nullable=True, default=0.0)
    reinvestment_price: Mapped[Optional[Numeric]] = mapped_column(Numeric(18, 6), nullable=True)

    corporate_action: Mapped["CorporateAction"] = relationship("CorporateAction", back_populates="dividend_detail")


class CorporateActionRatio(Base):
    """
    Stores integer terms for stock splits, reverse splits, and bonus issues.
    """
    __tablename__ = "corporate_action_ratios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("corporate_actions.event_id", ondelete="CASCADE"), unique=True, nullable=False
    )
    numerator: Mapped[int] = mapped_column(Integer, nullable=False)
    denominator: Mapped[int] = mapped_column(Integer, nullable=False)
    additional_shares: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    existing_shares: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    corporate_action: Mapped["CorporateAction"] = relationship("CorporateAction", back_populates="ratio_detail")


class CorporateActionMerger(Base):
    """
    Stores merger, conversion, and acquisition terms.
    """
    __tablename__ = "corporate_action_mergers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("corporate_actions.event_id", ondelete="CASCADE"), unique=True, nullable=False
    )
    consideration_type: Mapped[ConsiderationType] = mapped_column(
        SAEnum(ConsiderationType, native_enum=False), nullable=False
    )
    successor_instrument_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("m04_instruments.instrument_id"), nullable=True
    )
    stock_conversion_numerator: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stock_conversion_denominator: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cash_per_share: Mapped[Optional[Numeric]] = mapped_column(Numeric(18, 6), nullable=True)
    cash_currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)

    corporate_action: Mapped["CorporateAction"] = relationship("CorporateAction", back_populates="merger_detail")


class CorporateActionAdjustmentRun(Base):
    """
    Deterministic audit run header for recalculating adjusted series.
    """
    __tablename__ = "corporate_action_adjustment_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m04_instruments.instrument_id"), nullable=False, index=True
    )
    policy_version: Mapped[str] = mapped_column(String(32), default="v1.0", nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    calculated_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)
    total_events_applied: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cumulative_price_factor: Mapped[Numeric] = mapped_column(Numeric(18, 12), nullable=False)
    cumulative_quantity_factor: Mapped[Numeric] = mapped_column(Numeric(18, 12), nullable=False)
    input_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    output_checksum: Mapped[str] = mapped_column(String(64), nullable=False)

    lineages: Mapped[List["CorporateActionAdjustmentLineage"]] = relationship(
        "CorporateActionAdjustmentLineage", back_populates="run", cascade="all, delete-orphan"
    )


class CorporateActionAdjustmentLineage(Base):
    """
    Step-by-step audit lineage from raw original observations to adjusted metrics.
    """
    __tablename__ = "corporate_action_adjustment_lineage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("corporate_action_adjustment_runs.run_id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_version: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    unadjusted_price: Mapped[Numeric] = mapped_column(Numeric(18, 6), nullable=False)
    step_price_factor: Mapped[Numeric] = mapped_column(Numeric(18, 12), nullable=False)
    adjusted_price: Mapped[Numeric] = mapped_column(Numeric(18, 6), nullable=False)
    
    unadjusted_quantity: Mapped[Numeric] = mapped_column(Numeric(18, 4), nullable=False)
    step_quantity_factor: Mapped[Numeric] = mapped_column(Numeric(18, 12), nullable=False)
    adjusted_quantity: Mapped[Numeric] = mapped_column(Numeric(18, 4), nullable=False)
    
    formula_description: Mapped[str] = mapped_column(String(256), nullable=False)

    run: Mapped["CorporateActionAdjustmentRun"] = relationship(
        "CorporateActionAdjustmentRun", back_populates="lineages"
    )
