"""
M08.02 Factor Exposure Database Models and Enums.
Establishes entities for:
1. factor_exposure_estimation_config: Versioned estimation settings
2. factor_return_series & factor_return_observations: Historical factor return storage
3. factor_loading_run: Multi-factor estimation execution logs & provenance
4. instrument_factor_loading: Security-level factor loadings, standard errors, R2, diagnostics
5. portfolio_factor_exposure_snapshot: NAV-weighted and gross-normalized factor exposures
6. factor_exposure_normalization: Normalization factors (1-sigma, cross-sectional z-score)
7. factor_exposure_change_attribution: Weight vs. Loading decomposition of factor tilt changes
"""
from datetime import datetime, date, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any
import uuid

from sqlalchemy import (
    String,
    DateTime,
    Date,
    Numeric,
    Integer,
    Boolean,
    ForeignKey,
    JSON,
    Enum as SQLEnum,
    Index,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base
from backend.app.modules.factor_risk.factor_definition.models import (
    MarketScope,
    FactorLifecycleStatus,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================================
# 1. ENUMERATIONS
# ============================================================================

class EstimationMethod(str, Enum):
    ROLLING_OLS = "ROLLING_OLS"
    EXPANDING_OLS = "EXPANDING_OLS"
    EWLS = "EWLS"
    RIDGE_REGRESSION = "RIDGE_REGRESSION"
    ROBUST_HUBER = "ROBUST_HUBER"


class DependentReturnBasis(str, Enum):
    EXCESS_TOTAL_RETURN = "EXCESS_TOTAL_RETURN"
    TOTAL_RETURN = "TOTAL_RETURN"
    EXCESS_SPLIT_ADJUSTED_RETURN = "EXCESS_SPLIT_ADJUSTED_RETURN"


class ReturnType(str, Enum):
    SIMPLE = "SIMPLE"
    LOGARITHMIC = "LOGARITHMIC"


class CorporateActionBasis(str, Enum):
    RAW = "RAW"
    SPLIT_ADJUSTED = "SPLIT_ADJUSTED"
    TOTAL_RETURN_ADJUSTED = "TOTAL_RETURN_ADJUSTED"


class StandardErrorMethod(str, Enum):
    OLS_CONVENTIONAL = "OLS_CONVENTIONAL"
    HC3_HETEROSKEDASTICITY_ROBUST = "HC3_HETEROSKEDASTICITY_ROBUST"
    HAC_NEWEY_WEST = "HAC_NEWEY_WEST"


class RunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
    FAILED = "FAILED"
    BLOCKED_MISSING_FACTOR_RETURNS = "BLOCKED_MISSING_FACTOR_RETURNS"
    BLOCKED_INCOMPATIBLE_MODEL = "BLOCKED_INCOMPATIBLE_MODEL"
    BLOCKED_INCOMPATIBLE_CURRENCY = "BLOCKED_INCOMPATIBLE_CURRENCY"


class LoadingQualityStatus(str, Enum):
    ESTIMATED = "ESTIMATED"
    INSUFFICIENT_OBSERVATIONS = "INSUFFICIENT_OBSERVATIONS"
    MISSING_SECURITY_RETURNS = "MISSING_SECURITY_RETURNS"
    MISSING_FACTOR_RETURNS = "MISSING_FACTOR_RETURNS"
    MISSING_RISK_FREE_SERIES = "MISSING_RISK_FREE_SERIES"
    LOW_DATA_COVERAGE = "LOW_DATA_COVERAGE"
    LOW_VARIANCE_FACTOR = "LOW_VARIANCE_FACTOR"
    MULTICOLLINEARITY_WARNING = "MULTICOLLINEARITY_WARNING"
    ILL_CONDITIONED = "ILL_CONDITIONED"
    REGRESSION_FAILED = "REGRESSION_FAILED"
    STALE_ESTIMATE = "STALE_ESTIMATE"
    NOT_MODELED = "NOT_MODELED"


class WeightingBasis(str, Enum):
    NAV_WEIGHTED = "NAV_WEIGHTED"
    GROSS_NORMALIZED = "GROSS_NORMALIZED"
    COVERED_HOLDINGS_NORMALIZED = "COVERED_HOLDINGS_NORMALIZED"


class TiltClassification(str, Enum):
    STRONG_POSITIVE = "STRONG_POSITIVE"
    MODERATE_POSITIVE = "MODERATE_POSITIVE"
    NEUTRAL = "NEUTRAL"
    MODERATE_NEGATIVE = "MODERATE_NEGATIVE"
    STRONG_NEGATIVE = "STRONG_NEGATIVE"
    UNAVAILABLE = "UNAVAILABLE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"


class ComparabilityStatus(str, Enum):
    COMPARABLE = "COMPARABLE"
    COMPARABLE_WITH_WARNING = "COMPARABLE_WITH_WARNING"
    NOT_COMPARABLE_MODEL_CHANGED = "NOT_COMPARABLE_MODEL_CHANGED"
    NOT_COMPARABLE_FACTOR_CHANGED = "NOT_COMPARABLE_FACTOR_CHANGED"
    NOT_COMPARABLE_RETURN_BASIS = "NOT_COMPARABLE_RETURN_BASIS"
    NOT_COMPARABLE_CURRENCY = "NOT_COMPARABLE_CURRENCY"
    NOT_COMPARABLE_FREQUENCY = "NOT_COMPARABLE_FREQUENCY"
    NOT_COMPARABLE_NORMALIZATION = "NOT_COMPARABLE_NORMALIZATION"
    INSUFFICIENT_METADATA = "INSUFFICIENT_METADATA"


class RestatementStatus(str, Enum):
    CONTEMPORANEOUS = "CONTEMPORANEOUS"
    RESTATED = "RESTATED"
    FIXED_MODEL = "FIXED_MODEL"


# ============================================================================
# 2. FACTOR RETURN SERIES & OBSERVATIONS
# ============================================================================

class FactorReturnSeries(Base):
    """
    Authoritative registration of historical factor return series.
    Linked to a specific FactorDefinition and FactorDefinitionVersion.
    """
    __tablename__ = "m08_02_factor_return_series"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    factor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    factor_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    version_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    market_scope: Mapped[MarketScope] = mapped_column(SQLEnum(MarketScope), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    frequency: Mapped[str] = mapped_column(String(16), default="DAILY", nullable=False)
    return_convention: Mapped[str] = mapped_column(String(32), default="SIMPLE", nullable=False)
    provider_name: Mapped[str] = mapped_column(String(64), default="CANONICAL_PORTFOLIO_CONSTRUCTION", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    observations: Mapped[List["FactorReturnObservation"]] = relationship(
        "FactorReturnObservation", back_populates="series", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("factor_id", "version_id", "frequency", "currency", name="uq_m08_factor_series"),
    )


class FactorReturnObservation(Base):
    """
    Point-in-time factor return observation for a specific trading session.
    """
    __tablename__ = "m08_02_factor_return_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    observation_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    series_id: Mapped[str] = mapped_column(String(36), ForeignKey("m08_02_factor_return_series.series_id", ondelete="CASCADE"), nullable=False, index=True)
    trading_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    return_value: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)  # Decimal return (e.g. 0.0125 for 1.25%)
    risk_free_rate: Mapped[Decimal] = mapped_column(Numeric(14, 8), default=Decimal("0.0"), nullable=False)
    excess_return_value: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    is_final: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    series: Mapped["FactorReturnSeries"] = relationship("FactorReturnSeries", back_populates="observations")

    __table_args__ = (
        UniqueConstraint("series_id", "trading_date", name="uq_m08_series_date"),
        Index("idx_m08_series_date", "series_id", "trading_date"),
    )


# ============================================================================
# 3. ESTIMATION CONFIGURATION
# ============================================================================

class FactorExposureEstimationConfig(Base):
    """
    Version-controlled parameter profile for running factor exposure regressions.
    """
    __tablename__ = "m08_02_factor_exposure_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    config_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    config_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    factor_model_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    factor_model_version_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    
    estimation_method: Mapped[EstimationMethod] = mapped_column(SQLEnum(EstimationMethod), default=EstimationMethod.ROLLING_OLS, nullable=False)
    lookback_observations: Mapped[int] = mapped_column(Integer, default=252, nullable=False)  # e.g., 60, 120, 252 days
    return_frequency: Mapped[str] = mapped_column(String(16), default="DAILY", nullable=False)
    dependent_return_basis: Mapped[DependentReturnBasis] = mapped_column(SQLEnum(DependentReturnBasis), default=DependentReturnBasis.EXCESS_TOTAL_RETURN, nullable=False)
    return_type: Mapped[ReturnType] = mapped_column(SQLEnum(ReturnType), default=ReturnType.SIMPLE, nullable=False)
    corporate_action_basis: Mapped[CorporateActionBasis] = mapped_column(SQLEnum(CorporateActionBasis), default=CorporateActionBasis.TOTAL_RETURN_ADJUSTED, nullable=False)
    
    include_intercept: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    minimum_observations: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    min_observations_per_param_multiplier: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    
    ewls_decay_factor: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4), default=Decimal("0.9400"), nullable=True)  # Lambda for EWLS
    standard_error_method: Mapped[StandardErrorMethod] = mapped_column(SQLEnum(StandardErrorMethod), default=StandardErrorMethod.HC3_HETEROSKEDASTICITY_ROBUST, nullable=False)
    
    currency_basis: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    configuration_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[FactorLifecycleStatus] = mapped_column(SQLEnum(FactorLifecycleStatus), default=FactorLifecycleStatus.ACTIVE, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)


# ============================================================================
# 4. ESTIMATION EXECUTION RUN & INSTRUMENT LOADINGS
# ============================================================================

class FactorLoadingRun(Base):
    """
    Execution run tracking batch or single estimation of factor loadings.
    """
    __tablename__ = "m08_02_factor_loading_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    config_id: Mapped[str] = mapped_column(String(36), ForeignKey("m08_02_factor_exposure_configs.config_id"), nullable=False, index=True)
    factor_model_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    factor_model_version_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    
    requested_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successful_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    run_status: Mapped[RunStatus] = mapped_column(SQLEnum(RunStatus), default=RunStatus.PENDING, nullable=False, index=True)
    failure_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    loadings: Mapped[List["InstrumentFactorLoading"]] = relationship(
        "InstrumentFactorLoading", back_populates="run", cascade="all, delete-orphan", lazy="selectin"
    )


class InstrumentFactorLoading(Base):
    """
    Statistical sensitivity coefficient (beta_i,k) for an individual instrument to a factor.
    """
    __tablename__ = "m08_02_instrument_factor_loadings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    loading_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("m08_02_factor_loading_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    factor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    factor_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    factor_position: Mapped[int] = mapped_column(Integer, nullable=False)  # k = 1, ..., K
    
    loading_value: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)  # Canonical raw beta
    standardized_loading_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)  # beta * sigma_factor
    cross_sectional_zscore: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)  # relative to universe
    
    intercept_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 8), nullable=True)  # Regression alpha
    standard_error: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    t_statistic: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    p_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    confidence_interval_lower: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    confidence_interval_upper: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    
    r_squared: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    adjusted_r_squared: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    residual_variance: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 8), nullable=True)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Regression Diagnostics
    design_matrix_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    condition_number: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    variance_inflation_factor: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    
    status: Mapped[LoadingQualityStatus] = mapped_column(SQLEnum(LoadingQualityStatus), default=LoadingQualityStatus.ESTIMATED, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    run: Mapped["FactorLoadingRun"] = relationship("FactorLoadingRun", back_populates="loadings")

    __table_args__ = (
        UniqueConstraint("run_id", "instrument_id", "factor_id", name="uq_m08_run_inst_factor"),
        Index("idx_m08_inst_factor_lookup", "instrument_id", "factor_id", "status"),
    )


# ============================================================================
# 5. PORTFOLIO FACTOR EXPOSURE SNAPSHOT
# ============================================================================

class PortfolioFactorExposureSnapshot(Base):
    """
    Authoritative aggregated portfolio factor exposure snapshot.
    beta_p,k = sum(w_i * beta_i,k) using signed portfolio NAV weights.
    """
    __tablename__ = "m08_02_portfolio_factor_exposures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exposure_snapshot_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    portfolio_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    loading_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("m08_02_factor_loading_runs.run_id"), nullable=False, index=True)
    
    factor_model_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    factor_model_version_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    factor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    factor_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    factor_position: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Portfolio Exposures
    exposure_value: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)  # Canonical NAV-weighted sum(w_i * beta_i)
    standardized_exposure_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)  # beta_p * sigma_factor
    gross_normalized_exposure: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)  # sum(w_gross * beta_i)
    weighting_basis: Mapped[WeightingBasis] = mapped_column(SQLEnum(WeightingBasis), default=WeightingBasis.NAV_WEIGHTED, nullable=False)
    tilt_classification: Mapped[TiltClassification] = mapped_column(SQLEnum(TiltClassification), default=TiltClassification.NEUTRAL, nullable=False)
    
    # Financial & Coverage Metrics
    portfolio_base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    nav_reference: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    gross_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    
    covered_signed_weight: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    covered_absolute_weight: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    missing_signed_weight: Mapped[Decimal] = mapped_column(Numeric(8, 6), default=Decimal("0.0"), nullable=False)
    missing_absolute_weight: Mapped[Decimal] = mapped_column(Numeric(8, 6), default=Decimal("0.0"), nullable=False)
    coverage_percentage: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)  # 0 to 100%
    
    holding_count: Mapped[int] = mapped_column(Integer, nullable=False)
    covered_holding_count: Mapped[int] = mapped_column(Integer, nullable=False)
    uncovered_holding_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    calculation_timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    restatement_status: Mapped[RestatementStatus] = mapped_column(SQLEnum(RestatementStatus), default=RestatementStatus.CONTEMPORANEOUS, nullable=False)
    quality_status: Mapped[LoadingQualityStatus] = mapped_column(SQLEnum(LoadingQualityStatus), default=LoadingQualityStatus.ESTIMATED, nullable=False)

    __table_args__ = (
        UniqueConstraint("portfolio_id", "as_of_date", "factor_id", "factor_model_version_id", "weighting_basis", "restatement_status", name="uq_m08_portfolio_factor_exp"),
        Index("idx_m08_port_exp_hist", "portfolio_id", "as_of_date", "factor_code"),
    )


