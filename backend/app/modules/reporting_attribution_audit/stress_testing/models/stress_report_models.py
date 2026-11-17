"""
M14.04 Stress Testing Reports ORM Models.
Durable, auditable storage for stress testing reports documenting scenario assumptions,
stressed portfolio & position P&L, sensitivity analyses, limit implications, and cryptographic artifacts.
"""
import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    String,
    Numeric,
    DateTime,
    Date,
    Boolean,
    Integer,
    ForeignKey,
    JSON,
    Enum as SQLEnum,
    Index,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class StressScenarioType(str, Enum):
    HISTORICAL = "HISTORICAL"
    HYPOTHETICAL = "HYPOTHETICAL"
    MARKET_CRASH = "MARKET_CRASH"
    SECTOR_SHOCK = "SECTOR_SHOCK"
    CORRELATION_SHOCK = "CORRELATION_SHOCK"
    LIQUIDITY_STRESS = "LIQUIDITY_STRESS"
    MONTE_CARLO = "MONTE_CARLO"
    COMBINED = "COMBINED"


class StressReportStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class StressReconciliationStatus(str, Enum):
    RECONCILED = "RECONCILED"
    RECONCILED_WITH_ROUNDING = "RECONCILED_WITH_ROUNDING"
    PARTIALLY_RECONCILED = "PARTIALLY_RECONCILED"
    UNRECONCILED = "UNRECONCILED"
    NOT_EVALUABLE = "NOT_EVALUABLE"


class LimitEvaluationStatus(str, Enum):
    WITHIN_LIMIT = "WITHIN_LIMIT"
    APPROACHING_LIMIT = "APPROACHING_LIMIT"
    PROJECTED_STRESS_EXCEEDANCE = "PROJECTED_STRESS_EXCEEDANCE"
    NOT_EVALUABLE = "NOT_EVALUABLE"
    UNSUPPORTED = "UNSUPPORTED"


class StressArtifactType(str, Enum):
    PDF = "PDF"
    HTML = "HTML"
    CSV = "CSV"
    JSON_MANIFEST = "JSON_MANIFEST"


class StressReport(Base):
    """
    Main entity representing a stress testing report run.
    """
    __tablename__ = "m14_stress_reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    report_name: Mapped[str] = mapped_column(String(128), nullable=False)
    report_status: Mapped[StressReportStatus] = mapped_column(SQLEnum(StressReportStatus), nullable=False, default=StressReportStatus.COMPLETED)
    report_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reporting_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    valuation_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reporting_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    # Summary Metrics across selected scenarios
    baseline_portfolio_nav: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    worst_stressed_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    worst_stressed_loss: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    worst_stress_impact_percentage: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    projected_exceedances_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # Status & Tolerances
    reconciliation_status: Mapped[StressReconciliationStatus] = mapped_column(SQLEnum(StressReconciliationStatus), nullable=False, default=StressReconciliationStatus.RECONCILED)
    reconciliation_residual: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    
    # Metadata & Manifests
    report_configuration: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    provenance_manifest: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    caveats_manifest: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    template_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    generator_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1.0")
    
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="SYSTEM")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    scenarios: Mapped[List["StressReportScenario"]] = relationship("StressReportScenario", back_populates="report", cascade="all, delete-orphan")
    position_results: Mapped[List["StressReportPositionResult"]] = relationship("StressReportPositionResult", back_populates="report", cascade="all, delete-orphan")
    sensitivities: Mapped[List["StressReportSensitivity"]] = relationship("StressReportSensitivity", back_populates="report", cascade="all, delete-orphan")
    limit_results: Mapped[List["StressReportLimitResult"]] = relationship("StressReportLimitResult", back_populates="report", cascade="all, delete-orphan")
    reconciliations: Mapped[List["StressReportReconciliation"]] = relationship("StressReportReconciliation", back_populates="report", cascade="all, delete-orphan")
    artifacts: Mapped[List["StressReportArtifact"]] = relationship("StressReportArtifact", back_populates="report", cascade="all, delete-orphan")


