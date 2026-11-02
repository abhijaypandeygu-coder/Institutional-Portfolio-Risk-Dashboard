"""
SQLAlchemy 2.x Database Models for M08.06 Idiosyncratic Risk Analytics.
Establishes tables for:
1. m08_06_residual_configs: Versioned residual risk & estimation settings
2. m08_06_residual_volatility_runs: Security-level residual volatility & robust scale metrics
3. m08_06_residual_covariance_snapshots: Aligned security/issuer residual covariance matrices
4. m08_06_portfolio_idiosyncratic_runs: Portfolio idiosyncratic risk run execution headers
5. m08_06_security_risk_contributions: Security-level Euler variance/volatility contributions
6. m08_06_issuer_risk_contributions: Consolidated issuer-level idiosyncratic risk contributions
7. m08_06_residual_diagnostic_runs: Econometric model diagnostic executions & misspecification flags
8. m08_06_residual_outliers: Detected standardized and robust residual outliers
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

class ResidualVarianceEstimator(str, Enum):
    SAMPLE = "SAMPLE"
    POPULATION = "POPULATION"
    EXPONENTIALLY_WEIGHTED = "EXPONENTIALLY_WEIGHTED"


class ResidualModelQualityStatus(str, Enum):
    ACCEPTABLE = "ACCEPTABLE"
    ACCEPTABLE_WITH_WARNINGS = "ACCEPTABLE_WITH_WARNINGS"
    WEAK_SPECIFICATION = "WEAK_SPECIFICATION"
    HIGH_MISSPECIFICATION_RISK = "HIGH_MISSPECIFICATION_RISK"
    INSUFFICIENT_DIAGNOSTIC_DATA = "INSUFFICIENT_DIAGNOSTIC_DATA"


class OutlierSeverity(str, Enum):
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ContributionStatus(str, Enum):
    POSITIVE_RISK_CONTRIBUTOR = "POSITIVE_RISK_CONTRIBUTOR"
    NEGATIVE_RISK_DIVERSIFIER = "NEGATIVE_RISK_DIVERSIFIER"
    ZERO_CONTRIBUTION = "ZERO_CONTRIBUTION"


# ============================================================================
# 2. DATABASE MODELS
# ============================================================================

class ResidualRiskConfig(Base):
    """Immutable, versioned residual risk calculation configuration."""
    __tablename__ = "m08_06_residual_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"IDIO_CFG_{uuid.uuid4().hex[:12].upper()}")
    config_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    config_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    factor_model_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_01_factor_models.model_id"), nullable=False, index=True)
    factor_model_version_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_01_factor_model_versions.model_version_id"), nullable=False, index=True)

    variance_estimator: Mapped[ResidualVarianceEstimator] = mapped_column(SQLEnum(ResidualVarianceEstimator, native_enum=False), default=ResidualVarianceEstimator.SAMPLE, nullable=False)
    observation_frequency: Mapped[str] = mapped_column(String(32), default="DAILY", nullable=False)
    annualization_factor: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("252.00"), nullable=False)
    decay_factor: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4), default=Decimal("0.94"), nullable=True)
    minimum_observations: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    outlier_z_threshold: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("3.00"), nullable=False)

    config_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[FactorLifecycleStatus] = mapped_column(SQLEnum(FactorLifecycleStatus, native_enum=False), default=FactorLifecycleStatus.ACTIVE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ResidualVolatilityRun(Base):
    """Execution record for instrument-level residual volatility & scale estimation."""
    __tablename__ = "m08_06_residual_volatility_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"IDIO_VOL_{uuid.uuid4().hex[:12].upper()}")
    config_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_06_residual_configs.config_id"), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    residual_mean: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    residual_variance_period: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    residual_volatility_period: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    residual_variance_annualized: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    residual_volatility_annualized: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)

    robust_mad_scale_annualized: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 8), nullable=True)
    ew_residual_volatility_annualized: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 8), nullable=True)
    effective_sample_size: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    result_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ResidualCovarianceSnapshot(Base):
    """Pinned security/issuer residual covariance matrix."""
    __tablename__ = "m08_06_residual_covariance_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"IDIO_COV_{uuid.uuid4().hex[:12].upper()}")
    factor_model_version_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    instrument_ids_ordered: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    covariance_matrix: Mapped[List[List[float]]] = mapped_column(JSON, nullable=False)
    correlation_matrix: Mapped[Optional[List[List[float]]]] = mapped_column(JSON, nullable=True)

    is_positive_semidefinite: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    min_eigenvalue: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    condition_number: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    matrix_rank: Mapped[int] = mapped_column(Integer, nullable=False)

    result_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class PortfolioIdiosyncraticRiskRun(Base):
    """Header execution record for portfolio idiosyncratic risk & diversification."""
    __tablename__ = "m08_06_portfolio_idiosyncratic_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"IDIO_PF_RUN_{uuid.uuid4().hex[:12].upper()}")
    config_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_06_residual_configs.config_id"), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    portfolio_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Actual Portfolio Idiosyncratic Risk (with cross-security covariance)
    portfolio_idiosyncratic_variance_annualized: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    portfolio_idiosyncratic_volatility_annualized: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)

    # Diversification Decomposition
    diagonal_baseline_variance_annualized: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    covariance_effect_annualized: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    diversification_benefit_annualized: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    absolute_contribution_hhi: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    effective_number_of_risk_contributors: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)

    coverage_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("100.00"), nullable=False)
    is_reconciled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    result_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    security_contributions: Mapped[List["SecurityResidualRiskContribution"]] = relationship(
        "SecurityResidualRiskContribution", back_populates="run", cascade="all, delete-orphan"
    )
    issuer_contributions: Mapped[List["IssuerResidualRiskContribution"]] = relationship(
        "IssuerResidualRiskContribution", back_populates="run", cascade="all, delete-orphan"
    )


class SecurityResidualRiskContribution(Base):
    """Holding-level Euler residual variance & volatility contributions."""
    __tablename__ = "m08_06_security_risk_contributions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_06_portfolio_idiosyncratic_runs.run_id"), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    issuer_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    signed_weight: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    absolute_weight: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    standalone_residual_volatility_annualized: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)

    marginal_volatility_contribution_annualized: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    volatility_contribution_annualized: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    variance_contribution_annualized: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    percentage_contribution: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)

    contribution_status: Mapped[ContributionStatus] = mapped_column(SQLEnum(ContributionStatus, native_enum=False), default=ContributionStatus.POSITIVE_RISK_CONTRIBUTOR, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    run: Mapped["PortfolioIdiosyncraticRiskRun"] = relationship("PortfolioIdiosyncraticRiskRun", back_populates="security_contributions")


class IssuerResidualRiskContribution(Base):
    """Consolidated issuer-level idiosyncratic risk contributions."""
    __tablename__ = "m08_06_issuer_risk_contributions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_06_portfolio_idiosyncratic_runs.run_id"), nullable=False, index=True)
    issuer_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    member_instrument_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    signed_issuer_weight: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    absolute_issuer_weight: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    issuer_residual_volatility_annualized: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)

    variance_contribution_annualized: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    volatility_contribution_annualized: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    percentage_contribution: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    run: Mapped["PortfolioIdiosyncraticRiskRun"] = relationship("PortfolioIdiosyncraticRiskRun", back_populates="issuer_contributions")


class ResidualDiagnosticRun(Base):
    """Detailed residual distribution, autocorrelation, heteroskedasticity & break diagnostics."""
    __tablename__ = "m08_06_residual_diagnostic_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    diagnostic_run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"IDIO_DIAG_{uuid.uuid4().hex[:12].upper()}")
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    factor_model_version_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    skewness: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    excess_kurtosis: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    jarque_bera_p_value: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)

    lag1_autocorrelation: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    ljung_box_p_value: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    arch_lm_p_value: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    has_structural_shift: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    model_quality_status: Mapped[ResidualModelQualityStatus] = mapped_column(SQLEnum(ResidualModelQualityStatus, native_enum=False), default=ResidualModelQualityStatus.ACCEPTABLE, nullable=False)
    warning_messages: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    outliers: Mapped[List["ResidualOutlierRecord"]] = relationship("ResidualOutlierRecord", back_populates="diagnostic_run", cascade="all, delete-orphan")


class ResidualOutlierRecord(Base):
    """Point-in-time residual outlier events exceeding statistical thresholds."""
    __tablename__ = "m08_06_residual_outliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    diagnostic_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_06_residual_diagnostic_runs.diagnostic_run_id"), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    residual_value: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    standardized_z_score: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    severity: Mapped[OutlierSeverity] = mapped_column(SQLEnum(OutlierSeverity, native_enum=False), default=OutlierSeverity.HIGH, nullable=False)
    detection_method: Mapped[str] = mapped_column(String(64), default="STANDARDIZED_Z", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    diagnostic_run: Mapped["ResidualDiagnosticRun"] = relationship("ResidualDiagnosticRun", back_populates="outliers")

