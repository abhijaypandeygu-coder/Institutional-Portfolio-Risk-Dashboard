"""
Pydantic 2.x schemas for M09.07 Position Liquidation.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class TargetReductionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_id: str
    target_sequence: int
    target_percentage: Decimal
    target_cumulative_quantity: Decimal
    target_incremental_quantity: Decimal
    remaining_quantity: Decimal
    target_market_value: Decimal


class ScheduleItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    interval_index: int
    session_index: int
    interval_start: datetime
    interval_end: datetime
    market_volume: Decimal
    allocated_quantity: Decimal
    participation_rate: Decimal
    expected_execution_price: Decimal
    estimated_interval_cost: Decimal
    estimated_remaining_quantity: Decimal


class HorizonResultSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_id: str
    baseline_duration_seconds: int
    stressed_duration_seconds: int
    estimated_interval_count: int
    estimated_session_count: int
    estimated_completion_timestamp: Optional[datetime] = None
    expected_liquidated_quantity: Decimal
    remaining_quantity: Decimal
    completion_status: str
    participation_rate: Decimal
    schedule_type: str


class CostResultSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_id: str
    baseline_spread_cost: Decimal
    baseline_depth_walk_cost: Decimal
    baseline_market_impact_cost: Decimal
    baseline_slippage_cost: Decimal
    baseline_explicit_fees: Decimal
    baseline_opportunity_cost: Decimal
    stressed_spread_cost: Decimal
    stressed_depth_walk_cost: Decimal
    stressed_market_impact_cost: Decimal
    stressed_slippage_cost: Decimal
    stressed_explicit_fees: Decimal
    stressed_opportunity_cost: Decimal
    cumulative_liquidation_cost: Decimal
    incremental_liquidation_cost: Decimal
    cost_bps: Decimal
    cost_per_share: Decimal
    cost_currency: str
    cost_inclusion_map: str
    reconciliation_difference: Decimal
    average_execution_price: Decimal
    quality_status: str


class LiquidationPlanCreateRequest(BaseModel):
    plan_name: str = Field(..., description="Human-readable name for the liquidation plan")
    portfolio_id: str
    position_id: str
    position_snapshot_id: Optional[str] = None
    instrument_id: str
    listing_id: Optional[str] = None
    venue_id: Optional[str] = "XNYS"

    starting_signed_quantity: Decimal
    starting_market_value: Optional[Decimal] = None
    benchmark_price: Decimal = Decimal("100.0")
    benchmark_type: str = "MIDPOINT"
    spread: Decimal = Decimal("0.05")
    position_currency: str = "USD"
    portfolio_base_currency: str = "USD"

    maximum_participation_rate: Decimal = Decimal("0.1000")  # 10%
    execution_schedule: str = "PARTICIPATION_CAPPED"  # UNIFORM, VOLUME_PROPORTIONAL, PARTICIPATION_CAPPED
    target_percentages: Optional[List[Decimal]] = None  # None -> default [10%, 25%, 50%, 75%, 90%, 100%]
    custom_quantities: Optional[List[Decimal]] = None
    stress_scenario_id: Optional[str] = None
    stress_scenario_version: Optional[int] = None
    interval_volumes: Optional[List[Decimal]] = None  # Mock/explicit volume profile


class LiquidationPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan_id: str
    plan_name: str
    portfolio_id: str
    position_id: str
    instrument_id: str
    liquidation_side: str
    starting_signed_quantity: Decimal
    starting_absolute_quantity: Decimal
    starting_market_value: Decimal
    position_currency: str
    portfolio_base_currency: str
    benchmark_price: Decimal
    maximum_participation_rate: Decimal
    execution_schedule: str
    plan_status: str
    version: int
    created_at: datetime
    targets: List[TargetReductionSchema] = []
    horizon_results: List[HorizonResultSchema] = []
    cost_results: List[CostResultSchema] = []


class PartialComparisonResponse(BaseModel):
    plan_id: str
    instrument_id: str
    liquidation_side: str
    starting_quantity: Decimal
    targets: List[Dict[str, Any]]


class PortfolioLiquidationRequest(BaseModel):
    portfolio_id: str
    schedule_mode: str = "CONCURRENT"  # CONCURRENT or SEQUENTIAL
    participation_rate: Decimal = Decimal("0.1000")
    positions: List[Dict[str, Any]]  # List of {instrument_id, quantity, price, spread}


class PortfolioLiquidationResponse(BaseModel):
    portfolio_id: str
    schedule_mode: str
    position_count: int
    total_market_value: Decimal
    total_liquidation_cost: Decimal
    long_liquidation_cost: Decimal
    short_covering_cost: Decimal
    critical_path_duration_seconds: int
    portfolio_duration_seconds: int
    completion_status: str
    positions: List[Dict[str, Any]]


class CalibrationRunCreateRequest(BaseModel):
    model_id: str
    model_version: str = "v1.0.0"
    calibration_start: datetime
    calibration_end: datetime
    training_sample_count: int
    duration_mae_seconds: Decimal
    duration_rmse_seconds: Decimal
    cost_mae_bps: Decimal
    cost_rmse_bps: Decimal
    prediction_bias_bps: Decimal


class CalibrationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    calibration_id: str
    model_id: str
    model_version: str
    calibration_start: datetime
    calibration_end: datetime
    training_sample_count: int
    duration_mae_seconds: Decimal
    duration_rmse_seconds: Decimal
    cost_mae_bps: Decimal
    cost_rmse_bps: Decimal
    prediction_bias_bps: Decimal
    validation_status: str
    created_at: datetime
