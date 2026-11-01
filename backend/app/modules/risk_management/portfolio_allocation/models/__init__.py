"""
SQLAlchemy 2.x Database Models for M06.07 Portfolio Allocation.

Includes:
- PortfolioAllocationResult: Top-level allocation run, NAV reconciliation, capital amounts.
- PortfolioAllocationComponent: Individual allocation entries (security, sector, country, cash).
- PortfolioAllocationTarget: Configurable effective-dated allocation targets by dimension/entity.
- PortfolioAllocationDrift: Calculated drift comparing actual weights against target or historical weights.
- PortfolioAllocationComparison: Point-to-point / historical snapshot allocation comparison.
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


class AllocationViewType(str, enum.Enum):
    NAV_CAPITAL_ALLOCATION = "NAV_CAPITAL_ALLOCATION"
    LONG_INVESTMENT_ALLOCATION = "LONG_INVESTMENT_ALLOCATION"
    GROSS_EXPOSURE_ALLOCATION = "GROSS_EXPOSURE_ALLOCATION"
    NET_EXPOSURE_ALLOCATION = "NET_EXPOSURE_ALLOCATION"
    AVAILABLE_CASH_ALLOCATION = "AVAILABLE_CASH_ALLOCATION"


class AllocationGroupingDimension(str, enum.Enum):
    SECURITY = "SECURITY"
    SECTOR = "SECTOR"
    INDUSTRY = "INDUSTRY"
    COUNTRY = "COUNTRY"
    REGION = "REGION"
    STRATEGY = "STRATEGY"
    SLEEVE = "SLEEVE"
    CASH = "CASH"


class AllocationReconciliationStatus(str, enum.Enum):
    RECONCILED = "RECONCILED"
    PARTIALLY_RECONCILED = "PARTIALLY_RECONCILED"
    UNRECONCILED = "UNRECONCILED"
    INCOMPLETE_DATA = "INCOMPLETE_DATA"
    NAV_UNAVAILABLE = "NAV_UNAVAILABLE"
    VALUATION_UNAVAILABLE = "VALUATION_UNAVAILABLE"
    CASH_DATA_UNAVAILABLE = "CASH_DATA_UNAVAILABLE"
    FX_UNAVAILABLE = "FX_UNAVAILABLE"


class AllocationDriftStatus(str, enum.Enum):
    WITHIN_TARGET = "WITHIN_TARGET"
    OVERWEIGHT = "OVERWEIGHT"
    UNDERWEIGHT = "UNDERWEIGHT"
    MATERIAL_DRIFT = "MATERIAL_DRIFT"
    UNPLANNED_ALLOCATION = "UNPLANNED_ALLOCATION"
    TARGET_UNAVAILABLE = "TARGET_UNAVAILABLE"
    COMPARISON_UNAVAILABLE = "COMPARISON_UNAVAILABLE"


class PortfolioAllocationResult(Base):
    """
    Primary portfolio allocation calculation record.
    Tracks authoritative NAV, security values, cash balances, reconciliation status, and residual.
    """
    __tablename__ = "m06_portfolio_allocation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    result_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"ALC_{uuid.uuid4().hex[:12].upper()}"
    )
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    portfolio_group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    allocation_view_type: Mapped[AllocationViewType] = mapped_column(
        Enum(AllocationViewType, name="allocation_view_type_enum", native_enum=False),
        default=AllocationViewType.NAV_CAPITAL_ALLOCATION,
        nullable=False,
        index=True
    )
    grouping_dimension: Mapped[AllocationGroupingDimension] = mapped_column(
        Enum(AllocationGroupingDimension, name="allocation_grouping_dimension_enum", native_enum=False),
        default=AllocationGroupingDimension.SECURITY,
        nullable=False,
        index=True
    )
    reporting_currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)

    # Core balance-sheet and capital values
    nav_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    total_long_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    total_short_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    net_security_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    gross_security_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)

    # Cash breakdown
    cash_nav_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    settled_cash_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    available_cash_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    restricted_cash_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)

    # Reconciliation and accounting residual
    other_nav_components: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    unallocated_nav_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    reconciliation_residual: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)

    reconciliation_status: Mapped[AllocationReconciliationStatus] = mapped_column(
        Enum(AllocationReconciliationStatus, name="allocation_reconciliation_status_enum", native_enum=False),
        default=AllocationReconciliationStatus.RECONCILED,
        nullable=False,
        index=True
    )
    data_completeness_status: Mapped[str] = mapped_column(String(32), default="COMPLETE", nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(32), default="v1.0", nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    components: Mapped[List["PortfolioAllocationComponent"]] = relationship(
        "PortfolioAllocationComponent", back_populates="allocation_result", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_alc_res_port_dim_view", "portfolio_id", "grouping_dimension", "allocation_view_type"),
        Index("ix_alc_res_grp_dim_view", "portfolio_group_id", "grouping_dimension", "allocation_view_type"),
    )


class PortfolioAllocationComponent(Base):
    """
    Individual allocation group component (security, sector, country, or cash bucket).
    Stores market values, signed NAV weights, normalized investment weights, and gross contribution weights.
    """
    __tablename__ = "m06_portfolio_allocation_components"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    component_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"ACOMP_{uuid.uuid4().hex[:12].upper()}"
    )
    result_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("m06_portfolio_allocation_results.result_id", ondelete="CASCADE"), nullable=False, index=True
    )
    grouping_dimension: Mapped[AllocationGroupingDimension] = mapped_column(
        Enum(AllocationGroupingDimension, name="allocation_grouping_dimension_enum", native_enum=False),
        nullable=False
    )
    group_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    group_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    group_name: Mapped[str] = mapped_column(String(256), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    long_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    short_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    net_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    gross_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    cash_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)

    actual_nav_weight: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    normalized_weight: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    gross_exposure_weight: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)

    allocation_status: Mapped[str] = mapped_column(String(32), default="ALLOCATED", nullable=False)
    source_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    allocation_result: Mapped["PortfolioAllocationResult"] = relationship("PortfolioAllocationResult", back_populates="components")

    __table_args__ = (
        Index("ix_acomp_res_rank", "result_id", "rank"),
    )


class PortfolioAllocationTarget(Base):
    """
    Configurable effective-dated target allocations for securities, sectors, countries, cash, or strategies.
    """
    __tablename__ = "m06_portfolio_allocation_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"TRGT_{uuid.uuid4().hex[:12].upper()}"
    )
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    portfolio_group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    grouping_dimension: Mapped[AllocationGroupingDimension] = mapped_column(
        Enum(AllocationGroupingDimension, name="allocation_grouping_dimension_enum", native_enum=False),
        nullable=False,
        index=True
    )
    group_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_weight: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)  # e.g. 0.250000 for 25%
    weight_denominator: Mapped[str] = mapped_column(String(32), default="NAV", nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)

    tolerance_band_pp: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.050000"), nullable=False)  # +/- 5%
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    configuration_version: Mapped[str] = mapped_column(String(32), default="v1.0", nullable=False)

    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class PortfolioAllocationDrift(Base):
    """
    Calculated drift comparing actual portfolio weights against targets or historical weights.
    """
    __tablename__ = "m06_portfolio_allocation_drifts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    drift_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"DRFT_{uuid.uuid4().hex[:12].upper()}"
    )
    result_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    grouping_dimension: Mapped[AllocationGroupingDimension] = mapped_column(
        Enum(AllocationGroupingDimension, name="allocation_grouping_dimension_enum", native_enum=False),
        nullable=False
    )
    group_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    group_name: Mapped[str] = mapped_column(String(256), nullable=False)

    actual_weight: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    target_weight: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    absolute_drift_pp: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)  # Actual - Target in pp
    relative_drift_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    capital_difference: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    drift_status: Mapped[AllocationDriftStatus] = mapped_column(
        Enum(AllocationDriftStatus, name="allocation_drift_status_enum", native_enum=False),
        default=AllocationDriftStatus.WITHIN_TARGET,
        nullable=False
    )
    calculation_version: Mapped[str] = mapped_column(String(32), default="v1.0", nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class PortfolioAllocationComparison(Base):
    """
    Historical point-to-point comparison between two allocation calculation runs.
    """
    __tablename__ = "m06_portfolio_allocation_comparisons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comparison_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"ACMP_{uuid.uuid4().hex[:12].upper()}"
    )
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    current_result_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    prior_result_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    grouping_dimension: Mapped[AllocationGroupingDimension] = mapped_column(
        Enum(AllocationGroupingDimension, name="allocation_grouping_dimension_enum", native_enum=False),
        nullable=False
    )
    reporting_currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)

    current_nav: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    prior_nav: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    nav_change: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    current_cash_weight: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    prior_cash_weight: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    cash_weight_change_pp: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    current_invested_weight: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    prior_invested_weight: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    invested_weight_change_pp: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    comparability_status: Mapped[str] = mapped_column(String(32), default="COMPARABLE", nullable=False)
    compared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
