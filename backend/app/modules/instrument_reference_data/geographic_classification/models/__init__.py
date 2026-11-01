"""
M04 Geographic Reference Data - SQLAlchemy 2.x Database Models.
Maintains canonical countries, regions, country-to-region assignments,
issuer geographic assignments (domicile/headquarters/economic), and revenue geography allocations.
"""

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    String, Integer, BigInteger, DateTime, Numeric, JSON, Boolean, Text, Index, UniqueConstraint, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GeographicAttributeType(str, enum.Enum):
    ISSUER_DOMICILE = "ISSUER_DOMICILE"
    ISSUER_HEADQUARTERS = "ISSUER_HEADQUARTERS"
    PRIMARY_ECONOMIC_DOMICILE = "PRIMARY_ECONOMIC_DOMICILE"
    REVENUE_GEOGRAPHY = "REVENUE_GEOGRAPHY"
    LISTING_COUNTRY = "LISTING_COUNTRY"


class GeographicMappingStatus(str, enum.Enum):
    MAPPED = "MAPPED"
    MULTI_COUNTRY_MAPPED = "MULTI_COUNTRY_MAPPED"
    UNMAPPED = "UNMAPPED"
    UNKNOWN_ISSUER = "UNKNOWN_ISSUER"
    UNKNOWN_COUNTRY = "UNKNOWN_COUNTRY"
    UNKNOWN_REGION = "UNKNOWN_REGION"
    AMBIGUOUS = "AMBIGUOUS"
    CONFLICTING_ASSIGNMENT = "CONFLICTING_ASSIGNMENT"
    UNVERIFIED = "UNVERIFIED"
    PENDING_REVIEW = "PENDING_REVIEW"
    EXPIRED = "EXPIRED"
    INVALID_ASSIGNMENT = "INVALID_ASSIGNMENT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class GeographicCountry(Base):
    __tablename__ = "m04_geographic_countries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_id: Mapped[str] = mapped_column(String(3), unique=True, nullable=False, index=True) # ISO-3 alpha code e.g. USA, IND, GBR
    iso_alpha2: Mapped[str] = mapped_column(String(2), unique=True, nullable=False, index=True) # e.g. US, IN, GB
    numeric_code: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    canonical_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class GeographicRegion(Base):
    __tablename__ = "m04_geographic_regions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    region_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True) # e.g. REG_NORTH_AMERICA, REG_ASIA
    region_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True) # e.g. NA, ASIA, EMEA
    region_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    taxonomy_scheme_code: Mapped[str] = mapped_column(String(32), default="STANDARD", nullable=False, index=True)
    taxonomy_version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    parent_region_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    hierarchy_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False) # 1: Macro-Region, 2: Region, 3: Subregion

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class CountryRegionAssignment(Base):
    __tablename__ = "m04_country_region_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_id: Mapped[str] = mapped_column(String(3), ForeignKey("m04_geographic_countries.country_id", ondelete="CASCADE"), nullable=False, index=True)
    region_id: Mapped[str] = mapped_column(String(64), ForeignKey("m04_geographic_regions.region_id", ondelete="CASCADE"), nullable=False, index=True)
    allocation_weight: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1.000000"), nullable=False)
    taxonomy_scheme_code: Mapped[str] = mapped_column(String(32), default="STANDARD", nullable=False, index=True)
    taxonomy_version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)

    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(32), default="VERIFIED", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class IssuerGeographicAssignment(Base):
    __tablename__ = "m04_issuer_geographic_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True) # maps canonical instrument
    issuer_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    attribute_type: Mapped[str] = mapped_column(String(32), default=GeographicAttributeType.ISSUER_DOMICILE.value, nullable=False, index=True)
    country_id: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    allocation_weight: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1.000000"), nullable=False) # 1.0 = 100%

    source_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(32), default="VERIFIED", nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class IssuerRevenueGeography(Base):
    __tablename__ = "m04_issuer_revenue_geography"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    issuer_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    country_id: Mapped[Optional[str]] = mapped_column(String(3), nullable=True, index=True)
    region_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    geographic_segment_code: Mapped[str] = mapped_column(String(64), nullable=False)

    fiscal_period: Mapped[str] = mapped_column(String(32), default="FY2024", nullable=False)
    fiscal_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revenue_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    revenue_currency: Mapped[Optional[str]] = mapped_column(String(3), default="USD", nullable=True)
    revenue_percentage: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False) # e.g. 0.40 for 40%
    allocation_weight: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    source_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(32), default="VERIFIED", nullable=False)
    filing_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
