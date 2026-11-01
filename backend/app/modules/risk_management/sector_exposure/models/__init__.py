"""
M06.03 Sector Exposure Models.
Database models for sector policies, calculation runs, sector/industry results,
unclassified holdings, classification coverage, benchmarks, and active relative weights.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String,
    Numeric,
    DateTime,
    Boolean,
    JSON,
    ForeignKey,
    Index,
    UniqueConstraint,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SectorWeightBasis(str, Enum):
    NAV = "NAV"                                      # Relative to portfolio Net Asset Value
    INVESTED_EQUITY = "INVESTED_EQUITY"              # Relative to total eligible Long Equity Market Value
    TOTAL_GROSS = "TOTAL_GROSS"                      # Relative to total Gross Exposure


class ClassificationCoverageStatus(str, Enum):
    COMPLETE = "COMPLETE"
    MOSTLY_COMPLETE = "MOSTLY_COMPLETE"
    PARTIAL = "PARTIAL"
    INCOMPLETE = "INCOMPLETE"
    UNAVAILABLE = "UNAVAILABLE"


class ActiveWeightStatus(str, Enum):
    OVERWEIGHT = "OVERWEIGHT"
    UNDERWEIGHT = "UNDERWEIGHT"
    APPROX_NEUTRAL = "APPROX_NEUTRAL"
    UNAVAILABLE = "UNAVAILABLE"
    INCOMPARABLE = "INCOMPARABLE"


class SectorClassificationStatus(str, Enum):
    CLASSIFIED = "CLASSIFIED"
    MISSING_CLASSIFICATION = "MISSING_CLASSIFICATION"
    UNMAPPED_INSTRUMENT = "UNMAPPED_INSTRUMENT"
    AMBIGUOUS_CLASSIFICATION = "AMBIGUOUS_CLASSIFICATION"
    UNVERIFIED_CLASSIFICATION = "UNVERIFIED_CLASSIFICATION"
    EXPIRED_CLASSIFICATION = "EXPIRED_CLASSIFICATION"
    PENDING_REVIEW = "PENDING_REVIEW"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class SectorExposurePolicy(Base):
    """
    Configured policy for sector/industry aggregation, weight bases, and active thresholds.
    """
    __tablename__ = "m06_sector_exposure_policies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_name: Mapped[str] = mapped_column(String(128), nullable=False)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    
    # Classification Scheme Configuration (References M04.02)
    classification_scheme_id: Mapped[Optional[int]] = mapped_column(Numeric(10, 0), nullable=True)
    classification_scheme_code: Mapped[str] = mapped_column(String(64), default="GICS", nullable=False)
    classification_version_code: Mapped[Optional[str]] = mapped_column(String(32), default="2023", nullable=True)
    
    # Weight & Denominator configuration
    primary_weight_basis: Mapped[str] = mapped_column(String(32), default=SectorWeightBasis.NAV.value, nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    
    # Benchmark relative parameters
    default_benchmark_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    active_weight_neutrality_threshold: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), default=Decimal("0.005000"), nullable=False # e.g. 0.50% (0.005)
    )

    policy_version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class SectorExposureCalculationRun(Base):
    """
    Audit execution record for a Sector Exposure calculation run.
    """
    __tablename__ = "m06_sector_exposure_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    calculation_scope: Mapped[str] = mapped_column(String(32), nullable=False) # PORTFOLIO or PORTFOLIO_GROUP
    effective_as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    knowledge_as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    classification_scheme_code: Mapped[str] = mapped_column(String(64), nullable=False)
    classification_version_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    benchmark_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reporting_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    weight_basis: Mapped[str] = mapped_column(String(32), nullable=False)
    input_manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class SectorExposureResult(Base):
    """
    Aggregated sector-level long, short, gross, net exposures and weights.
    """
    __tablename__ = "m06_sector_exposure_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    calculation_run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m06_sector_exposure_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sector_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sector_name: Mapped[str] = mapped_column(String(128), nullable=False)
    classification_scheme_code: Mapped[str] = mapped_column(String(64), nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(3), nullable=False)

    # Core exposures
    long_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    absolute_short_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    gross_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    net_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    # Calculated weights
    long_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    short_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    gross_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    net_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    allocation_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)

    contributing_instrument_count: Mapped[int] = mapped_column(Numeric(10, 0), default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class IndustryExposureResult(Base):
    """
    Granular industry-level aggregation within parent sectors.
    """
    __tablename__ = "m06_industry_exposure_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    calculation_run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m06_sector_exposure_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sector_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    industry_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    industry_name: Mapped[str] = mapped_column(String(128), nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(3), nullable=False)

    long_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    absolute_short_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    gross_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    net_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    long_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    net_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    parent_sector_contribution_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)

    contributing_instrument_count: Mapped[int] = mapped_column(Numeric(10, 0), default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class UnclassifiedExposureResult(Base):
    """
    Separately tracked unclassified, unmapped, or ambiguous holdings.
    """
    __tablename__ = "m06_unclassified_exposure_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    calculation_run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m06_sector_exposure_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    classification_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_sector_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    long_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    absolute_short_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    gross_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    net_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    allocation_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)

    contributing_instrument_count: Mapped[int] = mapped_column(Numeric(10, 0), default=0, nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ClassificationCoverage(Base):
    """
    Completeness and data-quality coverage statistics for the exposure calculation.
    """
    __tablename__ = "m06_sector_classification_coverages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    calculation_run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m06_sector_exposure_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    total_positions: Mapped[int] = mapped_column(Numeric(10, 0), nullable=False)
    classified_positions: Mapped[int] = mapped_column(Numeric(10, 0), nullable=False)
    unclassified_positions: Mapped[int] = mapped_column(Numeric(10, 0), nullable=False)

    classified_gross_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unclassified_gross_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    gross_value_coverage_pct: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    position_count_coverage_pct: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)

    coverage_status: Mapped[str] = mapped_column(String(32), default=ClassificationCoverageStatus.COMPLETE.value, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class BenchmarkSectorComposition(Base):
    """
    Benchmark sector compositions and weights for relative sector comparison.
    """
    __tablename__ = "m06_benchmark_sector_compositions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    benchmark_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    benchmark_name: Mapped[str] = mapped_column(String(128), nullable=False)
    sector_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sector_name: Mapped[str] = mapped_column(String(128), nullable=False)
    classification_scheme_code: Mapped[str] = mapped_column(String(64), nullable=False)
    benchmark_weight: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    effective_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    source_reference: Mapped[str] = mapped_column(String(128), default="AUTHORITATIVE_INDEX_PROVIDER", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class RelativeSectorExposureResult(Base):
    """
    Portfolio vs. Benchmark active sector weights and overweight/underweight classification.
    """
    __tablename__ = "m06_relative_sector_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    calculation_run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m06_sector_exposure_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    benchmark_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sector_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sector_name: Mapped[str] = mapped_column(String(128), nullable=False)

    portfolio_sector_weight: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    benchmark_sector_weight: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    active_sector_weight: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    active_weight_status: Mapped[str] = mapped_column(String(32), nullable=False)

    comparison_basis: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
