"""
Module M07.01: Historical Volatility - SQLAlchemy 2.x Models.
Defines entities for configurations, annualization conventions, return observations,
volatility results, rolling series, and diagnostics.
"""
import enum
import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from typing import Optional, List

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
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VolatilityScopeType(str, enum.Enum):
    INSTRUMENT = "INSTRUMENT"
    LISTING = "LISTING"
    PORTFOLIO = "PORTFOLIO"
    PORTFOLIO_GROUP = "PORTFOLIO_GROUP"


class ReturnType(str, enum.Enum):
    LOGARITHMIC = "LOGARITHMIC"
    SIMPLE = "SIMPLE"


class ReturnFrequency(str, enum.Enum):
    DAILY = "DAILY"
    INTRADAY_1_MINUTE = "INTRADAY_1_MINUTE"
    INTRADAY_5_MINUTE = "INTRADAY_5_MINUTE"
    INTRADAY_15_MINUTE = "INTRADAY_15_MINUTE"
    INTRADAY_30_MINUTE = "INTRADAY_30_MINUTE"
    CUSTOM_INTERVAL = "CUSTOM_INTERVAL"


class PriceSourceType(str, enum.Enum):
    OFFICIAL_CLOSE = "OFFICIAL_CLOSE"
    ADJUSTED_CLOSE = "ADJUSTED_CLOSE"
    OHLCV_BAR_CLOSE = "OHLCV_BAR_CLOSE"
    TRADE_PRICE = "TRADE_PRICE"
    QUOTE_MIDPOINT = "QUOTE_MIDPOINT"
    PORTFOLIO_NAV = "PORTFOLIO_NAV"


class PriceMeasure(str, enum.Enum):
    CLOSE = "CLOSE"
    MIDQUOTE = "MIDQUOTE"
    TRADE_TICK = "TRADE_TICK"
    NAV = "NAV"


class CorporateActionAdjustmentPolicy(str, enum.Enum):
    RAW = "RAW"
    SPLIT_ADJUSTED = "SPLIT_ADJUSTED"
    TOTAL_RETURN_ADJUSTED = "TOTAL_RETURN_ADJUSTED"


class StatisticalEstimator(str, enum.Enum):
    SAMPLE_STD_DEV = "SAMPLE_STD_DEV"  # N - 1 degrees of freedom
    POPULATION_STD_DEV = "POPULATION_STD_DEV"  # N degrees of freedom


class VolatilityCalculationStatus(str, enum.Enum):
    CALCULATED = "CALCULATED"
    INSUFFICIENT_OBSERVATIONS = "INSUFFICIENT_OBSERVATIONS"
    PARTIAL_WINDOW = "PARTIAL_WINDOW"
    DATA_GAP = "DATA_GAP"
    INVALID_RETURN_SERIES = "INVALID_RETURN_SERIES"
    MICROSTRUCTURE_NOISE_REJECTED = "MICROSTRUCTURE_NOISE_REJECTED"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class VolatilityTrendClassification(str, enum.Enum):
    VOLATILITY_INCREASING = "VOLATILITY_INCREASING"
    VOLATILITY_DECREASING = "VOLATILITY_DECREASING"
    VOLATILITY_STABLE = "VOLATILITY_STABLE"
    VOLATILITY_ELEVATED = "VOLATILITY_ELEVATED"
    VOLATILITY_NORMALIZING = "VOLATILITY_NORMALIZING"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    INCOMPARABLE_DATA = "INCOMPARABLE_DATA"


class VolatilityWindowComparisonLabel(str, enum.Enum):
    SHORT_TERM_HIGHER = "SHORT_TERM_HIGHER"
    SHORT_TERM_LOWER = "SHORT_TERM_LOWER"
    HORIZONS_SIMILAR = "HORIZONS_SIMILAR"
    LONG_TERM_HIGHER = "LONG_TERM_HIGHER"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    INCOMPARABLE_METHODOLOGY = "INCOMPARABLE_METHODOLOGY"


