"""
M04.01 Instrument Master - Database Models (SQLAlchemy 2.x).
Implements canonical instruments, venue listings, identifiers, source provenance,
attribute version history, import batches, import records, identity reviews, and audit events.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    String, Integer, BigInteger, DateTime, Numeric, JSON, Boolean, Text, Index, UniqueConstraint, ForeignKey
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# 1. Canonical Instrument Master
class Instrument(Base):
    __tablename__ = "m04_instruments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"INST_{uuid.uuid4().hex[:12].upper()}"
    )
    canonical_name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    short_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    instrument_type: Mapped[str] = mapped_column(String(64), default="COMMON_STOCK", nullable=False, index=True)
    asset_class: Mapped[str] = mapped_column(String(32), default="EQUITY", nullable=False)
    security_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    issuer_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, index=True)
    isin: Mapped[Optional[str]] = mapped_column(String(12), unique=True, nullable=True, index=True)
    country_of_issue: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)  # ISO 3166-1 alpha-3
    issue_currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)  # ISO 4217
    primary_market_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # e.g. NSE, NASDAQ

    lifecycle_status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False, index=True)
    verification_status: Mapped[str] = mapped_column(String(32), default="VERIFIED", nullable=False, index=True)
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


# 2. Exchange-Specific Listings
class InstrumentListing(Base):
    __tablename__ = "m04_instrument_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listing_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"LST_{uuid.uuid4().hex[:12].upper()}"
    )
    instrument_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m04_instruments.instrument_id", ondelete="CASCADE"), nullable=False, index=True
    )
    market_id: Mapped[str] = mapped_column(String(32), nullable=False)  # IN, US
    exchange_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # NSE, BSE, NYSE, NASDAQ
    exchange_symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # RELIANCE, AAPL, 500325
    exchange_security_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    trading_currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    listing_type: Mapped[str] = mapped_column(String(32), default="PRIMARY_LISTING", nullable=False)
    listing_status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False, index=True)
    is_primary_listing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(32), default="VERIFIED", nullable=False)
    source_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("exchange_id", "exchange_symbol", "effective_to", name="uq_exchange_symbol_period"),
    )


# 3. Basic Security Identifiers (SEDOL, CUSIP, RIC, etc.)
class InstrumentIdentifier(Base):
    __tablename__ = "m04_instrument_identifiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m04_instruments.instrument_id", ondelete="CASCADE"), nullable=False, index=True
    )
    listing_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("m04_instrument_listings.listing_id", ondelete="CASCADE"), nullable=True, index=True
    )
    identifier_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # ISIN, CUSIP, SEDOL, RIC, BLOOMBERG_FIGI
    identifier_value: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(32), default="VERIFIED", nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


# 4. Source Provenance Records
class InstrumentSource(Base):
    __tablename__ = "m04_instrument_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m04_instruments.instrument_id", ondelete="CASCADE"), nullable=False, index=True
    )
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_name: Mapped[str] = mapped_column(String(64), nullable=False)  # NSE_EXCHANGE_MASTER, ALPHA_VANTAGE, SEC_EDGAR
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)  # EXCHANGE_OFFICIAL, VENDOR_FEED, MANUAL_ADMIN
    source_record_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    source_file_reference: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    import_batch_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    verification_status: Mapped[str] = mapped_column(String(32), default="UNVERIFIED", nullable=False)


# 5. Effective-Dated Attribute Version History
class InstrumentAttributeHistory(Base):
    __tablename__ = "m04_instrument_attribute_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m04_instruments.instrument_id", ondelete="CASCADE"), nullable=False, index=True
    )
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    field_name: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g. canonical_name, isin, exchange_symbol
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[str] = mapped_column(Text, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(64), nullable=False)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    record_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


# 6. Import Batches
class InstrumentImportBatch(Base):
    __tablename__ = "m04_instrument_import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_reference: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"IMP_{uuid.uuid4().hex[:12].upper()}"
    )
    source_name: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), default="CSV", nullable=False)
    file_reference: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    import_status: Mapped[str] = mapped_column(String(32), default="RECEIVED", nullable=False, index=True)

    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invalid_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_candidates: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)


# 7. Import Records (Per-Row Outcomes)
class InstrumentImportRecord(Base):
    __tablename__ = "m04_instrument_import_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_reference: Mapped[str] = mapped_column(
        String(64), ForeignKey("m04_instrument_import_batches.batch_reference", ondelete="CASCADE"), nullable=False, index=True
    )
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parsed_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(32), default="VALID", nullable=False)
    match_status: Mapped[str] = mapped_column(String(32), default="NO_MATCH", nullable=False)
    resolved_instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    resolved_listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


# 8. Ambiguous Identity Reviews
class InstrumentIdentityReview(Base):
    __tablename__ = "m04_instrument_identity_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"REV_{uuid.uuid4().hex[:12].upper()}"
    )
    candidate_instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    candidate_listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    match_classification: Mapped[str] = mapped_column(String(32), default="POSSIBLE_MATCH", nullable=False)
    evidence: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), default="PENDING_REVIEW", nullable=False, index=True)

    reviewed_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_decision: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    review_reason: Mapped[Optional[Text]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


# 9. Audit Events
class InstrumentAuditEvent(Base):
    __tablename__ = "m04_instrument_audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audit_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=lambda: f"AUD_{uuid.uuid4().hex[:12].upper()}"
    )
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    previous_state: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    new_state: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

