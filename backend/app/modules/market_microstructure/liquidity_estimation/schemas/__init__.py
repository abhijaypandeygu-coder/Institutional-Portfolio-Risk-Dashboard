"""
M09.03 Liquidity Estimation - Pydantic v2 Schemas.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class DirectTradeInput(BaseModel):
    """Direct input of a single trade execution."""
    trade_id: str
    price: Decimal = Field(..., gt=0)
    quantity: Decimal = Field(..., gt=0)
    timestamp: datetime
    status: str = Field(default="ACTIVE")


# Config Schemas
class MetricConfigRequest(BaseModel):
    config_code: str
    name: str
    market: str = "ALL"
    currency: str = "USD"
    volume_aggregation_interval: str = "1d"
    turnover_aggregation_interval: str = "1d"
    volume_lookback_sessions: int = 20
    turnover_lookback_sessions: int = 20
    minimum_coverage: float = 0.50


class MetricConfigResponse(MetricConfigRequest):
    config_id: str
    version: int
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ScoreProfileRequest(BaseModel):
    profile_code: str
    name: str
    market_scope: str = "ALL"
    currency: str = "USD"
    peer_group_definition: str = "DEFAULT_PEERS"
    spread_weight: float = 0.25
    depth_weight: float = 0.30
    turnover_weight: float = 0.30
    availability_weight: float = 0.15
    minimum_spread_coverage: float = 0.50
    minimum_depth_coverage: float = 0.50
    minimum_turnover_coverage: float = 0.50
    minimum_reference_sample_size: int = 5
    winsorization_enabled: bool = False
    winsor_lower_percentile: float = 1.0
    winsor_upper_percentile: float = 99.0


class ScoreProfileResponse(ScoreProfileRequest):
    profile_id: str
    version: int
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class BucketPolicyRequest(BaseModel):
    policy_code: str
    name: str
    classification_method: str = "SCORE_THRESHOLD"
    market_scope: str = "ALL"
    threshold_definitions: List[Dict[str, Any]]


class BucketPolicyResponse(BucketPolicyRequest):
    policy_id: str
    version: int
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# Aggregates & Calculations
class VolumeAggregateResponse(BaseModel):
    aggregate_id: str
    instrument_id: str
    listing_id: Optional[str] = None
    exchange: str
    venue: str
    aggregation_start: datetime
    aggregation_end: datetime
    aggregation_interval: str
    traded_volume: Decimal
    eligible_trade_count: int
    valid_coverage_ratio: float
    quality_status: str
    model_config = ConfigDict(from_attributes=True)


class TurnoverAggregateResponse(BaseModel):
    aggregate_id: str
    instrument_id: str
    listing_id: Optional[str] = None
    exchange: str
    venue: str
    aggregation_start: datetime
    aggregation_end: datetime
    aggregation_interval: str
    turnover_amount: Decimal
    currency: str
    eligible_trade_count: int
    valid_coverage_ratio: float
    quality_status: str
    model_config = ConfigDict(from_attributes=True)


class RollingStatisticsResponse(BaseModel):
    instrument_id: str
    venue: str
    as_of_timestamp: datetime
    lookback_sessions: int
    eligible_session_count: int
    coverage_ratio: float
    average_daily_volume: Optional[Decimal] = None
    median_daily_volume: Optional[Decimal] = None
    volume_stddev: Optional[Decimal] = None
    volume_cv: Optional[float] = None
    volume_percentiles: Optional[Dict[str, Any]] = None
    average_daily_turnover: Optional[Decimal] = None
    median_daily_turnover: Optional[Decimal] = None
    turnover_stddev: Optional[Decimal] = None
    turnover_cv: Optional[float] = None
    turnover_percentiles: Optional[Dict[str, Any]] = None
    currency: str
    intraday_volume_pace: Optional[float] = None
    intraday_turnover_pace: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)


class DirectCalculationRequest(BaseModel):
    """Direct request to calculate liquidity score and bucket without persistence."""
    instrument_id: str
    exchange: str = "NSE"
    venue: str = "NSE_CASH"
    currency: str = "USD"
    spread_bps: Optional[float] = None
    depth_notional: Optional[Decimal] = None
    turnover_amount: Optional[Decimal] = None
    spread_coverage: Optional[float] = 1.0
    depth_coverage: Optional[float] = 1.0
    turnover_coverage: Optional[float] = 1.0
    # Reference population arrays
    peer_spreads: List[float] = Field(default_factory=list)
    peer_depths: List[float] = Field(default_factory=list)
    peer_turnovers: List[float] = Field(default_factory=list)
    weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "spread_weight": 0.25,
            "depth_weight": 0.30,
            "turnover_weight": 0.30,
            "availability_weight": 0.15
        }
    )


class LiquidityScoreResponse(BaseModel):
    snapshot_id: Optional[str] = None
    instrument_id: str
    as_of_timestamp: datetime
    composite_liquidity_score: Optional[float] = None
    scoring_status: str
    status_reason: Optional[str] = None
    spread_subscore: Optional[float] = None
    depth_subscore: Optional[float] = None
    turnover_subscore: Optional[float] = None
    availability_subscore: Optional[float] = None
    spread_contribution: Optional[float] = None
    depth_contribution: Optional[float] = None
    turnover_contribution: Optional[float] = None
    availability_contribution: Optional[float] = None
    spread_raw_value: Optional[float] = None
    depth_raw_value: Optional[Decimal] = None
    turnover_raw_value: Optional[Decimal] = None
    currency: str = "USD"
    model_config = ConfigDict(from_attributes=True)


class LiquidityBucketResponse(BaseModel):
    instrument_id: str
    as_of_timestamp: datetime
    bucket_name: str
    bucket_rank: int
    underlying_score: Optional[float] = None
    peer_group_percentile: Optional[float] = None
    classification_status: str
    classification_reason: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class LiquidityOverviewResponse(BaseModel):
    instrument_id: str
    exchange: str
    venue: str
    currency: str
    current_traded_volume: Optional[Decimal] = None
    current_turnover: Optional[Decimal] = None
    average_daily_volume: Optional[Decimal] = None
    average_daily_turnover: Optional[Decimal] = None
    spread_bps: Optional[float] = None
    depth_notional: Optional[Decimal] = None
    composite_score: Optional[float] = None
    liquidity_bucket: str
    scoring_status: str
    as_of_timestamp: datetime


class LiquidityScreenRequest(BaseModel):
    market: Optional[str] = None
    venue: Optional[str] = None
    min_score: Optional[float] = None
    max_score: Optional[float] = None
    bucket: Optional[str] = None
    min_adv: Optional[Decimal] = None
    min_adtv: Optional[Decimal] = None
    max_spread_bps: Optional[float] = None
    min_depth_notional: Optional[Decimal] = None
    limit: int = 50
    offset: int = 0
