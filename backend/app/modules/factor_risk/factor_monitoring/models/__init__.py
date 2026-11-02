"""
SQLAlchemy 2.x Database Models for M08.08 Factor Monitoring.
Defines tables for:
1. m08_08_monitoring_configs: Versioned monitoring profiles
2. m08_08_exposure_targets: Approved portfolio factor target profiles
3. m08_08_exposure_target_components: Factor-specific target values and bounds
4. m08_08_threshold_policies: Immutable threshold boundary policies
5. m08_08_monitoring_runs: Header execution logs & input freshness audit
6. m08_08_exposure_drift_results: Factor exposure drift records & sign transitions
7. m08_08_concentration_results: Exposure & Risk Contribution HHI and top factor shares
8. m08_08_threshold_evaluations: Utilization, headroom, and boundary states
9. m08_08_breaches: Breach lifecycle (detection, acknowledgement, recovery)
10. m08_08_monitoring_events: Typed monitoring events ready for M12 notification publishing
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


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================================
# 1. ENUMERATIONS
# ============================================================================

class MonitoringScope(str, Enum):
    PORTFOLIO = "PORTFOLIO"
    PORTFOLIO_GROUP = "PORTFOLIO_GROUP"
    STRATEGY = "STRATEGY"


class EvaluationFrequency(str, Enum):
    INTRADAY = "INTRADAY"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    CUSTOM = "CUSTOM"


class DriftReferenceType(str, Enum):
    PREVIOUS_SNAPSHOT = "PREVIOUS_SNAPSHOT"
    HISTORICAL_BASELINE = "HISTORICAL_BASELINE"
    APPROVED_TARGET = "APPROVED_TARGET"
    STRATEGIC_PROFILE = "STRATEGIC_PROFILE"


class DriftClassification(str, Enum):
    WITHIN_TOLERANCE = "WITHIN_TOLERANCE"
    LOW_DRIFT = "LOW_DRIFT"
    MODERATE_DRIFT = "MODERATE_DRIFT"
    HIGH_DRIFT = "HIGH_DRIFT"
    CRITICAL_DRIFT = "CRITICAL_DRIFT"
    SIGN_REVERSAL = "SIGN_REVERSAL"
    TARGET_BREACH = "TARGET_BREACH"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    STALE_REFERENCE = "STALE_REFERENCE"
    NOT_COMPARABLE = "NOT_COMPARABLE"
    DATA_QUALITY_IMPACTED = "DATA_QUALITY_IMPACTED"


class ConcentrationStatus(str, Enum):
    LOW_FACTOR_CONCENTRATION = "LOW_FACTOR_CONCENTRATION"
    MODERATE_FACTOR_CONCENTRATION = "MODERATE_FACTOR_CONCENTRATION"
    HIGH_FACTOR_CONCENTRATION = "HIGH_FACTOR_CONCENTRATION"
    VERY_HIGH_FACTOR_CONCENTRATION = "VERY_HIGH_FACTOR_CONCENTRATION"
    SINGLE_FACTOR_DEPENDENCE = "SINGLE_FACTOR_DEPENDENCE"
    INSUFFICIENT_FACTOR_DATA = "INSUFFICIENT_FACTOR_DATA"
    CONCENTRATION_UNAVAILABLE = "CONCENTRATION_UNAVAILABLE"


class ThresholdMetricType(str, Enum):
    ABSOLUTE_FACTOR_EXPOSURE = "ABSOLUTE_FACTOR_EXPOSURE"
    DIRECTIONAL_FACTOR_EXPOSURE = "DIRECTIONAL_FACTOR_EXPOSURE"
    TARGET_DEVIATION = "TARGET_DEVIATION"
    STANDARDIZED_EXPOSURE = "STANDARDIZED_EXPOSURE"
    EXPOSURE_DRIFT = "EXPOSURE_DRIFT"
    EXPOSURE_HHI = "EXPOSURE_HHI"
    RISK_CONTRIBUTION_HHI = "RISK_CONTRIBUTION_HHI"
    EFFECTIVE_FACTOR_COUNT = "EFFECTIVE_FACTOR_COUNT"
    TOP_FACTOR_SHARE = "TOP_FACTOR_SHARE"
    SYSTEMATIC_VOLATILITY = "SYSTEMATIC_VOLATILITY"


class ThresholdEvaluationStatus(str, Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    BREACH = "BREACH"
    CRITICAL_BREACH = "CRITICAL_BREACH"
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    RECOVERY_PENDING = "RECOVERY_PENDING"
    RECOVERED = "RECOVERED"
    UNAVAILABLE = "UNAVAILABLE"
    STALE_INPUT = "STALE_INPUT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class BreachSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class BreachStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RECOVERY_PENDING = "RECOVERY_PENDING"
    RECOVERED = "RECOVERED"
    CLOSED = "CLOSED"


class MonitoringRunStatus(str, Enum):
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
    PARTIAL = "PARTIAL"
    BLOCKED_MISSING_INPUTS = "BLOCKED_MISSING_INPUTS"
    FAILED = "FAILED"


# ============================================================================
# 2. DATABASE MODELS
# ============================================================================

class FactorMonitoringConfig(Base):
    """Overall versioned factor monitoring profile."""
    __tablename__ = "m08_08_monitoring_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"MON_CFG_{uuid.uuid4().hex[:12].upper()}")
    config_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    factor_model_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_01_factor_models.model_id"), nullable=False, index=True)
    factor_model_version_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_01_factor_model_versions.model_version_id"), nullable=False, index=True)

    evaluation_frequency: Mapped[EvaluationFrequency] = mapped_column(SQLEnum(EvaluationFrequency, native_enum=False), default=EvaluationFrequency.DAILY, nullable=False)
    drift_reference_type: Mapped[DriftReferenceType] = mapped_column(SQLEnum(DriftReferenceType, native_enum=False), default=DriftReferenceType.PREVIOUS_SNAPSHOT, nullable=False)
    historical_baseline_window: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    persistence_required: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    recovery_required: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)


class FactorExposureTarget(Base):
    """Approved target factor exposure profile."""
    __tablename__ = "m08_08_exposure_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"TGT_PROF_{uuid.uuid4().hex[:12].upper()}")
    target_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    factor_model_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_01_factor_models.model_id"), nullable=False, index=True)
    factor_model_version_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_01_factor_model_versions.model_version_id"), nullable=False, index=True)

    target_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    components: Mapped[List["FactorExposureTargetComponent"]] = relationship("FactorExposureTargetComponent", back_populates="target", cascade="all, delete-orphan", lazy="selectin")


class FactorExposureTargetComponent(Base):
    """Factor-specific target loading and tolerance bounds."""
    __tablename__ = "m08_08_exposure_target_components"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_08_exposure_targets.target_id", ondelete="CASCADE"), nullable=False, index=True)
    factor_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_01_factor_definitions.factor_id"), nullable=False, index=True)
    factor_code: Mapped[str] = mapped_column(String(32), nullable=False)
    target_exposure: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    min_exposure: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    max_exposure: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    tolerance: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0.20"), nullable=False)

    target: Mapped["FactorExposureTarget"] = relationship("FactorExposureTarget", back_populates="components")


class FactorThresholdPolicy(Base):
    """Configurable, versioned threshold policies for exposures, drift, concentration, and risk."""
    __tablename__ = "m08_08_threshold_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"POL_{uuid.uuid4().hex[:12].upper()}")
    policy_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    factor_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    factor_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    metric_type: Mapped[ThresholdMetricType] = mapped_column(SQLEnum(ThresholdMetricType, native_enum=False), nullable=False)
    min_boundary: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 6), nullable=True)
    max_boundary: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 6), nullable=True)
    warning_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 6), nullable=True)
    breach_threshold: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    critical_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 6), nullable=True)
    recovery_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 6), nullable=True)

    persistence_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    recovery_count: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    severity: Mapped[BreachSeverity] = mapped_column(SQLEnum(BreachSeverity, native_enum=False), default=BreachSeverity.WARNING, nullable=False)
    policy_precedence: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)


class FactorMonitoringRun(Base):
    """Header execution record for a complete factor monitoring evaluation."""
    __tablename__ = "m08_08_monitoring_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"MON_RUN_{uuid.uuid4().hex[:12].upper()}")
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    factor_model_version_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_01_factor_model_versions.model_version_id"), nullable=False, index=True)
    config_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    status: Mapped[MonitoringRunStatus] = mapped_column(SQLEnum(MonitoringRunStatus, native_enum=False), default=MonitoringRunStatus.COMPLETED, nullable=False)
    drift_status: Mapped[str] = mapped_column(String(32), default="NORMAL", nullable=False)
    concentration_status: Mapped[ConcentrationStatus] = mapped_column(SQLEnum(ConcentrationStatus, native_enum=False), default=ConcentrationStatus.LOW_FACTOR_CONCENTRATION, nullable=False)
    has_active_breaches: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active_breach_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warning_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    critical_breach_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    input_freshness: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)

    drifts: Mapped[List["FactorExposureDriftResult"]] = relationship("FactorExposureDriftResult", back_populates="run", cascade="all, delete-orphan", lazy="selectin")
    evaluations: Mapped[List["FactorThresholdEvaluation"]] = relationship("FactorThresholdEvaluation", back_populates="run", cascade="all, delete-orphan", lazy="selectin")


class FactorExposureDriftResult(Base):
    """Factor-specific signed and absolute exposure drift records."""
    __tablename__ = "m08_08_exposure_drift_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_08_monitoring_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    factor_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_01_factor_definitions.factor_id"), nullable=False, index=True)
    factor_code: Mapped[str] = mapped_column(String(32), nullable=False)

    current_exposure: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    reference_exposure: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    target_exposure: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)

    signed_drift: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    absolute_drift: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    percentage_drift: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    is_percentage_drift_defined: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    standardized_current_exposure: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    standardized_reference_exposure: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    standardized_drift: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)

    is_sign_reversal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sign_change_description: Mapped[str] = mapped_column(String(32), default="UNCHANGED", nullable=False)
    drift_classification: Mapped[DriftClassification] = mapped_column(SQLEnum(DriftClassification, native_enum=False), default=DriftClassification.WITHIN_TOLERANCE, nullable=False)

    run: Mapped["FactorMonitoringRun"] = relationship("FactorMonitoringRun", back_populates="drifts")


class FactorConcentrationResult(Base):
    """Factor concentration evaluation records (Exposure HHI and Risk Contribution HHI)."""
    __tablename__ = "m08_08_concentration_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_08_monitoring_runs.run_id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    exposure_hhi: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    effective_exposure_factors: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    top_factor_exposure_share: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    top_two_exposure_share: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    top_three_exposure_share: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    top_exposure_factor: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    risk_hhi: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    effective_risk_factors: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    top_factor_risk_share: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    top_two_risk_share: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    top_three_risk_share: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    top_risk_factor: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    concentration_status: Mapped[ConcentrationStatus] = mapped_column(SQLEnum(ConcentrationStatus, native_enum=False), default=ConcentrationStatus.LOW_FACTOR_CONCENTRATION, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class FactorThresholdEvaluation(Base):
    """Detailed evaluation of individual threshold policies within a run."""
    __tablename__ = "m08_08_threshold_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_08_monitoring_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    policy_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_08_threshold_policies.policy_id"), nullable=False, index=True)
    factor_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    metric_type: Mapped[ThresholdMetricType] = mapped_column(SQLEnum(ThresholdMetricType, native_enum=False), nullable=False)

    measurement_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 6), nullable=True)
    limit_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 6), nullable=True)
    utilization_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    headroom: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 6), nullable=True)

    evaluation_status: Mapped[ThresholdEvaluationStatus] = mapped_column(SQLEnum(ThresholdEvaluationStatus, native_enum=False), default=ThresholdEvaluationStatus.NORMAL, nullable=False)
    is_breach: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_warning: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    run: Mapped["FactorMonitoringRun"] = relationship("FactorMonitoringRun", back_populates="evaluations")


class FactorMonitoringBreach(Base):
    """Persistent breach lifecycle entity (tracking detection, persistence, acknowledgement, recovery)."""
    __tablename__ = "m08_08_breaches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    breach_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"BREACH_{uuid.uuid4().hex[:12].upper()}")
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    policy_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_08_threshold_policies.policy_id"), nullable=False, index=True)
    factor_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    metric_type: Mapped[ThresholdMetricType] = mapped_column(SQLEnum(ThresholdMetricType, native_enum=False), nullable=False)

    severity: Mapped[BreachSeverity] = mapped_column(SQLEnum(BreachSeverity, native_enum=False), default=BreachSeverity.WARNING, nullable=False)
    breach_status: Mapped[BreachStatus] = mapped_column(SQLEnum(BreachStatus, native_enum=False), default=BreachStatus.ACTIVE, nullable=False)

    current_measurement: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    utilization_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)

    first_detected_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    last_detected_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    consecutive_observation_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    recovered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class FactorMonitoringEvent(Base):
    """Typed monitoring event generated for M12 notification delivery."""
    __tablename__ = "m08_08_monitoring_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"MON_EVT_{uuid.uuid4().hex[:12].upper()}")
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("m08_08_monitoring_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    factor_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[BreachSeverity] = mapped_column(SQLEnum(BreachSeverity, native_enum=False), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    event_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    deduplication_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
