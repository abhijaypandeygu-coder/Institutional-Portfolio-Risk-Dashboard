"""
M06.05 Geographic Exposure - SQLAlchemy 2.x Database Models.
Tracks geographic exposure calculation runs, country & regional aggregated results,
unknown residual allocations, and historical geographic comparisons.
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


class GeographicLevel(str, enum.Enum):
    COUNTRY = "COUNTRY"
    REGION = "REGION"
    SUBREGION = "SUBREGION"


class GeographicCoverageStatus(str, enum.Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    CRITICAL_GAP = "CRITICAL_GAP"


class GeographicExposureCalculationRun(Base):
    __tablename__ = "m06_geographic_exposure_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"GEO-RUN-{uuid.uuid4().hex[:12].upper()}"
    )
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    portfolio_group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(32), default="PORTFOLIO", nullable=False)
    snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    knowledge_as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    geographic_attribute: Mapped[str] = mapped_column(String(32), default="ISSUER_DOMICILE", nullable=False)
    taxonomy_scheme_code: Mapped[str] = mapped_column(String(32), default="STANDARD", nullable=False)

    nav: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    total_long_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    total_short_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    total_net_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    total_gross_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)

    classified_gross_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    unknown_gross_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    coverage_ratio: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1.000000"), nullable=False)
    coverage_status: Mapped[str] = mapped_column(String(32), default=GeographicCoverageStatus.COMPLETE.value, nullable=False)

    dominant_country_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    dominant_region_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    calculation_version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class CountryExposureResult(Base):
    __tablename__ = "m06_country_exposure_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("m06_geographic_exposure_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    country_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True) # ISO-3 or "UNKNOWN_COUNTRY"
    country_name: Mapped[str] = mapped_column(String(128), nullable=False)
    iso_alpha2: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    region_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    region_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    long_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    short_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    net_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    gross_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)

    long_nav_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    short_nav_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    net_nav_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    gross_nav_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)

    gross_contribution_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    long_contribution_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    short_contribution_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)

    instrument_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class RegionExposureResult(Base):
    __tablename__ = "m06_region_exposure_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("m06_geographic_exposure_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    region_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    region_code: Mapped[str] = mapped_column(String(32), nullable=False)
    region_name: Mapped[str] = mapped_column(String(128), nullable=False)
    taxonomy_scheme_code: Mapped[str] = mapped_column(String(32), default="STANDARD", nullable=False)
    hierarchy_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    long_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    short_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    net_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    gross_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)

    long_nav_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    short_nav_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    net_nav_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    gross_nav_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)

    gross_contribution_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    instrument_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class UnknownGeographicExposure(Base):
    __tablename__ = "m06_unknown_geographic_exposures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("m06_geographic_exposure_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False) # UNMAPPED, AMBIGUOUS, UNKNOWN_ISSUER
    unmapped_gross_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unmapped_weight: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)


class GeographicExposureComparison(Base):
    __tablename__ = "m06_geographic_exposure_comparisons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    current_snapshot_id: Mapped[str] = mapped_column(String(64), nullable=False)
    prior_snapshot_id: Mapped[str] = mapped_column(String(64), nullable=False)
    geographic_level: Mapped[str] = mapped_column(String(32), default=GeographicLevel.COUNTRY.value, nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_name: Mapped[str] = mapped_column(String(128), nullable=False)

    current_gross_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    prior_gross_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    gross_exposure_change: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    gross_percentage_change: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    nav_weight_change_pp: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="UNCHANGED", nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
