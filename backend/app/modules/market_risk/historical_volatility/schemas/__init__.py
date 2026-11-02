"""
Module M07.01: Historical Volatility Pydantic v2 Schemas.
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

from backend.app.modules.market_risk.historical_volatility.models import (
    VolatilityScopeType,
    ReturnType,
    ReturnFrequency,
    PriceSourceType,
    PriceMeasure,
    CorporateActionAdjustmentPolicy,
    StatisticalEstimator,
    VolatilityCalculationStatus,
    VolatilityTrendClassification,
    VolatilityWindowComparisonLabel,
)


class AnnualizationConventionCreateRequest(BaseModel):
    convention_name: str
    market_code: str = "US"
    exchange_code: str = "NASDAQ"
    return_frequency: ReturnFrequency = ReturnFrequency.DAILY
    sampling_interval_minutes: Optional[int] = None
    trading_sessions_per_year: int = 252
    trading_hours_per_session: Decimal = Decimal("6.5")
    intervals_per_session: int = 1
    periods_per_year: int = 252
    session_break_policy: str = "REGULAR_HOURS_ONLY"
    methodology_description: str = "Standard 252-day annual trading session convention."


class AnnualizationConventionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    convention_id: str
    convention_name: str
    market_code: str
    exchange_code: str
    return_frequency: ReturnFrequency
    sampling_interval_minutes: Optional[int] = None
    trading_sessions_per_year: int
    trading_hours_per_session: Decimal
    intervals_per_session: int
    periods_per_year: int
    annualization_factor: Decimal
    session_break_policy: str
    methodology_description: str
    is_active: bool
    created_at: datetime


class VolatilityConfigCreateRequest(BaseModel):
    config_name: str
    scope_type: VolatilityScopeType = VolatilityScopeType.INSTRUMENT
    portfolio_id: Optional[str] = None
    instrument_id: Optional[str] = None
    listing_id: Optional[str] = None
    return_type: ReturnType = ReturnType.LOGARITHMIC
    return_frequency: ReturnFrequency = ReturnFrequency.DAILY
    sampling_interval: Optional[str] = "1d"
    price_source: PriceSourceType = PriceSourceType.OFFICIAL_CLOSE
    price_measure: PriceMeasure = PriceMeasure.CLOSE
    corporate_action_policy: CorporateActionAdjustmentPolicy = CorporateActionAdjustmentPolicy.SPLIT_ADJUSTED
    lookback_window: int = 20
    window_type: str = "TRADING_SESSIONS"
    estimator: StatisticalEstimator = StatisticalEstimator.SAMPLE_STD_DEV
    annualization_convention_id: Optional[str] = None
    session_boundary_policy: str = "EXCLUDE_OVERNIGHT"
    minimum_observations: int = 20
    minimum_coverage_ratio: Decimal = Decimal("0.9000")
    gap_tolerance_days: int = 3


class VolatilityConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    config_id: str
    config_name: str
    scope_type: VolatilityScopeType
    portfolio_id: Optional[str] = None
    instrument_id: Optional[str] = None
    listing_id: Optional[str] = None
    return_type: ReturnType
    return_frequency: ReturnFrequency
    sampling_interval: Optional[str] = None
    price_source: PriceSourceType
    price_measure: PriceMeasure
    corporate_action_policy: CorporateActionAdjustmentPolicy
    lookback_window: int
    window_type: str
    estimator: StatisticalEstimator
    annualization_convention_id: Optional[str] = None
    session_boundary_policy: str
    minimum_observations: int
    minimum_coverage_ratio: Decimal
    gap_tolerance_days: int
    is_active: bool
    config_version: int
    created_at: datetime


class HistoricalVolatilityCalculateRequest(BaseModel):
    instrument_id: Optional[str] = None
    listing_id: Optional[str] = None
    portfolio_id: Optional[str] = None
    scope_type: VolatilityScopeType = VolatilityScopeType.INSTRUMENT
    return_type: ReturnType = ReturnType.LOGARITHMIC
    return_frequency: ReturnFrequency = ReturnFrequency.DAILY
    sampling_interval: Optional[str] = "1d"
    lookback_window: int = 20
    price_source: PriceSourceType = PriceSourceType.OFFICIAL_CLOSE
    price_measure: PriceMeasure = PriceMeasure.CLOSE
    corporate_action_policy: CorporateActionAdjustmentPolicy = CorporateActionAdjustmentPolicy.SPLIT_ADJUSTED
    annualization_convention_id: Optional[str] = None
    as_of: Optional[date] = None


class HistoricalVolatilityResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    result_id: str
    scope_type: VolatilityScopeType
    instrument_id: Optional[str] = None
    listing_id: Optional[str] = None
    portfolio_id: Optional[str] = None
    as_of_date: date
    window_start: datetime
    window_end: datetime
    lookback_window: int
    return_type: ReturnType
    return_frequency: ReturnFrequency
    observation_count: int
    expected_observation_count: int
    coverage_percentage: Decimal
    mean_return: Decimal
    period_volatility: Decimal
    annualized_volatility: Decimal
    annualization_factor: Decimal
    periods_per_year: int
    estimator: StatisticalEstimator
    calculation_status: VolatilityCalculationStatus
    quality_status: str
    calculation_version: str
    calculated_at: datetime


class RollingVolatilityPointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    point_id: str
    observation_timestamp: datetime
    trading_date: date
    lookback_window: int
    return_frequency: ReturnFrequency
    period_volatility: Decimal
    annualized_volatility: Decimal
    observation_count: int
    coverage_percentage: Decimal
    status: VolatilityCalculationStatus


class RollingVolatilitySeriesResponse(BaseModel):
    instrument_id: Optional[str] = None
    portfolio_id: Optional[str] = None
    lookback_window: int
    return_frequency: ReturnFrequency
    total_points: int
    series: List[RollingVolatilityPointResponse]


class WindowHorizonMetric(BaseModel):
    horizon: str  # SHORT, MEDIUM, LONG
    lookback_sessions: int
    observation_count: int
    expected_observation_count: int
    coverage_percentage: Decimal
    period_volatility: Decimal
    annualized_volatility: Decimal
    annualization_factor: Decimal
    status: VolatilityCalculationStatus


class WindowComparisonResponse(BaseModel):
    instrument_id: Optional[str] = None
    listing_id: Optional[str] = None
    as_of_date: date
    return_frequency: ReturnFrequency
    return_type: ReturnType
    horizons: List[WindowHorizonMetric]
    short_vs_medium_spread: Decimal
    medium_vs_long_spread: Decimal
    short_vs_long_spread: Decimal
    short_to_long_ratio: Optional[Decimal] = None
    comparison_label: VolatilityWindowComparisonLabel
    calculated_at: datetime


class VolatilityTrendResponse(BaseModel):
    instrument_id: Optional[str] = None
    listing_id: Optional[str] = None
    lookback_window: int
    return_frequency: ReturnFrequency
    current_volatility: Decimal
    prior_volatility: Optional[Decimal] = None
    volatility_change: Decimal
    volatility_pct_change: Optional[Decimal] = None
    trend_slope: Optional[Decimal] = None
    trend_classification: VolatilityTrendClassification
    points_evaluated: int
    as_of_date: date


class IntradayVolatilityResponse(BaseModel):
    instrument_id: str
    listing_id: Optional[str] = None
    sampling_interval: str  # 1m, 5m, 15m, 30m
    price_measure: PriceMeasure
    price_source: PriceSourceType
    session_boundary_policy: str
    intraday_period_volatility: Decimal
    annualized_volatility: Decimal
    annualization_factor: Decimal
    bars_evaluated: int
    expected_bars: int
    coverage_percentage: Decimal
    microstructure_suitability: str
    is_suitable: bool
    status: VolatilityCalculationStatus
    calculated_at: datetime


class VolatilityDiagnosticItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    diagnostic_id: str
    diagnostic_code: str
    severity: str
    description: str
    affected_timestamp: Optional[datetime] = None
    source_reference: Optional[str] = None
    created_at: datetime

