"""
M08.02 Factor Exposure Pydantic Schemas.
Request and response models for:
- Factor return observation ingestion
- Factor exposure estimation configurations
- Estimation run execution
- Instrument-level factor loadings
- Portfolio-level factor exposures & tilt classification
- Exposure change attribution & comparison
"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from backend.app.modules.factor_risk.factor_exposure.models import (
    EstimationMethod,
    DependentReturnBasis,
    ReturnType,
    CorporateActionBasis,
    StandardErrorMethod,
    RunStatus,
    LoadingQualityStatus,
    WeightingBasis,
    TiltClassification,
    ComparabilityStatus,
    RestatementStatus,
)


# ----------------------------------------------------------------------------
# 1. FACTOR RETURN INGESTION
# ----------------------------------------------------------------------------

class FactorReturnObservationInput(BaseModel):
    trading_date: date
    return_value: Decimal = Field(..., description="Daily return in decimal (e.g. 0.0125 for 1.25%)")
    risk_free_rate: Decimal = Field(Decimal("0.0"), description="Daily risk-free rate in decimal")


class IngestFactorReturnsRequest(BaseModel):
    factor_id: str
    factor_code: str
    version_id: str
    market_scope: str = "INDIA"
    currency: str = "INR"
    frequency: str = "DAILY"
    return_convention: str = "SIMPLE"
    observations: List[FactorReturnObservationInput]


class FactorReturnObservationResponse(BaseModel):
    observation_id: str
    series_id: str
    trading_date: date
    return_value: Decimal
    risk_free_rate: Decimal
    excess_return_value: Decimal
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ----------------------------------------------------------------------------
# 2. ESTIMATION CONFIGURATION
# ----------------------------------------------------------------------------

class CreateEstimationConfigRequest(BaseModel):
    config_code: str = Field(..., max_length=64)
    config_name: str = Field(..., max_length=128)
    description: str
    factor_model_id: str
    factor_model_version_id: str
    estimation_method: EstimationMethod = EstimationMethod.ROLLING_OLS
    lookback_observations: int = Field(252, ge=10, le=1260)
    return_frequency: str = "DAILY"
    dependent_return_basis: DependentReturnBasis = DependentReturnBasis.EXCESS_TOTAL_RETURN
    return_type: ReturnType = ReturnType.SIMPLE
    corporate_action_basis: CorporateActionBasis = CorporateActionBasis.TOTAL_RETURN_ADJUSTED
    include_intercept: bool = True
    minimum_observations: int = Field(30, ge=5)
    min_observations_per_param_multiplier: int = Field(5, ge=2)
    ewls_decay_factor: Optional[Decimal] = Decimal("0.9400")
    standard_error_method: StandardErrorMethod = StandardErrorMethod.HC3_HETEROSKEDASTICITY_ROBUST
    currency_basis: str = "INR"


class EstimationConfigResponse(BaseModel):
    config_id: str
    config_code: str
    config_name: str
    description: str
    factor_model_id: str
    factor_model_version_id: str
    estimation_method: EstimationMethod
    lookback_observations: int
    return_frequency: str
    dependent_return_basis: DependentReturnBasis
    return_type: ReturnType
    corporate_action_basis: CorporateActionBasis
    include_intercept: bool
    minimum_observations: int
    min_observations_per_param_multiplier: int
    ewls_decay_factor: Optional[Decimal]
    standard_error_method: StandardErrorMethod
    currency_basis: str
    configuration_hash: str
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ----------------------------------------------------------------------------
# 3. ESTIMATION EXECUTION RUN
# ----------------------------------------------------------------------------

class RunEstimationRequest(BaseModel):
    config_id: str
    factor_model_id: str
    factor_model_version_id: str
    as_of_date: Optional[date] = None
    instrument_ids: Optional[List[str]] = None  # None => all instruments in active books
    lookback_override: Optional[int] = None
    estimation_method_override: Optional[EstimationMethod] = None


class FactorLoadingRunResponse(BaseModel):
    run_id: str
    config_id: str
    factor_model_id: str
    factor_model_version_id: str
    as_of_date: date
    window_start: date
    window_end: date
    requested_count: int
    successful_count: int
    failed_count: int
    run_status: RunStatus
    failure_summary: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


# ----------------------------------------------------------------------------
# 4. INSTRUMENT FACTOR LOADINGS
# ----------------------------------------------------------------------------

class InstrumentFactorLoadingResponse(BaseModel):
    loading_id: str
    run_id: str
    instrument_id: str
    listing_id: Optional[str] = None
    factor_id: str
    factor_code: str
    factor_position: int
    loading_value: Decimal
    standardized_loading_value: Optional[Decimal] = None
    cross_sectional_zscore: Optional[Decimal] = None
    intercept_value: Optional[Decimal] = None
    standard_error: Optional[Decimal] = None
    t_statistic: Optional[Decimal] = None
    p_value: Optional[Decimal] = None
    confidence_interval_lower: Optional[Decimal] = None
    confidence_interval_upper: Optional[Decimal] = None
    r_squared: Optional[Decimal] = None
    adjusted_r_squared: Optional[Decimal] = None
    residual_variance: Optional[Decimal] = None
    observation_count: int
    design_matrix_rank: Optional[int] = None
    condition_number: Optional[Decimal] = None
    variance_inflation_factor: Optional[Decimal] = None
    status: LoadingQualityStatus
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ----------------------------------------------------------------------------
# 5. PORTFOLIO FACTOR EXPOSURE
# ----------------------------------------------------------------------------

class PortfolioFactorExposureItem(BaseModel):
    factor_id: str
    factor_code: str
    factor_position: int
    exposure_value: Decimal
    standardized_exposure_value: Optional[Decimal] = None
    gross_normalized_exposure: Optional[Decimal] = None
    tilt_classification: TiltClassification
    quality_status: LoadingQualityStatus


class PortfolioFactorExposureResponse(BaseModel):
    portfolio_id: str
    portfolio_snapshot_id: Optional[str] = None
    loading_run_id: str
    factor_model_id: str
    factor_model_version_id: str
    as_of_date: date
    weighting_basis: WeightingBasis
    portfolio_base_currency: str
    nav_reference: Decimal
    gross_market_value: Decimal
    covered_signed_weight: Decimal
    covered_absolute_weight: Decimal
    missing_signed_weight: Decimal
    missing_absolute_weight: Decimal
    coverage_percentage: Decimal
    holding_count: int
    covered_holding_count: int
    uncovered_holding_count: int
    calculation_timestamp: datetime
    restatement_status: RestatementStatus
    exposures: List[PortfolioFactorExposureItem]
    model_config = ConfigDict(from_attributes=True)


# ----------------------------------------------------------------------------
# 6. EXPOSURE CHANGE ATTRIBUTION
# ----------------------------------------------------------------------------

class ExposureChangeAttributionItem(BaseModel):
    instrument_id: str
    type: str
    earlier_weight: Decimal
    later_weight: Decimal
    earlier_loading: Decimal
    later_loading: Decimal
    weight_effect: Decimal
    loading_effect: Decimal
    total_effect: Decimal


class CompareFactorExposuresRequest(BaseModel):
    portfolio_id: str
    earlier_date: date
    later_date: date
    factor_code: str = "MKT_INDIA"
    factor_model_version_id: Optional[str] = None


class CompareFactorExposuresResponse(BaseModel):
    portfolio_id: str
    factor_code: str
    earlier_date: date
    later_date: date
    earlier_exposure: Decimal
    later_exposure: Decimal
    total_change: Decimal
    percentage_change: Optional[Decimal] = None
    weight_effect: Decimal
    loading_effect: Decimal
    entry_exit_effect: Decimal
    unreconciled_residual: Decimal
    comparability_status: ComparabilityStatus
    instruments: List[ExposureChangeAttributionItem]

