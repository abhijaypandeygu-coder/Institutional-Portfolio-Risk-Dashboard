"""
M08.04 Factor Attribution Pydantic Schemas.
Data transfer objects and request/response models for:
1. Attribution Configurations
2. Return Attribution Requests and Responses
3. Risk Attribution Requests and Responses
4. Covariance Snapshots
5. Reconciliation Bridges
6. Attribution Comparisons
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from backend.app.modules.factor_risk.factor_definition.models import (
    FactorLifecycleStatus,
)
from backend.app.modules.factor_risk.factor_attribution.models import (
    AttributionMode,
    AttributionReturnBasis,
    MultiPeriodLinkingMethod,
    ReturnComponentType,
    RiskComponentType,
    AttributionReconciliationStatus,
    AttributionRunStatus,
    CovarianceMethod,
)


# ============================================================================
# 1. ATTRIBUTION CONFIGURATION SCHEMAS
# ============================================================================

class AttributionConfigBase(BaseModel):
    config_code: str = Field(..., max_length=64)
    config_name: str = Field(..., max_length=128)
    description: str
    factor_model_id: str = Field(..., max_length=36)
    factor_model_version_id: str = Field(..., max_length=36)
    attribution_mode: AttributionMode = Field(default=AttributionMode.EX_ANTE_PINNED)
    return_basis: AttributionReturnBasis = Field(default=AttributionReturnBasis.EXCESS_RETURN)
    linking_method: MultiPeriodLinkingMethod = Field(default=MultiPeriodLinkingMethod.CARINO)
    covariance_method: CovarianceMethod = Field(default=CovarianceMethod.SAMPLE)
    annualization_factor: Decimal = Field(default=Decimal("252.00"), ge=Decimal("1.00"))
    reconciliation_tolerance: Decimal = Field(default=Decimal("0.00001000"))
    coverage_threshold_pct: Decimal = Field(default=Decimal("80.00"), ge=Decimal("10.00"), le=Decimal("100.00"))
    currency_basis: str = Field(default="INR", max_length=3)


class CreateAttributionConfigRequest(AttributionConfigBase):
    pass


class AttributionConfigResponse(AttributionConfigBase):
    config_id: str
    config_hash: str
    status: FactorLifecycleStatus
    created_at: datetime
    created_by: str

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# 2. RETURN ATTRIBUTION SCHEMAS
# ============================================================================

class RunReturnAttributionRequest(BaseModel):
    portfolio_id: str = Field(..., description="Target portfolio ID")
    config_id: str = Field(..., description="Factor attribution config ID")
    start_date: date = Field(..., description="Attribution period start date")
    end_date: date = Field(..., description="Attribution period end date")
    attribution_mode: Optional[AttributionMode] = None
    linking_method: Optional[MultiPeriodLinkingMethod] = None
    sensitivity_run_id: Optional[str] = None
    exposure_snapshot_id: Optional[str] = None


class ReturnAttributionComponentResponse(BaseModel):
    component_id: str
    run_id: str
    component_type: ReturnComponentType
    factor_id: Optional[str] = None
    factor_code: Optional[str] = None
    factor_sensitivity_beta: Optional[Decimal] = None
    factor_realized_return: Optional[Decimal] = None
    arithmetic_contribution: Decimal
    linked_contribution: Optional[Decimal] = None
    contribution_percentage_of_return: Optional[Decimal] = None
    currency: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttributionReconciliationResponse(BaseModel):
    reconciliation_id: str
    return_run_id: Optional[str] = None
    risk_run_id: Optional[str] = None
    reconciliation_type: str
    observed_value: Decimal
    reported_value: Decimal
    absolute_difference: Decimal
    relative_difference: Optional[Decimal] = None
    tolerance: Decimal
    coverage_percentage: Decimal
    reconciliation_status: AttributionReconciliationStatus
    reason_codes: Optional[List[str]] = None
    diagnostic_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReturnAttributionRunResponse(BaseModel):
    run_id: str
    config_id: str
    portfolio_id: str
    factor_model_id: str
    factor_model_version_id: str
    sensitivity_run_id: Optional[str] = None
    exposure_snapshot_id: Optional[str] = None
    period_start: date
    period_end: date
    attribution_mode: AttributionMode
    linking_method: MultiPeriodLinkingMethod
    realized_portfolio_return: Decimal
    total_attributed_return: Decimal
    factor_explained_return: Decimal
    risk_free_contribution: Decimal
    intercept_contribution: Decimal
    model_residual: Decimal
    reconciliation_residual: Decimal
    reconciliation_status: AttributionReconciliationStatus
    coverage_percentage: Decimal
    run_status: AttributionRunStatus
    failure_reason: Optional[str] = None
    result_hash: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    components: List[ReturnAttributionComponentResponse] = []
    reconciliation: Optional[AttributionReconciliationResponse] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# 3. COVARIANCE SNAPSHOT SCHEMAS
# ============================================================================

class FactorCovarianceSnapshotResponse(BaseModel):
    snapshot_id: str
    factor_model_id: str
    factor_model_version_id: str
    covariance_method: CovarianceMethod
    observation_frequency: str
    estimation_window_start: date
    estimation_window_end: date
    observation_count: int
    annualization_factor: Decimal
    factor_names_ordered: List[str]
    covariance_matrix: List[List[float]]
    is_positive_semidefinite: bool
    min_eigenvalue: Decimal
    condition_number: Decimal
    result_hash: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# 4. RISK ATTRIBUTION SCHEMAS
# ============================================================================

class RunRiskAttributionRequest(BaseModel):
    portfolio_id: str = Field(..., description="Target portfolio ID")
    config_id: str = Field(..., description="Factor attribution config ID")
    as_of_date: date = Field(..., description="Risk calculation as-of date")
    covariance_snapshot_id: Optional[str] = None
    sensitivity_run_id: Optional[str] = None
    exposure_snapshot_id: Optional[str] = None


class RiskAttributionComponentResponse(BaseModel):
    component_id: str
    run_id: str
    component_type: RiskComponentType
    factor_id: Optional[str] = None
    factor_code: Optional[str] = None
    factor_sensitivity_beta: Optional[Decimal] = None
    variance_contribution: Decimal
    volatility_contribution: Decimal
    marginal_volatility_contribution: Optional[Decimal] = None
    marginal_variance_contribution: Optional[Decimal] = None
    percentage_volatility_contribution: Optional[Decimal] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RiskAttributionRunResponse(BaseModel):
    run_id: str
    config_id: str
    portfolio_id: str
    factor_model_id: str
    factor_model_version_id: str
    covariance_snapshot_id: str
    sensitivity_run_id: Optional[str] = None
    exposure_snapshot_id: Optional[str] = None
    as_of_date: date
    observation_frequency: str
    annualization_factor: Decimal
    systematic_variance: Decimal
    systematic_volatility: Decimal
    residual_variance: Optional[Decimal] = None
    residual_volatility: Optional[Decimal] = None
    factor_residual_covariance: Optional[Decimal] = None
    total_modeled_variance: Decimal
    total_modeled_volatility: Decimal
    realized_portfolio_variance: Optional[Decimal] = None
    variance_reconciliation_difference: Optional[Decimal] = None
    run_status: AttributionRunStatus
    failure_reason: Optional[str] = None
    result_hash: Optional[str] = None
    created_at: datetime
    components: List[RiskAttributionComponentResponse] = []
    reconciliation: Optional[AttributionReconciliationResponse] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# 5. ATTRIBUTION COMPARISON SCHEMA
# ============================================================================

class AttributionComparisonRequest(BaseModel):
    portfolio_id: str
    run_id_base: str
    run_id_target: str
    comparison_dimension: str = Field(default="PERIOD", description="PERIOD, PORTFOLIO, or METHODOLOGY")


class AttributionComparisonResponse(BaseModel):
    portfolio_id: str
    comparison_dimension: str
    run_id_base: str
    run_id_target: str
    base_portfolio_return: Optional[Decimal] = None
    target_portfolio_return: Optional[Decimal] = None
    return_difference: Optional[Decimal] = None
    base_systematic_volatility: Optional[Decimal] = None
    target_systematic_volatility: Optional[Decimal] = None
    volatility_difference: Optional[Decimal] = None
    factor_shifts: Dict[str, Dict[str, Any]] = {}

