"""
M09.04 Market Impact - Pydantic v2 Schemas.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# Direct Level Input
class DepthLevelInput(BaseModel):
    price: Decimal = Field(..., gt=0)
    quantity: Decimal = Field(..., gt=0)
    level: Optional[int] = None


# Configuration Schemas
class MarketImpactConfigRequest(BaseModel):
    config_code: str
    name: str
    reference_price_method: str = "MIDPOINT"
    default_execution_horizon_seconds: int = 300
    default_max_participation_rate: float = 0.10
    default_schedule: str = "UNIFORM"
    square_root_y_coefficient: float = 0.50


class MarketImpactConfigResponse(MarketImpactConfigRequest):
    config_id: str
    version: int
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ImpactModelConfigRequest(BaseModel):
    model_code: str
    name: str
    model_type: str  # SQUARE_ROOT, EMPIRICAL_REGRESSION, KYLE_OFI
    parameter_values: Dict[str, Any]
    calibration_sample_count: int = 0


class ImpactModelConfigResponse(ImpactModelConfigRequest):
    model_id: str
    version: int
    model_status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# Direct Simulation Request
class DirectDepthWalkRequest(BaseModel):
    side: str = Field(..., pattern="^(BUY|SELL|buy|sell)$")
    proposed_quantity: Decimal = Field(..., gt=0)
    reference_price: Decimal = Field(..., gt=0)
    levels: List[DepthLevelInput]
    instrument_multiplier: Decimal = Decimal("1.0")


class DepthWalkLevelResponse(BaseModel):
    level_index: int
    price: Decimal
    available_quantity: Decimal
    consumed_quantity: Decimal
    remaining_quantity: Decimal
    executed_value: Decimal


class DepthWalkResponse(BaseModel):
    depth_walk_id: Optional[str] = None
    side: str
    proposed_quantity: Decimal
    reference_price: Decimal
    visible_fill_quantity: Decimal
    residual_unfilled_quantity: Decimal
    fill_percentage: float
    average_execution_price: Optional[Decimal] = None
    marginal_execution_price: Optional[Decimal] = None
    gross_execution_value: Decimal
    estimated_cost_amount: Optional[Decimal] = None
    estimated_cost_bps: Optional[float] = None
    spread_crossing_bps: Optional[float] = None
    additional_depth_bps: Optional[float] = None
    consumed_level_count: int
    available_level_count: int
    consumed_levels: List[DepthWalkLevelResponse] = Field(default_factory=list)


# Sensitivity Request
class OrderSizeSensitivityRequest(BaseModel):
    side: str = Field(..., pattern="^(BUY|SELL|buy|sell)$")
    sizes: List[Decimal]
    reference_price: Decimal = Field(..., gt=0)
    levels: List[DepthLevelInput]
    instrument_multiplier: Decimal = Decimal("1.0")


# Horizon & Scenario Requests
class ScenarioCreateRequest(BaseModel):
    instrument_id: str
    exchange: str = "NSE"
    venue: str = "NSE_CASH"
    order_side: str = Field(..., pattern="^(BUY|SELL|buy|sell)$")
    proposed_quantity: Decimal = Field(..., gt=0)
    reference_price: Decimal = Field(..., gt=0)
    reference_price_method: str = "MIDPOINT"
    currency: str = "USD"
    execution_horizon_seconds: int = 0
    maximum_participation_rate: float = 0.10
    execution_schedule: str = "IMMEDIATE"
    market_regime: str = "NORMAL"


class ScenarioResponse(ScenarioCreateRequest):
    scenario_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# Empirical Model Predict Request
class EmpiricalPredictRequest(BaseModel):
    model_type: str = "EMPIRICAL_REGRESSION"  # SQUARE_ROOT, EMPIRICAL_REGRESSION, KYLE_OFI
    order_quantity: float
    expected_horizon_volume: float
    volatility: float  # e.g. 0.02
    spread_bps: float = 5.0
    depth_notional: float = 1000000.0
    regime_multiplier: float = 1.0
    impact_coefficient_y: float = 0.50
    signed_order_flow: Optional[float] = None


class EmpiricalPredictResponse(BaseModel):
    model_type: str
    impact_bps: Optional[float] = None
    temporary_impact_bps: Optional[float] = None
    permanent_impact_bps: Optional[float] = None
    standard_error_bps: Optional[float] = None
    prediction_lower_bps: Optional[float] = None
    prediction_upper_bps: Optional[float] = None
    price_change: Optional[float] = None
    status: str


class ValidationRunRequest(BaseModel):
    model_code: str
    sample_count: int
    mae: float
    rmse: float
    mean_bias_error: float
    interval_coverage_pct: float
    validation_status: str = "PASSED"


class ValidationRunResponse(ValidationRunRequest):
    run_id: str
    model_version: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

