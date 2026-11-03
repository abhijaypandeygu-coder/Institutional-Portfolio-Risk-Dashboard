"""
Pydantic schemas for M09.06 Liquidity Stress Testing.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


# -------------------------------------------------------------------------
# Scenario Configuration Schemas
# -------------------------------------------------------------------------
class StressConfigCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scenario_code: str = Field(..., json_schema_extra={"example": "MODERATE_STRESS"})
    version: int = Field(1, json_schema_extra={"example": 1})
    name: str = Field(..., json_schema_extra={"example": "Moderate Market Stress Policy"})
    description: Optional[str] = Field(None, json_schema_extra={"example": "50% wider spread, 25% depth cut, 20% volume drop"})
    scenario_type: str = Field("COMBINED_STRESS", json_schema_extra={"example": "COMBINED_STRESS"})
    
    spread_shock_method: str = Field("MULTIPLIER", json_schema_extra={"example": "MULTIPLIER"})
    spread_multiplier: Decimal = Field(Decimal("1.50"), json_schema_extra={"example": "1.50"})
    spread_additive_bps: Decimal = Field(Decimal("0.0"), json_schema_extra={"example": "0.0"})
    
    depth_shock_method: str = Field("UNIFORM", json_schema_extra={"example": "UNIFORM"})
    bid_depth_reduction: Decimal = Field(Decimal("0.25"), json_schema_extra={"example": "0.25"})
    ask_depth_reduction: Decimal = Field(Decimal("0.25"), json_schema_extra={"example": "0.25"})
    
    volume_shock_method: str = Field("UNIFORM", json_schema_extra={"example": "UNIFORM"})
    volume_contraction: Decimal = Field(Decimal("0.20"), json_schema_extra={"example": "0.20"})
    participation_rate: Decimal = Field(Decimal("0.10"), json_schema_extra={"example": "0.10"})
    
    execution_horizon_intervals: int = Field(20, json_schema_extra={"example": 20})
    is_active: bool = Field(True, json_schema_extra={"example": True})


class StressConfigResponse(StressConfigCreate):
    id: int
    created_at: datetime


# -------------------------------------------------------------------------
# Synthetic Stressed Book Schemas
# -------------------------------------------------------------------------
class BookLevelSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    price: Decimal
    quantity: Decimal
    notional: Optional[Decimal] = None


class SyntheticStressBookResponse(BaseModel):
    baseline_midpoint: Decimal
    stressed_midpoint: Decimal
    baseline_spread: Decimal
    stressed_spread: Decimal
    bids: List[BookLevelSchema]
    asks: List[BookLevelSchema]
    total_bid_depth: Decimal
    total_ask_depth: Decimal
    total_bid_notional: Decimal
    total_ask_notional: Decimal


# -------------------------------------------------------------------------
# Stress Test Execution Request & Response
# -------------------------------------------------------------------------
class StressRunRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str = Field(..., json_schema_extra={"example": "RUN_STRESS_AAPL_001"})
    scenario_code: str = Field(..., json_schema_extra={"example": "MODERATE_STRESS"})
    instrument_id: str = Field(..., json_schema_extra={"example": "AAPL"})
    venue: str = Field("NASDAQ", json_schema_extra={"example": "NASDAQ"})
    side: str = Field(..., json_schema_extra={"example": "BUY"})  # BUY or SELL
    order_quantity: Decimal = Field(..., json_schema_extra={"example": "10000"})
    reference_price: Decimal = Field(..., json_schema_extra={"example": "150.00"})
    
    # Baseline market inputs
    baseline_spread: Decimal = Field(..., json_schema_extra={"example": "0.10"})
    baseline_bids: List[BookLevelSchema] = Field(default_factory=list)
    baseline_asks: List[BookLevelSchema] = Field(default_factory=list)
    
    # Interval volume profile (e.g. 5-min intervals)
    interval_volumes: List[Decimal] = Field(default_factory=list, json_schema_extra={"example": ["5000", "5000", "5000"]})
    
    # Optional shocks overrides (if not using saved config)
    spread_multiplier: Optional[Decimal] = None
    bid_depth_reduction: Optional[Decimal] = None
    ask_depth_reduction: Optional[Decimal] = None
    volume_contraction: Optional[Decimal] = None
    participation_rate: Optional[Decimal] = None
    
    explicit_fees: Decimal = Field(Decimal("0.0"), json_schema_extra={"example": "15.00"})
    terminal_price: Optional[Decimal] = Field(None, json_schema_extra={"example": "151.00"})


class CostDecompositionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    spread_cost: Decimal
    depth_walk_concession_cost: Decimal
    market_impact_cost: Decimal
    slippage_cost: Decimal
    explicit_fees: Decimal
    opportunity_cost: Decimal
    total_cost: Decimal
    total_cost_bps: Decimal


class StressRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    scenario_code: str
    instrument_id: str
    venue: str
    side: str
    order_quantity: Decimal
    reference_price: Decimal
    
    baseline_spread: Decimal
    stressed_spread: Decimal
    
    baseline_visible_depth: Decimal
    stressed_visible_depth: Decimal
    
    baseline_duration_intervals: int
    stressed_duration_intervals: int
    duration_increase_intervals: int
    liquidation_status: str
    
    stressed_fillable_quantity: Decimal
    stressed_residual_quantity: Decimal
    
    baseline_cost: CostDecompositionSchema
    stressed_cost: CostDecompositionSchema
    cost_escalation_monetary: Decimal
    cost_escalation_pct: Optional[Decimal] = None
    cost_escalation_bps: Decimal
    
    synthetic_stress_book: Optional[SyntheticStressBookResponse] = None
    created_at: datetime


# -------------------------------------------------------------------------
# Reverse Stress Testing Schemas
# -------------------------------------------------------------------------
class ReverseStressRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str = Field(..., json_schema_extra={"example": "AAPL"})
    baseline_spread: Decimal = Field(..., json_schema_extra={"example": "0.10"})
    baseline_interval_volume: Decimal = Field(..., json_schema_extra={"example": "10000"})
    order_quantity: Decimal = Field(..., json_schema_extra={"example": "5000"})
    max_acceptable_cost: Decimal = Field(..., json_schema_extra={"example": "1000.00"})
    max_acceptable_intervals: int = Field(..., json_schema_extra={"example": 5})
    participation_rate: Decimal = Field(Decimal("0.10"), json_schema_extra={"example": "0.10"})
    reference_price: Decimal = Field(Decimal("100.00"), json_schema_extra={"example": "100.00"})


class ReverseStressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    time_breached_at_baseline: bool
    critical_volume_contraction_pct: Decimal
    critical_spread_multiplier: Decimal
    max_acceptable_cost: Decimal
    max_acceptable_intervals: int


# -------------------------------------------------------------------------
# Portfolio Liquidity Stress Schemas
# -------------------------------------------------------------------------
class PortfolioPositionStressItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    quantity: Decimal
    reference_price: Decimal
    side: str  # BUY or SELL
    baseline_spread: Decimal
    interval_volume: Decimal


class PortfolioStressRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str = Field(..., json_schema_extra={"example": "PORT_US_TECH"})
    scenario_code: str = Field(..., json_schema_extra={"example": "MODERATE_STRESS"})
    spread_multiplier: Decimal = Field(Decimal("1.50"), json_schema_extra={"example": "1.50"})
    volume_contraction: Decimal = Field(Decimal("0.20"), json_schema_extra={"example": "0.20"})
    participation_rate: Decimal = Field(Decimal("0.10"), json_schema_extra={"example": "0.10"})
    positions: List[PortfolioPositionStressItem] = Field(..., min_length=1)


class PortfolioPositionStressResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    quantity: Decimal
    baseline_cost: Decimal
    stressed_cost: Decimal
    cost_escalation: Decimal
    baseline_duration_intervals: int
    stressed_duration_intervals: int


class PortfolioStressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str
    scenario_code: str
    total_positions: int
    portfolio_baseline_cost: Decimal
    portfolio_stressed_cost: Decimal
    portfolio_cost_escalation: Decimal
    portfolio_cost_escalation_pct: Optional[Decimal]
    critical_path_duration_intervals: int  # maximum across concurrent positions
    position_results: List[PortfolioPositionStressResult]

