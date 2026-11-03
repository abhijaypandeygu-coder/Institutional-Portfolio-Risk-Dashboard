"""
Pydantic schemas for M09.05 Slippage Estimation.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# -------------------------------------------------------------------------
# Benchmark Config Schemas
# -------------------------------------------------------------------------
class BenchmarkConfigCreate(BaseModel):
    config_code: str = Field(..., example="US_EQUITIES_DEFAULT")
    version: int = Field(1, example=1)
    description: Optional[str] = Field(None, example="Standard benchmark config for US equities")
    benchmark_type: str = Field("ARRIVAL_MIDPOINT", example="ARRIVAL_MIDPOINT")
    max_quote_age_seconds: int = Field(60, example=60)
    allow_cross_venue_benchmarking: bool = Field(True, example=True)
    currency: str = Field("USD", example="USD")
    multiplier: Decimal = Field(Decimal("1.0"), example="1.0")
    is_active: bool = Field(True, example=True)


class BenchmarkConfigResponse(BenchmarkConfigCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# -------------------------------------------------------------------------
# Fill Input & Attribution Schemas
# -------------------------------------------------------------------------
class FillInputSchema(BaseModel):
    fill_id: str = Field(..., example="FILL_001")
    fill_timestamp: datetime = Field(..., example="2026-11-03T09:30:05Z")
    price: Decimal = Field(..., example="100.50")
    quantity: Decimal = Field(..., example="500")
    venue: Optional[str] = Field("NASDAQ", example="NASDAQ")
    bid_at_fill: Optional[Decimal] = Field(None, example="100.48")
    ask_at_fill: Optional[Decimal] = Field(None, example="100.52")
    midpoint_at_fill: Optional[Decimal] = Field(None, example="100.50")
    fees: Decimal = Field(Decimal("0.0"), example="1.50")


class FillAttributionSchema(BaseModel):
    fill_id: str
    quantity: Decimal
    fill_price: Decimal
    multiplier: Decimal
    side: str
    reference_price: Decimal
    fill_slippage_price: Decimal
    fill_slippage_bps: Decimal
    fill_slippage_money: Decimal
    market_movement_price: Decimal
    market_movement_bps: Decimal
    market_movement_money: Decimal
    spread_crossing_price: Decimal
    spread_crossing_bps: Decimal
    spread_crossing_money: Decimal
    residual_execution_price: Decimal
    residual_execution_bps: Decimal
    residual_execution_money: Decimal
    total_reconciled: bool
    reconciliation_discrepancy: Decimal

    class Config:
        from_attributes = True


# -------------------------------------------------------------------------
# Execution Analysis Request & Response Schemas
# -------------------------------------------------------------------------
class SlippageAnalysisRequest(BaseModel):
    order_id: str = Field(..., example="ORD_1001")
    symbol: str = Field(..., example="AAPL")
    side: str = Field(..., example="BUY")  # BUY or SELL
    order_created_at: datetime = Field(..., example="2026-11-03T09:30:00Z")
    requested_quantity: Decimal = Field(..., example="1000")
    
    benchmark_type: str = Field("ARRIVAL_MIDPOINT", example="ARRIVAL_MIDPOINT")
    benchmark_price: Decimal = Field(..., example="100.00")
    benchmark_timestamp: Optional[datetime] = Field(None, example="2026-11-03T09:30:00Z")
    
    fills: List[FillInputSchema] = Field(..., min_items=1)
    terminal_price: Optional[Decimal] = Field(None, example="101.20")
    multiplier: Decimal = Field(Decimal("1.0"), example="1.0")


class SlippageExecutionSummaryResponse(BaseModel):
    order_id: str
    symbol: str
    side: str
    order_created_at: datetime
    execution_completed_at: Optional[datetime]
    requested_quantity: Decimal
    filled_quantity: Decimal
    unfilled_quantity: Decimal
    fill_rate_pct: Decimal
    
    benchmark_type: str
    benchmark_price: Decimal
    vwap_execution_price: Decimal
    gross_executed_notional: Decimal
    
    # Realized Slippage
    slippage_price_units: Decimal
    slippage_bps: Decimal
    slippage_monetary_amount: Decimal
    is_favorable: bool
    
    # Attribution Totals
    total_market_movement_price: Decimal
    total_market_movement_bps: Decimal
    total_market_movement_money: Decimal
    total_spread_crossing_price: Decimal
    total_spread_crossing_bps: Decimal
    total_spread_crossing_money: Decimal
    total_residual_execution_price: Decimal
    total_residual_execution_bps: Decimal
    total_residual_execution_money: Decimal
    attribution_reconciled: bool
    
    # Fees and Total
    total_explicit_fees: Decimal
    total_all_in_cost: Decimal
    
    # Opportunity Cost & Implementation Shortfall
    terminal_price: Optional[Decimal] = None
    opportunity_cost_price_units: Optional[Decimal] = None
    opportunity_cost_bps: Optional[Decimal] = None
    opportunity_cost_monetary_amount: Optional[Decimal] = None
    implementation_shortfall_monetary_amount: Optional[Decimal] = None
    
    fill_attributions: List[FillAttributionSchema] = []

    class Config:
        from_attributes = True


# -------------------------------------------------------------------------
# Calibration Schemas
# -------------------------------------------------------------------------
class CalibrationObservationInput(BaseModel):
    order_id: str = Field(..., example="ORD_1001")
    symbol: str = Field(..., example="AAPL")
    side: str = Field(..., example="BUY")
    observation_timestamp: datetime = Field(..., example="2026-11-03T09:30:00Z")
    estimated_slippage_bps: Decimal = Field(..., example="12.5")
    realized_slippage_bps: Decimal = Field(..., example="14.2")
    predicted_lower_bound_bps: Optional[Decimal] = Field(None, example="8.0")
    predicted_upper_bound_bps: Optional[Decimal] = Field(None, example="17.0")


class CalibrationRunRequest(BaseModel):
    run_code: str = Field(..., example="CALIB_2026_Q4")
    model_name: str = Field(..., example="HISTORICAL_MEDIAN_SPREAD_DEPTH")
    observations: List[CalibrationObservationInput] = Field(..., min_items=1)


class CalibrationRunResponse(BaseModel):
    run_code: str
    model_name: str
    observation_count: int
    mean_error_bps: Decimal
    mean_absolute_error_bps: Decimal
    root_mean_squared_error_bps: Decimal
    t_statistic: Optional[Decimal] = None
    p_value: Optional[Decimal] = None
    is_bias_significant: bool
    interval_coverage_pct: Decimal

    class Config:
        from_attributes = True

