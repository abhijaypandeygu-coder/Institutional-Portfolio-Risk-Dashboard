import enum
from datetime import datetime, date
from typing import Optional, List
from decimal import Decimal
from sqlalchemy import (
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


class PriceReferenceType(str, enum.Enum):
    OFFICIAL_CLOSE = "OFFICIAL_CLOSE"
    PREVIOUS_OFFICIAL_CLOSE = "PREVIOUS_OFFICIAL_CLOSE"
    OPENING_AUCTION_PRICE = "OPENING_AUCTION_PRICE"
    CLOSING_AUCTION_PRICE = "CLOSING_AUCTION_PRICE"
    AUCTION_REFERENCE_PRICE = "AUCTION_REFERENCE_PRICE"
    SETTLEMENT_PRICE = "SETTLEMENT_PRICE"
    EXCHANGE_REFERENCE_PRICE = "EXCHANGE_REFERENCE_PRICE"
    THEORETICAL_REFERENCE_PRICE = "THEORETICAL_REFERENCE_PRICE"
    OTHER_APPROVED_REFERENCE = "OTHER_APPROVED_REFERENCE"


class PriceOrigin(str, enum.Enum):
    EXCHANGE_OFFICIAL = "EXCHANGE_OFFICIAL"
    REGULATORY_OR_AUTHORITATIVE_SOURCE = "REGULATORY_OR_AUTHORITATIVE_SOURCE"
    APPROVED_VENDOR = "APPROVED_VENDOR"
    INTERNAL_CALCULATION = "INTERNAL_CALCULATION"
    MANUAL_VERIFIED = "MANUAL_VERIFIED"
    SYNTHETIC_SIMULATOR = "SYNTHETIC_SIMULATOR"
    UNKNOWN = "UNKNOWN"


class PriceBasis(str, enum.Enum):
    RAW = "RAW"
    SPLIT_ADJUSTED = "SPLIT_ADJUSTED"
    DIVIDEND_ADJUSTED = "DIVIDEND_ADJUSTED"
    CORPORATE_ACTION_ADJUSTED = "CORPORATE_ACTION_ADJUSTED"
    TOTAL_RETURN_ADJUSTED = "TOTAL_RETURN_ADJUSTED"
    OTHER_APPROVED_ADJUSTMENT = "OTHER_APPROVED_ADJUSTMENT"
    UNKNOWN = "UNKNOWN"


class CurrencyBasis(str, enum.Enum):
    NATIVE_CURRENCY = "NATIVE_CURRENCY"
    CONVERTED_CURRENCY = "CONVERTED_CURRENCY"
    UNKNOWN = "UNKNOWN"


class VerificationStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    VALIDATING = "VALIDATING"
    VERIFIED = "VERIFIED"
    APPROVED = "APPROVED"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"
    CONFLICTED = "CONFLICTED"


class ResolutionStatus(str, enum.Enum):
    RESOLVED = "RESOLVED"
    UNAVAILABLE = "UNAVAILABLE"
    PENDING_SOURCE = "PENDING_SOURCE"
    MULTIPLE_CANDIDATES = "MULTIPLE_CANDIDATES"
    CONFLICTED = "CONFLICTED"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class PriceReferenceObservation(Base):
    """
    Authoritative reference-price observation entity.
    Stores immutable raw or transformed reference prices with full provenance.
    """
    __tablename__ = "price_reference_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    price_reference_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m04_instruments.instrument_id"), nullable=False, index=True
    )
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    exchange_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    market_segment: Mapped[str] = mapped_column(String(64), default="EQUITY_CASH", nullable=False)
    trading_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    reference_type: Mapped[PriceReferenceType] = mapped_column(
        SAEnum(PriceReferenceType, native_enum=False), nullable=False, index=True
    )
    price_value: Mapped[Numeric] = mapped_column(Numeric(18, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    quotation_unit: Mapped[str] = mapped_column(String(32), default="PER_SHARE", nullable=False)
    
    price_basis: Mapped[PriceBasis] = mapped_column(
        SAEnum(PriceBasis, native_enum=False), default=PriceBasis.RAW, nullable=False
    )
    currency_basis: Mapped[CurrencyBasis] = mapped_column(
        SAEnum(CurrencyBasis, native_enum=False), default=CurrencyBasis.NATIVE_CURRENCY, nullable=False
    )
    price_origin: Mapped[PriceOrigin] = mapped_column(
        SAEnum(PriceOrigin, native_enum=False), default=PriceOrigin.EXCHANGE_OFFICIAL, nullable=False
    )
    
    source_name: Mapped[str] = mapped_column(String(64), nullable=False, default="EXCHANGE_FEED")
    source_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus, native_enum=False), default=VerificationStatus.VERIFIED, nullable=False
    )
    
    # Versioning & audit
    observation_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    superseded_by_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    publication_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    retrieved_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class PreviousCloseResolution(Base):
    """
    Session-aware previous-close resolution record.
    Tracks which prior official close applies to a target trading session.
    """
    __tablename__ = "previous_close_resolutions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resolution_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m04_instruments.instrument_id"), nullable=False, index=True
    )
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    exchange_code: Mapped[str] = mapped_column(String(32), nullable=False)
    
    target_trading_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    previous_trading_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_price_reference_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("price_reference_observations.price_reference_id"), nullable=False
    )
    resolved_price_value: Mapped[Numeric] = mapped_column(Numeric(18, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    price_basis: Mapped[PriceBasis] = mapped_column(
        SAEnum(PriceBasis, native_enum=False), default=PriceBasis.RAW, nullable=False
    )
    
    calendar_version: Mapped[str] = mapped_column(String(32), default="v1.0", nullable=False)
    selection_policy: Mapped[str] = mapped_column(String(64), default="OFFICIAL_EXCHANGE_CLOSE_PREFERRED", nullable=False)
    resolution_status: Mapped[ResolutionStatus] = mapped_column(
        SAEnum(ResolutionStatus, native_enum=False), default=ResolutionStatus.RESOLVED, nullable=False
    )
    resolved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PriceBasisMetadata(Base):
    """
    Stores lineage linking an adjusted price back to M04.03 corporate action events.
    """
    __tablename__ = "price_basis_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    adjusted_price_reference_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("price_reference_observations.price_reference_id"), unique=True, nullable=False
    )
    original_price_reference_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("price_reference_observations.price_reference_id"), nullable=False
    )
    adjustment_basis: Mapped[PriceBasis] = mapped_column(
        SAEnum(PriceBasis, native_enum=False), nullable=False
    )
    adjustment_run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    cumulative_price_factor: Mapped[Numeric] = mapped_column(Numeric(18, 12), nullable=False)
    event_ids: Mapped[str] = mapped_column(Text, nullable=False)  # Comma-separated or JSON list
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PriceCurrencyConversion(Base):
    """
    Stores lineage linking a currency-converted price to its source price and FX rate.
    """
    __tablename__ = "price_currency_conversions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    converted_price_reference_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("price_reference_observations.price_reference_id"), unique=True, nullable=False
    )
    original_price_reference_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("price_reference_observations.price_reference_id"), nullable=False
    )
    source_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    target_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    fx_rate: Mapped[Numeric] = mapped_column(Numeric(18, 8), nullable=False)
    fx_pair: Mapped[str] = mapped_column(String(16), nullable=False) # e.g. "USD/INR"
    conversion_direction: Mapped[str] = mapped_column(String(32), default="SOURCE_TO_TARGET", nullable=False)
    fx_source: Mapped[str] = mapped_column(String(64), default="CENTRAL_BANK_REFERENCE", nullable=False)
    conversion_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
