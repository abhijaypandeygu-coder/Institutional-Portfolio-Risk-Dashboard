"""
Module M07.02: Value at Risk Pydantic v2 Schemas.
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

from backend.app.modules.market_risk.value_at_risk.models import (
    VaRMethodology,
    HistoricalVaRSubMethod,
    VaRDistributionAssumption,
    VaRValuationBaseType,
    VaRQuantileMethod,
    VaRCalculationStatus,
    VaRTrendStatus,
)


class VaRModelConfigCreateRequest(BaseModel):
    config_name: str
    portfolio_id: Optional[str] = None
    portfolio_group_id: Optional[str] = None
    methodology: VaRMethodology = VaRMethodology.HISTORICAL
    historical_sub_method: HistoricalVaRSubMethod = HistoricalVaRSubMethod.PORTFOLIO_RETURNS
    confidence_level: Decimal = Decimal("0.9900")
    holding_horizon_days: int = 1
    valuation_base_type: VaRValuationBaseType = VaRValuationBaseType.PORTFOLIO_NAV
    reporting_currency: str = "USD"
    lookback_period_days: int = 252
    distribution_assumption: VaRDistributionAssumption = VaRDistributionAssumption.EMPIRICAL
    quantile_method: VaRQuantileMethod = VaRQuantileMethod.LINEAR_INTERPOLATION
    covariance_method: str = "SAMPLE_COVARIANCE"
    simulation_count: int = 10000
    random_seed: Optional[int] = 42


class VaRModelConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    config_id: str
    config_name: str
    portfolio_id: Optional[str] = None
    portfolio_group_id: Optional[str] = None
    methodology: VaRMethodology
    historical_sub_method: HistoricalVaRSubMethod
    confidence_level: Decimal
    holding_horizon_days: int
    valuation_base_type: VaRValuationBaseType
    reporting_currency: str
    lookback_period_days: int
    distribution_assumption: VaRDistributionAssumption
    quantile_method: VaRQuantileMethod
    covariance_method: str
    simulation_count: int
    random_seed: Optional[int] = None
    is_active: bool
    config_version: int
    created_at: datetime


class VaRCalculateRequest(BaseModel):
    portfolio_id: str
    snapshot_id: Optional[str] = None
    config_id: Optional[str] = None
    methodology: VaRMethodology = VaRMethodology.HISTORICAL
    confidence_level: Decimal = Decimal("0.9900")
    holding_horizon_days: int = 1
    valuation_base_type: VaRValuationBaseType = VaRValuationBaseType.PORTFOLIO_NAV
    reporting_currency: str = "USD"
    lookback_period_days: int = 252
    distribution_assumption: VaRDistributionAssumption = VaRDistributionAssumption.EMPIRICAL
    quantile_method: VaRQuantileMethod = VaRQuantileMethod.LINEAR_INTERPOLATION
    simulation_count: int = 10000
    random_seed: Optional[int] = 42
    as_of: Optional[date] = None


class VaRRiskContributionItem(BaseModel):
    grouping_dimension: str
    entity_id: str
    entity_name: str
    weight_percentage: Decimal
    marginal_var: Decimal
    component_var_amount: Decimal
    percentage_of_total_var: Decimal
    is_additive: bool


class VaRResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    result_id: str
    portfolio_id: str
    portfolio_group_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    config_id: Optional[str] = None
    methodology: VaRMethodology
    confidence_level: Decimal
    holding_horizon_days: int
    as_of_date: date
    valuation_base_amount: Decimal
    reporting_currency: str
    signed_loss_quantile: Decimal
    var_return_percentage: Decimal
    var_monetary_amount: Decimal
    distribution_assumption: str
    lookback_observations: int
    tail_observations_count: int
    portfolio_period_volatility: Optional[Decimal] = None
    expected_return: Optional[Decimal] = None
    simulation_count: Optional[int] = None
    successful_simulation_count: Optional[int] = None
    random_seed: Optional[int] = None
    calculation_status: VaRCalculationStatus
    data_quality_status: str
    calculation_version: str
    calculated_at: datetime
    contributions: Optional[List[VaRRiskContributionItem]] = None


class VaRMethodologyComparisonItem(BaseModel):
    methodology: VaRMethodology
    var_monetary_amount: Decimal
    var_return_percentage: Decimal
    confidence_level: Decimal
    holding_horizon_days: int
    valuation_base_amount: Decimal
    lookback_observations: int
    distribution_assumption: str
    calculation_status: VaRCalculationStatus


class VaRModelComparisonResponse(BaseModel):
    portfolio_id: str
    as_of_date: date
    reporting_currency: str
    confidence_level: Decimal
    holding_horizon_days: int
    valuation_base_amount: Decimal
    historical_var: Optional[VaRMethodologyComparisonItem] = None
    parametric_var: Optional[VaRMethodologyComparisonItem] = None
    monte_carlo_var: Optional[VaRMethodologyComparisonItem] = None
    diff_historical_minus_parametric: Optional[Decimal] = None
    diff_historical_minus_monte_carlo: Optional[Decimal] = None
    diff_parametric_minus_monte_carlo: Optional[Decimal] = None
    comparison_notes: str


class VaRHistoricalTrendPoint(BaseModel):
    result_id: str
    as_of_date: date
    methodology: VaRMethodology
    confidence_level: Decimal
    holding_horizon_days: int
    var_monetary_amount: Decimal
    var_return_percentage: Decimal
    valuation_base_amount: Decimal
    calculated_at: datetime


class VaRHistoricalTrendResponse(BaseModel):
    portfolio_id: str
    methodology: VaRMethodology
    total_points: int
    current_var_amount: Decimal
    prior_var_amount: Optional[Decimal] = None
    var_change: Decimal
    var_pct_change: Optional[Decimal] = None
    trend_status: VaRTrendStatus
    series: List[VaRHistoricalTrendPoint]


class VaRDiagnosticItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    diagnostic_id: str
    diagnostic_code: str
    severity: str
    description: str
    created_at: datetime
