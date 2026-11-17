"""
Pydantic schemas for M13.05 — Correlation Dashboard.

Defines presentation-layer contracts for:
1. Universe Selection & Instrument Metadata
2. Matrix Presentation & Comparison (M07.05 Integration)
3. Hierarchical Agglomerative Clustering & Dendrograms
4. Outlier & Changing Correlation Inspection
5. Rolling Correlation Trend & Scatter Diagnostics
6. Saved Universes, Preferences & Investigation Notes

Strictly adheres to Part B Section 3: Authoritative quantitative correlation math resides in M07.05.
"""

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UniverseType(str, Enum):
    PORTFOLIO_HOLDINGS = "PORTFOLIO_HOLDINGS"
    SECTOR_GROUP = "SECTOR_GROUP"
    CUSTOM_SECURITIES = "CUSTOM_SECURITIES"
    RISK_FACTORS = "RISK_FACTORS"
    MIXED = "MIXED"


class SamplingFrequency(str, Enum):
    ONE_MINUTE = "ONE_MINUTE"
    FIVE_MINUTE = "FIVE_MINUTE"
    FIFTEEN_MINUTE = "FIFTEEN_MINUTE"
    THIRTY_MINUTE = "THIRTY_MINUTE"
    HOURLY = "HOURLY"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"


class CorrelationEstimatorType(str, Enum):
    PEARSON = "PEARSON"
    SPEARMAN = "SPEARMAN"
    KENDALL = "KENDALL_TAU_B"


class ReturnDefinitionType(str, Enum):
    LOGARITHMIC = "LOGARITHMIC"
    SIMPLE = "SIMPLE"


class ClusteringMethod(str, Enum):
    HIERARCHICAL = "HIERARCHICAL"
    K_MEANS = "K_MEANS"


class HierarchicalLinkage(str, Enum):
    AVERAGE = "AVERAGE"
    SINGLE = "SINGLE"
    COMPLETE = "COMPLETE"
    WARD = "WARD"


class MatrixSortOrder(str, Enum):
    ORIGINAL = "ORIGINAL"
    ALPHABETICAL = "ALPHABETICAL"
    SECTOR = "SECTOR"
    CLUSTER = "CLUSTER"
    AVERAGE_CORRELATION = "AVERAGE_CORRELATION"


class OutlierDetectionReason(str, Enum):
    HIGH_POSITIVE_CORRELATION = "HIGH_POSITIVE_CORRELATION"
    STRONG_NEGATIVE_CORRELATION = "STRONG_NEGATIVE_CORRELATION"
    LARGE_CORRELATION_CHANGE = "LARGE_CORRELATION_CHANGE"
    SIGN_REVERSAL = "SIGN_REVERSAL"
    REGIME_BREAK = "REGIME_BREAK"


# ---------------------------------------------------------------------------
# Universe Selection Models
# ---------------------------------------------------------------------------

class UniverseInstrumentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    symbol: str
    instrument_name: str
    exchange_code: str
    market: str = "US" # US or INDIA
    asset_class: str = "EQUITY"
    currency: str = "USD"
    sector_name: Optional[str] = None
    industry_name: Optional[str] = None
    is_eligible: bool = True
    data_quality_status: str = "FRESH"
    observation_count: int = 0


class UniverseResolveRequest(BaseModel):
    portfolio_id: Optional[str] = None
    universe_type: UniverseType = UniverseType.PORTFOLIO_HOLDINGS
    instrument_ids: Optional[List[str]] = None
    sector_name: Optional[str] = None
    as_of_date: Optional[date] = None


class UniverseResolveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    universe_type: UniverseType
    portfolio_id: Optional[str] = None
    total_eligible: int
    total_excluded: int
    instruments: List[UniverseInstrumentItem]
    warnings: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Matrix Presentation Models
# ---------------------------------------------------------------------------

