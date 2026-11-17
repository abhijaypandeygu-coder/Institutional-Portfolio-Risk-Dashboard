"""
SQLAlchemy ORM models for M14.01 — Daily Risk Reports.

Entities:
1. `daily_report_configurations`: Configurable reporting definitions per portfolio.
2. `daily_report_runs`: Executed daily report runs containing generation status, control & freshness summaries.
3. `daily_report_sections`: Structured report sections (portfolio summary, risk metrics, limit breaches, manifests).
4. `daily_report_artifacts`: Immutable rendered artifacts (PDF, HTML, CSV) with cryptographic content hashes.
5. `daily_report_versions`: Version lineage mapping superseded report versions and audit notes.
6. `daily_report_generation_events`: Audit logs capturing lifecycle generation events.
"""

from datetime import datetime, timezone, date
import uuid
from typing import Optional, Dict, Any, List

from sqlalchemy import (
    String,
    Integer,
    Boolean,
    DateTime,
    Date,
    Numeric,
    JSON,
    ForeignKey,
    Index,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DailyReportConfiguration(Base):
    """
    Configuration profile governing scheduled or manual daily risk report generation.
    """
    __tablename__ = "daily_report_configurations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"DRCFG_{uuid.uuid4().hex[:12].upper()}")
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    configuration_name: Mapped[str] = mapped_column(String(128), nullable=False)
    reporting_calendar: Mapped[str] = mapped_column(String(32), default="NSE_INDIA", nullable=False) # 'NSE_INDIA', 'NYSE_US', etc.
    reporting_currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    valuation_cutoff_policy: Mapped[str] = mapped_column(String(32), default="EOD_CLOSE", nullable=False)
    report_template_version: Mapped[str] = mapped_column(String(32), default="v1.0", nullable=False)
    
    # JSON inclusion settings
    metric_inclusion_config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    freshness_policy: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    schedule_config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    
    configuration_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        Index("idx_daily_report_cfg_port", "portfolio_id"),
        Index("idx_daily_report_cfg_active", "is_active"),
    )


class DailyReportRun(Base):
    """
    Executed report run instance capturing point-in-time state, control status, and source manifests.
    """
    __tablename__ = "daily_report_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"DRRUN_{uuid.uuid4().hex[:12].upper()}")
    report_configuration_id: Mapped[str] = mapped_column(String(64), ForeignKey("daily_report_configurations.id"), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    valuation_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    
    # Statuses
    # Generation: 'QUEUED', 'RUNNING', 'VALIDATING', 'COMPLETED', 'COMPLETED_WITH_WARNINGS', 'FAILED', 'CANCELLED'
    generation_status: Mapped[str] = mapped_column(String(32), default="QUEUED", nullable=False)
    # Overall Control: 'CLEAR', 'WARNINGS_PRESENT', 'BREACHES_PRESENT', 'CRITICAL_BREACHES_PRESENT', 'EMERGENCY_BREACHES_PRESENT', 'DATA_INCOMPLETE', 'CONTROL_STATUS_UNAVAILABLE'
    overall_control_status: Mapped[str] = mapped_column(String(64), default="DATA_INCOMPLETE", nullable=False)
    # Overall Freshness: 'FRESH', 'STALE', 'DELAYED', 'PARTIAL', 'UNAVAILABLE', 'NOT_APPLICABLE'
    overall_freshness_status: Mapped[str] = mapped_column(String(32), default="FRESH", nullable=False)
    
    report_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    report_schema_version: Mapped[str] = mapped_column(String(16), default="1.0", nullable=False)
    template_version: Mapped[str] = mapped_column(String(32), default="v1.0", nullable=False)
    
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    source_manifest: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    methodology_manifest: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)

    __table_args__ = (
        Index("idx_daily_report_run_lookup", "portfolio_id", "report_date"),
        Index("idx_daily_report_run_status", "generation_status"),
    )


class DailyReportSection(Base):
    """
    Structured sections stored individually for high-fidelity retrieval and granular inspection.
    Section types: 'PORTFOLIO_SUMMARY', 'RISK_METRICS', 'LIMIT_STATUS', 'FRESHNESS', 'METHODOLOGY'
    """
    __tablename__ = "daily_report_sections"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"DRSEC_{uuid.uuid4().hex[:12].upper()}")
    report_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("daily_report_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    section_type: Mapped[str] = mapped_column(String(64), nullable=False)
    section_status: Mapped[str] = mapped_column(String(32), default="COMPLETE", nullable=False)
    structured_content: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source_references: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    validation_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("idx_daily_report_sections_lookup", "report_run_id", "section_type"),
    )


class DailyReportArtifact(Base):
    """
    Rendered file artifacts (PDF, HTML, CSV) with cryptographic content hashes.
    """
    __tablename__ = "daily_report_artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"DRART_{uuid.uuid4().hex[:12].upper()}")
    report_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("daily_report_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    artifact_type: Mapped[str] = mapped_column(String(16), nullable=False) # 'PDF', 'HTML', 'CSV'
    storage_reference: Mapped[str] = mapped_column(String(256), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False) # SHA-256
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    template_version: Mapped[str] = mapped_column(String(32), default="v1.0", nullable=False)

    __table_args__ = (
        Index("idx_daily_report_artifacts_lookup", "report_run_id", "artifact_type"),
    )


class DailyReportVersion(Base):
    """
    Lineage relationship tracking report regenerations and superseding records.
    """
    __tablename__ = "daily_report_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"DRVER_{uuid.uuid4().hex[:12].upper()}")
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    report_configuration_id: Mapped[str] = mapped_column(String(64), nullable=False)
    report_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("daily_report_runs.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_version_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    version_reason: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        Index("idx_daily_report_versions_lineage", "portfolio_id", "report_date", "version_number"),
    )


class DailyReportGenerationEvent(Base):
    """
    Audit log of operations performed against report runs.
    """
    __tablename__ = "daily_report_generation_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"DREVT_{uuid.uuid4().hex[:12].upper()}")
    report_run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    event_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("idx_daily_report_events_lookup", "report_run_id", "event_timestamp"),
    )
