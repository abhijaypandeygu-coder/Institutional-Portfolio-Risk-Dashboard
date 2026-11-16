"""
SQLAlchemy ORM models for M10.08 Scenario Comparison.
Strictly conforms to SQLAlchemy 2.0 type conventions using Mapped[Optional[T]].
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List
import uuid

from sqlalchemy import (
    String,
    Integer,
    Numeric,
    DateTime,
    Boolean,
    ForeignKey,
    Text,
    JSON,
    Float,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class ScenarioComparison(Base):
    """
    Scenario comparison entity defining identity, baseline, portfolio, and versioned configuration.
    """
    __tablename__ = "m10_scenario_comparisons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    comparison_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    baseline_snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    base_currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    comparison_status: Mapped[str] = mapped_column(String(32), default="DRAFT", nullable=False) # DRAFT, READY, RUNNING, COMPLETED, FAILED
    configuration_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    ranking_metric: Mapped[str] = mapped_column(String(64), default="loss_amount", nullable=False)
    ranking_direction: Mapped[str] = mapped_column(String(16), default="DESCENDING", nullable=False) # DESCENDING, ASCENDING
    normalization_method: Mapped[str] = mapped_column(String(32), default="MIN_MAX", nullable=False)
    weights_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    members: Mapped[List["ScenarioComparisonMember"]] = relationship(
        "ScenarioComparisonMember", back_populates="comparison", cascade="all, delete-orphan"
    )
    runs: Mapped[List["ScenarioComparisonRun"]] = relationship(
        "ScenarioComparisonRun", back_populates="comparison", cascade="all, delete-orphan"
    )


class ScenarioComparisonMember(Base):
    """
    Scenarios included in a comparison set.
    Prevents duplicate inclusion of the same scenario run within a comparison.
    """
    __tablename__ = "m10_scenario_comparison_members"
    __table_args__ = (
        UniqueConstraint("comparison_id", "scenario_run_id", name="uq_comparison_scenario_run"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    comparison_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m10_scenario_comparisons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scenario_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scenario_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scenario_type: Mapped[str] = mapped_column(String(64), nullable=False) # HISTORICAL, HYPOTHETICAL, MARKET_CRASH, SECTOR_SHOCK, CORRELATION_SHOCK, LIQUIDITY_STRESS, MONTE_CARLO
    scenario_name: Mapped[str] = mapped_column(String(128), nullable=False)
    scenario_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    scenario_configuration_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    inclusion_status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    comparison: Mapped["ScenarioComparison"] = relationship("ScenarioComparison", back_populates="members")


class ScenarioComparisonRun(Base):
    """
    Immutable comparison execution record with lineage, input manifest, and status.
    """
    __tablename__ = "m10_scenario_comparison_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    comparison_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m10_scenario_comparisons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    configuration_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    baseline_snapshot_id: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_status: Mapped[str] = mapped_column(String(32), default="COMPLETED", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    application_version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    calculation_engine_version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    input_manifest: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    validation_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    comparison: Mapped["ScenarioComparison"] = relationship("ScenarioComparison", back_populates="runs")
    metric_results: Mapped[List["ScenarioComparisonMetricResult"]] = relationship(
        "ScenarioComparisonMetricResult", back_populates="run", cascade="all, delete-orphan"
    )
    rankings: Mapped[List["ScenarioComparisonRanking"]] = relationship(
        "ScenarioComparisonRanking", back_populates="run", cascade="all, delete-orphan"
    )
    sensitivities: Mapped[List["ScenarioComparisonSensitivity"]] = relationship(
        "ScenarioComparisonSensitivity", back_populates="run", cascade="all, delete-orphan"
    )
    attributions: Mapped[List["ScenarioComparisonAttribution"]] = relationship(
        "ScenarioComparisonAttribution", back_populates="run", cascade="all, delete-orphan"
    )
    audit_events: Mapped[List["ScenarioComparisonAuditLog"]] = relationship(
        "ScenarioComparisonAuditLog", back_populates="run", cascade="all, delete-orphan"
    )


class ScenarioComparisonMetricResult(Base):
    """
    Scenario financial and risk metric comparison results against baseline.
    """
    __tablename__ = "m10_scenario_comparison_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    comparison_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m10_scenario_comparison_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scenario_run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scenario_name: Mapped[str] = mapped_column(String(128), nullable=False)
    scenario_type: Mapped[str] = mapped_column(String(64), nullable=False)
    baseline_nav: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    scenario_nav: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    return_pct: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    loss_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    loss_pct: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    var_95_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    cvar_95_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    max_drawdown_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    liquidity_cost_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    quality_status: Mapped[str] = mapped_column(String(32), default="AVAILABLE", nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    run: Mapped["ScenarioComparisonRun"] = relationship("ScenarioComparisonRun", back_populates="metric_results")


class ScenarioComparisonRanking(Base):
    """
    Rankings assigned to scenarios for a comparison run.
    """
    __tablename__ = "m10_scenario_comparison_rankings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    comparison_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m10_scenario_comparison_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scenario_run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scenario_name: Mapped[str] = mapped_column(String(128), nullable=False)
    ranking_metric: Mapped[str] = mapped_column(String(64), nullable=False)
    ranking_direction: Mapped[str] = mapped_column(String(16), nullable=False)
    rank_position: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_metric_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    normalized_score: Mapped[float] = mapped_column(Float, nullable=False)
    composite_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tie_group: Mapped[int] = mapped_column(Integer, nullable=False)
    eligibility_status: Mapped[str] = mapped_column(String(32), default="ELIGIBLE", nullable=False)
    exclusion_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    run: Mapped["ScenarioComparisonRun"] = relationship("ScenarioComparisonRun", back_populates="rankings")


class ScenarioComparisonSensitivity(Base):
    """
    Parameter-level sensitivity comparisons across scenarios.
    """
    __tablename__ = "m10_scenario_comparison_sensitivities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    comparison_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m10_scenario_comparison_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parameter_code: Mapped[str] = mapped_column(String(64), nullable=False)
    parameter_name: Mapped[str] = mapped_column(String(128), nullable=False)
    scenario_a_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scenario_b_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scenario_a_value: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    scenario_b_value: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    absolute_difference: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    relative_difference: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sensitivity_method: Mapped[str] = mapped_column(String(32), default="CONFIGURATION_DIFF", nullable=False)
    is_material: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    run: Mapped["ScenarioComparisonRun"] = relationship("ScenarioComparisonRun", back_populates="sensitivities")


class ScenarioComparisonAttribution(Base):
    """
    Attribution of outcome differences between paired scenarios.
    """
    __tablename__ = "m10_scenario_comparison_attributions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    comparison_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m10_scenario_comparison_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scenario_a_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scenario_b_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    attribution_dimension: Mapped[str] = mapped_column(String(64), default="INSTRUMENT", nullable=False) # INSTRUMENT, SECTOR, LIQUIDITY
    component_reference: Mapped[str] = mapped_column(String(64), nullable=False)
    scenario_a_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    scenario_b_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    difference_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reconciliation_residual: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)

    # Relationships
    run: Mapped["ScenarioComparisonRun"] = relationship("ScenarioComparisonRun", back_populates="attributions")


class ScenarioComparisonAuditLog(Base):
    """
    Audit log of actions, configuration revisions, and execution runs.
    """
    __tablename__ = "m10_scenario_comparison_audit"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    comparison_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    comparison_run_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("m10_scenario_comparison_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), default="system", nullable=False)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    run: Mapped[Optional["ScenarioComparisonRun"]] = relationship("ScenarioComparisonRun", back_populates="audit_events")

