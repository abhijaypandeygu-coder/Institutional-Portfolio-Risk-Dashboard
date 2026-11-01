"""
SQLAlchemy 2.x Database Models for M06.06 Concentration Analytics.

Implements concentration results, individual ranked contributors, concentration histories,
point-to-point / rolling comparisons, and configurable concentration threshold policies.
"""

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    String, Integer, BigInteger, DateTime, Numeric, JSON, Boolean, Text, Index, UniqueConstraint, ForeignKey, Enum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ConcentrationGroupingDimension(str, enum.Enum):
    INSTRUMENT = "INSTRUMENT"
    ISSUER = "ISSUER"
    SECTOR = "SECTOR"
    INDUSTRY = "INDUSTRY"
    COUNTRY = "COUNTRY"
    REGION = "REGION"
    PORTFOLIO = "PORTFOLIO"
    CUSTOM_GROUP = "CUSTOM_GROUP"


class ConcentrationExposureBasis(str, enum.Enum):
    GROSS_EXPOSURE = "GROSS_EXPOSURE"
    LONG_EXPOSURE = "LONG_EXPOSURE"
    SHORT_EXPOSURE = "SHORT_EXPOSURE"
    ABSOLUTE_NET_EXPOSURE = "ABSOLUTE_NET_EXPOSURE"
    NAV_WEIGHTED_EXPOSURE = "NAV_WEIGHTED_EXPOSURE"


class ConcentrationCalculationStatus(str, enum.Enum):
    CALCULATED = "CALCULATED"
    ZERO_EXPOSURE = "ZERO_EXPOSURE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    INSUFFICIENT_GROUPS = "INSUFFICIENT_GROUPS"
    INCOMPLETE_UNIVERSE = "INCOMPLETE_UNIVERSE"
    INVALID_WEIGHTS = "INVALID_WEIGHTS"
    CLASSIFICATION_INCOMPLETE = "CLASSIFICATION_INCOMPLETE"
    DENOMINATOR_UNAVAILABLE = "DENOMINATOR_UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ConcentrationTrendStatus(str, enum.Enum):
    INCREASING = "INCREASING"
    DECREASING = "DECREASING"
    STABLE = "STABLE"
    VOLATILE = "VOLATILE"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    INCOMPARABLE = "INCOMPARABLE"
    INCOMPLETE_DATA = "INCOMPLETE_DATA"


class ConcentrationInterpretationLevel(str, enum.Enum):
    NORMAL = "NORMAL"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNAVAILABLE = "UNAVAILABLE"


class ConcentrationResult(Base):
    """
    Primary concentration calculation record for a portfolio/group snapshot.
    Stores aggregate concentration metrics (CR1-CR20, HHI decimal & 10k, effective groups, coverage).
    """
    __tablename__ = "m06_concentration_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    result_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"CONC_{uuid.uuid4().hex[:12].upper()}"
    )
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    portfolio_group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    grouping_dimension: Mapped[ConcentrationGroupingDimension] = mapped_column(
        Enum(ConcentrationGroupingDimension, name="concentration_grouping_dimension_enum", native_enum=False),
        nullable=False,
        index=True
    )
    exposure_basis: Mapped[ConcentrationExposureBasis] = mapped_column(
        Enum(ConcentrationExposureBasis, name="concentration_exposure_basis_enum", native_enum=False),
        nullable=False,
        index=True
    )
    weighting_methodology: Mapped[str] = mapped_column(String(64), default="NORMALIZED_POSITIVE_SHARES", nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)

    total_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    denominator_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    eligible_group_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    top_1_ratio: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    top_3_ratio: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    top_5_ratio: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    top_10_ratio: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    top_20_ratio: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)

    hhi_decimal: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    hhi_10000: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    effective_number_of_groups: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)

    classification_coverage: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1.0"), nullable=False)
    unknown_exposure_share: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)

    calculation_status: Mapped[ConcentrationCalculationStatus] = mapped_column(
        Enum(ConcentrationCalculationStatus, name="concentration_calc_status_enum", native_enum=False),
        default=ConcentrationCalculationStatus.CALCULATED,
        nullable=False,
        index=True
    )
    calculation_version: Mapped[str] = mapped_column(String(32), default="v1.0", nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    contributors: Mapped[List["ConcentrationContributor"]] = relationship(
        "ConcentrationContributor", back_populates="concentration_result", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_conc_result_port_dim_basis", "portfolio_id", "grouping_dimension", "exposure_basis"),
        Index("ix_conc_result_grp_dim_basis", "portfolio_group_id", "grouping_dimension", "exposure_basis"),
    )


class ConcentrationContributor(Base):
    """
    Ranked individual contributor (holding, issuer, sector, country, etc.) within a concentration result.
    """
    __tablename__ = "m06_concentration_contributors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contributor_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"CONTR_{uuid.uuid4().hex[:12].upper()}"
    )
    result_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m06_concentration_results.result_id", ondelete="CASCADE"), nullable=False, index=True
    )
    group_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    group_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    group_name: Mapped[str] = mapped_column(String(256), nullable=False)
    grouping_dimension: Mapped[ConcentrationGroupingDimension] = mapped_column(
        Enum(ConcentrationGroupingDimension, name="concentration_grouping_dimension_enum", native_enum=False),
        nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    long_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    short_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    net_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    gross_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)

    exposure_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    exposure_share: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    cumulative_share: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)

    source_exposure_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    classification_status: Mapped[str] = mapped_column(String(32), default="CLASSIFIED", nullable=False)

    concentration_result: Mapped["ConcentrationResult"] = relationship("ConcentrationResult", back_populates="contributors")

    __table_args__ = (
        Index("ix_contr_result_rank", "result_id", "rank"),
    )


