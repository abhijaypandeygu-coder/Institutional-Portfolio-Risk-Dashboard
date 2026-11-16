"""
Pydantic schemas for M12.03 Liquidity Alerts.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class LiquidityAlertRuleCreate(BaseModel):
    rule_code: str = Field(..., max_length=64)
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    rule_type: str = Field(..., description="SPREAD_WIDENING, DEPTH_DETERIORATION, LIQUIDITY_SCORE, LIQUIDATION_COST, LIQUIDATION_HORIZON")
    metric_type: str = Field(..., description="SPREAD_BPS, BID_DEPTH, ASK_DEPTH, COMPOSITE_SCORE, LIQUIDATION_COST_BPS, LIQUIDATION_TIME_MINUTES")
    market: str = Field(default="INDIA")
    exchange: Optional[str] = None
    instrument_id: Optional[str] = None
    listing_id: Optional[str] = None
    portfolio_id: Optional[str] = None
    observation_horizon_seconds: int = Field(default=300)
    baseline_window_seconds: int = Field(default=86400 * 10)
    threshold_value: Decimal = Field(...)
    threshold_unit: str = Field(default="BPS")
    persistence_seconds: int = Field(default=60)
    minimum_observations: int = Field(default=3)
    minimum_coverage: Decimal = Field(default=Decimal("0.8000"))
    cooldown_seconds: int = Field(default=300)
    recovery_threshold: Optional[Decimal] = None
    created_by: str = Field(default="SYSTEM")


class LiquidityAlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    threshold_value: Optional[Decimal] = None
    threshold_unit: Optional[str] = None
    observation_horizon_seconds: Optional[int] = None
    cooldown_seconds: Optional[int] = None
    recovery_threshold: Optional[Decimal] = None
    enabled: Optional[bool] = None
    change_reason: str = Field(default="Rule update")
    changed_by: str = Field(default="SYSTEM")


class LiquidityAlertRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    rule_code: str
    name: str
    description: Optional[str]
    rule_type: str
    metric_type: str
    market: str
    exchange: Optional[str]
    instrument_id: Optional[str]
    listing_id: Optional[str]
    portfolio_id: Optional[str]
    observation_horizon_seconds: int
    baseline_window_seconds: int
    threshold_value: Decimal
    threshold_unit: str
    persistence_seconds: int
    minimum_observations: int
    minimum_coverage: Decimal
    cooldown_seconds: int
    recovery_threshold: Optional[Decimal]
    enabled: bool
    created_at: datetime
    created_by: str


class SpreadEvaluationRequest(BaseModel):
    rule_code: str
    instrument_id: str
    listing_id: Optional[str] = None
    exchange: str
    market: str = "INDIA"
    best_bid: Decimal
    best_ask: Decimal
    baseline_spread_bps: Optional[Decimal] = None
    historical_spreads_bps: Optional[List[Decimal]] = None
    event_timestamp: datetime
    quality_state: str = "VALID"
    source_feed_id: str = "FEED_PRIMARY"


class DepthEvaluationRequest(BaseModel):
    rule_code: str
    instrument_id: str
    listing_id: Optional[str] = None
    exchange: str
    market: str = "INDIA"
    depth_side: str = Field(..., description="BID or ASK")
    current_depth: Decimal
    baseline_depth: Decimal
    event_timestamp: datetime
    quality_state: str = "VALID"
    source_feed_id: str = "FEED_PRIMARY"


class LiquidityScoreEvaluationRequest(BaseModel):
    rule_code: str
    instrument_id: str
    exchange: str
    market: str = "INDIA"
    current_score: Decimal
    baseline_score: Optional[Decimal] = None
    methodology_version: str = "M09.03_v1"
    components_json: Dict[str, Any] = Field(default_factory=dict)
    event_timestamp: datetime
    quality_state: str = "VALID"


class LiquidationRiskEvaluationRequest(BaseModel):
    rule_code: str
    instrument_id: str
    exchange: str
    market: str = "INDIA"
    position_direction: str = "LONG"
    position_quantity: Decimal
    estimated_liquidation_cost: Optional[Decimal] = None
    estimated_liquidation_cost_unit: str = "BPS"
    baseline_cost: Optional[Decimal] = None
    estimated_liquidation_horizon_minutes: Optional[Decimal] = None
    baseline_horizon_minutes: Optional[Decimal] = None
    event_timestamp: datetime
    quality_state: str = "VALID"


class LiquidityEvidenceResponse(BaseModel):
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


class LiquidityPortfolioImpactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    portfolio_id: str
    instrument_id: str
    listing_id: Optional[str]
    position_quantity: Decimal
    position_direction: str
    affected_liquidity_side: str
    estimated_liquidation_cost: Optional[Decimal]
    estimated_liquidation_cost_unit: str
    estimated_liquidation_horizon: Optional[Decimal]
    mapping_status: str
    effective_timestamp: datetime


class LiquidityAlertEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_code: str
    event_type: str
    instrument_id: str
    listing_id: Optional[str]
    market: str
    exchange: Optional[str]
    metric_type: str
    direction: str
    detected_at: datetime
    first_observed_at: datetime
    last_observed_at: datetime
    event_state: str
    event_fingerprint: str
    evidence_summary: str
    source_metric_reference: str
    evidence_items: List[LiquidityEvidenceResponse] = Field(default_factory=list)
    portfolio_impacts: List[LiquidityPortfolioImpactResponse] = Field(default_factory=list)


class LiquidityOverviewResponse(BaseModel):
    market: str
    active_liquidity_alerts_count: int
    spread_deterioration_count: int
    depth_deterioration_count: int
    score_deterioration_count: int
    liquidation_risk_count: int
    feed_coverage_ratio: Decimal
    timestamp: datetime


class LiquidityReviewLabelCreate(BaseModel):
    review_label: str = Field(..., description="VALID_LIQUIDITY_DETERIORATION, FALSE_POSITIVE, DATA_QUALITY_ISSUE, DUPLICATE, INSUFFICIENT_EVIDENCE")
    review_comment: Optional[str] = None
    reviewed_by: str = Field(default="RISK_ANALYST")

