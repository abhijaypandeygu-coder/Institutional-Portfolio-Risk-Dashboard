"""
M08.03 Factor Sensitivity Database Models and Enums.
Establishes entities for:
1. factor_sensitivity_model_config: Immutable, versioned factor sensitivity regression specifications
2. factor_sensitivity_window_config: Observation window & sample frequency configurations
3. factor_sensitivity_run: Estimation execution tracking & provenance (securities & direct portfolios)
4. factor_sensitivity_coefficient: Point-in-time estimated sensitivity coefficients & inference statistics
5. factor_sensitivity_model_diagnostics: Model goodness-of-fit, residual diagnostics & multicollinearity
6. factor_sensitivity_stability: Rolling coefficient evolution, deviation metrics & stability classifications
7. factor_sensitivity_break_test: Structural break tests (Chow F-test, CUSUM recursive residuals)
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

class TargetType(str, Enum):
    INSTRUMENT = "INSTRUMENT"
    PORTFOLIO = "PORTFOLIO"
    BENCHMARK = "BENCHMARK"


class ModelFamily(str, Enum):
    OLS = "OLS"
    WLS = "WLS"
    EWLS = "EWLS"
    RIDGE = "RIDGE"
    QUANTILE = "QUANTILE"


class SensitivityWindowType(str, Enum):
    ROLLING = "ROLLING"
    EXPANDING = "EXPANDING"
    CALENDAR = "CALENDAR"
    CUSTOM_DATE = "CUSTOM_DATE"


class MissingDataPolicy(str, Enum):
    LISTWISE_COMPLETE = "LISTWISE_COMPLETE"
    PAIRWISE_COMPLETE = "PAIRWISE_COMPLETE"
    MINIMUM_COVERAGE = "MINIMUM_COVERAGE"
    BLOCK_ON_GAP = "BLOCK_ON_GAP"


class StandardErrorMethod(str, Enum):
    OLS_CONVENTIONAL = "OLS_CONVENTIONAL"
    HC3_HETEROSKEDASTICITY_ROBUST = "HC3_HETEROSKEDASTICITY_ROBUST"
    HAC_NEWEY_WEST = "HAC_NEWEY_WEST"


class StatisticalSignificanceCategory(str, Enum):
    HIGH_SIGNIFICANCE = "HIGH_SIGNIFICANCE"        # p < 0.01
    MODERATE_SIGNIFICANCE = "MODERATE_SIGNIFICANCE"  # 0.01 <= p < 0.05
    LOW_SIGNIFICANCE = "LOW_SIGNIFICANCE"            # 0.05 <= p < 0.10
    NOT_SIGNIFICANT = "NOT_SIGNIFICANT"              # p >= 0.10
    INFERENCE_UNAVAILABLE = "INFERENCE_UNAVAILABLE"


class CoefficientStabilityStatus(str, Enum):
    STABLE = "STABLE"
    MODERATELY_UNSTABLE = "MODERATELY_UNSTABLE"
    HIGHLY_UNSTABLE = "HIGHLY_UNSTABLE"
    STRUCTURAL_BREAK_SUSPECTED = "STRUCTURAL_BREAK_SUSPECTED"
    INSUFFICIENT_STABILITY_HISTORY = "INSUFFICIENT_STABILITY_HISTORY"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    DATA_QUALITY_IMPACTED = "DATA_QUALITY_IMPACTED"


class StructuralBreakTestType(str, Enum):
    CHOW_TEST = "CHOW_TEST"
    CUSUM_TEST = "CUSUM_TEST"
    ROLLING_DEVIATION = "ROLLING_DEVIATION"


class StructuralBreakResultStatus(str, Enum):
    BREAK_DETECTED = "BREAK_DETECTED"
    NO_BREAK_DETECTED = "NO_BREAK_DETECTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    INSUFFICIENT_OBSERVATIONS = "INSUFFICIENT_OBSERVATIONS"


class SensitivityRunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
    FAILED = "FAILED"
    BLOCKED_MISSING_FACTOR_RETURNS = "BLOCKED_MISSING_FACTOR_RETURNS"
    BLOCKED_MISSING_SECURITY_RETURNS = "BLOCKED_MISSING_SECURITY_RETURNS"
    BLOCKED_INCOMPATIBLE_MODEL = "BLOCKED_INCOMPATIBLE_MODEL"


# ============================================================================
# 2. SENSITIVITY MODEL & WINDOW CONFIGURATION
# ============================================================================

class FactorSensitivityModelConfig(Base):
    """
    Immutable, version-controlled factor sensitivity model specification profile.
    """
    __tablename__ = "m08_03_sensitivity_model_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    config_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    config_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    model_family: Mapped[ModelFamily] = mapped_column(SQLEnum(ModelFamily), default=ModelFamily.OLS, nullable=False)
    factor_model_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    factor_model_version_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    
    include_intercept: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    standard_error_method: Mapped[StandardErrorMethod] = mapped_column(
        SQLEnum(StandardErrorMethod), default=StandardErrorMethod.HC3_HETEROSKEDASTICITY_ROBUST, nullable=False
    )
    confidence_level: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("0.95"), nullable=False)
    ewls_decay_factor: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4), default=Decimal("0.9400"), nullable=True)
    ridge_lambda: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), default=Decimal("0.0100"), nullable=True)
    quantile_tau: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 2), default=Decimal("0.50"), nullable=True)
    
    dependent_return_basis: Mapped[str] = mapped_column(String(32), default="EXCESS_TOTAL_RETURN", nullable=False)
    return_type: Mapped[str] = mapped_column(String(16), default="SIMPLE", nullable=False)
    currency_basis: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[FactorLifecycleStatus] = mapped_column(SQLEnum(FactorLifecycleStatus), default=FactorLifecycleStatus.ACTIVE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)

    window_configs: Mapped[List["FactorSensitivityWindowConfig"]] = relationship(
        "FactorSensitivityWindowConfig", back_populates="model_config", cascade="all, delete-orphan", lazy="selectin"
    )


class FactorSensitivityWindowConfig(Base):
    """
    Observation window, sampling frequency, and sample size requirements.
    """
    __tablename__ = "m08_03_sensitivity_window_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    window_config_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    config_id: Mapped[str] = mapped_column(String(36), ForeignKey("m08_03_sensitivity_model_configs.config_id", ondelete="CASCADE"), nullable=False, index=True)
    
    window_type: Mapped[SensitivityWindowType] = mapped_column(SQLEnum(SensitivityWindowType), default=SensitivityWindowType.ROLLING, nullable=False)
    lookback_observations: Mapped[int] = mapped_column(Integer, default=252, nullable=False)
    frequency: Mapped[str] = mapped_column(String(16), default="DAILY", nullable=False)
    missing_data_policy: Mapped[MissingDataPolicy] = mapped_column(SQLEnum(MissingDataPolicy), default=MissingDataPolicy.LISTWISE_COMPLETE, nullable=False)
    
    minimum_observations: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    min_observations_per_param_multiplier: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    minimum_coverage_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("80.00"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    model_config: Mapped["FactorSensitivityModelConfig"] = relationship("FactorSensitivityModelConfig", back_populates="window_configs")


# ============================================================================
# 3. SENSITIVITY ESTIMATION RUN
# ============================================================================

class FactorSensitivityRun(Base):
    """
    Execution run record for estimating sensitivity of a security or direct portfolio.
    """
    __tablename__ = "m08_03_sensitivity_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    config_id: Mapped[str] = mapped_column(String(36), ForeignKey("m08_03_sensitivity_model_configs.config_id"), nullable=False, index=True)
    factor_model_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    factor_model_version_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    
    target_type: Mapped[TargetType] = mapped_column(SQLEnum(TargetType), default=TargetType.INSTRUMENT, nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # instrument_id or portfolio_id
    target_listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    
    observation_count_expected: Mapped[int] = mapped_column(Integer, nullable=False)
    observation_count_used: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_sample_size: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    
    run_status: Mapped[SensitivityRunStatus] = mapped_column(SQLEnum(SensitivityRunStatus), default=SensitivityRunStatus.PENDING, nullable=False, index=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    coefficients: Mapped[List["FactorSensitivityCoefficient"]] = relationship(
        "FactorSensitivityCoefficient", back_populates="run", cascade="all, delete-orphan", lazy="selectin"
    )
    diagnostics: Mapped[Optional["FactorSensitivityModelDiagnostics"]] = relationship(
        "FactorSensitivityModelDiagnostics", back_populates="run", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )


# ============================================================================
# 4. SENSITIVITY COEFFICIENTS & INFERENCE
# ============================================================================

class FactorSensitivityCoefficient(Base):
    """
    Estimated sensitivity parameter (beta_k) to an individual factor with statistical inference.
    """
    __tablename__ = "m08_03_sensitivity_coefficients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    coefficient_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("m08_03_sensitivity_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    
    factor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    factor_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    factor_position: Mapped[int] = mapped_column(Integer, nullable=False)  # k = 1..K
    
    coefficient_value: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)  # Raw beta
    coefficient_standard_error: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    t_statistic: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    p_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    adjusted_p_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)  # Multiple-testing corrected
    
    confidence_interval_lower: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    confidence_interval_upper: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    confidence_level: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("0.95"), nullable=False)
    
    significance_status: Mapped[StatisticalSignificanceCategory] = mapped_column(
        SQLEnum(StatisticalSignificanceCategory), default=StatisticalSignificanceCategory.HIGH_SIGNIFICANCE, nullable=False
    )
    economic_contribution_1sigma: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)  # beta * sigma_F
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    run: Mapped["FactorSensitivityRun"] = relationship("FactorSensitivityRun", back_populates="coefficients")

    __table_args__ = (
        UniqueConstraint("run_id", "factor_id", name="uq_m08_run_factor_coeff"),
        Index("idx_m08_coeff_lookup", "factor_code", "significance_status"),
    )


# ============================================================================
# 5. MODEL DIAGNOSTICS & RESIDUALS
# ============================================================================

class FactorSensitivityModelDiagnostics(Base):
    """
    Run-level model fit, conditioning, and residual diagnostic metrics.
    """
    __tablename__ = "m08_03_sensitivity_diagnostics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    diagnostic_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("m08_03_sensitivity_runs.run_id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    
    intercept_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 8), nullable=True)
    intercept_standard_error: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 8), nullable=True)
    intercept_t_statistic: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    intercept_p_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    
    # Goodness-of-Fit Metrics
    r_squared: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    adjusted_r_squared: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    residual_sum_of_squares: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    total_sum_of_squares: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    residual_variance: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    residual_standard_error: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    rmse: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    mae: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    degrees_of_freedom: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Multicollinearity & Conditioning
    design_matrix_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    condition_number: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    variance_inflation_factors: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)  # {factor_code: vif}
    
    # Residual Diagnostic Tests
    durbin_watson_stat: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4), nullable=True)
    jarque_bera_stat: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    jarque_bera_p_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    run: Mapped["FactorSensitivityRun"] = relationship("FactorSensitivityRun", back_populates="diagnostics")


# ============================================================================
# 6. COEFFICIENT STABILITY & STRUCTURAL BREAKS
# ============================================================================

class FactorSensitivityStability(Base):
    """
    Time-series stability tracking for a target factor coefficient.
    """
    __tablename__ = "m08_03_sensitivity_stability"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stability_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    target_type: Mapped[TargetType] = mapped_column(SQLEnum(TargetType), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    factor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    factor_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    
    analysis_start: Mapped[date] = mapped_column(Date, nullable=False)
    analysis_end: Mapped[date] = mapped_column(Date, nullable=False)
    observations_analyzed: Mapped[int] = mapped_column(Integer, nullable=False)
    
    rolling_coefficient_mean: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    rolling_coefficient_std: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    rolling_coefficient_min: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    rolling_coefficient_max: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    
    latest_coefficient: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    previous_coefficient: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    absolute_change: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    relative_change: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    sign_change_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    stability_status: Mapped[CoefficientStabilityStatus] = mapped_column(
        SQLEnum(CoefficientStabilityStatus), default=CoefficientStabilityStatus.STABLE, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    break_tests: Mapped[List["FactorSensitivityBreakTest"]] = relationship(
        "FactorSensitivityBreakTest", back_populates="stability", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index("idx_m08_stab_lookup", "target_type", "target_id", "factor_code", "analysis_end"),
    )


class FactorSensitivityBreakTest(Base):
    """
    Formal structural break test record (Chow F-test or CUSUM test).
    """
    __tablename__ = "m08_03_sensitivity_break_tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    break_test_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    stability_id: Mapped[str] = mapped_column(String(36), ForeignKey("m08_03_sensitivity_stability.stability_id", ondelete="CASCADE"), nullable=False, index=True)
    
    test_type: Mapped[StructuralBreakTestType] = mapped_column(SQLEnum(StructuralBreakTestType), nullable=False)
    candidate_break_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    pre_break_count: Mapped[int] = mapped_column(Integer, nullable=False)
    post_break_count: Mapped[int] = mapped_column(Integer, nullable=False)
    test_statistic: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    p_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    critical_value_95: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    
    result_status: Mapped[StructuralBreakResultStatus] = mapped_column(SQLEnum(StructuralBreakResultStatus), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    stability: Mapped["FactorSensitivityStability"] = relationship("FactorSensitivityStability", back_populates="break_tests")
