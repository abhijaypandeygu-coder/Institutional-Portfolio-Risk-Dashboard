"""M14.05 Liquidity Reports database models.

Follows SQLAlchemy 2.x conventions.
Implements:
- LiquidityReport
- LiquidityReportSnapshot
- LiquidityReportPosition
- LiquidityReportLiquidation
- LiquidityReportConcentration
- LiquidityReportStress
- LiquidityReportLimit
- LiquidityReportReconciliation
- LiquidityReportArtifact
- LiquidityReportAuditEvent
- LiquidityReportVersion
"""

import enum
from datetime import datetime, timezone
import uuid

from sqlalchemy import (
    String,
    Numeric,
    Integer,
    DateTime,
    ForeignKey,
    JSON,
    Enum as SQLEnum,
    Index,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class LiquidityReportStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    GENERATING = "GENERATING"
    GENERATED = "GENERATED"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"


class LiquidityQualityStatus(str, enum.Enum):
    VALID = "VALID"
    STALE = "STALE"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    INVALID = "INVALID"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    FAILED = "FAILED"


class LiquidityReconciliationStatus(str, enum.Enum):
    RECONCILED = "RECONCILED"
    RECONCILED_WITH_ROUNDING = "RECONCILED_WITH_ROUNDING"
    PARTIALLY_RECONCILED = "PARTIALLY_RECONCILED"
    UNRECONCILED = "UNRECONCILED"
    NOT_EVALUABLE = "NOT_EVALUABLE"


class LiquidityLimitEvaluationStatus(str, enum.Enum):
    WITHIN_LIMIT = "WITHIN_LIMIT"
    APPROACHING_LIMIT = "APPROACHING_LIMIT"
    PROJECTED_STRESS_EXCEEDANCE = "PROJECTED_STRESS_EXCEEDANCE"
    ACTUAL_LIMIT_BREACH = "ACTUAL_LIMIT_BREACH"
    NOT_EVALUABLE = "NOT_EVALUABLE"
    UNSUPPORTED = "UNSUPPORTED"
    STALE_INPUTS = "STALE_INPUTS"


class LiquidityArtifactType(str, enum.Enum):
    PDF = "PDF"
    HTML = "HTML"
    CSV = "CSV"
    JSON_MANIFEST = "JSON_MANIFEST"


class LiquidityReport(Base):
    """Authoritative M14.05 Liquidity Report instance."""

    __tablename__ = "m14_liquidity_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    portfolio_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    report_name: Mapped[str] = mapped_column(String(255), nullable=False)
    report_status: Mapped[LiquidityReportStatus] = mapped_column(
        SQLEnum(LiquidityReportStatus), default=LiquidityReportStatus.DRAFT, nullable=False, index=True
    )
    report_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    as_of_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    report_configuration: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    coverage_status: Mapped[str] = mapped_column(String(32), default="FULL", nullable=False)
    reconciliation_status: Mapped[LiquidityReconciliationStatus] = mapped_column(
        SQLEnum(LiquidityReconciliationStatus), default=LiquidityReconciliationStatus.NOT_EVALUABLE, nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    template_version: Mapped[str] = mapped_column(String(32), default="v1.0.0", nullable=False)
    generator_version: Mapped[str] = mapped_column(String(32), default="v1.0.0", nullable=False)

    # Relationships
    snapshots: Mapped[list["LiquidityReportSnapshot"]] = relationship(
        "LiquidityReportSnapshot", back_populates="report", cascade="all, delete-orphan"
    )
    positions: Mapped[list["LiquidityReportPosition"]] = relationship(
        "LiquidityReportPosition", back_populates="report", cascade="all, delete-orphan"
    )
    liquidations: Mapped[list["LiquidityReportLiquidation"]] = relationship(
        "LiquidityReportLiquidation", back_populates="report", cascade="all, delete-orphan"
    )
    concentrations: Mapped[list["LiquidityReportConcentration"]] = relationship(
        "LiquidityReportConcentration", back_populates="report", cascade="all, delete-orphan"
    )
    stress_comparisons: Mapped[list["LiquidityReportStress"]] = relationship(
        "LiquidityReportStress", back_populates="report", cascade="all, delete-orphan"
    )
    limits: Mapped[list["LiquidityReportLimit"]] = relationship(
        "LiquidityReportLimit", back_populates="report", cascade="all, delete-orphan"
    )
    reconciliations: Mapped[list["LiquidityReportReconciliation"]] = relationship(
        "LiquidityReportReconciliation", back_populates="report", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list["LiquidityReportArtifact"]] = relationship(
        "LiquidityReportArtifact", back_populates="report", cascade="all, delete-orphan"
    )
    audit_events: Mapped[list["LiquidityReportAuditEvent"]] = relationship(
        "LiquidityReportAuditEvent", back_populates="report", cascade="all, delete-orphan"
    )
    versions: Mapped[list["LiquidityReportVersion"]] = relationship(
        "LiquidityReportVersion", back_populates="report", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_m14_liq_rep_port_date", "portfolio_id", "as_of_timestamp"),
    )


class LiquidityReportSnapshot(Base):
    """Snapshot and data provenance references for Liquidity Report."""

    __tablename__ = "m14_liquidity_report_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m14_liquidity_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    portfolio_snapshot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    market_data_snapshot_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    order_book_snapshot_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    liquidity_calculation_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_quality_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_version_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    report: Mapped["LiquidityReport"] = relationship("LiquidityReport", back_populates="snapshots")


class LiquidityReportPosition(Base):
    """Position-level market liquidity profile metrics."""

    __tablename__ = "m14_liquidity_report_positions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m14_liquidity_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    instrument_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    listing_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    position_snapshot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    exchange: Mapped[str] = mapped_column(String(32), default="NSE", nullable=False)
    sector: Mapped[str | None] = mapped_column(String(64), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(64), nullable=True)
    position_quantity: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    position_market_value: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    spread: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    relative_spread: Mapped[float | None] = mapped_column(Numeric(14, 6), nullable=True)
    spread_bps: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    bid_depth: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    ask_depth: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    traded_volume: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    average_daily_volume: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    turnover: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    liquidity_score: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    liquidity_classification: Mapped[str] = mapped_column(String(32), default="MODERATE", nullable=False)
    liquidity_quality_status: Mapped[LiquidityQualityStatus] = mapped_column(
        SQLEnum(LiquidityQualityStatus), default=LiquidityQualityStatus.VALID, nullable=False
    )
    source_result_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)

    report: Mapped["LiquidityReport"] = relationship("LiquidityReport", back_populates="positions")

    __table_args__ = (
        Index("idx_m14_liq_rep_pos_inst", "report_id", "instrument_id"),
    )


class LiquidityReportLiquidation(Base):
    """Estimated liquidation time, cost, and schedule components."""

    __tablename__ = "m14_liquidity_report_liquidations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m14_liquidity_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    instrument_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    liquidation_direction: Mapped[str] = mapped_column(String(16), default="SELL", nullable=False)  # SELL (for long) or BUY (for short cover)
    target_quantity: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    target_fraction: Mapped[float] = mapped_column(Numeric(8, 4), default=1.0, nullable=False)
    participation_rate: Mapped[float] = mapped_column(Numeric(8, 4), default=0.10, nullable=False)
    estimated_executable_volume: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    estimated_duration_days: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    estimated_duration_sessions: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    estimated_completion_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    estimated_spread_cost: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0, nullable=False)
    estimated_market_impact: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0, nullable=False)
    estimated_slippage: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0, nullable=False)
    estimated_fees: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0, nullable=False)
    estimated_total_cost: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0, nullable=False)
    estimated_cost_bps: Mapped[float] = mapped_column(Numeric(14, 4), default=0.0, nullable=False)
    cost_currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    estimation_scope: Mapped[str] = mapped_column(String(32), default="INDEPENDENT", nullable=False)  # INDEPENDENT vs SHARED_CAPACITY
    methodology_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    quality_status: Mapped[LiquidityQualityStatus] = mapped_column(
        SQLEnum(LiquidityQualityStatus), default=LiquidityQualityStatus.VALID, nullable=False
    )

    report: Mapped["LiquidityReport"] = relationship("LiquidityReport", back_populates="liquidations")


