"""
Pydantic schemas for M11.04 Liquidity Limits.
Conforms strictly to Pydantic v2.0 conventions.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class LiquidityLimitConfigCreate(BaseModel):
    limit_code: str = Field(..., max_length=64)
    limit_name: str = Field(..., max_length=128)
    description: Optional[str] = None
    portfolio_id: Optional[str] = None
    instrument_id: Optional[str] = None
    profile_id: Optional[str] = None
    limit_type: str = Field(..., description="MIN_LIQUIDITY_SCORE, MIN_DISPLAYED_DEPTH, MIN_DAILY_VOLUME, MIN_DAILY_TURNOVER, MAX_SPREAD_BPS, MAX_LIQUIDATION_COST, MAX_LIQUIDATION_HORIZON, MAX_PARTICIPATION_RATE")
    metric_name: str = Field(..., description="score, depth, adv, adtv, spread_bps, cost, horizon_days, participation_rate")
    minimum_threshold: Optional[Decimal] = None
    maximum_threshold: Optional[Decimal] = None
    warning_threshold: Optional[Decimal] = None
    threshold_unit: str = "POINTS"
    threshold_currency: str = "USD"
    participation_rate: Decimal = Decimal("0.1000")
    lookback_sessions: int = 20
    horizon_unit: str = "TRADING_DAYS"
    cost_methodology: str = "ALL_IN_SLIPPAGE"
    is_stress_limit: bool = False
    stress_scenario_id: Optional[str] = None
    precedence: int = 1
    created_by: str = "risk_admin"


class LiquidityLimitConfigResponse(LiquidityLimitConfigCreate):
    id: str
    status: str
    approval_status: str
    version: int
    effective_from: datetime
    effective_to: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LiquidityProfileCreate(BaseModel):
    profile_code: str = Field(..., max_length=64)
    profile_name: str = Field(..., max_length=128)
    description: Optional[str] = None
    profile_tier: str = "STANDARD"
    base_currency: str = "USD"
    created_by: str = "risk_admin"
    initial_limits: Optional[List[LiquidityLimitConfigCreate]] = None


class LiquidityProfileResponse(BaseModel):
    id: str
    profile_code: str
    profile_name: str
    description: Optional[str] = None
    profile_tier: str
    base_currency: str
    status: str
    is_active: bool
    created_by: str
    created_at: datetime
    updated_at: datetime
    configurations: List[LiquidityLimitConfigResponse] = []

    model_config = ConfigDict(from_attributes=True)


class LiquidityAssignmentCreate(BaseModel):
    profile_id: str
    target_type: str = "PORTFOLIO"
    target_id: str
    precedence: int = 1
    assigned_by: str = "risk_admin"
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None


class LiquidityAssignmentResponse(LiquidityAssignmentCreate):
    id: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PositionLiquidityInput(BaseModel):
    instrument_id: str
    position_side: str = "LONG"  # LONG or SHORT
    quantity: Decimal
    market_value: Decimal
    currency: str = "USD"
    liquidity_score: Optional[Decimal] = None
    bid_depth: Optional[Decimal] = None
    ask_depth: Optional[Decimal] = None
    adv: Optional[Decimal] = None
    adtv: Optional[Decimal] = None
    spread_bps: Optional[Decimal] = None
    estimated_liquidation_cost: Optional[Decimal] = None
    daily_volumes: Optional[List[Decimal]] = None


class StressedParametersInput(BaseModel):
    scenario_id: str = "HYPO_CRASH_2026"
    volume_contraction_pct: Decimal = Decimal("40.0")
    depth_reduction_pct: Decimal = Decimal("30.0")
    spread_widening_pct: Decimal = Decimal("50.0")
    participation_reduction_pct: Decimal = Decimal("20.0")


class LiquidityEvaluationRequest(BaseModel):
    portfolio_id: str
    portfolio_nav: Decimal
    base_currency: str = "USD"
    positions: List[PositionLiquidityInput] = []
    evaluation_type: str = "PORTFOLIO_WIDE"
    evaluator: str = "system"
    stress_parameters: Optional[StressedParametersInput] = None


class PositionEvaluationResultItem(BaseModel):
    limit_id: Optional[str] = None
    limit_code: str
    limit_type: str
    instrument_id: str
    position_side: str
    position_quantity: Decimal
    position_notional: Decimal
    actual_value: Optional[Decimal] = None
    liquidity_score: Optional[Decimal] = None
    available_depth: Optional[Decimal] = None
    adv: Optional[Decimal] = None
    spread_bps: Optional[Decimal] = None
    estimated_liquidation_cost: Optional[Decimal] = None
    estimated_horizon_days: Optional[Decimal] = None
    participation_rate: Decimal
    threshold_value: Decimal
    warning_threshold: Optional[Decimal] = None
    threshold_unit: str
    utilization_pct: Optional[Decimal] = None
    headroom_or_capacity: Optional[Decimal] = None
    breach_amount: Decimal
    evaluation_status: str
    quality_status: str
    details: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)


class LiquidityEvaluationResponse(BaseModel):
    id: str
    portfolio_id: str
    evaluation_type: str
    evaluation_timestamp: datetime
    portfolio_nav: Decimal
    base_currency: str
    total_positions_evaluated: int
    total_liquidation_cost: Decimal
    max_liquidation_horizon_days: Decimal
    overall_status: str
    warning_breaches_count: int
    hard_breaches_count: int
    unavailable_count: int
    execution_duration_ms: int
    results: List[PositionEvaluationResultItem] = []

    model_config = ConfigDict(from_attributes=True)


class ProposedOrderLiquidityRequest(BaseModel):
    portfolio_id: str
    instrument_id: str
    order_side: str  # BUY or SELL
    proposed_quantity: Decimal
    current_quantity: Decimal = Decimal("0.0")
    adv: Optional[Decimal] = None
    participation_rate: Decimal = Decimal("0.1000")
    estimated_cost_per_share: Decimal = Decimal("0.0")
    max_horizon_days_limit: Optional[Decimal] = None
    max_cost_limit: Optional[Decimal] = None


class ProposedOrderLiquidityResponse(BaseModel):
    portfolio_id: str
    instrument_id: str
    order_side: str
    proposed_quantity: Decimal
    current_quantity: Decimal
    projected_quantity: Decimal
    projected_side: str
    projected_horizon_days: Optional[Decimal] = None
    projected_cost: Decimal
    evaluation_status: str
    reason: Optional[str] = None

