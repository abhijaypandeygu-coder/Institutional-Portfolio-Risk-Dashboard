"""
Hypothetical Scenarios Pydantic Schemas (M10.02).
Strict validation using Pydantic 2.x and ConfigDict.
"""

from pydantic import BaseModel, ConfigDict, Field
from decimal import Decimal
from typing import List, Optional, Dict, Any
from datetime import datetime


class PriceShockDefinition(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_type: str = Field(..., pattern="^(INSTRUMENT|SECTOR|MARKET|PORTFOLIO)$")
    target_identifier: str # e.g. AAPL_US, TECHNOLOGY, US, ALL
    shock_method: str = Field(..., pattern="^(PERCENTAGE|ABSOLUTE|TARGET_PRICE)$")
    shock_value: Decimal


class FactorShockDefinition(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    factor_name: str # e.g. MARKET, SIZE, VALUE, MOMENTUM, QUALITY
    shock_value: Decimal # return shock e.g. -0.15 for -15%
    residual_shock: Decimal = Decimal("0")


class VolatilityShockDefinition(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_type: str = Field(default="PORTFOLIO", pattern="^(INSTRUMENT|PORTFOLIO)$")
    target_identifier: Optional[str] = "PORTFOLIO"
    shock_method: str = Field(..., pattern="^(PERCENTAGE|ABSOLUTE|TARGET_VOLATILITY)$")
    shock_value: Decimal # e.g. 0.50 for +50% scaling


class CorrelationShockDefinition(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_a: str
    instrument_b: str
    target_correlation: Decimal = Field(..., ge=-1.0, le=1.0)


class LiquidityShockDefinition(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_type: str = Field(default="PORTFOLIO", pattern="^(INSTRUMENT|PORTFOLIO)$")
    target_identifier: Optional[str] = "PORTFOLIO"
    spread_shock_pct: Decimal = Decimal("0") # e.g. 0.50 for +50% widening
    depth_shock_pct: Decimal = Decimal("0")  # e.g. 0.30 for -30% reduction
    volume_shock_pct: Decimal = Decimal("0") # e.g. 0.20 for -20% contraction


class ScenarioTemplateCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    template_code: str = Field(..., max_length=100)
    template_name: str = Field(..., max_length=150)
    description: Optional[str] = Field(None, max_length=255)
    category: str = Field(default="CUSTOM", max_length=50)
    tags: Optional[str] = Field(None, max_length=255)
    author_id: str = Field(default="QUANT_ANALYST", max_length=50)
    owner_id: str = Field(default="QUANT_TEAM", max_length=50)
    visibility: str = Field(default="SHARED", max_length=20)
    
    # Shocks embedded in template
    price_shocks: Optional[List[PriceShockDefinition]] = None
    factor_shocks: Optional[List[FactorShockDefinition]] = None
    volatility_shocks: Optional[List[VolatilityShockDefinition]] = None
    correlation_shocks: Optional[List[CorrelationShockDefinition]] = None
    liquidity_shocks: Optional[List[LiquidityShockDefinition]] = None


class ScenarioTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    template_code: str
    template_name: str
    description: Optional[str]
    category: str
    tags: Optional[str]
    author_id: str
    owner_id: str
    visibility: str
    current_version: str
    status: str
    created_at: datetime
    updated_at: datetime


class PositionInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    listing_id: str
    signed_quantity: Decimal
    baseline_price: Decimal = Field(..., gt=0)
    baseline_volatility: Optional[Decimal] = Decimal("0.20")
    currency: str = Field(default="USD")
    sector: Optional[str] = None
    factor_sensitivities: Optional[Dict[str, Decimal]] = None
    baseline_spread: Optional[Decimal] = Decimal("0.05")
    baseline_bid_depth: Optional[Decimal] = Decimal("10000")
    baseline_ask_depth: Optional[Decimal] = Decimal("10000")
    baseline_volume: Optional[Decimal] = Decimal("500000")


class ScenarioExecutionRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scenario_name: str = Field(..., max_length=150)
    portfolio_id: str
    template_id: Optional[str] = None
    base_currency: str = Field(default="USD")
    baseline_nav: Decimal = Field(..., gt=0)
    positions: List[PositionInput] = Field(..., min_length=1)
    
    # Direct shock payloads (or inherited from template)
    price_shocks: Optional[List[PriceShockDefinition]] = None
    factor_shocks: Optional[List[FactorShockDefinition]] = None
    volatility_shocks: Optional[List[VolatilityShockDefinition]] = None
    correlation_shocks: Optional[List[CorrelationShockDefinition]] = None
    liquidity_shocks: Optional[List[LiquidityShockDefinition]] = None

    # Policies
    missing_data_policy: str = Field(default="STRICT", pattern="^(STRICT|PARTIAL)$")
    conflict_policy: str = Field(default="MOST_SPECIFIC_WINS", pattern="^(MOST_SPECIFIC_WINS|REJECT_CONFLICT)$")
    correlation_validation_policy: str = Field(default="NEAREST_CORRELATION_MATRIX_REPAIR", pattern="^(REJECT_INVALID_MATRIX|NEAREST_CORRELATION_MATRIX_REPAIR)$")
    
    # FX shocks (currency -> return)
    fx_shocks: Optional[Dict[str, Decimal]] = None


class PositionResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    listing_id: str
    signed_quantity: Decimal
    baseline_price: Decimal
    scenario_price: Decimal
    price_shock: Decimal
    factor_return: Optional[Decimal]
    baseline_market_value: Decimal
    scenario_market_value: Decimal
    scenario_pnl: Decimal
    baseline_weight: Decimal
    scenario_contribution: Decimal
    local_currency: str
    base_currency_return: Decimal


class RiskResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metric_code: str
    baseline_value: Decimal
    scenario_value: Decimal
    difference_value: Decimal
    unit: str
    horizon: str
    confidence_level: Optional[Decimal]
    methodology: str


class LiquidityResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    baseline_spread: Decimal
    scenario_spread: Decimal
    baseline_bid_depth: Decimal
    scenario_bid_depth: Decimal
    baseline_ask_depth: Decimal
    scenario_ask_depth: Decimal
    baseline_volume: Decimal
    scenario_volume: Decimal


class WarningResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    warning_code: str
    severity: str
    category: str
    message: str


class ScenarioRunSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    scenario_code: str
    scenario_name: str
    portfolio_id: str
    base_currency: str
    run_status: str
    baseline_nav: Decimal
    scenario_nav: Decimal
    scenario_pnl: Decimal
    scenario_return: Decimal
    direct_coverage: Decimal
    positions: List[PositionResultResponse]
    risk_results: List[RiskResultResponse]
    liquidity_results: List[LiquidityResultResponse]
    warnings: List[WarningResponse]
    caveat_summary: str