class MatrixCellMetadata(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_a_id: str
    instrument_b_id: str
    instrument_a_symbol: str
    instrument_b_symbol: str
    correlation: Optional[Decimal] = None
    observation_count: int
    data_quality_status: str
    is_statistically_valid: bool = True
    color_hex: Optional[str] = None


class CorrelationMatrixViewRequest(BaseModel):
    portfolio_id: Optional[str] = None
    instrument_ids: Optional[List[str]] = None
    lookback_days: int = Field(60, ge=5, le=2520)
    as_of: Optional[date] = None
    frequency: SamplingFrequency = SamplingFrequency.DAILY
    estimator: CorrelationEstimatorType = CorrelationEstimatorType.PEARSON
    return_type: ReturnDefinitionType = ReturnDefinitionType.LOGARITHMIC
    min_observations: int = Field(20, ge=3, le=500)
    sort_order: MatrixSortOrder = MatrixSortOrder.ORIGINAL
    repair_psd: bool = False


class CorrelationMatrixViewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    matrix_id: str
    portfolio_id: Optional[str] = None
    as_of_date: datetime
    lookback_days: int
    frequency: SamplingFrequency
    estimator: CorrelationEstimatorType
    return_type: ReturnDefinitionType
    dimension: int
    asset_ids: List[str]
    asset_symbols: List[str]
    
    # 2D numeric matrix
    matrix: List[List[Optional[Decimal]]]
    
    # Diagnostics & PSD
    psd_status: str
    min_eigenvalue: Decimal
    max_eigenvalue: Decimal
    condition_number: Optional[Decimal] = None
    average_correlation: Decimal
    median_correlation: Decimal
    completeness_ratio: Decimal
    
    # Ordering & Metadata
    sort_order: MatrixSortOrder
    reordered_symbols: List[str]
    pair_metadata: List[MatrixCellMetadata]
    warnings: List[str] = Field(default_factory=list)


class MatrixComparisonRequest(BaseModel):
    portfolio_id: Optional[str] = None
    instrument_ids: Optional[List[str]] = None
    current_lookback_days: int = Field(60, ge=5, le=2520)
    comparison_lookback_days: int = Field(60, ge=5, le=2520)
    current_as_of: Optional[date] = None
    comparison_as_of: Optional[date] = None
    frequency: SamplingFrequency = SamplingFrequency.DAILY
    estimator: CorrelationEstimatorType = CorrelationEstimatorType.PEARSON


class MatrixComparisonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: Optional[str] = None
    dimension: int
    asset_ids: List[str]
    asset_symbols: List[str]
    current_matrix: List[List[Optional[Decimal]]]
    comparison_matrix: List[List[Optional[Decimal]]]
    difference_matrix: List[List[Optional[Decimal]]] # Delta rho = current - comparison
    average_absolute_change: Decimal
    largest_positive_change: Decimal
    largest_negative_change: Decimal
    warnings: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Clustering Models
# ---------------------------------------------------------------------------

class ClusterSummaryNode(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cluster_id: int
    cluster_name: str
    member_instrument_ids: List[str]
    member_symbols: List[str]
    dominant_sector: Optional[str] = None
    average_within_correlation: Decimal
    min_within_correlation: Decimal
    max_within_correlation: Decimal
    member_count: int


class DendrogramNode(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    node_id: int
    left_child: Optional[int] = None
    right_child: Optional[int] = None
    distance: Decimal
    count: int
    label: Optional[str] = None


class CorrelationClusteringRequest(BaseModel):
    portfolio_id: Optional[str] = None
    instrument_ids: Optional[List[str]] = None
    lookback_days: int = Field(60, ge=5, le=2520)
    as_of: Optional[date] = None
    estimator: CorrelationEstimatorType = CorrelationEstimatorType.PEARSON
    clustering_method: ClusteringMethod = ClusteringMethod.HIERARCHICAL
    linkage: HierarchicalLinkage = HierarchicalLinkage.AVERAGE
    target_clusters: Optional[int] = Field(None, ge=2, le=50)
    distance_formula: str = "SQRT_2_MINUS_2_RHO" # d_ij = sqrt(2*(1 - rho))


class CorrelationClusteringResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: Optional[str] = None
    as_of_date: datetime
    clustering_method: ClusteringMethod
    linkage: HierarchicalLinkage
    distance_formula: str
    total_instruments: int
    number_of_clusters: int
    clusters: List[ClusterSummaryNode]
    reordered_symbols: List[str]
    dendrogram_leaves: List[int]
    dendrogram_nodes: Optional[List[DendrogramNode]] = None
    silhouette_score: Optional[Decimal] = None
    warnings: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Outlier & Change Detection Models
# ---------------------------------------------------------------------------

class CorrelationOutlierItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_a_id: str
    instrument_b_id: str
    instrument_a_symbol: str
    instrument_b_symbol: str
    instrument_a_sector: Optional[str] = None
    instrument_b_sector: Optional[str] = None
    current_correlation: Decimal
    reference_correlation: Optional[Decimal] = None
    delta_correlation: Optional[Decimal] = None
    detection_reason: OutlierDetectionReason
    threshold_crossed: Optional[Decimal] = None
    observation_count: int
    quality_status: str
    z_score: Optional[Decimal] = None


class CorrelationOutliersRequest(BaseModel):
    portfolio_id: Optional[str] = None
    instrument_ids: Optional[List[str]] = None
    lookback_days: int = Field(60, ge=5, le=2520)
    as_of: Optional[date] = None
    estimator: CorrelationEstimatorType = CorrelationEstimatorType.PEARSON
    high_positive_threshold: Decimal = Decimal("0.75")
    strong_negative_threshold: Decimal = Decimal("-0.50")
    large_change_threshold: Decimal = Decimal("0.30")
    comparison_lookback_days: int = Field(60, ge=5, le=2520)


class CorrelationOutliersResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: Optional[str] = None
    as_of_date: datetime
    high_positive_pairs: List[CorrelationOutlierItem]
    strong_negative_pairs: List[CorrelationOutlierItem]
    large_change_pairs: List[CorrelationOutlierItem]
    sign_reversal_pairs: List[CorrelationOutlierItem]
    total_outliers_flagged: int


# ---------------------------------------------------------------------------
# Pair Detail & Rolling Models
# ---------------------------------------------------------------------------

class ReturnObservationPair(BaseModel):
    observation_date: date
    return_a: Decimal
    return_b: Decimal


class CorrelationPairDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_a_id: str
    instrument_b_id: str
    instrument_a_symbol: str
    instrument_b_symbol: str
    instrument_a_name: str
    instrument_b_name: str
    instrument_a_sector: Optional[str] = None
    instrument_b_sector: Optional[str] = None
    
    correlation: Decimal
    estimator: CorrelationEstimatorType
    lookback_days: int
    frequency: SamplingFrequency
    sample_size: int
    
    p_value: Optional[Decimal] = None
    t_statistic: Optional[Decimal] = None
    std_error: Optional[Decimal] = None
    ci_lower_95: Optional[Decimal] = None
    ci_upper_95: Optional[Decimal] = None
    covariance: Optional[Decimal] = None
    volatility_a: Optional[Decimal] = None
    volatility_b: Optional[Decimal] = None
    
    # Scatter Data (capped at recent 60 observations for performance)
    scatter_points: List[ReturnObservationPair] = Field(default_factory=list)
    least_squares_slope: Optional[Decimal] = None
    least_squares_intercept: Optional[Decimal] = None
    
    # Rolling Trend Summary
    rolling_points: List[Dict[str, Any]] = Field(default_factory=list)
    data_quality_status: str
    provenance_module: str = "M07.05 — Correlation Analysis"


# ---------------------------------------------------------------------------
# Saved Universes, Preferences & Investigation Schemas
# ---------------------------------------------------------------------------

class CorrelationDashboardPreferenceCreate(BaseModel):
    dashboard_name: str = "Default Correlation Dashboard"
    default_portfolio_id: Optional[str] = None
    default_universe_type: UniverseType = UniverseType.PORTFOLIO_HOLDINGS
    default_lookback_days: int = 60
    sampling_frequency: SamplingFrequency = SamplingFrequency.DAILY
    correlation_method: CorrelationEstimatorType = CorrelationEstimatorType.PEARSON
    return_definition: ReturnDefinitionType = ReturnDefinitionType.LOGARITHMIC
    min_observations: int = 20
    display_configuration: Dict[str, Any] = Field(default_factory=dict)


class CorrelationDashboardPreferenceResponse(CorrelationDashboardPreferenceCreate):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CorrelationSavedUniverseCreate(BaseModel):
    universe_name: str
    description: Optional[str] = None
    universe_type: UniverseType = UniverseType.CUSTOM_SECURITIES
    portfolio_id: Optional[str] = None
    instrument_ids: List[str] = Field(..., min_length=2)


class CorrelationSavedUniverseResponse(BaseModel):
    id: str
    user_id: str
    universe_name: str
    description: Optional[str] = None
    universe_type: UniverseType
    portfolio_id: Optional[str] = None
    member_instrument_ids: List[str]
    member_count: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CorrelationInvestigationCreate(BaseModel):
    portfolio_id: Optional[str] = None
    instrument_a_id: str
    instrument_b_id: str
    correlation_value: Decimal
    previous_correlation: Optional[Decimal] = None
    correlation_method: CorrelationEstimatorType = CorrelationEstimatorType.PEARSON
    lookback_days: int
    sampling_frequency: SamplingFrequency = SamplingFrequency.DAILY
    observation_count: int
    detection_reason: OutlierDetectionReason
    source_result_reference: Optional[str] = None
    user_notes: str


class CorrelationInvestigationResponse(CorrelationInvestigationCreate):
    id: str
    user_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
