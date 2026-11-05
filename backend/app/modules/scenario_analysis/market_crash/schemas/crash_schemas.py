"""
Market Crash Simulation Pydantic v2 Schemas (M10.03).
Strict input validation, serialization, and type hints for:
- Benchmark shock configuration (Percentage, Target level, Point change, Multi-stage)
- Benchmark mapping definitions & overrides
- Instrument sensitivity snapshots (Beta, Downside beta)
- Nonlinear downside parameters (Piecewise, Stress amplification, Quadratic, User defined)
- Simulation execution request & response
- Granular position results, loss attribution, warnings, and comparisons
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


# -------------------------------------------------------------------------
# Benchmark & Shock Schemas
# -------------------------------------------------------------------------

class BenchmarkShockConfig(BaseModel):
    benchmark_id: str = Field(..., description="Canonical benchmark identifier, e.g., NIFTY_50, SPX, NASDAQ")
    benchmark_name: Optional[str] = None
    market_region: str = Field("US", description="INDIA, US, GLOBAL")
    shock_method: str = Field("PERCENTAGE", description="PERCENTAGE, TARGET_LEVEL, POINT_CHANGE, MULTI_STAGE")
    baseline_index_level: Optional[Decimal] = None
    target_index_level: Optional[Decimal] = None
    index_point_change: Optional[Decimal] = None
    percentage_shock: Optional[Decimal] = Field(None, description="Decimal return, e.g. -0.20 for -20%")
    multi_stage_returns: Optional[List[Decimal]] = None
    return_definition: str = Field("PRICE_RETURN", description="PRICE_RETURN, TOTAL_RETURN")
    benchmark_currency: str = Field("USD", description="Currency of benchmark return")
    stage_order: int = Field(1, ge=1)

    model_config = ConfigDict(from_attributes=True)


class NonlinearParameterConfig(BaseModel):
    instrument_id: Optional[str] = None
    sector_id: Optional[str] = None
    model_type: str = Field(..., description="DOWNSIDE_BETA, PIECEWISE_BETA, STRESS_AMPLIFICATION, QUADRATIC, USER_DEFINED")
    threshold: Optional[Decimal] = None
    stress_multiplier: Optional[Decimal] = None # lambda
    curvature_parameter: Optional[Decimal] = None # gamma
    exponent: Optional[Decimal] = None # p
    user_adjustment: Optional[Decimal] = None # direct additive adjustment
    parameter_source: str = Field("ASSUMPTION", description="ASSUMPTION, CALIBRATED, ANALYST_INPUT")

    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------------------
# Scenario Management Schemas
# -------------------------------------------------------------------------

class MarketCrashScenarioCreate(BaseModel):
    scenario_code: str = Field(..., min_length=3, max_length=64)
    scenario_name: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    category: str = Field("BROAD_MARKET", description="BROAD_MARKET, SECTOR_CRASH, GLOBAL_SYNCHRONIZED, HIGH_BETA, DOWNSIDE_BETA, NONLINEAR")
    portfolio_id: Optional[str] = None
    visibility: str = Field("PRIVATE", description="PRIVATE, TEAM, ORGANIZATION")
    author_id: Optional[str] = None
    owner_id: Optional[str] = None

    benchmark_shocks: List[BenchmarkShockConfig] = Field(..., min_length=1)
    nonlinear_parameters: Optional[List[NonlinearParameterConfig]] = None

    model_config = ConfigDict(from_attributes=True)


class MarketCrashScenarioResponse(BaseModel):
    id: str
    scenario_code: str
    scenario_name: str
    description: Optional[str]
    category: str
    portfolio_id: Optional[str]
    visibility: str
    author_id: Optional[str]
    owner_id: Optional[str]
    current_version: int
    status: str
    created_at: datetime
    updated_at: datetime

    benchmark_shocks: Optional[List[BenchmarkShockConfig]] = None
    nonlinear_parameters: Optional[List[NonlinearParameterConfig]] = None

    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------------------
# Simulation Request & Input Schemas
# -------------------------------------------------------------------------

class PositionInput(BaseModel):
    instrument_id: str
    listing_id: Optional[str] = None
    signed_quantity: Decimal = Field(..., description="Signed position quantity (positive for long, negative for short)")
    baseline_price: Decimal = Field(..., gt=0, description="Baseline security price in local currency")
    currency: str = Field("USD", description="Currency of instrument")
    sector: Optional[str] = None
    market_region: Optional[str] = Field("US", description="INDIA, US")
    
    # Optional direct benchmark mapping & sensitivity override
    benchmark_id: Optional[str] = None
    beta_value: Optional[Decimal] = None
    downside_beta: Optional[Decimal] = None
    fx_return: Optional[Decimal] = Field(Decimal("0"), description="Simulated FX return against portfolio base currency")
    sector_adjustment: Optional[Decimal] = None
    user_adjustment: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)


class SimulationExecutionRequest(BaseModel):
    scenario_name: str
    portfolio_id: str
    portfolio_snapshot_id: Optional[str] = None
    scenario_id: Optional[str] = None
    base_currency: str = Field("USD", description="Portfolio base currency")
    baseline_nav: Decimal = Field(..., gt=0, description="Authoritative portfolio baseline NAV")
    response_model: str = Field("LINEAR", description="LINEAR, DOWNSIDE_BETA, PIECEWISE_BETA, STRESS_AMPLIFICATION, QUADRATIC, COMPOSITE")
    missing_data_policy: str = Field("STRICT", description="STRICT, PARTIAL, EXCLUDE_UNMAPPED, APPROVED_FALLBACK")
    
    benchmark_shocks: List[BenchmarkShockConfig] = Field(..., min_length=1)
    nonlinear_parameters: Optional[List[NonlinearParameterConfig]] = None
    positions: List[PositionInput] = Field(..., min_length=1)

    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------------------
# Output Schemas
# -------------------------------------------------------------------------

class PositionResultResponse(BaseModel):
    instrument_id: str
    listing_id: Optional[str] = None
    sector: Optional[str] = None
    market_region: Optional[str] = None
    currency: str
    signed_quantity: Decimal
    baseline_price: Decimal
    scenario_price: Decimal
    baseline_market_value: Decimal
    scenario_market_value: Decimal
    benchmark_id: str
    benchmark_shock: Decimal
    beta_value: Decimal
    downside_beta: Optional[Decimal] = None
    linear_return: Decimal
    downside_adjustment: Decimal
    nonlinear_adjustment: Decimal
    sector_adjustment: Decimal
    user_adjustment: Decimal
    final_scenario_return: Decimal
    scenario_pnl: Decimal
    scenario_loss: Decimal
    portfolio_contribution: Decimal
    mapping_status: str
    quality_status: str

    model_config = ConfigDict(from_attributes=True)


class AttributionResultResponse(BaseModel):
    attribution_type: str
    attribution_identifier: str
    baseline_exposure: Decimal
    scenario_pnl: Decimal
    scenario_loss: Decimal
    linear_impact: Decimal
    nonlinear_impact: Decimal
    contribution_percentage: Decimal
    reconciliation_residual: Decimal

    model_config = ConfigDict(from_attributes=True)


class WarningResponse(BaseModel):
    warning_code: str
    severity: str
    category: str
    message: str
    instrument_id: Optional[str] = None
    benchmark_id: Optional[str] = None
    details_json: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class SimulationSummaryResponse(BaseModel):
    simulation_id: str
    simulation_code: str
    scenario_id: Optional[str] = None
    portfolio_id: str
    base_currency: str
    response_model: str
    run_status: str
    baseline_nav: Decimal
    scenario_nav: Decimal
    scenario_pnl: Decimal
    scenario_loss: Decimal
    scenario_return: Decimal
    gross_exposure: Decimal
    net_exposure: Decimal
    mapped_coverage: Decimal
    beta_coverage: Decimal
    nonlinear_coverage: Decimal
    affected_positions: int
    started_at: datetime
    completed_at: Optional[datetime] = None

    position_results: Optional[List[PositionResultResponse]] = None
    attribution_results: Optional[List[AttributionResultResponse]] = None
    warnings: Optional[List[WarningResponse]] = None

    model_config = ConfigDict(from_attributes=True)
