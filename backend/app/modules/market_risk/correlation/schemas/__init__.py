"""
M07.05 Correlation Analysis Pydantic Schemas.
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from backend.app.modules.market_risk.correlation.models import (
    CorrelationEstimator,
    CorrelationAlignmentPolicy,
    CorrelationMissingDataPolicy,
    CorrelationScopeType,
    PSDStatus,
    CorrelationRegimeEventType,
    CorrelationRegimeStatus,
)


class CorrelationConfigCreate(BaseModel):
    config_name: str = Field(..., max_length=100)
    estimator: CorrelationEstimator = CorrelationEstimator.PEARSON
    alignment_policy: CorrelationAlignmentPolicy = CorrelationAlignmentPolicy.COMMON_SESSION_DATE
    missing_data_policy: CorrelationMissingDataPolicy = CorrelationMissingDataPolicy.STRICT_PAIRWISE_COMPLETE
    default_lookback_days: int = Field(60, ge=5, le=2520)
    min_observations: int = Field(20, ge=3, le=500)
    high_correlation_threshold: Decimal = Field(Decimal("0.7000"), ge=-1.0, le=1.0)
    negative_correlation_threshold: Decimal = Field(Decimal("-0.5000"), ge=-1.0, le=1.0)
    rapid_change_threshold: Decimal = Field(Decimal("0.3000"), ge=0.01, le=2.0)
    persistence_periods: int = Field(3, ge=1, le=50)
    description: Optional[str] = None


class CorrelationConfigResponse(CorrelationConfigCreate):
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PairwiseCorrelationRequest(BaseModel):
    asset_a_id: str
    asset_b_id: str
    lookback_days: int = Field(60, ge=5, le=2520)
    as_of: Optional[date] = None
    estimator: CorrelationEstimator = CorrelationEstimator.PEARSON
    alignment_policy: CorrelationAlignmentPolicy = CorrelationAlignmentPolicy.COMMON_SESSION_DATE
    missing_data_policy: CorrelationMissingDataPolicy = CorrelationMissingDataPolicy.STRICT_PAIRWISE_COMPLETE
    portfolio_id: Optional[str] = None
    reporting_currency: Optional[str] = None


class PairwiseCorrelationResponse(BaseModel):
    asset_a_id: str
    asset_b_id: str
    asset_a_symbol: str
    asset_b_symbol: str
    as_of_date: datetime
    lookback_days: int
    estimator: CorrelationEstimator
    correlation_coefficient: Decimal
    sample_size: int
    p_value: Optional[Decimal] = None
    t_statistic: Optional[Decimal] = None
    std_error: Optional[Decimal] = None
    ci_lower_95: Optional[Decimal] = None
    ci_upper_95: Optional[Decimal] = None
    covariance: Optional[Decimal] = None
    volatility_a: Optional[Decimal] = None
    volatility_b: Optional[Decimal] = None
    alignment_applied: str
    missing_data_strategy: str


class MatrixCorrelationRequest(BaseModel):
    portfolio_id: Optional[str] = None
    asset_ids: Optional[List[str]] = None
    lookback_days: int = Field(60, ge=5, le=2520)
    as_of: Optional[date] = None
    estimator: CorrelationEstimator = CorrelationEstimator.PEARSON
    alignment_policy: CorrelationAlignmentPolicy = CorrelationAlignmentPolicy.COMMON_SESSION_DATE
    missing_data_policy: CorrelationMissingDataPolicy = CorrelationMissingDataPolicy.STRICT_PAIRWISE_COMPLETE
    repair_psd: bool = False
    transformation_method: Optional[str] = "EIGENVALUE_CLIPPING"


class CorrelationMatrixCell(BaseModel):
    row_symbol: str
    col_symbol: str
    row_asset_id: str
    col_asset_id: str
    correlation: Decimal


class CorrelationMatrixResponse(BaseModel):
    matrix_id: str
    matrix_code: str
    portfolio_id: Optional[str] = None
    as_of_date: datetime
    lookback_days: int
    estimator: CorrelationEstimator
    dimension: int
    asset_ids: List[str]
    asset_symbols: List[str]
    matrix: List[List[Decimal]]
    
    # PSD & Quality Metrics
    psd_status: PSDStatus
    min_eigenvalue: Decimal
    max_eigenvalue: Decimal
    condition_number: Optional[Decimal] = None
    negative_eigenvalues_count: int
    completeness_ratio: Decimal
    average_correlation: Decimal
    median_correlation: Decimal
    
    # Transformed matrix if requested
    transformed_matrix: Optional[List[List[Decimal]]] = None
    transformation_info: Optional[Dict[str, Any]] = None


class RollingCorrelationRequest(BaseModel):
    asset_a_id: str
    asset_b_id: str
    window_days: int = Field(30, ge=5, le=252)
    history_lookback_days: int = Field(180, ge=30, le=2520)
    as_of: Optional[date] = None
    estimator: CorrelationEstimator = CorrelationEstimator.PEARSON
    alignment_policy: CorrelationAlignmentPolicy = CorrelationAlignmentPolicy.COMMON_SESSION_DATE


class RollingCorrelationPoint(BaseModel):
    observation_date: date
    correlation: Decimal
    delta_rho: Optional[Decimal] = None
    baseline_deviation: Optional[Decimal] = None
    sample_size: int


class RollingCorrelationResponse(BaseModel):
    asset_a_id: str
    asset_b_id: str
    asset_a_symbol: str
    asset_b_symbol: str
    window_days: int
    history_lookback_days: int
    estimator: CorrelationEstimator
    baseline_correlation: Decimal
    series: List[RollingCorrelationPoint]


class CorrelationRankingsResponse(BaseModel):
    portfolio_id: Optional[str] = None
    as_of_date: datetime
    lookback_days: int
    top_positive_correlations: List[PairwiseCorrelationResponse]
    top_negative_correlations: List[PairwiseCorrelationResponse]
    most_stable_correlations: List[PairwiseCorrelationResponse]


class CorrelationRegimeEventResponse(BaseModel):
    id: str
    event_code: str
    event_type: CorrelationRegimeEventType
    portfolio_id: Optional[str] = None
    asset_a_id: str
    asset_b_id: str
    asset_a_symbol: str
    asset_b_symbol: str
    detected_at: datetime
    status: CorrelationRegimeStatus
    current_correlation: Decimal
    baseline_correlation: Optional[Decimal] = None
    delta_rho: Optional[Decimal] = None
    threshold_value: Decimal
    consecutive_periods_observed: int
    resolved_at: Optional[datetime] = None
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MultiHorizonCorrelationResponse(BaseModel):
    asset_a_id: str
    asset_b_id: str
    asset_a_symbol: str
    asset_b_symbol: str
    as_of_date: datetime
    horizons: Dict[str, Optional[Decimal]]  # e.g., "20D", "60D", "120D", "252D"