class VolatilityAnnualizationConvention(Base):
    """
    Explicit annual trading-session and intraday period conventions.
    """
    __tablename__ = "m07_volatility_annualization_conventions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    convention_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"ANN_{uuid.uuid4().hex[:12].upper()}"
    )
    convention_name: Mapped[str] = mapped_column(String(128), nullable=False)
    market_code: Mapped[str] = mapped_column(String(32), default="US", nullable=False)  # US, IN
    exchange_code: Mapped[str] = mapped_column(String(32), default="NASDAQ", nullable=False)  # NYSE, NASDAQ, NSE, BSE
    return_frequency: Mapped[ReturnFrequency] = mapped_column(
        SAEnum(ReturnFrequency, native_enum=False), default=ReturnFrequency.DAILY, nullable=False
    )
    sampling_interval_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g. 1, 5, 15, 30
    
    trading_sessions_per_year: Mapped[int] = mapped_column(Integer, default=252, nullable=False)
    trading_hours_per_session: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("6.5"), nullable=False)
    intervals_per_session: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 1 for daily, 78 for 5m US session
    periods_per_year: Mapped[int] = mapped_column(Integer, default=252, nullable=False)
    annualization_factor: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)  # sqrt(periods_per_year)
    
    session_break_policy: Mapped[str] = mapped_column(String(64), default="REGULAR_HOURS_ONLY", nullable=False)
    methodology_description: Mapped[str] = mapped_column(Text, nullable=False)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class HistoricalVolatilityConfig(Base):
    """
    Versioned configuration for historical volatility calculation methodologies.
    """
    __tablename__ = "m07_historical_volatility_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"VCFG_{uuid.uuid4().hex[:12].upper()}"
    )
    config_name: Mapped[str] = mapped_column(String(128), nullable=False)
    scope_type: Mapped[VolatilityScopeType] = mapped_column(
        SAEnum(VolatilityScopeType, native_enum=False), default=VolatilityScopeType.INSTRUMENT, nullable=False
    )
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    
    return_type: Mapped[ReturnType] = mapped_column(
        SAEnum(ReturnType, native_enum=False), default=ReturnType.LOGARITHMIC, nullable=False
    )
    return_frequency: Mapped[ReturnFrequency] = mapped_column(
        SAEnum(ReturnFrequency, native_enum=False), default=ReturnFrequency.DAILY, nullable=False
    )
    sampling_interval: Mapped[Optional[str]] = mapped_column(String(32), default="1d", nullable=True)
    price_source: Mapped[PriceSourceType] = mapped_column(
        SAEnum(PriceSourceType, native_enum=False), default=PriceSourceType.OFFICIAL_CLOSE, nullable=False
    )
    price_measure: Mapped[PriceMeasure] = mapped_column(
        SAEnum(PriceMeasure, native_enum=False), default=PriceMeasure.CLOSE, nullable=False
    )
    corporate_action_policy: Mapped[CorporateActionAdjustmentPolicy] = mapped_column(
        SAEnum(CorporateActionAdjustmentPolicy, native_enum=False),
        default=CorporateActionAdjustmentPolicy.SPLIT_ADJUSTED,
        nullable=False,
    )
    
    lookback_window: Mapped[int] = mapped_column(Integer, default=20, nullable=False)  # e.g. 20, 60, 252
    window_type: Mapped[str] = mapped_column(String(32), default="TRADING_SESSIONS", nullable=False)
    estimator: Mapped[StatisticalEstimator] = mapped_column(
        SAEnum(StatisticalEstimator, native_enum=False), default=StatisticalEstimator.SAMPLE_STD_DEV, nullable=False
    )
    
    annualization_convention_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("m07_volatility_annualization_conventions.convention_id"), nullable=True
    )
    
    session_boundary_policy: Mapped[str] = mapped_column(String(64), default="EXCLUDE_OVERNIGHT", nullable=False)
    minimum_observations: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    minimum_coverage_ratio: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.9000"), nullable=False)
    gap_tolerance_days: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class HistoricalReturnObservation(Base):
    """
    Derived return observation record preserving complete price pair lineage.
    """
    __tablename__ = "m07_historical_return_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    observation_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"RET_{uuid.uuid4().hex[:12].upper()}"
    )
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    
    observation_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    observation_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    trading_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    return_frequency: Mapped[ReturnFrequency] = mapped_column(
        SAEnum(ReturnFrequency, native_enum=False), nullable=False
    )
    return_type: Mapped[ReturnType] = mapped_column(
        SAEnum(ReturnType, native_enum=False), nullable=False
    )
    
    start_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    end_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    return_value: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    
    price_source: Mapped[str] = mapped_column(String(64), nullable=False)
    price_measure: Mapped[str] = mapped_column(String(32), default="CLOSE", nullable=False)
    adjustment_policy: Mapped[str] = mapped_column(String(32), default="SPLIT_ADJUSTED", nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    quality_status: Mapped[str] = mapped_column(String(32), default="VALID", nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_ret_inst_freq_date", "instrument_id", "return_frequency", "trading_date"),
    )


class HistoricalVolatilityResult(Base):
    """
    Authoritative historical volatility calculation record for a specific window.
    """
    __tablename__ = "m07_historical_volatility_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    result_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"VOL_{uuid.uuid4().hex[:12].upper()}"
    )
    scope_type: Mapped[VolatilityScopeType] = mapped_column(
        SAEnum(VolatilityScopeType, native_enum=False), nullable=False
    )
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    config_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lookback_window: Mapped[int] = mapped_column(Integer, nullable=False)
    
    return_type: Mapped[ReturnType] = mapped_column(
        SAEnum(ReturnType, native_enum=False), nullable=False
    )
    return_frequency: Mapped[ReturnFrequency] = mapped_column(
        SAEnum(ReturnFrequency, native_enum=False), nullable=False
    )
    
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    coverage_percentage: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    
    mean_return: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    period_volatility: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)  # Standard deviation
    annualized_volatility: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)  # Realized vol %
    annualization_factor: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    periods_per_year: Mapped[int] = mapped_column(Integer, nullable=False)
    
    estimator: Mapped[StatisticalEstimator] = mapped_column(
        SAEnum(StatisticalEstimator, native_enum=False), default=StatisticalEstimator.SAMPLE_STD_DEV, nullable=False
    )
    calculation_status: Mapped[VolatilityCalculationStatus] = mapped_column(
        SAEnum(VolatilityCalculationStatus, native_enum=False), default=VolatilityCalculationStatus.CALCULATED, nullable=False
    )
    quality_status: Mapped[str] = mapped_column(String(32), default="PASSED", nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class RollingVolatilityPoint(Base):
    """
    Time-series rolling volatility observation point for charting and trend evaluation.
    """
    __tablename__ = "m07_rolling_volatility_series"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    point_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"RP_{uuid.uuid4().hex[:12].upper()}"
    )
    result_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    
    observation_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    trading_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    lookback_window: Mapped[int] = mapped_column(Integer, nullable=False)
    return_frequency: Mapped[ReturnFrequency] = mapped_column(
        SAEnum(ReturnFrequency, native_enum=False), nullable=False
    )
    
    period_volatility: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    annualized_volatility: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    coverage_percentage: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    status: Mapped[VolatilityCalculationStatus] = mapped_column(
        SAEnum(VolatilityCalculationStatus, native_enum=False), default=VolatilityCalculationStatus.CALCULATED, nullable=False
    )
    
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_rolling_inst_window_time", "instrument_id", "lookback_window", "observation_timestamp"),
    )


class VolatilityCalculationDiagnostic(Base):
    """
    Diagnostics ledger capturing quality, gap, sampling, or microstructure rejection events.
    """
    __tablename__ = "m07_volatility_calculation_diagnostics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    diagnostic_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"VDIAG_{uuid.uuid4().hex[:12].upper()}"
    )
    result_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    diagnostic_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), default="WARNING", nullable=False)  # INFO, WARNING, ERROR, REJECTED
    description: Mapped[str] = mapped_column(Text, nullable=False)
    affected_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    source_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

