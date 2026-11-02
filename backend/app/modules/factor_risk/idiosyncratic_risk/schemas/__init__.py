"""
Pydantic schemas for M08.06 Idiosyncratic Risk.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from backend.app.modules.factor_risk.idiosyncratic_risk.models import (
    ResidualVarianceEstimator,
    ResidualModelQualityStatus,
    ContributionStatus,
    OutlierSeverity,
)


# ---------------------------------------------------------
# Configuration Schemas
# ---------------------------------------------------------

class ResidualConfigCreate(BaseModel):
    config_code: str = Field(..., max_length=64)
    config_name: str = Field(..., max_length=128)
    description: Optional[str] = None
    factor_model_id: str
    factor_model_version_id: str
    variance_estimator: ResidualVarianceEstimator = ResidualVarianceEstimator.SAMPLE
    observation_frequency: str = "DAILY"
    annualization_factor: Decimal = Field(Decimal("252.00"), gt=0)
    decay_factor: Optional[Decimal] = Field(Decimal("0.94"), gt=0, lt=1)
    minimum_observations: int = Field(20, ge=10)
    outlier_z_threshold: Decimal = Field(Decimal("3.00"), gt=0)


class ResidualConfigResponse(BaseModel):
    id: int
    config_id: str
    config_code: str
    config_name: str
    description: Optional[str] = None
    factor_model_id: str
    factor_model_version_id: str
    variance_estimator: ResidualVarianceEstimator
    observation_frequency: str
    annualization_factor: Decimal
    decay_factor: Optional[Decimal] = None
    minimum_observations: int
    outlier_z_threshold: Decimal
    config_hash: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------
# Instrument Residual Volatility Schemas
# ---------------------------------------------------------

class InstrumentResidualVolRequest(BaseModel):
    config_id: str
    instrument_id: str
    as_of_date: date
    listing_id: Optional[str] = None


class InstrumentResidualVolResponse(BaseModel):
    id: int
    run_id: str
    config_id: str
    instrument_id: str
    listing_id: Optional[str] = None
    as_of_date: date
    observation_count: int
    residual_mean: Decimal
    residual_variance_period: Decimal
    residual_volatility_period: Decimal
    residual_variance_annualized: Decimal
    residual_volatility_annualized: Decimal
    robust_mad_scale_annualized: Optional[Decimal] = None
    ew_residual_volatility_annualized: Optional[Decimal] = None
    effective_sample_size: Optional[Decimal] = None
    result_hash: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------
# Residual Covariance Snapshot Schemas
# ---------------------------------------------------------

class ResidualCovarianceRequest(BaseModel):
    factor_model_version_id: str
    as_of_date: date
    instrument_ids: List[str] = Field(..., min_length=1)
    use_diagonal: bool = False


class ResidualCovarianceResponse(BaseModel):
    id: int
    snapshot_id: str
    factor_model_version_id: str
    as_of_date: date
    observation_count: int
    dimension: int
    instrument_ids_ordered: List[str]
    covariance_matrix: List[List[float]]
    correlation_matrix: Optional[List[List[float]]] = None
    is_positive_semidefinite: bool
    min_eigenvalue: Decimal
    condition_number: Decimal
    matrix_rank: int
    result_hash: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------
# Security Risk Contribution Schemas
# ---------------------------------------------------------

class SecurityRiskContributionResponse(BaseModel):
    id: int
    instrument_id: str
    issuer_id: Optional[str] = None
    signed_weight: Decimal
    absolute_weight: Decimal
    standalone_residual_volatility_annualized: Decimal
    marginal_volatility_contribution_annualized: Decimal
    volatility_contribution_annualized: Decimal
    variance_contribution_annualized: Decimal
    percentage_contribution: Decimal
    contribution_status: ContributionStatus
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------
# Issuer Risk Contribution Schemas
# ---------------------------------------------------------

class IssuerRiskContributionResponse(BaseModel):
    id: int
    issuer_id: str
    member_instrument_count: int
    signed_issuer_weight: Decimal
    absolute_issuer_weight: Decimal
    issuer_residual_volatility_annualized: Decimal
    variance_contribution_annualized: Decimal
    volatility_contribution_annualized: Decimal
    percentage_contribution: Decimal
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------
# Portfolio Idiosyncratic Risk Schemas
# ---------------------------------------------------------

class PortfolioIdiosyncraticRiskRequest(BaseModel):
    config_id: str
    portfolio_id: str
    as_of_date: date
    use_diagonal: bool = False


class PortfolioIdiosyncraticRiskResponse(BaseModel):
    id: int
    run_id: str
    config_id: str
    portfolio_id: str
    portfolio_snapshot_id: Optional[str] = None
    as_of_date: date
    portfolio_idiosyncratic_variance_annualized: Decimal
    portfolio_idiosyncratic_volatility_annualized: Decimal
    diagonal_baseline_variance_annualized: Decimal
    covariance_effect_annualized: Decimal
    diversification_benefit_annualized: Decimal
    absolute_contribution_hhi: Decimal
    effective_number_of_risk_contributors: Decimal
    coverage_percentage: Decimal
    is_reconciled: bool
    result_hash: str
    security_contributions: List[SecurityRiskContributionResponse] = []
    issuer_contributions: List[IssuerRiskContributionResponse] = []
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------
# Residual Diagnostics Schemas
# ---------------------------------------------------------

class OutlierDetailResponse(BaseModel):
    id: int
    observation_date: date
    instrument_id: str
    residual_value: Decimal
    standardized_z_score: Decimal
    severity: OutlierSeverity
    detection_method: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ResidualDiagnosticRequest(BaseModel):
    config_id: str
    instrument_id: str
    as_of_date: date


class ResidualDiagnosticResponse(BaseModel):
    id: int
    diagnostic_run_id: str
    instrument_id: str
    factor_model_version_id: str
    as_of_date: date
    observation_count: int
    skewness: Decimal
    excess_kurtosis: Decimal
    jarque_bera_p_value: Decimal
    lag1_autocorrelation: Decimal
    ljung_box_p_value: Decimal
    arch_lm_p_value: Decimal
    has_structural_shift: bool
    model_quality_status: ResidualModelQualityStatus
    warning_messages: List[str]
    outliers: List[OutlierDetailResponse] = []
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
