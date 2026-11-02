"""
M07.08 Sharpe & Sortino Ratios Database Models (SQLAlchemy 2.x).
"""
from datetime import datetime, timezone, date
import enum
from typing import Optional, Dict, Any, List
from uuid import uuid4

from sqlalchemy import (
    String,
    DateTime,
    Date,
    Numeric,
    Integer,
    ForeignKey,
    JSON,
    Boolean,
    Enum,
    Index,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SharpeDenominatorPolicy(str, enum.Enum):
    PORTFOLIO_RETURN_VOLATILITY = "PORTFOLIO_RETURN_VOLATILITY"
    EXCESS_RETURN_VOLATILITY = "EXCESS_RETURN_VOLATILITY"


class SortinoTargetPolicy(str, enum.Enum):
    RISK_FREE_RATE = "RISK_FREE_RATE"
    CONSTANT_PERIOD_TARGET = "CONSTANT_PERIOD_TARGET"
    ANNUAL_TARGET_CONVERTED_TO_PERIOD = "ANNUAL_TARGET_CONVERTED_TO_PERIOD"
    CUSTOM_TARGET_SERIES = "CUSTOM_TARGET_SERIES"


class SortinoDenominatorPolicy(str, enum.Enum):
    ALL_PERIODS_SEMIDEVIATION = "ALL_PERIODS_SEMIDEVIATION"
    BELOW_TARGET_CONDITIONAL_DOWNSIDE_DISPERSION = "BELOW_TARGET_CONDITIONAL_DOWNSIDE_DISPERSION"


class RateConvention(str, enum.Enum):
    EFFECTIVE_ANNUAL_RATE = "EFFECTIVE_ANNUAL_RATE"
    SIMPLE_ANNUAL_RATE = "SIMPLE_ANNUAL_RATE"
    CONTINUOUSLY_COMPOUNDED = "CONTINUOUSLY_COMPOUNDED"
    NOMINAL_ANNUAL_RATE = "NOMINAL_ANNUAL_RATE"


class DayCountConvention(str, enum.Enum):
    ACTUAL_365 = "ACTUAL_365"
    ACTUAL_360 = "ACTUAL_360"
    THIRTY_360 = "THIRTY_360"


class RateMissingPolicy(str, enum.Enum):
    STRICT_MATCH = "STRICT_MATCH"
    EFFECTIVE_RATE_CARRY_FORWARD = "EFFECTIVE_RATE_CARRY_FORWARD"


class RatioCalculationStatus(str, enum.Enum):
    VALID = "VALID"
    VALID_WITH_WARNINGS = "VALID_WITH_WARNINGS"
    INSUFFICIENT_OBSERVATIONS = "INSUFFICIENT_OBSERVATIONS"
    RATE_CURRENCY_MISMATCH = "RATE_CURRENCY_MISMATCH"
    ZERO_VOLATILITY = "ZERO_VOLATILITY"
    ZERO_DOWNSIDE_DEVIATION = "ZERO_DOWNSIDE_DEVIATION"
    UNDEFINED_SHARPE = "UNDEFINED_SHARPE"
    UNDEFINED_SORTINO = "UNDEFINED_SORTINO"
    ALIGNMENT_FAILED = "ALIGNMENT_FAILED"
    CALCULATION_FAILED = "CALCULATION_FAILED"


class RiskFreeRateSeries(Base):
    """
    Registry for risk-free rates (e.g. MIBOR 91D, US Treasury 3M Bill, SOFR, etc.).
    """
    __tablename__ = "m07_risk_free_rate_series"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    series_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    rate_name: Mapped[str] = mapped_column(String(128), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    market: Mapped[str] = mapped_column(String(32), default="INDIA", nullable=False)
    provider: Mapped[str] = mapped_column(String(64), default="CENTRAL_BANK", nullable=False)
    rate_convention: Mapped[RateConvention] = mapped_column(
        Enum(RateConvention, native_enum=False), default=RateConvention.EFFECTIVE_ANNUAL_RATE, nullable=False
    )
    day_count_convention: Mapped[DayCountConvention] = mapped_column(
        Enum(DayCountConvention, native_enum=False), default=DayCountConvention.ACTUAL_365, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class RiskFreeRateObservation(Base):
    """
    Historical observation points for risk-free interest rate series.
    """
    __tablename__ = "m07_risk_free_rate_observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    series_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m07_risk_free_rate_series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rate_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    annualized_rate: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_m07_rf_obs_lookup", "series_id", "rate_date", unique=True),
    )


class RiskAdjustedReturnConfig(Base):
    """
    Profile configurations for Sharpe and Sortino ratio estimation.
    """
    __tablename__ = "m07_risk_adjusted_return_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    config_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    risk_free_rate_series_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("m07_risk_free_rate_series.id", ondelete="SET NULL"), nullable=True
    )
    sharpe_denominator_policy: Mapped[SharpeDenominatorPolicy] = mapped_column(
        Enum(SharpeDenominatorPolicy, native_enum=False),
        default=SharpeDenominatorPolicy.PORTFOLIO_RETURN_VOLATILITY,
        nullable=False,
    )
    sortino_target_policy: Mapped[SortinoTargetPolicy] = mapped_column(
        Enum(SortinoTargetPolicy, native_enum=False),
        default=SortinoTargetPolicy.RISK_FREE_RATE,
        nullable=False,
    )
    sortino_denominator_policy: Mapped[SortinoDenominatorPolicy] = mapped_column(
        Enum(SortinoDenominatorPolicy, native_enum=False),
        default=SortinoDenominatorPolicy.ALL_PERIODS_SEMIDEVIATION,
        nullable=False,
    )
    rate_missing_policy: Mapped[RateMissingPolicy] = mapped_column(
        Enum(RateMissingPolicy, native_enum=False),
        default=RateMissingPolicy.EFFECTIVE_RATE_CARRY_FORWARD,
        nullable=False,
    )
    constant_mar_annual: Mapped[Optional[float]] = mapped_column(Numeric(8, 4), nullable=True)
    default_lookback_days: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    min_observations: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    annualization_factor: Mapped[float] = mapped_column(Numeric(8, 2), default=252.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class SharpeRatioResult(Base):
    """
    Sharpe ratio calculation outcomes.
    """
    __tablename__ = "m07_sharpe_ratio_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    calculation_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)  # SECURITY, PORTFOLIO, PORTFOLIO_GROUP
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    as_of_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lookback_days: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    
    mean_return_period: Mapped[float] = mapped_column(Numeric(12, 8), nullable=False)
    mean_risk_free_period: Mapped[float] = mapped_column(Numeric(12, 8), nullable=False)
    mean_excess_return_period: Mapped[float] = mapped_column(Numeric(12, 8), nullable=False)
    return_volatility_period: Mapped[float] = mapped_column(Numeric(12, 8), nullable=False)
    period_sharpe: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    annualized_sharpe: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    annualization_factor: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    denominator_policy: Mapped[SharpeDenominatorPolicy] = mapped_column(
        Enum(SharpeDenominatorPolicy, native_enum=False), nullable=False
    )
    status: Mapped[RatioCalculationStatus] = mapped_column(
        Enum(RatioCalculationStatus, native_enum=False), default=RatioCalculationStatus.VALID, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class SortinoRatioResult(Base):
    """
    Sortino ratio calculation outcomes.
    """
    __tablename__ = "m07_sortino_ratio_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    calculation_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    as_of_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lookback_days: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    
    mean_return_period: Mapped[float] = mapped_column(Numeric(12, 8), nullable=False)
    target_return_period: Mapped[float] = mapped_column(Numeric(12, 8), nullable=False)
    mean_excess_over_target_period: Mapped[float] = mapped_column(Numeric(12, 8), nullable=False)
    downside_deviation_period: Mapped[float] = mapped_column(Numeric(12, 8), nullable=False)
    period_sortino: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    annualized_sortino: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    annualization_factor: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    downside_periods_count: Mapped[int] = mapped_column(Integer, nullable=False)
    downside_percentage: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    target_policy: Mapped[SortinoTargetPolicy] = mapped_column(
        Enum(SortinoTargetPolicy, native_enum=False), nullable=False
    )
    denominator_policy: Mapped[SortinoDenominatorPolicy] = mapped_column(
        Enum(SortinoDenominatorPolicy, native_enum=False), nullable=False
    )
    status: Mapped[RatioCalculationStatus] = mapped_column(
        Enum(RatioCalculationStatus, native_enum=False), default=RatioCalculationStatus.VALID, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
