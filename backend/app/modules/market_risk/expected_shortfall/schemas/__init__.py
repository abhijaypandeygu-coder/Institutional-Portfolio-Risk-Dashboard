"""
Module M07.03: Expected Shortfall Pydantic Schemas.
Provides request and response validation for:
1. Configurations (CRUD)
2. Calculations (Historical Portfolio Returns, Historical Simulation, Monte Carlo)
3. Tail Diagnostics
4. Tail Scenarios Drill-Down
5. Risk Contributions
6. VaR & ES Comparison
7. Confidence-Level Sensitivity
8. Historical Trends
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from backend.app.modules.market_risk.expected_shortfall.models import (
    ESMethodology,
    ESTailWeightingMethod,
    ESQuantileMethod,
    ESTailStabilityStatus,
    ESCalculationStatus,
    ESTrendDirection,
)


class ESConfigCreateRequest(BaseModel):
    config_name: str = Field(..., max_length=128)
    portfolio_id: Optional[str] = None
    portfolio_group_id: Optional[str] = None
    methodology: ESMethodology = ESMethodology.HISTORICAL_PORTFOLIO_RETURNS
    confidence_level: Decimal = Field(default=Decimal("0.9750"), ge=Decimal("0.8000"), le=Decimal("0.9999"))
    holding_horizon_days: int = Field(default=1, ge=1, le=252)
    valuation_base_type: str = "PORTFOLIO_NAV"
    reporting_currency: str = Field(default="USD", max_length=3)
    lookback_period_days: int = Field(default=252, ge=10, le=2520)
    quantile_method: ESQuantileMethod = ESQuantileMethod.LINEAR_INTERPOLATION
    tail_weighting_method: ESTailWeightingMethod = ESTailWeightingMethod.FRACTIONAL_BOUNDARY
    simulation_count: int = Field(default=10000, ge=100, le=100000)
    random_seed: Optional[int] = 42


class ESConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    config_id: str
    config_name: str
    portfolio_id: Optional[str] = None
    portfolio_group_id: Optional[str] = None
    methodology: ESMethodology
    confidence_level: Decimal
    tail_probability: Decimal
    holding_horizon_days: int
    valuation_base_type: str
    reporting_currency: str
    lookback_period_days: int
    quantile_method: ESQuantileMethod
    tail_weighting_method: ESTailWeightingMethod
    simulation_count: int
    random_seed: Optional[int]
    is_active: bool
    config_version: int
    created_at: datetime


class ESCalculateRequest(BaseModel):
    portfolio_id: str
    methodology: ESMethodology = ESMethodology.HISTORICAL_PORTFOLIO_RETURNS
    confidence_level: Decimal = Field(default=Decimal("0.9750"), ge=Decimal("0.8000"), le=Decimal("0.9999"))
    holding_horizon_days: int = Field(default=1, ge=1, le=252)
    valuation_base_type: str = "PORTFOLIO_NAV"
    reporting_currency: Optional[str] = None
    lookback_period_days: int = Field(default=252, ge=5, le=2520)
    quantile_method: ESQuantileMethod = ESQuantileMethod.LINEAR_INTERPOLATION
    tail_weighting_method: ESTailWeightingMethod = ESTailWeightingMethod.FRACTIONAL_BOUNDARY
    snapshot_id: Optional[str] = None
    config_id: Optional[str] = None
    var_result_id: Optional[str] = None
    as_of: Optional[date] = None
    simulation_count: int = Field(default=10000, ge=100, le=100000)
    random_seed: Optional[int] = 42


class ESTailObservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scenario_index: int
    scenario_reference: Optional[str] = None
    observation_date: Optional[date] = None
    portfolio_return: Decimal
    portfolio_loss: Decimal
    tail_weight: Decimal
    is_boundary_observation: bool
    loss_amount_native: Decimal


class ESContributionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    grouping_dimension: str
    entity_id: str
    entity_name: Optional[str] = None
    weight_percentage: Decimal
    average_tail_loss_percentage: Decimal
    contribution_amount: Decimal
    percentage_of_total_es: Decimal
    is_additive: bool


class ESDiagnosticResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    diagnostic_code: str
    severity: str
    diagnostic_value: Optional[str] = None
    description: str
    details: Optional[Dict[str, Any]] = None


class ExpectedShortfallResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    result_id: str
    portfolio_id: str
    portfolio_group_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    config_id: Optional[str] = None
    var_result_id: Optional[str] = None

    methodology: ESMethodology
    confidence_level: Decimal
    tail_probability: Decimal
    holding_horizon_days: int
    as_of_date: date
    valuation_base_amount: Decimal
    reporting_currency: str

    # Value at Risk comparison metrics
    var_return_percentage: Decimal
    var_monetary_amount: Decimal
    signed_var_loss_quantile: Decimal

    # Expected Shortfall metrics
    es_return_percentage: Decimal
    es_monetary_amount: Decimal
    signed_es_loss_average: Decimal

    # Tail Excess
    tail_excess_monetary_amount: Decimal
    tail_excess_percentage: Decimal
    es_to_var_ratio: Optional[Decimal] = None

    # Tail Sample Counts & Diagnostics
    total_observations_count: int
    eligible_observations_count: int
    expected_tail_observations: Decimal
    full_tail_observations_count: int
    effective_tail_sample_size: Decimal
    boundary_weight: Decimal

    # Tail loss dispersion
    worst_tail_loss_percentage: Decimal
    tail_median_loss_percentage: Decimal
    tail_standard_deviation: Optional[Decimal] = None

    quantile_method: str
    tail_weighting_method: str
    tail_stability_status: ESTailStabilityStatus
    calculation_status: ESCalculationStatus
    data_quality_status: str
    calculation_version: str
    calculated_at: datetime

    tail_observations: Optional[List[ESTailObservationResponse]] = None
    contributions: Optional[List[ESContributionResponse]] = None
    diagnostics: Optional[List[ESDiagnosticResponse]] = None


class ESConfidenceLevelItem(BaseModel):
    confidence_level: Decimal
    tail_probability: Decimal
    var_monetary_amount: Decimal
    var_return_percentage: Decimal
    es_monetary_amount: Decimal
    es_return_percentage: Decimal
    tail_excess_monetary_amount: Decimal
    tail_excess_percentage: Decimal
    expected_tail_observations: Decimal
    effective_tail_sample_size: Decimal
    tail_stability: ESTailStabilityStatus


class ESConfidenceComparisonResponse(BaseModel):
    portfolio_id: str
    as_of_date: date
    methodology: ESMethodology
    reporting_currency: str
    valuation_base_amount: Decimal
    levels: List[ESConfidenceLevelItem]


class ESMethodologyComparisonItem(BaseModel):
    methodology: ESMethodology
    var_monetary_amount: Decimal
    var_return_percentage: Decimal
    es_monetary_amount: Decimal
    es_return_percentage: Decimal
    tail_excess_monetary_amount: Decimal
    tail_excess_percentage: Decimal
    tail_observations_count: int
    effective_tail_sample_size: Decimal
    tail_stability_status: ESTailStabilityStatus


class ESMethodologyComparisonResponse(BaseModel):
    portfolio_id: str
    as_of_date: date
    reporting_currency: str
    valuation_base_amount: Decimal
    confidence_level: Decimal
    holding_horizon_days: int
    historical_portfolio_returns: Optional[ESMethodologyComparisonItem] = None
    historical_simulation: Optional[ESMethodologyComparisonItem] = None
    monte_carlo: Optional[ESMethodologyComparisonItem] = None
    max_absolute_es_difference: Decimal
    divergence_percentage: Decimal


class ESHistoricalTrendPoint(BaseModel):
    result_id: str
    as_of_date: date
    es_monetary_amount: Decimal
    es_return_percentage: Decimal
    var_monetary_amount: Decimal
    tail_excess_amount: Decimal
    tail_stability_status: str
    trend_direction: ESTrendDirection


class ESHistoricalTrendResponse(BaseModel):
    portfolio_id: str
    data_points: List[ESHistoricalTrendPoint]
    average_es_amount: Decimal
    peak_es_amount: Decimal
    min_es_amount: Decimal