class StressReportScenario(Base):
    """
    Scenarios included in the report with assumptions and aggregated stressed financial outcomes.
    """
    __tablename__ = "m14_stress_report_scenarios"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id: Mapped[str] = mapped_column(String(64), ForeignKey("m14_stress_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    scenario_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scenario_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scenario_name: Mapped[str] = mapped_column(String(128), nullable=False)
    scenario_type: Mapped[StressScenarioType] = mapped_column(SQLEnum(StressScenarioType), nullable=False)
    scenario_horizon: Mapped[str] = mapped_column(String(32), nullable=False, default="10_DAYS")
    scenario_description: Mapped[str] = mapped_column(Text, nullable=False)
    scenario_execution_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Financial Impact
    baseline_portfolio_nav: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    stressed_portfolio_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    stressed_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    stressed_loss: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    stress_impact_percentage: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    
    # Assumptions & Shocks Documentation
    shock_magnitude_summary: Mapped[str] = mapped_column(String(256), nullable=False)
    shocks_breakdown: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    affected_groups: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    methodology: Mapped[str] = mapped_column(String(64), nullable=False, default="HISTORICAL_REPLAY")
    assumption_limitations: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    comparison_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    report: Mapped[StressReport] = relationship("StressReport", back_populates="scenarios")


class StressReportPositionResult(Base):
    """
    Position-level stressed P&L breakdown by security, sector, and industry.
    """
    __tablename__ = "m14_stress_report_positions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id: Mapped[str] = mapped_column(String(64), ForeignKey("m14_stress_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    scenario_id: Mapped[str] = mapped_column(String(64), nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    instrument_name: Mapped[str] = mapped_column(String(128), nullable=False)
    sector: Mapped[str] = mapped_column(String(64), nullable=False, default="UNCLASSIFIED")
    industry: Mapped[str] = mapped_column(String(64), nullable=False, default="UNCLASSIFIED")
    position_side: Mapped[str] = mapped_column(String(8), nullable=False)  # LONG, SHORT
    position_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    baseline_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    stressed_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    baseline_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    stressed_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    stressed_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    stressed_loss: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    impact_percentage: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    applied_shock: Mapped[str] = mapped_column(String(64), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(128), nullable=False, default="M10")

    report: Mapped[StressReport] = relationship("StressReport", back_populates="position_results")


class StressReportSensitivity(Base):
    """
    Sensitivity comparison across alternative scenario shock magnitudes and assumptions.
    """
    __tablename__ = "m14_stress_report_sensitivities"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id: Mapped[str] = mapped_column(String(64), ForeignKey("m14_stress_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    sensitivity_dimension: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g., MARKET_SHOCK, VOLATILITY, LIQUIDITY
    assumption_name: Mapped[str] = mapped_column(String(64), nullable=False)
    assumption_value: Mapped[str] = mapped_column(String(64), nullable=False)
    assumption_unit: Mapped[str] = mapped_column(String(32), nullable=False, default="PERCENTAGE")
    stressed_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    stressed_loss: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    impact_percentage: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    incremental_loss: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    source_sensitivity_reference: Mapped[str] = mapped_column(String(128), nullable=False, default="M10.02")

    report: Mapped[StressReport] = relationship("StressReport", back_populates="sensitivities")


class StressReportLimitResult(Base):
    """
    Stressed risk-limit utilization and projected exceedances derived from M11 policies.
    """
    __tablename__ = "m14_stress_report_limits"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id: Mapped[str] = mapped_column(String(64), ForeignKey("m14_stress_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    scenario_id: Mapped[str] = mapped_column(String(64), nullable=False)
    limit_id: Mapped[str] = mapped_column(String(64), nullable=False)
    limit_name: Mapped[str] = mapped_column(String(128), nullable=False)
    limit_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="PORTFOLIO")
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    limit_policy_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1.0")
    configured_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    stressed_metric: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    utilization_percentage: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    evaluation_status: Mapped[LimitEvaluationStatus] = mapped_column(SQLEnum(LimitEvaluationStatus), nullable=False)
    difference_from_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    is_projected_exceedance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    evaluation_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    report: Mapped[StressReport] = relationship("StressReport", back_populates="limit_results")


class StressReportReconciliation(Base):
    """
    Reconciliation between authoritative M10 scenario outputs and position-level aggregates.
    """
    __tablename__ = "m14_stress_report_reconciliations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id: Mapped[str] = mapped_column(String(64), ForeignKey("m14_stress_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    scenario_id: Mapped[str] = mapped_column(String(64), nullable=False)
    authoritative_total_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reported_total_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    position_level_pnl_sum: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    other_components_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    residual: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    tolerance: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=Decimal("0.01"))
    reconciliation_status: Mapped[StressReconciliationStatus] = mapped_column(SQLEnum(StressReconciliationStatus), nullable=False)
    exception_details: Mapped[str] = mapped_column(Text, nullable=False, default="")

    report: Mapped[StressReport] = relationship("StressReport", back_populates="reconciliations")


class StressReportArtifact(Base):
    """
    Durable rendered export artifacts (PDF, HTML, CSV) with cryptographic verification.
    """
    __tablename__ = "m14_stress_report_artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id: Mapped[str] = mapped_column(String(64), ForeignKey("m14_stress_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    report_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    artifact_type: Mapped[StressArtifactType] = mapped_column(SQLEnum(StressArtifactType), nullable=False)
    storage_reference: Mapped[str] = mapped_column(String(256), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    report: Mapped[StressReport] = relationship("StressReport", back_populates="artifacts")


class StressReportVersion(Base):
    """
    Immutable version lineage tracking for regenerated stress testing reports.
    """
    __tablename__ = "m14_stress_report_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reporting_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    report_id: Mapped[str] = mapped_column(String(64), ForeignKey("m14_stress_reports.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_report_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    version_reason: Mapped[str] = mapped_column(String(256), nullable=False, default="Initial generation")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="SYSTEM")

    __table_args__ = (
        Index("ix_m14_stress_ver_port_date_ver", "portfolio_id", "reporting_date", "version_number", unique=True),
    )
