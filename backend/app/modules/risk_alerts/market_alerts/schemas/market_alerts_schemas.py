"""
Pydantic schemas for M12.02 Market Alerts.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class MarketAlertRuleCreate(BaseModel):
    rule_code: str = Field(..., max_length=64)
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    rule_type: str = Field(..., description="ABNORMAL_PRICE_MOVEMENT, HISTORICAL_DEVIATION, MARKET_BAND, VOLATILITY_SPIKE, TRADING_HALT, MARKET_WIDE")
    market: str = Field(default="INDIA")
    exchange: Optional[str] = None
    instrument_id: Optional[str] = None
    listing_id: Optional[str] = None
    portfolio_id: Optional[str] = None
    observation_horizon_seconds: int = Field(default=900)
    reference_window_seconds: int = Field(default=86400 * 20)
    threshold_value: Decimal = Field(...)
    threshold_unit: str = Field(default="PERCENT")
    percentile_threshold: Optional[Decimal] = None
    persistence_seconds: int = Field(default=0)
    minimum_observations: int = Field(default=5)
    minimum_coverage: Decimal = Field(default=Decimal("0.8000"))
    cooldown_seconds: int = Field(default=300)
    recovery_threshold: Optional[Decimal] = None
    created_by: str = Field(default="SYSTEM")


class MarketAlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    threshold_value: Optional[Decimal] = None
    threshold_unit: Optional[str] = None
    percentile_threshold: Optional[Decimal] = None
    observation_horizon_seconds: Optional[int] = None
    cooldown_seconds: Optional[int] = None
    recovery_threshold: Optional[Decimal] = None
    enabled: Optional[bool] = None
    change_reason: str = Field(default="Rule update")
    changed_by: str = Field(default="SYSTEM")


class MarketAlertRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    rule_code: str
    name: str
    description: Optional[str]
    rule_type: str
    market: str
    exchange: Optional[str]
    instrument_id: Optional[str]
    listing_id: Optional[str]
    portfolio_id: Optional[str]
    observation_horizon_seconds: int
    reference_window_seconds: int
    threshold_value: Decimal
    threshold_unit: str
    percentile_threshold: Optional[Decimal]
    persistence_seconds: int
    minimum_observations: int
    minimum_coverage: Decimal
    cooldown_seconds: int
    recovery_threshold: Optional[Decimal]
    enabled: bool
    created_at: datetime
    created_by: str


class PriceObservationInput(BaseModel):
    instrument_id: str
    listing_id: Optional[str] = None
    exchange: str
    market: str = "INDIA"
    price_type: str = "LAST"
    price_value: Decimal
    currency: str = "INR"
    event_timestamp: datetime
    source_feed_id: str = "FEED_PRIMARY"
    source_event_id: Optional[str] = None
    quality_state: str = "VALID"
    session_id: Optional[str] = None
    source_metadata: Dict[str, Any] = Field(default_factory=dict)


class PriceMovementEvaluationRequest(BaseModel):
    rule_code: str
    observation: PriceObservationInput
    reference_price: Decimal
    historical_returns_pct: Optional[List[Decimal]] = None
    corporate_action_adjusted: bool = True


class VolatilityEvaluationRequest(BaseModel):
    rule_code: str
    instrument_id: str
    exchange: str
    market: str = "INDIA"
    interval_returns: List[Decimal]
    baseline_rv: Decimal
    annualization_factor: Decimal = Decimal("252.0")
    source_event_timestamp: datetime
    source_feed_id: str = "FEED_PRIMARY"


class MarketBandEvaluationRequest(BaseModel):
    rule_code: str
    observation: PriceObservationInput
    reference_price: Decimal
    band_pct: Optional[Decimal] = None
    volatility: Optional[Decimal] = None
    multiplier_k: Decimal = Decimal("2.0")
    official_upper_band: Optional[Decimal] = None
    official_lower_band: Optional[Decimal] = None


class TradingStatusEventRequest(BaseModel):
    instrument_id: str
    listing_id: Optional[str] = None
    exchange: str
    market: str = "INDIA"
    source_status_code: str
    normalized_status: str = Field(..., description="HALTED, SUSPENDED, RESUMED, AUCTION_ONLY, RESTRICTED")
    halt_reason: Optional[str] = None
    event_timestamp: datetime
    expected_resumption_timestamp: Optional[datetime] = None
    source_feed_id: str = "FEED_PRIMARY"
    source_event_id: Optional[str] = None
    quality_state: str = "VALID"


class MarketWideEventRequest(BaseModel):
    market: str = "INDIA"
    index_instrument_id: Optional[str] = None
    index_return: Optional[Decimal] = None
    advancing_count: int = 0
    declining_count: int = 0
    unchanged_count: int = 0
    downside_anomalies: int = 0
    upside_anomalies: int = 0
    eligible_universe: int = 50
    expected_universe: int = 50
    event_timestamp: datetime
    source_feed_id: str = "FEED_PRIMARY"


class MarketEventEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    evidence_type: str
    metric_name: str
    observed_value: Decimal
    reference_value: Optional[Decimal]
    threshold_value: Optional[Decimal]
    unit: str
    source_reference: Optional[str]
    quality_state: str
    evidence_timestamp: datetime
    evidence_json: Dict[str, Any]


class MarketEventPortfolioImpactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    portfolio_id: str
    instrument_id: str
    listing_id: Optional[str]
    position_quantity: Decimal
    position_direction: str
    movement_direction: str
    directional_impact: str
    exposure_reference: Optional[Decimal]
    mapping_status: str
    effective_timestamp: datetime


class MarketEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_code: str
    event_type: str
    event_scope: str
    market: str
    exchange: Optional[str]
    instrument_id: Optional[str]
    listing_id: Optional[str]
    index_instrument_id: Optional[str]
    direction: str
    detected_at: datetime
    source_event_timestamp: datetime
    last_observed_at: datetime
    event_state: str
    event_fingerprint: str
    coverage_ratio: Decimal
    evidence_summary: str
    evidence_items: List[MarketEventEvidenceResponse] = Field(default_factory=list)
    portfolio_impacts: List[MarketEventPortfolioImpactResponse] = Field(default_factory=list)


class ReviewLabelCreate(BaseModel):
    review_label: str = Field(..., description="VALID_EVENT, FALSE_POSITIVE, DATA_QUALITY_ISSUE, DUPLICATE, INSUFFICIENT_EVIDENCE")
    review_comment: Optional[str] = None
    reviewed_by: str = Field(default="ANALYST")


class MarketOverviewResponse(BaseModel):
    market: str
    active_events_count: int
    halts_count: int
    volatility_spikes_count: int
    price_anomalies_count: int
    market_wide_events_count: int
    feed_coverage_ratio: Decimal
    data_quality_summary: Dict[str, int]
    timestamp: datetime
