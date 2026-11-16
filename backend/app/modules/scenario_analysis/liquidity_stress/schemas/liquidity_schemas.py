"""
M10.06 Liquidity Stress Testing Pydantic Schemas.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from backend.app.modules.scenario_analysis.liquidity_stress.models import (
    ScenarioCategory,
    ScenarioStatus,
    RunStatus,
)


class InstrumentOverrideCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    listing_id: Optional[str] = None
    spread_widening_override_pct: Optional[Decimal] = None
    depth_multiplier_override: Optional[Decimal] = None
    volume_multiplier_override: Optional[Decimal] = None
    participation_cap_override: Optional[Decimal] = None
    override_metadata: Optional[Dict[str, Any]] = None


class InstrumentOverrideResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    instrument_id: str
    listing_id: Optional[str] = None
    spread_widening_override_pct: Optional[Decimal] = None
    depth_multiplier_override: Optional[Decimal] = None
    volume_multiplier_override: Optional[Decimal] = None
    participation_cap_override: Optional[Decimal] = None


class LiquidityStressScenarioCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scenario_code: str = Field(..., max_length=64)
    name: str = Field(..., max_length=128)
    description: Optional[str] = None
    scenario_category: ScenarioCategory = ScenarioCategory.SEVERE_LIQUIDITY_DETERIORATION
    
    # Stress Configuration Parameters
    spread_stress_type: str = "PERCENTAGE"
    spread_increase_pct: Decimal = Field(Decimal("2.0000"), description="200% widening (3x baseline)")
    spread_multiplier: Decimal = Field(Decimal("3.0000"), description="3x multiplier")
    absolute_spread_change: Optional[Decimal] = None
    
    bid_depth_multiplier: Decimal = Field(Decimal("0.4000"), description="60% reduction -> 40% remaining")
    ask_depth_multiplier: Decimal = Field(Decimal("0.4000"), description="60% reduction -> 40% remaining")
    depth_stress_profile: str = "UNIFORM"
    
    market_volume_multiplier: Decimal = Field(Decimal("0.5000"), description="50% volume contraction")
    participation_multiplier: Decimal = Field(Decimal("0.5000"), description="50% reduction in participation cap")
    base_participation_cap: Decimal = Field(Decimal("0.1000"), description="Baseline 10% participation cap")
    
    impact_multiplier: Decimal = Field(Decimal("1.5000"), description="1.5x market impact multiplier")
    execution_horizon_sessions: int = Field(5, description="Horizon in trading sessions")
    market_price_shock_pct: Decimal = Field(Decimal("0.0000"), description="Simultaneous market crash shock e.g. -0.20")
    
    overrides: Optional[List[InstrumentOverrideCreate]] = None
    created_by: Optional[str] = "risk_manager"


class LiquidityStressScenarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    scenario_code: str
    name: str
    description: Optional[str] = None
    scenario_category: ScenarioCategory
    status: ScenarioStatus
    version: int
    parent_scenario_id: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    # Latest Configuration Summary
    spread_increase_pct: Decimal
    bid_depth_multiplier: Decimal
    ask_depth_multiplier: Decimal
    market_volume_multiplier: Decimal
    participation_multiplier: Decimal
    impact_multiplier: Decimal
    execution_horizon_sessions: int


class ExecuteLiquidityStressRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str = Field(..., description="Target portfolio identifier")
    baseline_snapshot_id: Optional[str] = None
    executed_by: Optional[str] = "lead_risk_officer"
    
    # Optional ad-hoc position inputs for testing / simulation
    custom_positions: Optional[List[Dict[str, Any]]] = None
    # Each item: {"instrument_id": str, "symbol": str, "quantity": Decimal, "price": Decimal, "bid": Decimal, "ask": Decimal, "depth": Decimal, "volume": Decimal}


class PositionResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    symbol: str
    signed_position_quantity: Decimal
    liquidation_side: str
    market_value: Decimal
    baseline_capacity: Decimal
    stressed_capacity: Decimal
    baseline_duration_sessions: Decimal
    stressed_duration_sessions: Decimal
    baseline_liquidation_cost: Decimal
    stressed_liquidation_cost: Decimal
    incremental_liquidation_cost: Decimal
    baseline_cost_bps: Decimal
    stressed_cost_bps: Decimal
    residual_quantity: Decimal
    residual_market_value: Decimal
    completion_status: str


class HorizonResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    horizon_type: str
    horizon_minutes: int
    cumulative_executed_quantity: Decimal
    residual_quantity: Decimal
    liquidation_ratio: Decimal
    estimated_cost: Decimal
    estimated_cost_bps: Decimal
    completion_status: str


class CostAttributionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cost_component: str
    baseline_cost: Decimal
    stressed_cost: Decimal
    incremental_cost: Decimal
    attribution_method: str


class LiquidityStressRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    run_code: str
    scenario_id: str
    scenario_version: int
    portfolio_id: str
    status: RunStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    execution_duration_ms: int
    
    # Portfolio Aggregate Metrics
    baseline_portfolio_notional: Decimal
    stressed_portfolio_notional: Decimal
    baseline_total_cost: Decimal
    stressed_total_cost: Decimal
    incremental_cost: Decimal
    baseline_cost_bps: Decimal
    stressed_cost_bps: Decimal
    
    baseline_duration_sessions: Decimal
    stressed_duration_sessions: Decimal
    portfolio_liquidation_ratio: Decimal
    residual_market_value: Decimal
    unliquidated_positions_count: int
    
    position_results: List[PositionResultResponse] = []
    horizon_results: List[HorizonResultResponse] = []
    cost_attributions: List[CostAttributionResponse] = []
    narrative: str
