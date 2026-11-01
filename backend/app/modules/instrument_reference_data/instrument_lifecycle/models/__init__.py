import enum
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import (
    String,
    Integer,
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
from backend.app.modules.instrument_reference_data.instrument_lifecycle.state_machine.transitions import (
    ListingLifecycleStatus,
    InstrumentLifecycleStatus
)


class SuspensionType(str, enum.Enum):
    REGULATORY_SUSPENSION = "REGULATORY_SUSPENSION"
    EXCHANGE_IMPOSED_SUSPENSION = "EXCHANGE_IMPOSED_SUSPENSION"
    ISSUER_RELATED_SUSPENSION = "ISSUER_RELATED_SUSPENSION"
    COMPLIANCE_SUSPENSION = "COMPLIANCE_SUSPENSION"
    CORPORATE_ACTION_SUSPENSION = "CORPORATE_ACTION_SUSPENSION"
    TECHNICAL_TRADING_HALT = "TECHNICAL_TRADING_HALT"
    VOLUNTARY_SUSPENSION = "VOLUNTARY_SUSPENSION"
    OTHER = "OTHER"


class ResumptionType(str, enum.Enum):
    NORMAL_RESUMPTION = "NORMAL_RESUMPTION"
    CONDITIONAL_RESUMPTION = "CONDITIONAL_RESUMPTION"
    PHASED_RESUMPTION = "PHASED_RESUMPTION"
    AUCTION_BASED_RESUMPTION = "AUCTION_BASED_RESUMPTION"
    REGULATORY_REINSTATEMENT = "REGULATORY_REINSTATEMENT"
    OTHER = "OTHER"


class DelistingType(str, enum.Enum):
    VOLUNTARY_DELISTING = "VOLUNTARY_DELISTING"
    INVOLUNTARY_DELISTING = "INVOLUNTARY_DELISTING"
    REGULATORY_DELISTING = "REGULATORY_DELISTING"
    MERGER_RELATED_DELISTING = "MERGER_RELATED_DELISTING"
    ACQUISITION_RELATED_DELISTING = "ACQUISITION_RELATED_DELISTING"
    EXCHANGE_INITIATED_DELISTING = "EXCHANGE_INITIATED_DELISTING"
    NON_COMPLIANCE_DELISTING = "NON_COMPLIANCE_DELISTING"
    OTHER = "OTHER"


class VerificationStatus(str, enum.Enum):
    VERIFIED = "VERIFIED"
    APPROVED = "APPROVED"
    UNVERIFIED = "UNVERIFIED"
    PENDING_REVIEW = "PENDING_REVIEW"
    CONFLICTED = "CONFLICTED"
    REJECTED = "REJECTED"


class ListingLifecycleRecord(Base):
    """
    Authoritative listing lifecycle entity.
    Maintains listing identity, first trading date, and rebuildable current status projection.
    """
    __tablename__ = "listing_lifecycle_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listing_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m04_instruments.instrument_id"), nullable=False, index=True
    )
    exchange_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    market_segment: Mapped[str] = mapped_column(String(64), default="EQUITY_CASH", nullable=False)
    
    first_listing_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    first_trading_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    last_trading_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    effective_delisting_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    
    # Current status projection
    current_status: Mapped[ListingLifecycleStatus] = mapped_column(
        SAEnum(ListingLifecycleStatus, native_enum=False), default=ListingLifecycleStatus.ACTIVE, nullable=False
    )
    status_as_of: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus, native_enum=False), default=VerificationStatus.VERIFIED, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    events: Mapped[List["ListingLifecycleEvent"]] = relationship(
        "ListingLifecycleEvent", back_populates="listing_record", cascade="all, delete-orphan"
    )


class ListingLifecycleEvent(Base):
    """
    Immutable bitemporal event history for listing lifecycle transitions.
    """
    __tablename__ = "listing_lifecycle_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    listing_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("listing_lifecycle_records.listing_id", ondelete="CASCADE"), nullable=False, index=True
    )
    instrument_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m04_instruments.instrument_id"), nullable=False, index=True
    )
    
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True) # LISTING, SUSPENSION, RESUMPTION, DELISTING
    previous_status: Mapped[ListingLifecycleStatus] = mapped_column(
        SAEnum(ListingLifecycleStatus, native_enum=False), nullable=False
    )
    new_status: Mapped[ListingLifecycleStatus] = mapped_column(
        SAEnum(ListingLifecycleStatus, native_enum=False), nullable=False
    )
    
    # Bitemporal timestamps
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    announcement_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    reason: Mapped[str] = mapped_column(String(256), nullable=False)
    source_name: Mapped[str] = mapped_column(String(64), default="EXCHANGE_NOTICE", nullable=False)
    source_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus, native_enum=False), default=VerificationStatus.VERIFIED, nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)

    listing_record: Mapped["ListingLifecycleRecord"] = relationship(
        "ListingLifecycleRecord", back_populates="events"
    )


class SuspensionEvent(Base):
    """
    Suspension-specific details capturing suspension type, interval, and open-ended flag.
    """
    __tablename__ = "suspension_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    suspension_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    listing_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("listing_lifecycle_records.listing_id", ondelete="CASCADE"), nullable=False, index=True
    )
    suspension_type: Mapped[SuspensionType] = mapped_column(
        SAEnum(SuspensionType, native_enum=False), nullable=False
    )
    effective_start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_start_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expected_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    actual_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_open_ended: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reason: Mapped[str] = mapped_column(String(256), nullable=False)
    source_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ResumptionEvent(Base):
    """
    Resumption details linking back to an active suspension.
    """
    __tablename__ = "resumption_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resumption_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    listing_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("listing_lifecycle_records.listing_id", ondelete="CASCADE"), nullable=False, index=True
    )
    related_suspension_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    resumption_type: Mapped[ResumptionType] = mapped_column(
        SAEnum(ResumptionType, native_enum=False), default=ResumptionType.NORMAL_RESUMPTION, nullable=False
    )
    effective_resume_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_resume_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    conditions: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    reason: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class DelistingEvent(Base):
    """
    Delisting details capturing announcement, last trading date, and effective delisting.
    """
    __tablename__ = "delisting_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    delisting_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    listing_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("listing_lifecycle_records.listing_id", ondelete="CASCADE"), nullable=False, index=True
    )
    delisting_type: Mapped[DelistingType] = mapped_column(
        SAEnum(DelistingType, native_enum=False), nullable=False
    )
    announcement_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_trading_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_delisting_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(256), nullable=False)
    successor_instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
