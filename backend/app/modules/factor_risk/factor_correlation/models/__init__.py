"""
SQLAlchemy 2.x Database Models for M08.07 Factor Correlation & Covariance Analytics.
Establishes tables for:
1. m08_07_correlation_configs: Immutable, versioned factor correlation settings
2. m08_07_correlation_runs: Header execution records for correlation matrix runs
3. m08_07_correlation_pairs: Pairwise factor correlation and covariance statistics
4. m08_07_correlation_matrix_snapshots: Pinned K x K correlation matrices & spectral diagnostics
5. m08_07_covariance_configs: Covariance estimation configurations (Sample, EWMA, Ledoit-Wolf)
6. m08_07_covariance_snapshots: Authoritative factor covariance matrices consumed by M08.05
7. m08_07_rolling_factor_correlations: Historical rolling correlation & covariance series
8. m08_07_regime_alert_configs: Thresholds and persistence parameters for relationship monitoring
9. m08_07_regime_alerts: Detected co-movement shocks, sign reversals, and structural breaks
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
    FactorLifecycleStatus,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================================
# 1. ENUMERATIONS
# ============================================================================

class FactorCorrelationMethod(str, Enum):
    PEARSON = "PEARSON"
    SPEARMAN = "SPEARMAN"
    KENDALL = "KENDALL"


class FactorCovarianceMethod(str, Enum):
    SAMPLE = "SAMPLE"
    EXPONENTIALLY_WEIGHTED = "EXPONENTIALLY_WEIGHTED"
    LEDOIT_WOLF = "LEDOIT_WOLF"


class CorrelationWindowType(str, Enum):
    FIXED_ROLLING = "FIXED_ROLLING"
    EXPANDING = "EXPANDING"
    CALENDAR_SESSION = "CALENDAR_SESSION"
    CUSTOM_RANGE = "CUSTOM_RANGE"


class MissingDataPolicy(str, Enum):
    LISTWISE_COMPLETE = "LISTWISE_COMPLETE"
    PAIRWISE_COMPLETE = "PAIRWISE_COMPLETE"
    MINIMUM_COVERAGE = "MINIMUM_COVERAGE"


class CorrelationRelationshipClassification(str, Enum):
    VERY_WEAK = "VERY_WEAK"
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"
    VERY_STRONG = "VERY_STRONG"


class CorrelationStabilityCategory(str, Enum):
    STABLE_POSITIVE = "STABLE_POSITIVE"
    STABLE_NEGATIVE = "STABLE_NEGATIVE"
    WEAK_RELATIONSHIP = "WEAK_RELATIONSHIP"
    INCREASING_POSITIVE = "INCREASING_POSITIVE"
    INCREASING_NEGATIVE = "INCREASING_NEGATIVE"
    DECLINING_RELATIONSHIP = "DECLINING_RELATIONSHIP"
    SIGN_REVERSAL = "SIGN_REVERSAL"
    HIGH_VOLATILITY_RELATIONSHIP = "HIGH_VOLATILITY_RELATIONSHIP"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    NOT_COMPARABLE = "NOT_COMPARABLE"


class CorrelationRegimeStatus(str, Enum):
    NORMAL = "NORMAL"
    HIGH_POSITIVE_COHERENCE = "HIGH_POSITIVE_COHERENCE"
    HIGH_NEGATIVE_COHERENCE = "HIGH_NEGATIVE_COHERENCE"
    CORRELATION_SHIFT = "CORRELATION_SHIFT"
    SIGN_REVERSAL = "SIGN_REVERSAL"
    POTENTIAL_STRUCTURAL_BREAK = "POTENTIAL_STRUCTURAL_BREAK"
    PERSISTENT_HIGH_CORRELATION = "PERSISTENT_HIGH_CORRELATION"
    PERSISTENT_LOW_CORRELATION = "PERSISTENT_LOW_CORRELATION"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class RegimeAlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RegimeAlertStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RECOVERED = "RECOVERED"
    DISMISSED = "DISMISSED"


# ============================================================================
# 2. DATABASE MODELS
# ============================================================================

class FactorCorrelationConfig(Base):
    """Immutable, versioned factor correlation settings."""
    __tablename__ = "m08_07_correlation_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"CORR_CFG_{uuid.uuid4().hex[:12].upper()}")
    config_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    config_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    factor_model_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_01_factor_models.model_id"), nullable=False, index=True)
    factor_model_version_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_01_factor_model_versions.model_version_id"), nullable=False, index=True)

    correlation_method: Mapped[FactorCorrelationMethod] = mapped_column(SQLEnum(FactorCorrelationMethod, native_enum=False), default=FactorCorrelationMethod.PEARSON, nullable=False)
    observation_frequency: Mapped[str] = mapped_column(String(32), default="DAILY", nullable=False)
    return_convention: Mapped[str] = mapped_column(String(32), default="SIMPLE", nullable=False)
    currency_basis: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    missing_data_policy: Mapped[MissingDataPolicy] = mapped_column(SQLEnum(MissingDataPolicy, native_enum=False), default=MissingDataPolicy.LISTWISE_COMPLETE, nullable=False)

    estimation_window: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    minimum_observations: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    confidence_level: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("0.95"), nullable=False)

    config_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[FactorLifecycleStatus] = mapped_column(SQLEnum(FactorLifecycleStatus, native_enum=False), default=FactorLifecycleStatus.ACTIVE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class FactorCorrelationRun(Base):
    """Execution header for a factor correlation matrix run."""
    __tablename__ = "m08_07_correlation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"CORR_RUN_{uuid.uuid4().hex[:12].upper()}")
    config_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_07_correlation_configs.config_id"), nullable=False, index=True)
    factor_model_version_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    factor_count: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_pair_count: Mapped[int] = mapped_column(Integer, nullable=False)
    invalid_pair_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    is_positive_semidefinite: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    min_eigenvalue: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    max_eigenvalue: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    condition_number: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    matrix_rank: Mapped[int] = mapped_column(Integer, nullable=False)

    result_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    pairs: Mapped[List["FactorCorrelationPair"]] = relationship("FactorCorrelationPair", back_populates="run", cascade="all, delete-orphan")
    matrix_snapshot: Mapped[Optional["FactorCorrelationMatrixSnapshot"]] = relationship("FactorCorrelationMatrixSnapshot", back_populates="run", uselist=False, cascade="all, delete-orphan")


class FactorCorrelationPair(Base):
    """Pairwise correlation and covariance record between two systematic factors."""
    __tablename__ = "m08_07_correlation_pairs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_07_correlation_runs.run_id"), nullable=False, index=True)
    factor_a_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    factor_b_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    factor_a_code: Mapped[str] = mapped_column(String(32), nullable=False)
    factor_b_code: Mapped[str] = mapped_column(String(32), nullable=False)

    correlation_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    covariance_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    factor_a_volatility_annualized: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    factor_b_volatility_annualized: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)

    p_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    ci_lower: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    ci_upper: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)

    relationship_classification: Mapped[CorrelationRelationshipClassification] = mapped_column(
        SQLEnum(CorrelationRelationshipClassification, native_enum=False), default=CorrelationRelationshipClassification.WEAK, nullable=False
    )
    is_defined: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    undefined_reason: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    run: Mapped["FactorCorrelationRun"] = relationship("FactorCorrelationRun", back_populates="pairs")


class FactorCorrelationMatrixSnapshot(Base):
    """Pinned, immutable K x K correlation matrix representation."""
    __tablename__ = "m08_07_correlation_matrix_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    matrix_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"CORR_MAT_{uuid.uuid4().hex[:12].upper()}")
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_07_correlation_runs.run_id"), unique=True, nullable=False, index=True)
    factor_model_version_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    factor_ordering: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    correlation_matrix: Mapped[List[List[float]]] = mapped_column(JSON, nullable=False)

    is_symmetric: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_positive_semidefinite: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    min_eigenvalue: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    max_eigenvalue: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    condition_number: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)

    result_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    run: Mapped["FactorCorrelationRun"] = relationship("FactorCorrelationRun", back_populates="matrix_snapshot")


# ----------------------------------------------------------------------------
# 3. AUTHORITATIVE FACTOR COVARIANCE MODELS
# ----------------------------------------------------------------------------

class FactorCovarianceConfig(Base):
    """Immutable covariance estimation configuration."""
    __tablename__ = "m08_07_covariance_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"COV_CFG_{uuid.uuid4().hex[:12].upper()}")
    config_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    covariance_method: Mapped[FactorCovarianceMethod] = mapped_column(SQLEnum(FactorCovarianceMethod, native_enum=False), default=FactorCovarianceMethod.SAMPLE, nullable=False)
    observation_frequency: Mapped[str] = mapped_column(String(32), default="DAILY", nullable=False)
    annualization_factor: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("252.00"), nullable=False)
    decay_factor: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4), default=Decimal("0.94"), nullable=True)
    shrinkage_target: Mapped[Optional[str]] = mapped_column(String(32), default="IDENTITY", nullable=True)
    shrinkage_intensity: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4), nullable=True)
    minimum_observations: Mapped[int] = mapped_column(Integer, default=20, nullable=False)

    config_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class FactorCovarianceSnapshot(Base):
    """
    Authoritative factor covariance snapshot consumed by M08.05 Systematic Risk.
    Guarantees Sigma_F == D * P_F * D consistency and spectral PSD validity.
    """
    __tablename__ = "m08_07_covariance_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"FACT_COV_{uuid.uuid4().hex[:12].upper()}")
    config_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("m08_07_covariance_configs.config_id"), nullable=True)
    factor_model_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    factor_model_version_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    covariance_method: Mapped[FactorCovarianceMethod] = mapped_column(SQLEnum(FactorCovarianceMethod, native_enum=False), default=FactorCovarianceMethod.SAMPLE, nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_sample_size: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    factor_ordering: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    covariance_matrix_period: Mapped[List[List[float]]] = mapped_column(JSON, nullable=False)
    covariance_matrix_annualized: Mapped[List[List[float]]] = mapped_column(JSON, nullable=False)
    correlation_matrix: Mapped[List[List[float]]] = mapped_column(JSON, nullable=False)
    factor_volatilities_annualized: Mapped[List[float]] = mapped_column(JSON, nullable=False)

    is_positive_semidefinite: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    min_eigenvalue: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    max_eigenvalue: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    condition_number: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    matrix_rank: Mapped[int] = mapped_column(Integer, nullable=False)

    is_regularized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    original_min_eigenvalue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)

    result_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


# ----------------------------------------------------------------------------
# 4. ROLLING FACTOR CORRELATIONS & REGIME ALERTS
# ----------------------------------------------------------------------------

class RollingFactorCorrelation(Base):
    """Historical point-in-time rolling correlation & covariance between two factors."""
    __tablename__ = "m08_07_rolling_correlations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    factor_model_version_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    factor_a_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    factor_b_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    factor_a_code: Mapped[str] = mapped_column(String(32), nullable=False)
    factor_b_code: Mapped[str] = mapped_column(String(32), nullable=False)

    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    window_length: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)

    correlation_value: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    covariance_value: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    previous_correlation: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    signed_correlation_change: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    absolute_strength_change: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)

    baseline_correlation: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    percentile_rank: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    stability_status: Mapped[CorrelationStabilityCategory] = mapped_column(
        SQLEnum(CorrelationStabilityCategory, native_enum=False), default=CorrelationStabilityCategory.STABLE_POSITIVE, nullable=False
    )
    is_sign_reversal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class FactorRegimeAlertConfig(Base):
    """Threshold settings for relationship break monitoring and alert triggers."""
    __tablename__ = "m08_07_regime_alert_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"ALRT_CFG_{uuid.uuid4().hex[:12].upper()}")
    config_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    factor_model_version_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    high_positive_threshold: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("0.70"), nullable=False)
    high_negative_threshold: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("-0.70"), nullable=False)
    rapid_change_threshold: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("0.25"), nullable=False)
    confirmation_observations: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    recovery_threshold: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("0.60"), nullable=False)
    cooldown_period_days: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    status: Mapped[FactorLifecycleStatus] = mapped_column(SQLEnum(FactorLifecycleStatus, native_enum=False), default=FactorLifecycleStatus.ACTIVE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class FactorRegimeAlert(Base):
    """Auditable factor co-movement regime alerts and structural break events."""
    __tablename__ = "m08_07_regime_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"ALRT_{uuid.uuid4().hex[:12].upper()}")
    factor_model_version_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    factor_a_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    factor_b_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[RegimeAlertSeverity] = mapped_column(SQLEnum(RegimeAlertSeverity, native_enum=False), default=RegimeAlertSeverity.WARNING, nullable=False)
    status: Mapped[RegimeAlertStatus] = mapped_column(SQLEnum(RegimeAlertStatus, native_enum=False), default=RegimeAlertStatus.ACTIVE, nullable=False, index=True)

    current_correlation: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    baseline_correlation: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    trigger_threshold: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    recovered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

