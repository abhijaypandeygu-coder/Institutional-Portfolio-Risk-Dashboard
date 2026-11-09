"""
M10.05 Correlation Shock SQLAlchemy Database Models.
Implements:
1. CorrelationShockScenario: Scenario definition & metadata
2. CorrelationShockScenarioVersion: Immutable versioned configuration snapshot
3. CorrelationShockScopeMember: Scope universe specification (instruments, sectors, groups, factors)
4. CorrelationShockPairRule: Canonical pairwise correlation override / shock rules
5. CorrelationShockExecution: Reproducible execution runs with status and timings
6. CorrelationShockMatrixDiagnostic: Eigendecomposition, PSD checks, condition metrics
7. CorrelationShockRepair: Audited matrix repair records with Frobenius norm and max delta
8. CorrelationShockRiskResult: Recalculated portfolio risk & diversification comparison
9. CorrelationShockRiskContribution: Euler component and marginal risk contributions per holding
10. CorrelationShockAuditLog: Governance and audit events
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


class ScenarioScope(str, enum.Enum):
    FULL_PORTFOLIO = "FULL_PORTFOLIO"
    SELECTED_INSTRUMENTS = "SELECTED_INSTRUMENTS"
    SELECTED_SECTORS = "SELECTED_SECTORS"
    SELECTED_INDUSTRIES = "SELECTED_INDUSTRIES"
    SELECTED_PAIRS = "SELECTED_PAIRS"
    SELECTED_FACTORS = "SELECTED_FACTORS"
    FULL_FACTOR_UNIVERSE = "FULL_FACTOR_UNIVERSE"


class ScenarioCategory(str, enum.Enum):
    HYPOTHETICAL = "HYPOTHETICAL"
    HISTORICAL_REPLAY = "HISTORICAL_REPLAY"
    REGULATORY = "REGULATORY"
    DIVERSIFICATION_BREAKDOWN = "DIVERSIFICATION_BREAKDOWN"
    CUSTOM = "CUSTOM"


class ScenarioStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class VolatilityMode(str, enum.Enum):
    HOLD_CONSTANT = "HOLD_CONSTANT"
    STRESSED_VOLATILITY = "STRESSED_VOLATILITY"


class ExecutionStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ---------------------------------------------------------
# Table 1: CorrelationShockScenario
# ---------------------------------------------------------
class CorrelationShockScenario(Base):
    """
    Parent configuration for correlation stress scenarios.
    """
    __tablename__ = "correlation_shock_scenarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    scenario_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scenario_scope: Mapped[ScenarioScope] = mapped_column(
        Enum(ScenarioScope, native_enum=False), default=ScenarioScope.FULL_PORTFOLIO, nullable=False
    )
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    scenario_category: Mapped[ScenarioCategory] = mapped_column(
        Enum(ScenarioCategory, native_enum=False), default=ScenarioCategory.HYPOTHETICAL, nullable=False
    )
    status: Mapped[ScenarioStatus] = mapped_column(
        Enum(ScenarioStatus, native_enum=False), default=ScenarioStatus.ACTIVE, nullable=False
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(64), default="system", nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    versions: Mapped[List["CorrelationShockScenarioVersion"]] = relationship(
        "CorrelationShockScenarioVersion", back_populates="scenario", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------
# Table 2: CorrelationShockScenarioVersion
# ---------------------------------------------------------
class CorrelationShockScenarioVersion(Base):
    """
    Immutable versioned snapshot of correlation scenario configuration.
    """
    __tablename__ = "correlation_shock_scenario_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    scenario_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("correlation_shock_scenarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    transformation_method: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., CONVERGENCE_TO_ONE, INCREASE
    stress_target: Mapped[Optional[float]] = mapped_column(Numeric(8, 6), nullable=True)
    stress_intensity: Mapped[float] = mapped_column(Numeric(6, 4), default=0.5000, nullable=False)
    volatility_mode: Mapped[VolatilityMode] = mapped_column(
        Enum(VolatilityMode, native_enum=False), default=VolatilityMode.HOLD_CONSTANT, nullable=False
    )
    matrix_repair_method: Mapped[str] = mapped_column(String(50), default="EIGENVALUE_CLIPPING", nullable=False)
    repair_parameters: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    risk_model_configuration: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    configuration_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(64), default="system", nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    scenario: Mapped["CorrelationShockScenario"] = relationship(
        "CorrelationShockScenario", back_populates="versions"
    )
    scope_members: Mapped[List["CorrelationShockScopeMember"]] = relationship(
        "CorrelationShockScopeMember", back_populates="scenario_version", cascade="all, delete-orphan"
    )
    pair_rules: Mapped[List["CorrelationShockPairRule"]] = relationship(
        "CorrelationShockPairRule", back_populates="scenario_version", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_m10_05_scenario_ver_unique", "scenario_id", "version_number", unique=True),
    )


# ---------------------------------------------------------
# Table 3: CorrelationShockScopeMember
# ---------------------------------------------------------
class CorrelationShockScopeMember(Base):
    """
    Scope universe members targeted by the scenario.
    """
    __tablename__ = "correlation_shock_scope_members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    scenario_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("correlation_shock_scenario_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)  # INSTRUMENT, SECTOR, INDUSTRY, FACTOR
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    factor_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    membership_source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    membership_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    scenario_version: Mapped["CorrelationShockScenarioVersion"] = relationship(
        "CorrelationShockScenarioVersion", back_populates="scope_members"
    )


# ---------------------------------------------------------
# Table 4: CorrelationShockPairRule
# ---------------------------------------------------------
class CorrelationShockPairRule(Base):
    """
    Pair-level override / selective shocks.
    Always canonically ordered: entity_a_id <= entity_b_id.
    """
    __tablename__ = "correlation_shock_pair_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    scenario_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("correlation_shock_scenario_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_a_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_b_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(32), default="INSTRUMENT", nullable=False)
    baseline_correlation: Mapped[Optional[float]] = mapped_column(Numeric(8, 6), nullable=True)
    target_correlation: Mapped[Optional[float]] = mapped_column(Numeric(8, 6), nullable=True)
    stress_intensity: Mapped[float] = mapped_column(Numeric(6, 4), default=1.0000, nullable=False)
    transformation_method: Mapped[str] = mapped_column(String(50), default="CUSTOM_TARGET", nullable=False)
    resulting_correlation: Mapped[Optional[float]] = mapped_column(Numeric(8, 6), nullable=True)

    scenario_version: Mapped["CorrelationShockScenarioVersion"] = relationship(
        "CorrelationShockScenarioVersion", back_populates="pair_rules"
    )

    __table_args__ = (
        Index("ix_m10_05_pair_unique", "scenario_version_id", "entity_a_id", "entity_b_id", unique=True),
    )


# ---------------------------------------------------------
# Table 5: CorrelationShockExecution
# ---------------------------------------------------------
class CorrelationShockExecution(Base):
    """
    Reproducible execution run of a correlation shock scenario.
    """
    __tablename__ = "correlation_shock_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    execution_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    scenario_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("correlation_shock_scenario_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    portfolio_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    baseline_matrix_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    stressed_matrix_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    repaired_matrix_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # Inlined matrices for high-fidelity audit & instant retrieval
    baseline_matrix_data: Mapped[Optional[List[List[float]]]] = mapped_column(JSON, nullable=True)
    stressed_matrix_data: Mapped[Optional[List[List[float]]]] = mapped_column(JSON, nullable=True)
    repaired_matrix_data: Mapped[Optional[List[List[float]]]] = mapped_column(JSON, nullable=True)
    matrix_asset_ids: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    matrix_asset_symbols: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    execution_status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus, native_enum=False), default=ExecutionStatus.PENDING, nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    executed_by: Mapped[Optional[str]] = mapped_column(String(64), default="system", nullable=True)

    diagnostics: Mapped[List["CorrelationShockMatrixDiagnostic"]] = relationship(
        "CorrelationShockMatrixDiagnostic", back_populates="execution", cascade="all, delete-orphan"
    )
    repairs: Mapped[List["CorrelationShockRepair"]] = relationship(
        "CorrelationShockRepair", back_populates="execution", cascade="all, delete-orphan"
    )
    risk_results: Mapped[List["CorrelationShockRiskResult"]] = relationship(
        "CorrelationShockRiskResult", back_populates="execution", cascade="all, delete-orphan"
    )
    risk_contributions: Mapped[List["CorrelationShockRiskContribution"]] = relationship(
        "CorrelationShockRiskContribution", back_populates="execution", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[List["CorrelationShockAuditLog"]] = relationship(
        "CorrelationShockAuditLog", back_populates="execution", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------
# Table 6: CorrelationShockMatrixDiagnostic
# ---------------------------------------------------------
class CorrelationShockMatrixDiagnostic(Base):
    """
    Mathematical validity diagnostics of matrix at specific stages (BASELINE, RAW_STRESSED, REPAIRED).
    """
    __tablename__ = "correlation_shock_matrix_diagnostics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    execution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("correlation_shock_executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    matrix_stage: Mapped[str] = mapped_column(String(32), nullable=False)  # BASELINE, RAW_STRESSED, REPAIRED
    is_symmetric: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    diagonal_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    bounds_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_psd: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    minimum_eigenvalue: Mapped[float] = mapped_column(Numeric(14, 8), nullable=False)
    maximum_eigenvalue: Mapped[float] = mapped_column(Numeric(14, 8), nullable=False)
    matrix_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    condition_number: Mapped[Optional[float]] = mapped_column(Numeric(16, 4), nullable=True)
    negative_eigenvalue_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    diagnostics_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    execution: Mapped["CorrelationShockExecution"] = relationship(
        "CorrelationShockExecution", back_populates="diagnostics"
    )


# ---------------------------------------------------------
# Table 7: CorrelationShockRepair
# ---------------------------------------------------------
class CorrelationShockRepair(Base):
    """
    Audit record of matrix repair transformations.
    """
    __tablename__ = "correlation_shock_repairs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    execution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("correlation_shock_executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    repair_method: Mapped[str] = mapped_column(String(50), nullable=False)
    repair_parameters: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    pre_repair_status: Mapped[str] = mapped_column(String(32), nullable=False)
    post_repair_status: Mapped[str] = mapped_column(String(32), nullable=False)
    maximum_adjustment: Mapped[float] = mapped_column(Numeric(10, 6), default=0.0, nullable=False)
    frobenius_adjustment: Mapped[float] = mapped_column(Numeric(12, 6), default=0.0, nullable=False)
    convergence_status: Mapped[str] = mapped_column(String(32), default="CONVERGED", nullable=False)
    iterations: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    execution: Mapped["CorrelationShockExecution"] = relationship(
        "CorrelationShockExecution", back_populates="repairs"
    )


# ---------------------------------------------------------
# Table 8: CorrelationShockRiskResult
# ---------------------------------------------------------
class CorrelationShockRiskResult(Base):
    """
    Persisted portfolio risk metrics before and after correlation shock.
    """
    __tablename__ = "correlation_shock_risk_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    execution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("correlation_shock_executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)  # VOLATILITY, VARIANCE, DIVERSIFICATION_BENEFIT, etc.
    baseline_value: Mapped[Optional[float]] = mapped_column(Numeric(16, 8), nullable=True)
    stressed_value: Mapped[Optional[float]] = mapped_column(Numeric(16, 8), nullable=True)
    absolute_change: Mapped[Optional[float]] = mapped_column(Numeric(16, 8), nullable=True)
    percentage_change: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    unit: Mapped[str] = mapped_column(String(20), default="PERCENT", nullable=False)
    calculation_method: Mapped[str] = mapped_column(String(64), default="EULER_ANALYTIC", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    execution: Mapped["CorrelationShockExecution"] = relationship(
        "CorrelationShockExecution", back_populates="risk_results"
    )


# ---------------------------------------------------------
# Table 9: CorrelationShockRiskContribution
# ---------------------------------------------------------
class CorrelationShockRiskContribution(Base):
    """
    Holding-level risk contributions under baseline vs. stressed correlations.
    """
    __tablename__ = "correlation_shock_risk_contributions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    execution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("correlation_shock_executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(32), default="INSTRUMENT", nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    weight: Mapped[float] = mapped_column(Numeric(10, 6), default=0.0, nullable=False)
    baseline_contribution: Mapped[Optional[float]] = mapped_column(Numeric(14, 8), nullable=True)
    stressed_contribution: Mapped[Optional[float]] = mapped_column(Numeric(14, 8), nullable=True)
    absolute_change: Mapped[Optional[float]] = mapped_column(Numeric(14, 8), nullable=True)
    percentage_change: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    baseline_contribution_share: Mapped[Optional[float]] = mapped_column(Numeric(8, 4), nullable=True)
    stressed_contribution_share: Mapped[Optional[float]] = mapped_column(Numeric(8, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    execution: Mapped["CorrelationShockExecution"] = relationship(
        "CorrelationShockExecution", back_populates="risk_contributions"
    )


# ---------------------------------------------------------
# Table 10: CorrelationShockAuditLog
# ---------------------------------------------------------
class CorrelationShockAuditLog(Base):
    """
    Audit log tracking scenario changes, executions, and repairs.
    """
    __tablename__ = "correlation_shock_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    execution_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("correlation_shock_executions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(String(64), default="system", nullable=True)
    event_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    execution: Mapped[Optional["CorrelationShockExecution"]] = relationship(
        "CorrelationShockExecution", back_populates="audit_logs"
    )
