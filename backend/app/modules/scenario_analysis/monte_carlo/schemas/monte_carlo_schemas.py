"""
Pydantic schemas for M10.07 Monte Carlo Scenarios.
Conforms to Pydantic v2.0 conventions.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class MonteCarloScenarioBase(BaseModel):
    name: str = Field(..., max_length=128)
    description: Optional[str] = None
    horizon_days: int = Field(20, ge=1, le=504, description="Simulation horizon in days (e.g. 1, 5, 10, 20, 60, 252)")
    time_step_days: int = Field(1, ge=1, le=21, description="Delta t step length in trading days (1 for daily)")
    distribution_type: str = Field("MULTIVARIATE_NORMAL", description="MULTIVARIATE_NORMAL, STUDENT_T, EMPIRICAL_BOOTSTRAP")
    degrees_of_freedom: Optional[float] = Field(5.0, ge=2.1, le=100.0, description="Degrees of freedom if Student-t")
    expected_return_model: str = Field("ZERO_DRIFT", description="ZERO_DRIFT, HISTORICAL_MEAN, or CUSTOM")
    volatility_model: str = Field("SAMPLE_ANNUALIZED", description="SAMPLE_ANNUALIZED, EWMA, STRESSED_MULTIPLIER")
    volatility_multiplier: float = Field(1.0, ge=0.1, le=10.0, description="Multiplier for stress testing (e.g. 1.5x vol)")
    correlation_repair_method: str = Field("EIGENVALUE_CLIPPING", description="EIGENVALUE_CLIPPING or SHRINKAGE")


class MonteCarloScenarioCreate(MonteCarloScenarioBase):
    scenario_code: str = Field(..., max_length=64)


class MonteCarloScenarioUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    horizon_days: Optional[int] = None
    time_step_days: Optional[int] = None
    distribution_type: Optional[str] = None
    degrees_of_freedom: Optional[float] = None
    expected_return_model: Optional[str] = None
    volatility_model: Optional[str] = None
    volatility_multiplier: Optional[float] = None
    correlation_repair_method: Optional[str] = None
    is_active: Optional[bool] = None


class MonteCarloScenarioResponse(MonteCarloScenarioBase):
    id: str
    scenario_code: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PositionOverride(BaseModel):
    symbol: str
    quantity: Decimal
    baseline_price: Optional[Decimal] = None
    annualized_volatility: Optional[float] = None
    annualized_drift: Optional[float] = None


class SimulationExecutionRequest(BaseModel):
    portfolio_id: str = Field(..., description="Target portfolio identifier")
    n_paths: int = Field(10000, ge=100, le=1000000, description="Number of Monte Carlo paths to generate")
    random_seed: Optional[int] = Field(None, description="Optional seed for deterministic reproducibility")
    positions_override: Optional[List[PositionOverride]] = Field(None, description="Optional custom positions and volatility overrides")
    correlation_matrix_override: Optional[List[List[float]]] = Field(None, description="Optional square correlation matrix")
    store_sample_paths: bool = Field(False, description="Whether to include sampled terminal paths in response")


class RiskMetricResponse(BaseModel):
    confidence_level: float
    var_loss_amount: Decimal
    cvar_loss_amount: Decimal
    var_percent: float
    cvar_percent: float
    pnl_cutoff_amount: Decimal

    model_config = ConfigDict(from_attributes=True)


class InstrumentResultResponse(BaseModel):
    symbol: str
    quantity: Decimal
    baseline_price: Decimal
    baseline_market_value: Decimal
    mean_terminal_price: Decimal
    mean_pnl: Decimal
    pnl_std: Decimal
    var_95_loss: Decimal
    annualized_volatility: float

    model_config = ConfigDict(from_attributes=True)


class SimulationSummaryResponse(BaseModel):
    baseline_portfolio_value: Decimal
    mean_terminal_value: Decimal
    median_terminal_value: Decimal
    std_terminal_value: Decimal
    mean_pnl: Decimal
    median_pnl: Decimal
    std_pnl: Decimal
    skewness_pnl: float
    excess_kurtosis_pnl: float
    loss_probability: float
    min_pnl: Decimal
    max_pnl: Decimal
    percentiles_json: Dict[str, float]

    model_config = ConfigDict(from_attributes=True)


class SimulationRunResponse(BaseModel):
    run_id: str
    scenario_code: str
    run_code: str
    portfolio_id: str
    n_paths: int
    n_steps: int
    random_seed: int
    generator_algorithm: str
    matrix_was_repaired: bool
    status: str
    execution_duration_ms: int
    input_parameters_hash: str
    executed_at: datetime
    summary: Optional[SimulationSummaryResponse] = None
    risk_metrics: List[RiskMetricResponse] = []
    instrument_results: List[InstrumentResultResponse] = []
    narrative: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

