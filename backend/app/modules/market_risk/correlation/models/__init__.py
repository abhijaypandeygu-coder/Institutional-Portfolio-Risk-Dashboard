"""
M07.05 Correlation Analysis Database Models.
"""
from datetime import datetime, timezone
import enum
from typing import Optional, Dict, Any, List
from uuid import uuid4

from sqlalchemy import (
    String,
    DateTime,
    Numeric,
    Integer,
    ForeignKey,
    JSON,
    Boolean,
    Enum,
    Index,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CorrelationEstimator(str, enum.Enum):
    PEARSON = "PEARSON"
    SPEARMAN = "SPEARMAN"
    KENDALL_TAU_B = "KENDALL_TAU_B"


class CorrelationAlignmentPolicy(str, enum.Enum):
    COMMON_SESSION_DATE = "COMMON_SESSION_DATE"
    COMMON_TIMESTAMP = "COMMON_TIMESTAMP"
    PREVIOUS_CLOSE_ALIGNMENT = "PREVIOUS_CLOSE_ALIGNMENT"
    CROSS_MARKET_CALENDAR_UNION = "CROSS_MARKET_CALENDAR_UNION"


class CorrelationMissingDataPolicy(str, enum.Enum):
    STRICT_PAIRWISE_COMPLETE = "STRICT_PAIRWISE_COMPLETE"
    FORWARD_FILL_LAST_PRICE = "FORWARD_FILL_LAST_PRICE"
    DROP_MISSING = "DROP_MISSING"


class CorrelationScopeType(str, enum.Enum):
    INSTRUMENT_PAIR = "INSTRUMENT_PAIR"
    PORTFOLIO_CONSTITUENTS = "PORTFOLIO_CONSTITUENTS"
    PORTFOLIO_VS_BENCHMARK = "PORTFOLIO_VS_BENCHMARK"
    CUSTOM_UNIVERSE = "CUSTOM_UNIVERSE"


class PSDStatus(str, enum.Enum):
    VALID_PSD = "VALID_PSD"
    NON_PSD = "NON_PSD"
    REPAIRED_PSD = "REPAIRED_PSD"


class CorrelationRegimeEventType(str, enum.Enum):
    HIGH_POSITIVE_CORRELATION = "HIGH_POSITIVE_CORRELATION"
    HIGH_ABSOLUTE_CORRELATION = "HIGH_ABSOLUTE_CORRELATION"
    STRONG_NEGATIVE_CORRELATION = "STRONG_NEGATIVE_CORRELATION"
    RAPID_CORRELATION_CHANGE = "RAPID_CORRELATION_CHANGE"
    BASELINE_DEVIATION = "BASELINE_DEVIATION"
    CORRELATION_BREAKDOWN = "CORRELATION_BREAKDOWN"


class CorrelationRegimeStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"
    ACKNOWLEDGED = "ACKNOWLEDGED"


class CorrelationConfiguration(Base):
    """
    Configuration profile for correlation analytics.
    """
    __tablename__ = "m07_correlation_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    config_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    estimator: Mapped[CorrelationEstimator] = mapped_column(
        Enum(CorrelationEstimator, native_enum=False), default=CorrelationEstimator.PEARSON, nullable=False
    )
    alignment_policy: Mapped[CorrelationAlignmentPolicy] = mapped_column(
        Enum(CorrelationAlignmentPolicy, native_enum=False), default=CorrelationAlignmentPolicy.COMMON_SESSION_DATE, nullable=False
    )
    missing_data_policy: Mapped[CorrelationMissingDataPolicy] = mapped_column(
        Enum(CorrelationMissingDataPolicy, native_enum=False), default=CorrelationMissingDataPolicy.STRICT_PAIRWISE_COMPLETE, nullable=False
    )
    default_lookback_days: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    min_observations: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    high_correlation_threshold: Mapped[float] = mapped_column(Numeric(6, 4), default=0.7000, nullable=False)
    negative_correlation_threshold: Mapped[float] = mapped_column(Numeric(6, 4), default=-0.5000, nullable=False)
    rapid_change_threshold: Mapped[float] = mapped_column(Numeric(6, 4), default=0.3000, nullable=False)
    persistence_periods: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class CorrelationCalculationRun(Base):
    """
    Execution run metadata audit trail for correlation runs.
    """
    __tablename__ = "m07_correlation_calculation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    scope_type: Mapped[CorrelationScopeType] = mapped_column(
        Enum(CorrelationScopeType, native_enum=False), nullable=False
    )
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    config_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("m07_correlation_configs.id", ondelete="SET NULL"), nullable=True
    )
    as_of_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lookback_window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    estimator_used: Mapped[CorrelationEstimator] = mapped_column(
        Enum(CorrelationEstimator, native_enum=False), nullable=False
    )
    currency_policy: Mapped[str] = mapped_column(String(30), default="LOCAL", nullable=False)
    reporting_currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    universe_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pairs_calculated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    execution_time_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    data_quality_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class CorrelationPairResult(Base):
    """
    Pairwise asset correlation result.
    Always canonically ordered such that asset_a_id <= asset_b_id.
    """
    __tablename__ = "m07_correlation_pair_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m07_correlation_calculation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    asset_a_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    asset_b_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    asset_a_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_b_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    as_of_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lookback_days: Mapped[int] = mapped_column(Integer, nullable=False)
    estimator: Mapped[CorrelationEstimator] = mapped_column(
        Enum(CorrelationEstimator, native_enum=False), nullable=False
    )
    correlation_coefficient: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    p_value: Mapped[Optional[float]] = mapped_column(Numeric(10, 8), nullable=True)
    t_statistic: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    std_error: Mapped[Optional[float]] = mapped_column(Numeric(8, 6), nullable=True)
    ci_lower_95: Mapped[Optional[float]] = mapped_column(Numeric(8, 6), nullable=True)
    ci_upper_95: Mapped[Optional[float]] = mapped_column(Numeric(8, 6), nullable=True)
    covariance: Mapped[Optional[float]] = mapped_column(Numeric(14, 8), nullable=True)
    volatility_a: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    volatility_b: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_m07_corr_pair_lookup", "asset_a_id", "asset_b_id", "as_of_date"),
        Index("ix_m07_corr_pair_run_assets", "run_id", "asset_a_id", "asset_b_id"),
    )


