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


class NamespaceType(str, enum.Enum):
    EXCHANGE_SYMBOL = "EXCHANGE_SYMBOL"
    EXCHANGE_SECURITY_CODE = "EXCHANGE_SECURITY_CODE"
    EXCHANGE_LISTING_CODE = "EXCHANGE_LISTING_CODE"
    VENDOR_SYMBOL = "VENDOR_SYMBOL"
    VENDOR_INSTRUMENT_ID = "VENDOR_INSTRUMENT_ID"
    BROKER_SYMBOL = "BROKER_SYMBOL"
    BROKER_SECURITY_ID = "BROKER_SECURITY_ID"
    ISIN = "ISIN"
    OTHER = "OTHER"


class MappingTargetType(str, enum.Enum):
    INSTRUMENT_LEVEL = "INSTRUMENT_LEVEL"
    LISTING_LEVEL = "LISTING_LEVEL"


class MappingStatus(str, enum.Enum):
    APPROVED_FOR_INGESTION = "APPROVED_FOR_INGESTION"
    APPROVED_FOR_HISTORICAL_LOOKUP = "APPROVED_FOR_HISTORICAL_LOOKUP"
    PENDING_REVIEW = "PENDING_REVIEW"
    RESTRICTED = "RESTRICTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class VerificationStatus(str, enum.Enum):
    VERIFIED = "VERIFIED"
    APPROVED = "APPROVED"
    UNVERIFIED = "UNVERIFIED"
    CONFLICTED = "CONFLICTED"
    REJECTED = "REJECTED"


class ResolutionMatchingLevel(str, enum.Enum):
    EXACT_VERIFIED_MATCH = "EXACT_VERIFIED_MATCH"
    NORMALIZED_MATCH = "NORMALIZED_MATCH"
    HISTORICAL_MATCH = "HISTORICAL_MATCH"
    AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"
    CONFLICTED_MATCH = "CONFLICTED_MATCH"
    NO_MATCH = "NO_MATCH"
    EXPIRED_MAPPING = "EXPIRED_MAPPING"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"


class IdentifierNamespace(Base):
    """
    Registry entity for external identifier namespaces (e.g. NSE_TICKER, BSE_CODE, ALPHA_VANTAGE_SYMBOL).
    """
    __tablename__ = "identifier_namespaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    namespace_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    namespace_name: Mapped[str] = mapped_column(String(128), nullable=False)
    namespace_type: Mapped[NamespaceType] = mapped_column(
        SAEnum(NamespaceType, native_enum=False), nullable=False
    )
    provider_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    exchange_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    case_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    strip_suffix: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    mappings: Mapped[List["ExternalIdentifierMapping"]] = relationship(
        "ExternalIdentifierMapping", back_populates="namespace", cascade="all, delete-orphan"
    )


class ExternalIdentifierMapping(Base):
    """
    Authoritative external identifier to canonical identity mapping.
    Links external codes to M04.01 instrument_id and/or listing_id with bitemporal dates.
    """
    __tablename__ = "external_identifier_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mapping_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    namespace_code: Mapped[str] = mapped_column(
        String(64), ForeignKey("identifier_namespaces.namespace_code", ondelete="CASCADE"), nullable=False, index=True
    )
    
    external_identifier_raw: Mapped[str] = mapped_column(String(128), nullable=False)
    external_identifier_normalized: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    
    target_type: Mapped[MappingTargetType] = mapped_column(
        SAEnum(MappingTargetType, native_enum=False), default=MappingTargetType.LISTING_LEVEL, nullable=False
    )
    instrument_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m04_instruments.instrument_id"), nullable=False, index=True
    )
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    exchange_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    
    mapping_status: Mapped[MappingStatus] = mapped_column(
        SAEnum(MappingStatus, native_enum=False), default=MappingStatus.APPROVED_FOR_INGESTION, nullable=False
    )
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus, native_enum=False), default=VerificationStatus.VERIFIED, nullable=False
    )
    
    # Bitemporal effective dates
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    mapping_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    source_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    namespace: Mapped["IdentifierNamespace"] = relationship("IdentifierNamespace", back_populates="mappings")


class MappingConflictRecord(Base):
    """
    Tracks ambiguous or conflicting mappings requiring investigator review.
    """
    __tablename__ = "mapping_conflict_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conflict_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    namespace_code: Mapped[str] = mapped_column(String(64), nullable=False)
    identifier_normalized: Mapped[str] = mapped_column(String(128), nullable=False)
    conflict_type: Mapped[str] = mapped_column(String(64), nullable=False) # MULTIPLE_TARGETS, OVERLAPPING_DATES
    candidate_instrument_ids: Mapped[str] = mapped_column(Text, nullable=False) # JSON or comma-separated
    reason: Mapped[str] = mapped_column(String(256), nullable=False)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
