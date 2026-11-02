"""
Pydantic schemas for M08.07 Factor Correlation & Covariance Analytics.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from backend.app.modules.factor_risk.factor_correlation.models import (
    FactorCorrelationMethod,
    FactorCovarianceMethod,
    MissingDataPolicy,
    CorrelationRelationshipClassification,
    CorrelationStabilityCategory,
    CorrelationRegimeStatus,
    RegimeAlertSeverity,
    RegimeAlertStatus,
)


# ---------------------------------------------------------
# Configuration Schemas
# ---------------------------------------------------------

class FactorCorrelationConfigCreate(BaseModel):
    config_code: str = Field(..., max_length=64)
    config_name: str = Field(..., max_length=128)
    description: Optional[str] = None
    factor_model_id: str
    factor_model_version_id: str
    correlation_method: FactorCorrelationMethod = FactorCorrelationMethod.PEARSON
    observation_frequency: str = "DAILY"
    return_convention: str = "SIMPLE"
    currency_basis: str = "INR"
    missing_data_policy: MissingDataPolicy = MissingDataPolicy.LISTWISE_COMPLETE
    estimation_window: int = Field(60, ge=10, le=1260)
    minimum_observations: int = Field(20, ge=5)
    confidence_level: Decimal = Field(Decimal("0.95"), gt=0, lt=1)


class FactorCorrelationConfigResponse(BaseModel):
    id: int
    config_id: str
    config_code: str
    config_name: str
    description: Optional[str] = None
    factor_model_id: str
    factor_model_version_id: str
    correlation_method: FactorCorrelationMethod
    observation_frequency: str
    return_convention: str
    currency_basis: str
    missing_data_policy: MissingDataPolicy
    estimation_window: int
    minimum_observations: int
    confidence_level: Decimal
    config_hash: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------
# Pairwise & Matrix Correlation Schemas
# ---------------------------------------------------------

class FactorCorrelationPairResponse(BaseModel):
    id: int
    factor_a_id: str
    factor_b_id: str
    factor_a_code: str
    factor_b_code: str
    correlation_value: Optional[Decimal] = None
    covariance_value: Optional[Decimal] = None
    factor_a_volatility_annualized: Decimal
    factor_b_volatility_annualized: Decimal
    p_value: Optional[Decimal] = None
    ci_lower: Optional[Decimal] = None
    ci_upper: Optional[Decimal] = None
    relationship_classification: CorrelationRelationshipClassification
    is_defined: bool
    undefined_reason: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class FactorCorrelationCalculateRequest(BaseModel):
    config_id: Optional[str] = None
    factor_model_version_id: str
    as_of_date: date
    selected_factor_ids: Optional[List[str]] = None
    correlation_method: Optional[FactorCorrelationMethod] = FactorCorrelationMethod.PEARSON
    estimation_window: Optional[int] = 60
    missing_data_policy: Optional[MissingDataPolicy] = MissingDataPolicy.LISTWISE_COMPLETE


class FactorCorrelationRunResponse(BaseModel):
    id: int
    run_id: str
    config_id: str
    factor_model_version_id: str
    as_of_date: date
    window_start: date
    window_end: date
    observation_count: int
    factor_count: int
    valid_pair_count: int
    invalid_pair_count: int
    is_positive_semidefinite: bool
    min_eigenvalue: Decimal
    max_eigenvalue: Decimal
    condition_number: Decimal
    matrix_rank: int
    result_hash: str
    pairs: List[FactorCorrelationPairResponse] = []
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class FactorCorrelationMatrixSnapshotResponse(BaseModel):
    id: int
    matrix_id: str
    run_id: str
    factor_model_version_id: str
    as_of_date: date
    dimension: int
    factor_ordering: List[str]
    correlation_matrix: List[List[float]]
    is_symmetric: bool
    is_positive_semidefinite: bool
    min_eigenvalue: Decimal
    max_eigenvalue: Decimal
    condition_number: Decimal
    result_hash: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------
# Covariance Schemas
# ---------------------------------------------------------

class FactorCovarianceCalculateRequest(BaseModel):
    factor_model_id: str
    factor_model_version_id: str
    as_of_date: date
    covariance_method: FactorCovarianceMethod = FactorCovarianceMethod.SAMPLE
    estimation_window: int = 252
    observation_frequency: str = "DAILY"
    annualization_factor: Decimal = Decimal("252.00")
    decay_factor: Optional[Decimal] = Decimal("0.94")
    shrinkage_target: Optional[str] = "IDENTITY"
    shrinkage_intensity: Optional[Decimal] = None
    regularize_if_non_psd: bool = True


class FactorCovarianceSnapshotResponse(BaseModel):
    id: int
    snapshot_id: str
    factor_model_id: str
    factor_model_version_id: str
    covariance_method: FactorCovarianceMethod
    as_of_date: date
    window_start: date
    window_end: date
    observation_count: int
    effective_sample_size: Decimal
    dimension: int
    factor_ordering: List[str]
    covariance_matrix_period: List[List[float]]
    covariance_matrix_annualized: List[List[float]]
    correlation_matrix: List[List[float]]
    factor_volatilities_annualized: List[float]
    is_positive_semidefinite: bool
    min_eigenvalue: Decimal
    max_eigenvalue: Decimal
    condition_number: Decimal
    matrix_rank: int
    is_regularized: bool
    original_min_eigenvalue: Optional[Decimal] = None
    result_hash: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------
# Rolling Correlation Schemas
# ---------------------------------------------------------

class RollingFactorCorrelationRequest(BaseModel):
    factor_model_version_id: str
    factor_a_code: str
    factor_b_code: str
    as_of_date: date
    window_length: int = 60
    min_observations: int = 20
    baseline_window: Optional[int] = 252


class RollingCorrelationPoint(BaseModel):
    date: date
    correlation: float
    covariance: float
    std_a: float
    std_b: float


class RollingFactorCorrelationResponse(BaseModel):
    factor_model_version_id: str
    factor_a_code: str
    factor_b_code: str
    as_of_date: date
    window_length: int
    current_correlation: Decimal
    previous_correlation: Decimal
    signed_correlation_change: Decimal
    absolute_strength_change: Decimal
    baseline_correlation: Decimal
    percentile_rank: Decimal
    stability_status: CorrelationStabilityCategory
    is_sign_reversal: bool
    rolling_min: float
    rolling_max: float
    rolling_mean: float
    rolling_std: float
    history: List[RollingCorrelationPoint] = []


# ---------------------------------------------------------
# Regime Detection & Alert Schemas
# ---------------------------------------------------------

class FactorRegimeEvaluateRequest(BaseModel):
    factor_model_version_id: str
    as_of_date: date
    window_length: int = 60
    high_positive_threshold: Optional[Decimal] = Decimal("0.70")
    high_negative_threshold: Optional[Decimal] = Decimal("-0.70")
    rapid_change_threshold: Optional[Decimal] = Decimal("0.25")
    confirmation_observations: Optional[int] = 2


class FactorRegimeAlertResponse(BaseModel):
    id: int
    alert_id: str
    factor_model_version_id: str
    factor_a_code: str
    factor_b_code: str
    as_of_date: date
    alert_type: str
    severity: RegimeAlertSeverity
    status: RegimeAlertStatus
    current_correlation: Decimal
    baseline_correlation: Decimal
    trigger_threshold: Decimal
    message: str
    first_detected_at: datetime
    last_detected_at: datetime
    recovered_at: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class FactorRegimeEvaluationResponse(BaseModel):
    factor_model_version_id: str
    as_of_date: date
    evaluated_pairs_count: int
    active_alerts_count: int
    structural_breaks_count: int
    alerts: List[FactorRegimeAlertResponse] = []