class LiquidityReportConcentration(Base):
    """Illiquidity concentration by position, sector, and industry."""

    __tablename__ = "m14_liquidity_report_concentrations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m14_liquidity_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    grouping_type: Mapped[str] = mapped_column(String(32), nullable=False)  # POSITION, SECTOR, INDUSTRY, LIQUIDITY_TIER
    grouping_reference: Mapped[str] = mapped_column(String(64), nullable=False)
    position_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    aggregate_position_value: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0, nullable=False)
    estimated_liquidation_cost: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0, nullable=False)
    cost_contribution_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    liquidity_coverage: Mapped[float] = mapped_column(Numeric(8, 4), default=1.0, nullable=False)
    methodology_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)

    report: Mapped["LiquidityReport"] = relationship("LiquidityReport", back_populates="concentrations")


class LiquidityReportStress(Base):
    """Current vs Stressed liquidity conditions across scenarios."""

    __tablename__ = "m14_liquidity_report_stress_comparisons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m14_liquidity_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scenario_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scenario_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scenario_name: Mapped[str] = mapped_column(String(128), nullable=False)
    scenario_version: Mapped[str] = mapped_column(String(32), default="v1", nullable=False)
    scenario_horizon: Mapped[str] = mapped_column(String(32), default="10D", nullable=False)
    baseline_snapshot_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    baseline_spread_bps: Mapped[float] = mapped_column(Numeric(14, 4), default=0.0, nullable=False)
    stressed_spread_bps: Mapped[float] = mapped_column(Numeric(14, 4), default=0.0, nullable=False)
    spread_widening_pct: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0, nullable=False)
    baseline_depth: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0, nullable=False)
    stressed_depth: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0, nullable=False)
    depth_reduction_pct: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0, nullable=False)
    baseline_volume: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0, nullable=False)
    stressed_volume: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0, nullable=False)
    volume_contraction_pct: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0, nullable=False)
    baseline_liquidity_score: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0, nullable=False)
    stressed_liquidity_score: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0, nullable=False)
    baseline_liquidation_time_days: Mapped[float] = mapped_column(Numeric(10, 4), default=0.0, nullable=False)
    stressed_liquidation_time_days: Mapped[float] = mapped_column(Numeric(10, 4), default=0.0, nullable=False)
    baseline_liquidation_cost: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0, nullable=False)
    stressed_liquidation_cost: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0, nullable=False)
    incremental_liquidation_cost: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0, nullable=False)
    comparison_status: Mapped[str] = mapped_column(String(32), default="COMPLETED", nullable=False)

    report: Mapped["LiquidityReport"] = relationship("LiquidityReport", back_populates="stress_comparisons")


