"""
M06.04 Instrument Exposure - SQLAlchemy 2.x Database Models.
Tracks instrument-level exposure results, listing details, exposure comparisons,
dominance flags, and portfolio settings.
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


class ExposureWeightBasis(str, enum.Enum):
    NAV = "NAV_BASED"
    GROSS_CONTRIBUTION = "GROSS_CONTRIBUTION"
    LONG_CONTRIBUTION = "LONG_CONTRIBUTION"
    SHORT_CONTRIBUTION = "SHORT_CONTRIBUTION"


class ExposureRankingBasis(str, enum.Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    GROSS = "GROSS"
    ABSOLUTE_NET = "ABSOLUTE_NET"


class ValuationQualityStatus(str, enum.Enum):
    VALUED = "VALUED"
    PARTIALLY_VALUED = "PARTIALLY_VALUED"
    PRICE_UNAVAILABLE = "PRICE_UNAVAILABLE"
    FX_UNAVAILABLE = "FX_UNAVAILABLE"
    STALE_VALUATION = "STALE_VALUATION"
    INVALID_VALUATION = "INVALID_VALUATION"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class DenominatorStatus(str, enum.Enum):
    CALCULATED = "CALCULATED"
    DENOMINATOR_ZERO = "DENOMINATOR_ZERO"
    DENOMINATOR_INVALID = "DENOMINATOR_INVALID"
    DENOMINATOR_UNAVAILABLE = "DENOMINATOR_UNAVAILABLE"
    INCOMPLETE_DATA = "INCOMPLETE_DATA"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ExposureLifecycleIndicator(str, enum.Enum):
    NEW_POSITION = "NEW_POSITION"
    INCREASED_EXPOSURE = "INCREASED_EXPOSURE"
    REDUCED_EXPOSURE = "REDUCED_EXPOSURE"
    UNCHANGED_EXPOSURE = "UNCHANGED_EXPOSURE"
    CLOSED_POSITION = "CLOSED_POSITION"
    DIRECTION_CHANGED = "DIRECTION_CHANGED"
    NEW_SHORT_EXPOSURE = "NEW_SHORT_EXPOSURE"
    SHORT_REDUCED = "SHORT_REDUCED"
    SHORT_INCREASED = "SHORT_INCREASED"
    DATA_INCOMPLETE = "DATA_INCOMPLETE"
    COMPARISON_UNAVAILABLE = "COMPARISON_UNAVAILABLE"


class DominanceSeverity(str, enum.Enum):
    NORMAL = "NORMAL"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNAVAILABLE = "UNAVAILABLE"


class InstrumentExposureCalculationRun(Base):
    __tablename__ = "m06_instrument_exposure_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"INST-RUN-{uuid.uuid4().hex[:12].upper()}"
    )
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    portfolio_group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(32), default="PORTFOLIO", nullable=False)
    snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    knowledge_as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    weight_basis: Mapped[str] = mapped_column(String(32), default=ExposureWeightBasis.NAV.value, nullable=False)

    nav: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    total_long_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    total_short_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    total_net_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    total_gross_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)

    total_instruments_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    long_instruments_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    short_instruments_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hedged_instruments_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    valuation_coverage_ratio: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1.000000"), nullable=False)
    data_completeness_status: Mapped[str] = mapped_column(String(32), default="COMPLETE", nullable=False)
    denominator_status: Mapped[str] = mapped_column(String(32), default=DenominatorStatus.CALCULATED.value, nullable=False)

    calculation_version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class InstrumentExposureResult(Base):
    __tablename__ = "m06_instrument_exposure_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("m06_instrument_exposure_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    symbol: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    instrument_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    exchange_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    asset_class: Mapped[str] = mapped_column(String(32), default="EQUITY", nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(3), nullable=False)

    long_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    short_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    net_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)

    long_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    short_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    net_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)
    gross_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.000000"), nullable=False)

    # Weights
    long_nav_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    short_nav_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    net_nav_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    gross_nav_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)

    gross_contribution_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    long_contribution_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    short_contribution_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)

    # Ranks
    long_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    short_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gross_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    net_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    valuation_status: Mapped[str] = mapped_column(String(32), default=ValuationQualityStatus.VALUED.value, nullable=False)
    price_source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    mark_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    mark_price_currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    valuation_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    dominance_severity: Mapped[str] = mapped_column(String(32), default=DominanceSeverity.NORMAL.value, nullable=False)
    dominance_flag_reason: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class InstrumentListingExposureDetail(Base):
    __tablename__ = "m06_instrument_listing_exposure_details"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("m06_instrument_exposure_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    exchange_code: Mapped[str] = mapped_column(String(32), nullable=False)
    native_currency: Mapped[str] = mapped_column(String(3), nullable=False)

    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    mark_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    native_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    reporting_currency_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    fx_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    fx_pair: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    valuation_status: Mapped[str] = mapped_column(String(32), default=ValuationQualityStatus.VALUED.value, nullable=False)


class InstrumentExposureComparison(Base):
    __tablename__ = "m06_instrument_exposure_comparisons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    current_snapshot_id: Mapped[str] = mapped_column(String(64), nullable=False)
    prior_snapshot_id: Mapped[str] = mapped_column(String(64), nullable=False)

    current_long_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    prior_long_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    long_exposure_change: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    current_short_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    prior_short_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    short_exposure_change: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    current_net_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    prior_net_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    net_exposure_change: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    current_gross_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    prior_gross_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    gross_exposure_change: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    gross_percentage_change: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    nav_weight_change_pp: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    gross_contribution_change_pp: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)

    lifecycle_indicator: Mapped[str] = mapped_column(String(32), default=ExposureLifecycleIndicator.UNCHANGED_EXPOSURE.value, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class InstrumentExposureDominanceFlag(Base):
    __tablename__ = "m06_instrument_exposure_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    flag_type: Mapped[str] = mapped_column(String(64), nullable=False) # e.g. GROSS_NAV_EXCEEDED, SHORT_NAV_EXCEEDED
    severity: Mapped[str] = mapped_column(String(32), default=DominanceSeverity.ELEVATED.value, nullable=False)
    measured_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    weight_basis: Mapped[str] = mapped_column(String(32), nullable=False)
    evaluation_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class InstrumentExposureSettings(Base):
    __tablename__ = "m06_instrument_exposure_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True, index=True)
    reporting_currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    default_weight_basis: Mapped[str] = mapped_column(String(32), default=ExposureWeightBasis.NAV.value, nullable=False)
    default_ranking_basis: Mapped[str] = mapped_column(String(32), default=ExposureRankingBasis.GROSS.value, nullable=False)

    # Dominance thresholds (in decimals, e.g. 0.10 for 10%)
    gross_nav_elevated_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.100000"), nullable=False)
    gross_nav_critical_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.200000"), nullable=False)
    long_nav_elevated_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.080000"), nullable=False)
    short_nav_elevated_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.050000"), nullable=False)
    gross_contribution_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.150000"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

