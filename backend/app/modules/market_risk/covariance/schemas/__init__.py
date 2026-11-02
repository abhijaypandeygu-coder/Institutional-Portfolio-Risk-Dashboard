"""
M07.06 Covariance Analysis Pydantic Schemas.
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from backend.app.modules.market_risk.covariance.models import (
    CovarianceEstimator,
    DenominatorPolicy,
    CovarianceScopeType,
    WeightBasis,
    MatrixPSDStatus,
)


class CovarianceConfigCreate(BaseModel):
    config_name: str = Field(..., max_length=100)
    estimator: CovarianceEstimator = CovarianceEstimator.SAMPLE
    denominator_policy: DenominatorPolicy = DenominatorPolicy.UNBIASED_SAMPLE
    default_lookback_days: int = Field(60, ge=5, le=2520)
    min_observations: int = Field(20, ge=3, le=500)
    annualization_factor: Decimal = Field(Decimal("252.0"), ge=1.0, le=100000.0)
    ewma_decay_factor: Optional[Decimal] = Field(Decimal("0.94"), ge=0.5, le=0.999)
    description: Optional[str] = None


class CovarianceConfigResponse(CovarianceConfigCreate):
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PairwiseCovarianceRequest(BaseModel):
    asset_a_id: str
    asset_b_id: str
    lookback_days: int = Field(60, ge=5, le=2520)
    as_of: Optional[date] = None
    estimator: CovarianceEstimator = CovarianceEstimator.SAMPLE
    denominator_policy: DenominatorPolicy = DenominatorPolicy.UNBIASED_SAMPLE
    annualize: bool = True
    annualization_factor: Decimal = Decimal("252.0")
    portfolio_id: Optional[str] = None


class PairwiseCovarianceResponse(BaseModel):
    asset_a_id: str
    asset_b_id: str
    asset_a_symbol: str
    asset_b_symbol: str
    as_of_date: datetime
    lookback_days: int
    estimator: CovarianceEstimator
    denominator_policy: DenominatorPolicy
    covariance_value: Decimal
    annualized_covariance: Optional[Decimal] = None
    variance_a: Decimal
    variance_b: Decimal
    std_dev_a: Decimal
    std_dev_b: Decimal
    correlation_coefficient: Decimal
    sample_size: int
    units: str = "decimal-return squared"


class MatrixCovarianceRequest(BaseModel):
    portfolio_id: Optional[str] = None
    asset_ids: Optional[List[str]] = None
    lookback_days: int = Field(60, ge=5, le=2520)
    as_of: Optional[date] = None
    estimator: CovarianceEstimator = CovarianceEstimator.SAMPLE
    denominator_policy: DenominatorPolicy = DenominatorPolicy.UNBIASED_SAMPLE
    annualize: bool = False
    annualization_factor: Decimal = Decimal("252.0")
    repair_psd: bool = False
    transformation_method: Optional[str] = "SPECTRAL_CLIPPING"


class CovarianceMatrixResponse(BaseModel):
    matrix_id: str
    matrix_code: str
    portfolio_id: Optional[str] = None
    as_of_date: datetime
    lookback_days: int
    estimator: CovarianceEstimator
    dimension: int
    asset_ids: List[str]
    asset_symbols: List[str]
    matrix: List[List[Decimal]]
    
    # Diagnostics & PSD
    psd_status: MatrixPSDStatus
    min_eigenvalue: Decimal
    max_eigenvalue: Decimal
    condition_number: Optional[Decimal] = None
    negative_eigenvalues_count: int
    is_symmetric: bool
    max_symmetry_discrepancy: Decimal
    completeness_ratio: Decimal
    average_variance: Decimal
    
    # Repaired Matrix if applicable
    transformed_matrix: Optional[List[List[Decimal]]] = None
    transformation_info: Optional[Dict[str, Any]] = None


class RollingCovarianceRequest(BaseModel):
    asset_a_id: str
    asset_b_id: str
    window_days: int = Field(30, ge=5, le=252)
    history_lookback_days: int = Field(180, ge=30, le=2520)
    as_of: Optional[date] = None
    estimator: CovarianceEstimator = CovarianceEstimator.SAMPLE
    denominator_policy: DenominatorPolicy = DenominatorPolicy.UNBIASED_SAMPLE


class RollingCovariancePoint(BaseModel):
    observation_date: date
    covariance: Decimal
    delta_covariance: Optional[Decimal] = None
    sample_size: int


class RollingCovarianceResponse(BaseModel):
    asset_a_id: str
    asset_b_id: str
    asset_a_symbol: str
    asset_b_symbol: str
    window_days: int
    history_lookback_days: int
    estimator: CovarianceEstimator
    series: List[RollingCovariancePoint]


class AssetRiskContribution(BaseModel):
    asset_id: str
    symbol: str
    weight: Decimal
    marginal_contribution_variance: Decimal
    component_contribution_variance: Decimal
    variance_contribution_percentage: Optional[Decimal] = None
    marginal_contribution_volatility: Decimal
    component_contribution_volatility: Decimal
    volatility_contribution_percentage: Optional[Decimal] = None


class PortfolioCovarianceRequest(BaseModel):
    portfolio_id: str
    lookback_days: int = Field(60, ge=5, le=2520)
    as_of: Optional[date] = None
    weight_basis: WeightBasis = WeightBasis.PORTFOLIO_NAV
    user_weights: Optional[Dict[str, Decimal]] = None
    annualization_factor: Decimal = Decimal("252.0")


class PortfolioCovarianceResponse(BaseModel):
    calculation_code: str
    portfolio_id: str
    as_of_date: datetime
    matrix_id: str
    weight_basis: WeightBasis
    period_portfolio_variance: Decimal
    period_portfolio_volatility: Decimal
    annualized_portfolio_variance: Decimal
    annualized_portfolio_volatility: Decimal
    annualization_factor: Decimal
    contributions: List[AssetRiskContribution]
    reconciliation_variance_sum: Decimal
    reconciliation_volatility_sum: Decimal
    variance_discrepancy: Decimal
    volatility_discrepancy: Decimal


class PortfolioPairCovarianceRequest(BaseModel):
    portfolio_a_id: str
    portfolio_b_id: str
    lookback_days: int = Field(60, ge=5, le=2520)
    as_of: Optional[date] = None
    annualize: bool = False
    annualization_factor: Decimal = Decimal("252.0")


class PortfolioPairCovarianceResponse(BaseModel):
    portfolio_a_id: str
    portfolio_b_id: str
    as_of_date: datetime
    period_covariance: Decimal
    annualized_covariance: Optional[Decimal] = None
    portfolio_a_variance: Decimal
    portfolio_b_variance: Decimal
    portfolio_a_volatility: Decimal
    portfolio_b_volatility: Decimal
    derived_correlation: Decimal
