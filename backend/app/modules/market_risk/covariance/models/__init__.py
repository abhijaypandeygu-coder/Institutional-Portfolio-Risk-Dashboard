"""
M07.06 Covariance Analysis Database Models.
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
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CovarianceEstimator(str, enum.Enum):
    SAMPLE = "SAMPLE"
    POPULATION = "POPULATION"
    EWMA = "EWMA"
    LEDOIT_WOLF_SHRINKAGE = "LEDOIT_WOLF_SHRINKAGE"


class DenominatorPolicy(str, enum.Enum):
    UNBIASED_SAMPLE = "UNBIASED_SAMPLE"  # n - 1
    POPULATION = "POPULATION"            # n


class CovarianceScopeType(str, enum.Enum):
    PAIRWISE = "PAIRWISE"
    PORTFOLIO_CONSTITUENTS = "PORTFOLIO_CONSTITUENTS"
    PORTFOLIO_PAIR = "PORTFOLIO_PAIR"
    MULTI_PORTFOLIO = "MULTI_PORTFOLIO"
    CUSTOM_UNIVERSE = "CUSTOM_UNIVERSE"


class WeightBasis(str, enum.Enum):
    PORTFOLIO_NAV = "PORTFOLIO_NAV"
    GROSS_EXPOSURE = "GROSS_EXPOSURE"
    USER_SPECIFIED = "USER_SPECIFIED"


class MatrixPSDStatus(str, enum.Enum):
    VALID_PSD = "VALID_PSD"
    NON_PSD = "NON_PSD"
    REPAIRED_PSD = "REPAIRED_PSD"


class CovarianceConfiguration(Base):
    """
    Configuration profile for covariance analysis.
    """
    __tablename__ = "m07_covariance_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    config_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    estimator: Mapped[CovarianceEstimator] = mapped_column(
        Enum(CovarianceEstimator, native_enum=False), default=CovarianceEstimator.SAMPLE, nullable=False
    )
    denominator_policy: Mapped[DenominatorPolicy] = mapped_column(
        Enum(DenominatorPolicy, native_enum=False), default=DenominatorPolicy.UNBIASED_SAMPLE, nullable=False
    )
    default_lookback_days: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    min_observations: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    annualization_factor: Mapped[float] = mapped_column(Numeric(8, 2), default=252.0, nullable=False)
    ewma_decay_factor: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), default=0.94, nullable=True)
    tolerance_symmetry: Mapped[float] = mapped_column(Numeric(10, 8), default=1e-8, nullable=False)
    tolerance_psd_eigenvalue: Mapped[float] = mapped_column(Numeric(10, 8), default=-1e-8, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class CovarianceCalculationRun(Base):
    """
    Execution run metadata audit trail for covariance runs.
    """
    __tablename__ = "m07_covariance_calculation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    scope_type: Mapped[CovarianceScopeType] = mapped_column(
        Enum(CovarianceScopeType, native_enum=False), nullable=False
    )
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    config_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("m07_covariance_configs.id", ondelete="SET NULL"), nullable=True
    )
    as_of_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lookback_window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    estimator_used: Mapped[CovarianceEstimator] = mapped_column(
        Enum(CovarianceEstimator, native_enum=False), nullable=False
    )
    denominator_policy: Mapped[DenominatorPolicy] = mapped_column(
        Enum(DenominatorPolicy, native_enum=False), nullable=False
    )
    universe_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pairs_calculated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    execution_time_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    data_quality_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class CovariancePairResult(Base):
    """
    Pairwise asset covariance result.
    Always canonically ordered such that asset_a_id <= asset_b_id.
    """
    __tablename__ = "m07_covariance_pair_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m07_covariance_calculation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    asset_a_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    asset_b_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    asset_a_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_b_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    as_of_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lookback_days: Mapped[int] = mapped_column(Integer, nullable=False)
    estimator: Mapped[CovarianceEstimator] = mapped_column(
        Enum(CovarianceEstimator, native_enum=False), nullable=False
    )
    covariance_value: Mapped[float] = mapped_column(Numeric(16, 10), nullable=False)
    variance_a: Mapped[float] = mapped_column(Numeric(16, 10), nullable=False)
    variance_b: Mapped[float] = mapped_column(Numeric(16, 10), nullable=False)
    std_dev_a: Mapped[float] = mapped_column(Numeric(12, 8), nullable=False)
    std_dev_b: Mapped[float] = mapped_column(Numeric(12, 8), nullable=False)
    correlation_coefficient: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    annualized_covariance: Mapped[Optional[float]] = mapped_column(Numeric(16, 10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_m07_cov_pair_lookup", "asset_a_id", "asset_b_id", "as_of_date"),
        Index("ix_m07_cov_pair_run_assets", "run_id", "asset_a_id", "asset_b_id"),
    )


class RollingCovarianceResult(Base):
    """
    Time series of covariance values over rolling historical windows.
    """
    __tablename__ = "m07_rolling_covariance_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    asset_a_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    asset_b_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    asset_a_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_b_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    observation_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    estimator: Mapped[CovarianceEstimator] = mapped_column(
        Enum(CovarianceEstimator, native_enum=False), nullable=False
    )
    covariance_value: Mapped[float] = mapped_column(Numeric(16, 10), nullable=False)
    delta_covariance: Mapped[Optional[float]] = mapped_column(Numeric(16, 10), nullable=True)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_m07_rolling_cov_series", "asset_a_id", "asset_b_id", "observation_timestamp"),
    )


class CovarianceMatrixMetadata(Base):
    """
    Persisted covariance matrix for a portfolio or universe.
    Includes PSD diagnostics, condition number, symmetry metrics.
    """
    __tablename__ = "m07_covariance_matrices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    matrix_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    as_of_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lookback_days: Mapped[int] = mapped_column(Integer, nullable=False)
    estimator: Mapped[CovarianceEstimator] = mapped_column(
        Enum(CovarianceEstimator, native_enum=False), nullable=False
    )
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    asset_ids: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    asset_symbols: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    raw_matrix_data: Mapped[List[List[float]]] = mapped_column(JSON, nullable=False)

    # Diagnostics & PSD Validation
    psd_status: Mapped[MatrixPSDStatus] = mapped_column(
        Enum(MatrixPSDStatus, native_enum=False), default=MatrixPSDStatus.VALID_PSD, nullable=False
    )
    min_eigenvalue: Mapped[float] = mapped_column(Numeric(16, 10), nullable=False)
    max_eigenvalue: Mapped[float] = mapped_column(Numeric(16, 10), nullable=False)
    condition_number: Mapped[Optional[float]] = mapped_column(Numeric(16, 4), nullable=True)
    negative_eigenvalues_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_symmetric: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_symmetry_discrepancy: Mapped[float] = mapped_column(Numeric(16, 10), default=0.0, nullable=False)
    completeness_ratio: Mapped[float] = mapped_column(Numeric(5, 4), default=1.0000, nullable=False)
    average_variance: Mapped[float] = mapped_column(Numeric(16, 10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class CovarianceMatrixTransformation(Base):
    """
    Transformed / repaired PSD covariance matrix (never mutates raw matrix).
    """
    __tablename__ = "m07_covariance_matrix_transformations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    original_matrix_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m07_covariance_matrices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    transformation_method: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "SPECTRAL_CLIPPING", "LEDOIT_WOLF"
    transformed_matrix_data: Mapped[List[List[float]]] = mapped_column(JSON, nullable=False)
    min_eigenvalue_after: Mapped[float] = mapped_column(Numeric(16, 10), nullable=False)
    frobenius_distance: Mapped[float] = mapped_column(Numeric(16, 10), nullable=False)
    max_absolute_cell_adjustment: Mapped[float] = mapped_column(Numeric(16, 10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class PortfolioCovarianceResult(Base):
    """
    Portfolio variance, volatility, and risk contribution results.
    """
    __tablename__ = "m07_portfolio_covariance_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    calculation_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    portfolio_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    matrix_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m07_covariance_matrices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    weight_basis: Mapped[WeightBasis] = mapped_column(
        Enum(WeightBasis, native_enum=False), default=WeightBasis.PORTFOLIO_NAV, nullable=False
    )
    as_of_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_portfolio_variance: Mapped[float] = mapped_column(Numeric(16, 10), nullable=False)
    period_portfolio_volatility: Mapped[float] = mapped_column(Numeric(12, 8), nullable=False)
    annualized_portfolio_variance: Mapped[float] = mapped_column(Numeric(16, 10), nullable=False)
    annualized_portfolio_volatility: Mapped[float] = mapped_column(Numeric(12, 8), nullable=False)
    annualization_factor: Mapped[float] = mapped_column(Numeric(8, 2), default=252.0, nullable=False)
    asset_ids: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    weights: Mapped[List[float]] = mapped_column(JSON, nullable=False)
    marginal_contributions_variance: Mapped[List[float]] = mapped_column(JSON, nullable=False)
    component_contributions_variance: Mapped[List[float]] = mapped_column(JSON, nullable=False)
    marginal_contributions_volatility: Mapped[List[float]] = mapped_column(JSON, nullable=False)
    component_contributions_volatility: Mapped[List[float]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