class ConcentrationComparison(Base):
    """
    Differential comparison of concentration metrics between two calculation runs or historical snapshots.
    """
    __tablename__ = "m06_concentration_comparisons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comparison_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"CCMP_{uuid.uuid4().hex[:12].upper()}"
    )
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    portfolio_group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    current_result_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    prior_result_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    grouping_dimension: Mapped[ConcentrationGroupingDimension] = mapped_column(
        Enum(ConcentrationGroupingDimension, name="concentration_grouping_dimension_enum", native_enum=False),
        nullable=False
    )
    exposure_basis: Mapped[ConcentrationExposureBasis] = mapped_column(
        Enum(ConcentrationExposureBasis, name="concentration_exposure_basis_enum", native_enum=False),
        nullable=False
    )
    weighting_methodology: Mapped[str] = mapped_column(String(64), default="NORMALIZED_POSITIVE_SHARES", nullable=False)

    current_hhi_decimal: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    prior_hhi_decimal: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    hhi_decimal_change: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)

    current_hhi_10000: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    prior_hhi_10000: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    hhi_10000_change: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)

    current_cr5: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    prior_cr5: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    cr5_change_pp: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)

    current_cr10: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    prior_cr10: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    cr10_change_pp: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)

    current_effective_groups: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    prior_effective_groups: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    effective_groups_change: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)

    trend_status: Mapped[ConcentrationTrendStatus] = mapped_column(
        Enum(ConcentrationTrendStatus, name="concentration_trend_status_enum", native_enum=False),
        default=ConcentrationTrendStatus.STABLE,
        nullable=False
    )
    comparability_status: Mapped[str] = mapped_column(String(32), default="COMPARABLE", nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(32), default="v1.0", nullable=False)
    compared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ConcentrationPolicy(Base):
    """
    Configurable concentration policy with thresholds for CR, HHI, and effective groups.
    """
    __tablename__ = "m06_concentration_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"CPOL_{uuid.uuid4().hex[:12].upper()}"
    )
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    portfolio_group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    grouping_dimension: Mapped[ConcentrationGroupingDimension] = mapped_column(
        Enum(ConcentrationGroupingDimension, name="concentration_grouping_dimension_enum", native_enum=False),
        nullable=False
    )
    exposure_basis: Mapped[ConcentrationExposureBasis] = mapped_column(
        Enum(ConcentrationExposureBasis, name="concentration_exposure_basis_enum", native_enum=False),
        nullable=False
    )

    # Threshold limits (e.g. CR5 max 50%, HHI max 1800, min effective groups 10)
    top_1_warning: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.20"), nullable=False)
    top_1_critical: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.30"), nullable=False)

    cr5_warning: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.50"), nullable=False)
    cr5_critical: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.70"), nullable=False)

    hhi_10000_warning: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1500.0"), nullable=False)
    hhi_10000_critical: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("2500.0"), nullable=False)

    min_effective_groups_warning: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("8.0"), nullable=False)
    min_effective_groups_critical: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("4.0"), nullable=False)

    interpretation_policy: Mapped[str] = mapped_column(String(64), default="STANDARD_INSTITUTIONAL", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(32), default="v1.0", nullable=False)

    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
