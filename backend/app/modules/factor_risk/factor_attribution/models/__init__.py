"""
M08.04 Factor Attribution Database Models and Enums.
Establishes entities for:
1. factor_attribution_config: Immutable versioned factor attribution methodology profile
2. factor_return_attribution_run: Portfolio return attribution execution and linking run
3. factor_return_attribution_component: Factor return contributions (Risk-free, Factor, Intercept, Residual)
4. factor_risk_attribution_run: Portfolio systematic and total modeled risk attribution run
5. factor_risk_attribution_component: Factor variance, volatility, and marginal risk contributions
6. factor_attribution_covariance_snapshot: Factor covariance matrix snapshot with PSD validation metadata
7. factor_attribution_reconciliation: Formal return and risk reconciliation verification records
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

class AttributionMode(str, Enum):
    EX_ANTE_PINNED = "EX_ANTE_PINNED"        # Default: Lagged sensitivity beta_{t-1}
    EX_POST_EXPLANATORY = "EX_POST_EXPLANATORY"  # Contemporaneous fitted window beta


class AttributionReturnBasis(str, Enum):
    EXCESS_RETURN = "EXCESS_RETURN"  # R_p - R_f = alpha + sum(beta*F) + eps
    TOTAL_RETURN = "TOTAL_RETURN"    # R_p = alpha + sum(beta*F) + eps


class MultiPeriodLinkingMethod(str, Enum):
    CARINO = "CARINO"                        # Exact Carino logarithmic scaling
    ARITHMETIC_UNLINKED = "ARITHMETIC_UNLINKED"  # Simple summation without compounding
    NONE = "NONE"


class ReturnComponentType(str, Enum):
    RISK_FREE = "RISK_FREE"
    FACTOR = "FACTOR"
    INTERCEPT = "INTERCEPT"
    MODEL_RESIDUAL = "MODEL_RESIDUAL"
    RECONCILIATION_RESIDUAL = "RECONCILIATION_RESIDUAL"


class RiskComponentType(str, Enum):
    FACTOR = "FACTOR"
    RESIDUAL = "RESIDUAL"
    FACTOR_RESIDUAL_COVARIANCE = "FACTOR_RESIDUAL_COVARIANCE"


class AttributionReconciliationStatus(str, Enum):
    FULLY_RECONCILED = "FULLY_RECONCILED"
    RECONCILED_WITHIN_TOLERANCE = "RECONCILED_WITHIN_TOLERANCE"
    RECONCILED_WITH_WARNING = "RECONCILED_WITH_WARNING"
    PARTIALLY_RECONCILED = "PARTIALLY_RECONCILED"
    UNRECONCILED = "UNRECONCILED"
    BLOCKED_INCOMPATIBLE_INPUTS = "BLOCKED_INCOMPATIBLE_INPUTS"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    LINKING_UNAVAILABLE = "LINKING_UNAVAILABLE"


class AttributionRunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
    FAILED = "FAILED"
    BLOCKED_MISSING_DATA = "BLOCKED_MISSING_DATA"


class CovarianceMethod(str, Enum):
    SAMPLE = "SAMPLE"
    EXPONENTIALLY_WEIGHTED = "EXPONENTIALLY_WEIGHTED"
    SHRINKAGE_LEDOIT_WOLF = "SHRINKAGE_LEDOIT_WOLF"


# ============================================================================
# 2. ATTRIBUTION CONFIGURATION
# ============================================================================

class FactorAttributionConfig(Base):
    """
    Immutable, version-controlled factor attribution specification profile.
    """
    __tablename__ = "m08_04_attribution_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    config_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    config_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    factor_model_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    factor_model_version_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    attribution_mode: Mapped[AttributionMode] = mapped_column(SQLEnum(AttributionMode), default=AttributionMode.EX_ANTE_PINNED, nullable=False)
    return_basis: Mapped[AttributionReturnBasis] = mapped_column(SQLEnum(AttributionReturnBasis), default=AttributionReturnBasis.EXCESS_RETURN, nullable=False)
    linking_method: Mapped[MultiPeriodLinkingMethod] = mapped_column(SQLEnum(MultiPeriodLinkingMethod), default=MultiPeriodLinkingMethod.CARINO, nullable=False)
    covariance_method: Mapped[CovarianceMethod] = mapped_column(SQLEnum(CovarianceMethod), default=CovarianceMethod.SAMPLE, nullable=False)
    
    annualization_factor: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("252.00"), nullable=False)
    reconciliation_tolerance: Mapped[Decimal] = mapped_column(Numeric(10, 8), default=Decimal("0.00001000"), nullable=False)
    coverage_threshold_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("80.00"), nullable=False)
    
    currency_basis: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[FactorLifecycleStatus] = mapped_column(SQLEnum(FactorLifecycleStatus), default=FactorLifecycleStatus.ACTIVE, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)


# ============================================================================
# 3. FACTOR RETURN ATTRIBUTION RUN & COMPONENTS
# ============================================================================

class FactorReturnAttributionRun(Base):
    """
    Execution run record for portfolio factor return attribution.
    """
    __tablename__ = "m08_04_return_attribution_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    config_id: Mapped[str] = mapped_column(String(36), ForeignKey("m08_04_attribution_configs.config_id"), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    
    factor_model_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    factor_model_version_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sensitivity_run_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    exposure_snapshot_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    attribution_mode: Mapped[AttributionMode] = mapped_column(SQLEnum(AttributionMode), nullable=False)
    linking_method: Mapped[MultiPeriodLinkingMethod] = mapped_column(SQLEnum(MultiPeriodLinkingMethod), nullable=False)

    realized_portfolio_return: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    total_attributed_return: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    factor_explained_return: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    
    risk_free_contribution: Mapped[Decimal] = mapped_column(Numeric(14, 8), default=Decimal("0.0"), nullable=False)
    intercept_contribution: Mapped[Decimal] = mapped_column(Numeric(14, 8), default=Decimal("0.0"), nullable=False)
    model_residual: Mapped[Decimal] = mapped_column(Numeric(14, 8), default=Decimal("0.0"), nullable=False)
    reconciliation_residual: Mapped[Decimal] = mapped_column(Numeric(14, 8), default=Decimal("0.0"), nullable=False)
    
    reconciliation_status: Mapped[AttributionReconciliationStatus] = mapped_column(
        SQLEnum(AttributionReconciliationStatus), default=AttributionReconciliationStatus.FULLY_RECONCILED, nullable=False, index=True
    )
    coverage_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("100.00"), nullable=False)
    run_status: Mapped[AttributionRunStatus] = mapped_column(SQLEnum(AttributionRunStatus), default=AttributionRunStatus.PENDING, nullable=False, index=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    components: Mapped[List["FactorReturnAttributionComponent"]] = relationship(
        "FactorReturnAttributionComponent", back_populates="run", cascade="all, delete-orphan", lazy="selectin"
    )
    reconciliation: Mapped[Optional["FactorAttributionReconciliation"]] = relationship(
        "FactorAttributionReconciliation", back_populates="return_run", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )


class FactorReturnAttributionComponent(Base):
    """
    Individual return attribution component (per factor, risk-free, intercept, residual).
    """
    __tablename__ = "m08_04_return_attribution_components"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    component_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("m08_04_return_attribution_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)

    component_type: Mapped[ReturnComponentType] = mapped_column(SQLEnum(ReturnComponentType), nullable=False, index=True)
    factor_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    factor_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)

    factor_sensitivity_beta: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    factor_realized_return: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 8), nullable=True)
    
    arithmetic_contribution: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    linked_contribution: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 8), nullable=True)
    contribution_percentage_of_return: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    run: Mapped["FactorReturnAttributionRun"] = relationship("FactorReturnAttributionRun", back_populates="components")


# ============================================================================
# 4. FACTOR COVARIANCE SNAPSHOT
# ============================================================================

class FactorAttributionCovarianceSnapshot(Base):
    """
    Factor return covariance matrix snapshot with positive semidefiniteness (PSD) audit.
    """
    __tablename__ = "m08_04_covariance_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    factor_model_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    factor_model_version_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    
    covariance_method: Mapped[CovarianceMethod] = mapped_column(SQLEnum(CovarianceMethod), nullable=False)
    observation_frequency: Mapped[str] = mapped_column(String(16), default="DAILY", nullable=False)
    estimation_window_start: Mapped[date] = mapped_column(Date, nullable=False)
    estimation_window_end: Mapped[date] = mapped_column(Date, nullable=False)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    
    annualization_factor: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("252.00"), nullable=False)
    factor_names_ordered: Mapped[List[str]] = mapped_column(JSON, nullable=False)  # ["MKT_RF", "SMB", "HML"]
    covariance_matrix: Mapped[List[List[float]]] = mapped_column(JSON, nullable=False)  # K x K array
    
    is_positive_semidefinite: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    min_eigenvalue: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    condition_number: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    
    result_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


# ============================================================================
# 5. FACTOR RISK ATTRIBUTION RUN & COMPONENTS
# ============================================================================

class FactorRiskAttributionRun(Base):
    """
    Execution run record for portfolio systematic and total modeled risk attribution.
    """
    __tablename__ = "m08_04_risk_attribution_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    config_id: Mapped[str] = mapped_column(String(36), ForeignKey("m08_04_attribution_configs.config_id"), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    
    factor_model_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    factor_model_version_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    covariance_snapshot_id: Mapped[str] = mapped_column(String(36), ForeignKey("m08_04_covariance_snapshots.snapshot_id"), nullable=False, index=True)
    sensitivity_run_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    exposure_snapshot_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    observation_frequency: Mapped[str] = mapped_column(String(16), default="DAILY", nullable=False)
    annualization_factor: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("252.00"), nullable=False)

    # Systematic Euler Risk Metrics (Annualized)
    systematic_variance: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    systematic_volatility: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    
    # Residual and Total Modeled Risk Metrics
    residual_variance: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 8), nullable=True)
    residual_volatility: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 8), nullable=True)
    factor_residual_covariance: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 8), nullable=True)
    total_modeled_variance: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    total_modeled_volatility: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    
    realized_portfolio_variance: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 8), nullable=True)
    variance_reconciliation_difference: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 8), nullable=True)

    run_status: Mapped[AttributionRunStatus] = mapped_column(SQLEnum(AttributionRunStatus), default=AttributionRunStatus.PENDING, nullable=False, index=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    components: Mapped[List["FactorRiskAttributionComponent"]] = relationship(
        "FactorRiskAttributionComponent", back_populates="run", cascade="all, delete-orphan", lazy="selectin"
    )
    reconciliation: Mapped[Optional["FactorAttributionReconciliation"]] = relationship(
        "FactorAttributionReconciliation", back_populates="risk_run", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )


class FactorRiskAttributionComponent(Base):
    """
    Factor and residual risk attribution component (variance contribution, volatility contribution, marginal risk).
    """
    __tablename__ = "m08_04_risk_attribution_components"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    component_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("m08_04_risk_attribution_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)

    component_type: Mapped[RiskComponentType] = mapped_column(SQLEnum(RiskComponentType), nullable=False, index=True)
    factor_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    factor_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)

    factor_sensitivity_beta: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    variance_contribution: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    volatility_contribution: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    
    marginal_volatility_contribution: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 8), nullable=True)
    marginal_variance_contribution: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 8), nullable=True)
    percentage_volatility_contribution: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    run: Mapped["FactorRiskAttributionRun"] = relationship("FactorRiskAttributionRun", back_populates="components")


# ============================================================================
# 6. ATTRIBUTION RECONCILIATION
# ============================================================================

class FactorAttributionReconciliation(Base):
    """
    Formal reconciliation result record for return or risk attribution.
    """
    __tablename__ = "m08_04_attribution_reconciliations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reconciliation_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    
    return_run_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("m08_04_return_attribution_runs.run_id", ondelete="CASCADE"), unique=True, nullable=True, index=True)
    risk_run_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("m08_04_risk_attribution_runs.run_id", ondelete="CASCADE"), unique=True, nullable=True, index=True)
    
    reconciliation_type: Mapped[str] = mapped_column(String(16), nullable=False)  # "RETURN" or "RISK"
    observed_value: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    reported_value: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    absolute_difference: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    relative_difference: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    
    tolerance: Mapped[Decimal] = mapped_column(Numeric(10, 8), nullable=False)
    coverage_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("100.00"), nullable=False)
    reconciliation_status: Mapped[AttributionReconciliationStatus] = mapped_column(SQLEnum(AttributionReconciliationStatus), nullable=False)
    
    reason_codes: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    diagnostic_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    return_run: Mapped[Optional["FactorReturnAttributionRun"]] = relationship("FactorReturnAttributionRun", back_populates="reconciliation")
    risk_run: Mapped[Optional["FactorRiskAttributionRun"]] = relationship("FactorRiskAttributionRun", back_populates="reconciliation")