class LiquidityReportLimit(Base):
    """M11 Liquidity risk limit utilization and projected exceedances."""

    __tablename__ = "m14_liquidity_report_limits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m14_liquidity_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scenario_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    limit_id: Mapped[str] = mapped_column(String(64), nullable=False)
    limit_code: Mapped[str] = mapped_column(String(64), nullable=False)
    limit_name: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(32), default="v1", nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), default="PORTFOLIO", nullable=False)  # PORTFOLIO or INSTRUMENT
    target_reference: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    configured_threshold: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    threshold_unit: Mapped[str] = mapped_column(String(16), default="BPS", nullable=False)
    current_metric: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    stressed_metric: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    utilization_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    evaluation_status: Mapped[LiquidityLimitEvaluationStatus] = mapped_column(
        SQLEnum(LiquidityLimitEvaluationStatus), default=LiquidityLimitEvaluationStatus.WITHIN_LIMIT, nullable=False
    )
    evaluation_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    evaluation_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    report: Mapped["LiquidityReport"] = relationship("LiquidityReport", back_populates="limits")


class LiquidityReportReconciliation(Base):
    """Reconciliation validation records between report aggregates and upstream sources."""

    __tablename__ = "m14_liquidity_report_reconciliations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m14_liquidity_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    source_value: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    report_value: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    difference: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0, nullable=False)
    tolerance: Mapped[float] = mapped_column(Numeric(18, 4), default=0.01, nullable=False)
    coverage_status: Mapped[str] = mapped_column(String(32), default="FULL", nullable=False)
    reconciliation_status: Mapped[LiquidityReconciliationStatus] = mapped_column(
        SQLEnum(LiquidityReconciliationStatus), default=LiquidityReconciliationStatus.RECONCILED, nullable=False
    )
    exception_details: Mapped[str | None] = mapped_column(Text, nullable=True)

    report: Mapped["LiquidityReport"] = relationship("LiquidityReport", back_populates="reconciliations")


class LiquidityReportArtifact(Base):
    """Generated document artifacts (PDF, HTML, CSV) with cryptographic verification."""

    __tablename__ = "m14_liquidity_report_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m14_liquidity_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    report_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    artifact_type: Mapped[LiquidityArtifactType] = mapped_column(
        SQLEnum(LiquidityArtifactType), default=LiquidityArtifactType.PDF, nullable=False
    )
    storage_reference: Mapped[str] = mapped_column(String(512), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    artifact_status: Mapped[str] = mapped_column(String(32), default="AVAILABLE", nullable=False)

    report: Mapped["LiquidityReport"] = relationship("LiquidityReport", back_populates="artifacts")


class LiquidityReportAuditEvent(Base):
    """Audit events recording report lifecycle and access."""

    __tablename__ = "m14_liquidity_report_audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m14_liquidity_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)  # CONFIGURED, GENERATED, REGENERATED, EXPORTED, ARCHIVED
    actor_id: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)
    event_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    event_details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    report: Mapped["LiquidityReport"] = relationship("LiquidityReport", back_populates="audit_events")


class LiquidityReportVersion(Base):
    """Immutable version lineages for regenerated liquidity reports."""

    __tablename__ = "m14_liquidity_report_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("m14_liquidity_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    summary_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    regeneration_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)

    report: Mapped["LiquidityReport"] = relationship("LiquidityReport", back_populates="versions")
