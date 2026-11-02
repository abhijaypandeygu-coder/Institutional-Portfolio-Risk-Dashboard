"""
Module M07.04: Drawdown Analytics Schemas.
Pydantic v2 validation models for:
- Current Drawdown Response
- Maximum Drawdown Response
- Drawdown Episodes Response
- Drawdown History Time Series
- Recovery Statistics
- Lookback Window Comparisons
- Config CRUD
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from backend.app.modules.market_risk.drawdown_analytics.models import (
    DrawdownScopeType,
    DrawdownValueSeriesType,
    HighWaterMarkPolicy,
    DrawdownEpisodeStatus,
    CurrentDrawdownStatus,
)


class DrawdownConfigCreateRequest(BaseModel):
    config_name: str = Field(..., max_length=128)
    scope_type: DrawdownScopeType = DrawdownScopeType.PORTFOLIO
    portfolio_id: Optional[str] = None
    portfolio_group_id: Optional[str] = None
    instrument_id: Optional[str] = None
    listing_id: Optional[str] = None
    value_series_type: DrawdownValueSeriesType = DrawdownValueSeriesType.PORTFOLIO_NAV_SERIES
    high_water_mark_policy: HighWaterMarkPolicy = HighWaterMarkPolicy.FULL_HISTORY_HIGH_WATER_MARK
    reporting_currency: str = Field(default="USD", max_length=3)
    recovery_tolerance: Decimal = Decimal("0.00000001")


class DrawdownConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    config_id: str
    config_name: str
    scope_type: DrawdownScopeType
    portfolio_id: Optional[str] = None
    portfolio_group_id: Optional[str] = None
    instrument_id: Optional[str] = None
    listing_id: Optional[str] = None
    value_series_type: DrawdownValueSeriesType
    high_water_mark_policy: HighWaterMarkPolicy
    reporting_currency: str
    recovery_tolerance: Decimal
    is_active: bool
    config_version: int
    created_at: datetime


class CurrentDrawdownResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scope_type: DrawdownScopeType
    portfolio_id: Optional[str] = None
    portfolio_group_id: Optional[str] = None
    instrument_id: Optional[str] = None
    latest_value: Decimal
    latest_observation_timestamp: datetime
    running_high_water_mark: Decimal
    high_water_mark_timestamp: datetime
    current_drawdown_amount: Decimal
    current_signed_drawdown: Decimal
    current_drawdown_percentage: Decimal
    days_since_peak: int
    current_status: CurrentDrawdownStatus
    current_episode_id: Optional[str] = None
    reporting_currency: str
    data_quality_status: str


class MaximumDrawdownResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scope_type: DrawdownScopeType
    portfolio_id: Optional[str] = None
    portfolio_group_id: Optional[str] = None
    instrument_id: Optional[str] = None
    lookback_window_name: str
    lookback_start: datetime
    lookback_end: datetime

    maximum_drawdown_percentage: Decimal
    signed_maximum_drawdown: Decimal
    maximum_drawdown_amount: Decimal

    peak_episode_id: Optional[str] = None
    peak_value: Decimal
    peak_timestamp: datetime
    trough_value: Decimal
    trough_timestamp: datetime
    recovery_timestamp: Optional[datetime] = None

    peak_to_trough_days: int
    trough_to_recovery_days: Optional[int] = None
    underwater_duration_days: int
    recovery_status: DrawdownEpisodeStatus
    reporting_currency: str
    data_quality_status: str


class DrawdownEpisodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    episode_id: str
    series_id: str
    scope_type: DrawdownScopeType
    portfolio_id: Optional[str] = None
    portfolio_group_id: Optional[str] = None
    instrument_id: Optional[str] = None

    peak_value: Decimal
    peak_timestamp: datetime
    trough_value: Decimal
    trough_timestamp: datetime
    recovery_value: Optional[Decimal] = None
    recovery_timestamp: Optional[datetime] = None

    drawdown_percentage: Decimal
    signed_drawdown: Decimal
    absolute_drawdown_amount: Decimal

    peak_to_trough_days: int
    trough_to_recovery_days: Optional[int] = None
    underwater_duration_days: int
    trading_sessions_count: int
    observation_count: int
    episode_status: DrawdownEpisodeStatus
    as_of_timestamp: datetime


class DrawdownSeriesPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    observation_timestamp: datetime
    observation_date: date
    selected_value: Decimal
    running_high_water_mark: Decimal
    high_water_mark_timestamp: datetime
    signed_drawdown: Decimal
    drawdown_percentage: Decimal
    absolute_drawdown_amount: Decimal
    episode_id: Optional[str] = None
    episode_status: Optional[str] = None


class DrawdownHistoryResponse(BaseModel):
    series_id: str
    scope_type: DrawdownScopeType
    portfolio_id: Optional[str] = None
    instrument_id: Optional[str] = None
    reporting_currency: str
    data_points: List[DrawdownSeriesPoint]
    total_observations: int


class RecoveryStatisticsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    series_id: str
    portfolio_id: Optional[str] = None
    instrument_id: Optional[str] = None
    total_episodes_count: int
    completed_episodes_count: int
    ongoing_episodes_count: int

    average_recovery_days: Optional[Decimal] = None
    median_recovery_days: Optional[Decimal] = None
    longest_recovery_days: Optional[int] = None
    shortest_recovery_days: Optional[int] = None

    average_peak_to_trough_days: Decimal
    average_underwater_days: Decimal
    longest_underwater_days: int
    as_of_date: date


class DrawdownLookbackComparisonItem(BaseModel):
    window_name: str
    lookback_days: int
    maximum_drawdown_percentage: Decimal
    maximum_drawdown_amount: Decimal
    peak_timestamp: datetime
    trough_timestamp: datetime
    recovery_timestamp: Optional[datetime] = None
    recovery_status: DrawdownEpisodeStatus
    peak_to_trough_days: int
    underwater_duration_days: int


class DrawdownLookbackComparisonResponse(BaseModel):
    series_id: str
    scope_type: DrawdownScopeType
    portfolio_id: Optional[str] = None
    instrument_id: Optional[str] = None
    reporting_currency: str
    as_of_date: date
    current_drawdown_percentage: Decimal
    windows: List[DrawdownLookbackComparisonItem]


class DrawdownSummaryResponse(BaseModel):
    series_id: str
    scope_type: DrawdownScopeType
    portfolio_id: Optional[str] = None
    portfolio_group_id: Optional[str] = None
    instrument_id: Optional[str] = None
    reporting_currency: str
    latest_value: Decimal
    running_high_water_mark: Decimal
    current_drawdown_percentage: Decimal
    current_drawdown_amount: Decimal
    current_status: CurrentDrawdownStatus
    maximum_drawdown_percentage: Decimal
    maximum_drawdown_amount: Decimal
    maximum_drawdown_peak_date: datetime
    maximum_drawdown_trough_date: datetime
    maximum_drawdown_recovery_date: Optional[datetime] = None
    total_episodes_count: int
    completed_episodes_count: int
    ongoing_episodes_count: int
    average_recovery_days: Optional[Decimal] = None
    longest_underwater_days: int
    data_quality_status: str