class RollingCorrelationResult(Base):
    """
    Time series of correlation values over rolling historical windows.
    """
    __tablename__ = "m07_rolling_correlation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    asset_a_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    asset_b_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    asset_a_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_b_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    observation_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    estimator: Mapped[CorrelationEstimator] = mapped_column(
        Enum(CorrelationEstimator, native_enum=False), nullable=False
    )
    correlation_coefficient: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    delta_rho: Mapped[Optional[float]] = mapped_column(Numeric(8, 6), nullable=True)
    baseline_deviation: Mapped[Optional[float]] = mapped_column(Numeric(8, 6), nullable=True)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_m07_rolling_corr_series", "asset_a_id", "asset_b_id", "observation_timestamp"),
    )


class CorrelationMatrixMetadata(Base):
    """
    Persisted correlation matrix for a portfolio or universe.
    Includes PSD diagnostics and matrix statistics.
    """
    __tablename__ = "m07_correlation_matrices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    matrix_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    as_of_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lookback_days: Mapped[int] = mapped_column(Integer, nullable=False)
    estimator: Mapped[CorrelationEstimator] = mapped_column(
        Enum(CorrelationEstimator, native_enum=False), nullable=False
    )
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    asset_ids: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    asset_symbols: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    raw_matrix_data: Mapped[List[List[float]]] = mapped_column(JSON, nullable=False)
    
    # PSD & Quality Diagnostics
    psd_status: Mapped[PSDStatus] = mapped_column(
        Enum(PSDStatus, native_enum=False), default=PSDStatus.VALID_PSD, nullable=False
    )
    min_eigenvalue: Mapped[float] = mapped_column(Numeric(12, 8), nullable=False)
    max_eigenvalue: Mapped[float] = mapped_column(Numeric(12, 8), nullable=False)
    condition_number: Mapped[Optional[float]] = mapped_column(Numeric(14, 4), nullable=True)
    negative_eigenvalues_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completeness_ratio: Mapped[float] = mapped_column(Numeric(5, 4), default=1.0000, nullable=False)
    average_correlation: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    median_correlation: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class CorrelationMatrixTransformation(Base):
    """
    Transformed / repaired PSD matrix (never mutates raw matrix data).
    """
    __tablename__ = "m07_correlation_matrix_transformations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    original_matrix_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m07_correlation_matrices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    transformation_method: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "EIGENVALUE_CLIPPING", "HIGHAM_NEAREST"
    transformed_matrix_data: Mapped[List[List[float]]] = mapped_column(JSON, nullable=False)
    min_eigenvalue_after: Mapped[float] = mapped_column(Numeric(12, 8), nullable=False)
    frobenius_distance: Mapped[float] = mapped_column(Numeric(12, 8), nullable=False)
    max_absolute_element_diff: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class CorrelationRegimeEvent(Base):
    """
    Detected correlation regime events, anomalies, breakdowns, or threshold breaches.
    """
    __tablename__ = "m07_correlation_regime_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    event_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    event_type: Mapped[CorrelationRegimeEventType] = mapped_column(
        Enum(CorrelationRegimeEventType, native_enum=False), nullable=False
    )
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    asset_a_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    asset_b_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    asset_a_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_b_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[CorrelationRegimeStatus] = mapped_column(
        Enum(CorrelationRegimeStatus, native_enum=False), default=CorrelationRegimeStatus.ACTIVE, nullable=False
    )
    current_correlation: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    baseline_correlation: Mapped[Optional[float]] = mapped_column(Numeric(8, 6), nullable=True)
    delta_rho: Mapped[Optional[float]] = mapped_column(Numeric(8, 6), nullable=True)
    threshold_value: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    consecutive_periods_observed: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

