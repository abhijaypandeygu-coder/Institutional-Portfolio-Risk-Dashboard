"""
Pydantic schemas for M10.09 Stress Loss Attribution.
Conforms to Pydantic v2.0 conventions.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class AttributionCreate(BaseModel):
    attribution_code: str = Field(..., max_length=64)
    name: str = Field(..., max_length=128)
    description: Optional[str] = None
    portfolio_id: str
    scenario_id: str
    scenario_run_id: str
    scenario_type: str = Field(..., description="HISTORICAL, HYPOTHETICAL, MARKET_CRASH, SECTOR_SHOCK, CORRELATION_SHOCK, LIQUIDITY_STRESS, MONTE_CARLO")
    baseline_snapshot_id: Optional[str] = None
    base_currency: str = "USD"
    attribution_method: str = "ARITHMETIC_EXACT"


class AttributionResponse(BaseModel):
    id: str
    attribution_code: str
    name: str
    description: Optional[str] = None
    portfolio_id: str
    scenario_id: str
    scenario_run_id: str
    scenario_type: str
    baseline_snapshot_id: Optional[str] = None
    base_currency: str
    attribution_method: str
    status: str
    completeness: str
    configuration_version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PositionContributionResponse(BaseModel):
    symbol: str
    quantity: Decimal
    position_direction: str
    baseline_price: Decimal
    stressed_price: Decimal
    baseline_market_value: Decimal
    stressed_market_value: Decimal
    price_pnl: Decimal
    fx_pnl: Decimal
    liquidity_cost: Decimal
    other_adjustments: Decimal
    total_pnl: Decimal
    loss_contribution: Decimal
    contribution_percentage: Decimal
    sector: str
    industry: str

    model_config = ConfigDict(from_attributes=True)


class SectorContributionResponse(BaseModel):
    sector_name: str
    holding_count: int
    baseline_market_value: Decimal
    stressed_market_value: Decimal
    total_pnl: Decimal
    loss_contribution: Decimal
    contribution_percentage: Decimal

    model_config = ConfigDict(from_attributes=True)


class IndustryContributionResponse(BaseModel):
    industry_name: str
    holding_count: int
    baseline_market_value: Decimal
    stressed_market_value: Decimal
    total_pnl: Decimal
    loss_contribution: Decimal
    contribution_percentage: Decimal

    model_config = ConfigDict(from_attributes=True)


class FactorContributionResponse(BaseModel):
    factor_name: str
    factor_shock: float
    factor_exposure: float
    contribution_value: Decimal
    loss_contribution: Decimal

    model_config = ConfigDict(from_attributes=True)


class InteractionEffectResponse(BaseModel):
    shock_driver_a: str
    shock_driver_b: str
    combined_effect: Decimal
    individual_effect_a: Decimal
    individual_effect_b: Decimal
    interaction_effect: Decimal
    interaction_method: str

    model_config = ConfigDict(from_attributes=True)


class AttributionExecutionRequest(BaseModel):
    baseline_nav_override: Optional[Decimal] = None
    authoritative_pnl_override: Optional[Decimal] = None
    custom_positions: Optional[List[Dict[str, Any]]] = None
    factor_exposures: Optional[Dict[str, float]] = None
    factor_shocks: Optional[Dict[str, float]] = None


class AttributionRunResponse(BaseModel):
    id: str
    attribution_id: str
    run_code: str
    scenario_run_id: str
    execution_status: str
    attribution_completeness: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: int
    authoritative_total_pnl: Decimal
    explained_pnl: Decimal
    residual_amount: Decimal
    is_reconciled: bool
    loss_hhi: float
    effective_contributor_count: float
    position_contributions: List[PositionContributionResponse] = []
    sector_contributions: List[SectorContributionResponse] = []
    industry_contributions: List[IndustryContributionResponse] = []
    factor_contributions: List[FactorContributionResponse] = []
    interaction_effects: List[InteractionEffectResponse] = []
    narrative: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