# ============================================================================
# 6. EXPOSURE NORMALIZATION METADATA
# ============================================================================

class FactorExposureNormalization(Base):
    """
    Reference volatility (sigma_factor) and cross-sectional statistics for standardization.
    """
    __tablename__ = "m08_02_factor_normalization"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    norm_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    factor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    factor_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    factor_standard_deviation: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    factor_mean: Mapped[Decimal] = mapped_column(Numeric(14, 8), default=Decimal("0.0"), nullable=False)
    reference_window_observations: Mapped[int] = mapped_column(Integer, nullable=False)
    
    cross_sectional_universe_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    cross_sectional_mean: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    cross_sectional_std: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    universe_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    normalization_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


# ============================================================================
# 7. EXPOSURE CHANGE ATTRIBUTION (WEIGHT VS. LOADING DECOMPOSITION)
# ============================================================================

class FactorExposureChangeAttribution(Base):
    """
    Symmetric exact decomposition of portfolio factor exposure changes:
    Delta(w_i * beta_i) = Delta(w_i) * ((beta_t + beta_t-1)/2) + Delta(beta_i) * ((w_t + w_t-1)/2)
    """
    __tablename__ = "m08_02_exposure_change_attributions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attribution_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    factor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    factor_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    
    earlier_date: Mapped[date] = mapped_column(Date, nullable=False)
    later_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    earlier_exposure: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    later_exposure: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    total_change: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    percentage_change: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    
    weight_effect: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    loading_effect: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    entry_exit_effect: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0.0"), nullable=False)
    unreconciled_residual: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0.0"), nullable=False)
    
    comparability_status: Mapped[ComparabilityStatus] = mapped_column(SQLEnum(ComparabilityStatus), default=ComparabilityStatus.COMPARABLE, nullable=False)
    breakdown_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

