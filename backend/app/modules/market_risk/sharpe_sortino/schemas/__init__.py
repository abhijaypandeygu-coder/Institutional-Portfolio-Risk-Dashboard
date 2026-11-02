"""
Pydantic v2 Schemas for M07.08 Sharpe & Sortino Ratios.
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

from backend.app.modules.market_risk.sharpe_sortino.models import (
    SharpeDenominatorPolicy,
    SortinoTargetPolicy,
    SortinoDenominatorPolicy,
    RateConvention,
    DayCountConvention,
    RateMissingPolicy,
    RatioCalculationStatus,
)


class RiskFreeRateSeriesCreate(BaseModel):
    series_code: str = Field(..., max_length=64)
    rate_name: str = Field(..., max_length=128)
    currency: str = Field("INR", max_length=3)
    market: str = Field("INDIA", max_length=32)
    provider: str = Field("RBI", max_length=64)
    rate_convention: RateConvention = RateConvention.EFFECTIVE_ANNUAL_RATE
    day_count_convention: DayCountConvention = DayCountConvention.ACTUAL_365
    is_active: bool = True


class RiskFreeRateSeriesResponse(RiskFreeRateSeriesCreate):
    id: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RiskFreeRateObservationCreate(BaseModel):
    series_id: str
    rate_date: date
    annualized_rate: Decimal


class RiskFreeRateObservationResponse(RiskFreeRateObservationCreate):
    id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SharpeRatioRequest(BaseModel):
    scope: str = Field("PORTFOLIO", description="SECURITY, PORTFOLIO, or PORTFOLIO_GROUP")
    entity_id: str = Field(..., description="Instrument ID or Portfolio ID")
    risk_free_series_code: Optional[str] = Field(None, description="Risk free rate series code (default resolves by currency)")
    lookback_days: int = Field(60, ge=5, le=2520)
    as_of: Optional[date] = None
    denominator_policy: SharpeDenominatorPolicy = SharpeDenominatorPolicy.PORTFOLIO_RETURN_VOLATILITY
    annualization_factor: Decimal = Field(Decimal("252.0"), ge=1.0, le=1000.0)


class SharpeRatioResponse(BaseModel):
    calculation_code: str
    scope: str
    entity_id: str
    as_of_date: datetime
    lookback_days: int
    currency: str
    mean_return_period: Decimal
    mean_risk_free_period: Decimal
    mean_excess_return_period: Decimal
    return_volatility_period: Decimal
    period_sharpe: Optional[Decimal] = None
    annualized_sharpe: Optional[Decimal] = None
    annualization_factor: Decimal
    sample_size: int
    denominator_policy: SharpeDenominatorPolicy
    status: RatioCalculationStatus
    model_config = ConfigDict(from_attributes=True)


class SortinoRatioRequest(BaseModel):
    scope: str = Field("PORTFOLIO", description="SECURITY, PORTFOLIO, or PORTFOLIO_GROUP")
    entity_id: str = Field(..., description="Instrument ID or Portfolio ID")
    risk_free_series_code: Optional[str] = Field(None, description="Risk free rate series code")
    target_policy: SortinoTargetPolicy = SortinoTargetPolicy.RISK_FREE_RATE
    constant_mar_annual: Optional[Decimal] = Field(None, description="Optional annualized MAR (e.g. 0.08 for 8%)")
    lookback_days: int = Field(60, ge=5, le=2520)
    as_of: Optional[date] = None
    denominator_policy: SortinoDenominatorPolicy = SortinoDenominatorPolicy.ALL_PERIODS_SEMIDEVIATION
    annualization_factor: Decimal = Field(Decimal("252.0"), ge=1.0, le=1000.0)


class SortinoRatioResponse(BaseModel):
    calculation_code: str
    scope: str
    entity_id: str
    as_of_date: datetime
    lookback_days: int
    currency: str
    mean_return_period: Decimal
    target_return_period: Decimal
    mean_excess_over_target_period: Decimal
    downside_deviation_period: Decimal
    period_sortino: Optional[Decimal] = None
    annualized_sortino: Optional[Decimal] = None
    annualization_factor: Decimal
    sample_size: int
    downside_periods_count: int
    downside_percentage: Decimal
    target_policy: SortinoTargetPolicy
    denominator_policy: SortinoDenominatorPolicy
    status: RatioCalculationStatus
    model_config = ConfigDict(from_attributes=True)


class CombinedRatiosRequest(BaseModel):
    scope: str = Field("PORTFOLIO", description="SECURITY, PORTFOLIO, or PORTFOLIO_GROUP")
    entity_id: str = Field(..., description="Instrument ID or Portfolio ID")
    risk_free_series_code: Optional[str] = None
    constant_mar_annual: Optional[Decimal] = None
    lookback_days: int = Field(60, ge=5, le=2520)
    as_of: Optional[date] = None
    sharpe_denominator_policy: SharpeDenominatorPolicy = SharpeDenominatorPolicy.PORTFOLIO_RETURN_VOLATILITY
    sortino_denominator_policy: SortinoDenominatorPolicy = SortinoDenominatorPolicy.ALL_PERIODS_SEMIDEVIATION
    annualization_factor: Decimal = Field(Decimal("252.0"), ge=1.0, le=1000.0)


class CombinedRatiosResponse(BaseModel):
    sharpe: SharpeRatioResponse
    sortino: SortinoRatioResponse
    model_config = ConfigDict(from_attributes=True)


class RollingRatioPoint(BaseModel):
    point_date: date
    period_sharpe: Optional[Decimal] = None
    annualized_sharpe: Optional[Decimal] = None
    period_sortino: Optional[Decimal] = None
    annualized_sortino: Optional[Decimal] = None
    volatility: Decimal
    downside_deviation: Decimal
    sample_size: int
    status: RatioCalculationStatus


class RollingRatiosRequest(BaseModel):
    scope: str = Field("PORTFOLIO", description="SECURITY or PORTFOLIO")
    entity_id: str = Field(..., description="Instrument ID or Portfolio ID")
    window_days: int = Field(30, ge=10, le=252)
    risk_free_series_code: Optional[str] = None
    constant_mar_annual: Optional[Decimal] = None
    annualization_factor: Decimal = Field(Decimal("252.0"), ge=1.0, le=1000.0)
    as_of: Optional[date] = None


class RollingRatiosResponse(BaseModel):
    scope: str
    entity_id: str
    window_days: int
    annualization_factor: Decimal
    points: List[RollingRatioPoint]
    model_config = ConfigDict(from_attributes=True)
