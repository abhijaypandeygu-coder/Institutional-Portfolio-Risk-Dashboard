"""
M08.03 Factor Sensitivity Pydantic Schemas.
Data transfer objects and request/response models for:
1. Sensitivity Model Configurations & Window Configurations
2. Estimation Execution Requests & Responses
3. Factor Sensitivity Coefficients & Statistical Inference
4. Model Diagnostics & Residual Analysis
5. Coefficient Stability & Structural Break Tests
6. Direct Portfolio Sensitivity vs. Weighted Exposure Reconciliation
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from backend.app.modules.factor_risk.factor_definition.models import (
    FactorLifecycleStatus,
)
from backend.app.modules.factor_risk.factor_sensitivity.models import (
    TargetType,
    ModelFamily,
    SensitivityWindowType,
    MissingDataPolicy,
    StandardErrorMethod,
    StatisticalSignificanceCategory,
    CoefficientStabilityStatus,
    StructuralBreakTestType,
    StructuralBreakResultStatus,
    SensitivityRunStatus,
)


# ============================================================================
# 1. WINDOW CONFIGURATION SCHEMAS
# ============================================================================

class WindowConfigBase(BaseModel):
    window_type: SensitivityWindowType = Field(default=SensitivityWindowType.ROLLING)
    lookback_observations: int = Field(default=252, ge=20, le=2520)
    frequency: str = Field(default="DAILY")
    missing_data_policy: MissingDataPolicy = Field(default=MissingDataPolicy.LISTWISE_COMPLETE)
    minimum_observations: int = Field(default=30, ge=10)
    min_observations_per_param_multiplier: int = Field(default=5, ge=2)
    minimum_coverage_percentage: Decimal = Field(default=Decimal("80.00"), ge=Decimal("10.00"), le=Decimal("100.00"))


class WindowConfigCreate(WindowConfigBase):
    pass


class WindowConfigResponse(WindowConfigBase):
    window_config_id: str
    config_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# 2. MODEL CONFIGURATION SCHEMAS
# ============================================================================

class ModelConfigBase(BaseModel):
    config_code: str = Field(..., max_length=64)
    config_name: str = Field(..., max_length=128)
    description: str
    model_family: ModelFamily = Field(default=ModelFamily.OLS)
    factor_model_id: str = Field(..., max_length=36)
    factor_model_version_id: str = Field(..., max_length=36)
    include_intercept: bool = Field(default=True)
    standard_error_method: StandardErrorMethod = Field(default=StandardErrorMethod.HC3_HETEROSKEDASTICITY_ROBUST)
    confidence_level: Decimal = Field(default=Decimal("0.95"), ge=Decimal("0.50"), le=Decimal("0.999"))
    ewls_decay_factor: Optional[Decimal] = Field(default=Decimal("0.9400"), ge=Decimal("0.5000"), le=Decimal("0.9999"))
    ridge_lambda: Optional[Decimal] = Field(default=Decimal("0.0100"), ge=Decimal("0.0000"))
    quantile_tau: Optional[Decimal] = Field(default=Decimal("0.50"), ge=Decimal("0.01"), le=Decimal("0.99"))
    dependent_return_basis: str = Field(default="EXCESS_TOTAL_RETURN")
    return_type: str = Field(default="SIMPLE")
    currency_basis: str = Field(default="INR")


class CreateModelConfigRequest(ModelConfigBase):
    window_config: WindowConfigCreate = Field(default_factory=WindowConfigCreate)


class ModelConfigResponse(ModelConfigBase):
    config_id: str
    config_hash: str
    status: FactorLifecycleStatus
    created_at: datetime
    created_by: str
    window_configs: List[WindowConfigResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# 3. ESTIMATION EXECUTION SCHEMAS
# ============================================================================

class RunSensitivityRequest(BaseModel):
    config_id: str = Field(..., description="ID of factor sensitivity model configuration")
    target_type: TargetType = Field(default=TargetType.INSTRUMENT)
    target_id: str = Field(..., description="instrument_id or portfolio_id")
    target_listing_id: Optional[str] = None
    as_of_date: date = Field(..., description="Anchor date for estimation window")
    custom_window_start: Optional[date] = None
    custom_window_end: Optional[date] = None


class SensitivityCoefficientResponse(BaseModel):
    coefficient_id: str
    run_id: str
    factor_id: str
    factor_code: str
    factor_position: int
    coefficient_value: Decimal
    coefficient_standard_error: Optional[Decimal] = None
    t_statistic: Optional[Decimal] = None
    p_value: Optional[Decimal] = None
    adjusted_p_value: Optional[Decimal] = None
    confidence_interval_lower: Optional[Decimal] = None
    confidence_interval_upper: Optional[Decimal] = None
    confidence_level: Decimal
    significance_status: StatisticalSignificanceCategory
    economic_contribution_1sigma: Optional[Decimal] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ModelDiagnosticsResponse(BaseModel):
    diagnostic_id: str
    run_id: str
    intercept_value: Optional[Decimal] = None
    intercept_standard_error: Optional[Decimal] = None
    intercept_t_statistic: Optional[Decimal] = None
    intercept_p_value: Optional[Decimal] = None
    r_squared: Decimal
    adjusted_r_squared: Decimal
    residual_sum_of_squares: Decimal
    total_sum_of_squares: Decimal
    residual_variance: Decimal
    residual_standard_error: Decimal
    rmse: Decimal
    mae: Decimal
    degrees_of_freedom: int
    design_matrix_rank: int
    condition_number: Decimal
    variance_inflation_factors: Optional[Dict[str, Any]] = None
    durbin_watson_stat: Optional[Decimal] = None
    jarque_bera_stat: Optional[Decimal] = None
    jarque_bera_p_value: Optional[Decimal] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SensitivityRunResponse(BaseModel):
    run_id: str
    config_id: str
    factor_model_id: str
    factor_model_version_id: str
    target_type: TargetType
    target_id: str
    target_listing_id: Optional[str] = None
    as_of_date: date
    window_start: date
    window_end: date
    observation_count_expected: int
    observation_count_used: int
    effective_sample_size: Optional[Decimal] = None
    run_status: SensitivityRunStatus
    failure_reason: Optional[str] = None
    result_hash: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    coefficients: List[SensitivityCoefficientResponse] = []
    diagnostics: Optional[ModelDiagnosticsResponse] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# 4. STABILITY & STRUCTURAL BREAK SCHEMAS
# ============================================================================

class StructuralBreakTestResponse(BaseModel):
    break_test_id: str
    stability_id: str
    test_type: StructuralBreakTestType
    candidate_break_date: date
    pre_break_count: int
    post_break_count: int
    test_statistic: Decimal
    p_value: Optional[Decimal] = None
    critical_value_95: Decimal
    result_status: StructuralBreakResultStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SensitivityStabilityResponse(BaseModel):
    stability_id: str
    target_type: TargetType
    target_id: str
    factor_id: str
    factor_code: str
    analysis_start: date
    analysis_end: date
    observations_analyzed: int
    rolling_coefficient_mean: Decimal
    rolling_coefficient_std: Decimal
    rolling_coefficient_min: Decimal
    rolling_coefficient_max: Decimal
    latest_coefficient: Decimal
    previous_coefficient: Decimal
    absolute_change: Decimal
    relative_change: Optional[Decimal] = None
    sign_change_count: int
    stability_status: CoefficientStabilityStatus
    created_at: datetime
    break_tests: List[StructuralBreakTestResponse] = []

    model_config = ConfigDict(from_attributes=True)


class RunBreakTestRequest(BaseModel):
    stability_id: str
    candidate_break_date: date
    test_type: StructuralBreakTestType = Field(default=StructuralBreakTestType.CHOW_TEST)


# ============================================================================
# 5. RECONCILIATION SCHEMAS (DIRECT PORTFOLIO SENSITIVITY VS. WEIGHTED EXPOSURE)
# ============================================================================

class FactorSensitivityComparisonItem(BaseModel):
    factor_id: str
    factor_code: str
    direct_sensitivity_beta: Decimal
    direct_p_value: Optional[Decimal] = None
    direct_significance: StatisticalSignificanceCategory
    holdings_weighted_exposure: Decimal
    absolute_discrepancy: Decimal
    discrepancy_explanation: str


class PortfolioSensitivityReconciliationResponse(BaseModel):
    portfolio_id: str
    as_of_date: date
    direct_run_id: str
    model_config_id: str
    factor_model_id: str
    factor_model_name: str
    direct_portfolio_r2: Decimal
    comparison_items: List[FactorSensitivityComparisonItem] = []
    overall_alignment_status: str
