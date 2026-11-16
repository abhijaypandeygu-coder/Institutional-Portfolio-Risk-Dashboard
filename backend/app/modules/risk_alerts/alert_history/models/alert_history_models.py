"""
SQLAlchemy ORM models for M12.08 — Alert History.

Tables:
1. `historical_alert_index`: Rebuildable historical search index linking to authoritative alerts.
2. `historical_alert_event_index`: Timeline event index linking to M12.06 and M11 lifecycle events.
3. `alert_recurrence_groups`: Analytical recurrence groupings by rule, category, portfolio, instrument.
4. `alert_recurrence_members`: Alert memberships in recurrence groups.
5. `alert_rule_analytics`: Historical rule trigger, interarrival, and noise score analytics.
6. `alert_export_jobs`: Controlled asynchronous export tasks (CSV, XLSX, PDF).
7. `alert_export_download_history`: Audit log of export file downloads.
8. `alert_history_integrity_issues`: Detected timeline gaps, sequencing anomalies, or orphaned references.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String,
    Numeric,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Index,
    Text,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.utcnow()


class HistoricalAlertIndex(Base):
    """
    Searchable index over historical alerts. Rebuildable from authoritative alert records.
    """
    __tablename__ = "historical_alert_index"
    __table_args__ = (
        Index("ix_hist_alert_portfolio_time", "portfolio_id", "triggered_at"),
        Index("ix_hist_alert_instrument_time", "instrument_id", "triggered_at"),
        Index("ix_hist_alert_severity_status", "severity_at_trigger", "current_or_final_status_snapshot"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_alert_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    alert_title: Mapped[str] = mapped_column(String(255), nullable=False)
    alert_category: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    alert_type: Mapped[str] = mapped_column(String(64), default="THRESHOLD")
    source_module: Mapped[str] = mapped_column(String(64), default="M12.01")
    source_rule_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source_rule_version: Mapped[int] = mapped_column(Integer, default=1)
    
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    portfolio_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    severity_at_trigger: Mapped[str] = mapped_column(String(16), index=True, nullable=False)  # WARNING, CRITICAL, EMERGENCY
    priority_at_trigger: Mapped[str] = mapped_column(String(16), default="P3_NORMAL")
    priority_score_at_trigger: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("50.00"))
    
    current_or_final_status_snapshot: Mapped[str] = mapped_column(String(32), default="OPEN", index=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    first_acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    first_assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_event_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    
    metric_value_snapshot: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    threshold_value_snapshot: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    metric_unit_snapshot: Mapped[Optional[str]] = mapped_column(String(32), default="NAV_PCT")
    
    indexed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    events: Mapped[List["HistoricalAlertEventIndex"]] = relationship(
        "HistoricalAlertEventIndex", back_populates="alert_index", cascade="all, delete-orphan", order_by="HistoricalAlertEventIndex.occurred_at"
    )
    recurrence_memberships: Mapped[List["AlertRecurrenceMember"]] = relationship(
        "AlertRecurrenceMember", back_populates="alert_index", cascade="all, delete-orphan"
    )


class HistoricalAlertEventIndex(Base):
    """
    Chronological lifecycle events for an alert. Reconstructed from M12.06, M11.08, and M12.07.
    """
    __tablename__ = "historical_alert_event_index"
    __table_args__ = (
        Index("ix_hist_event_alert_occurred", "source_alert_id", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_alert_id: Mapped[str] = mapped_column(String(64), ForeignKey("historical_alert_index.source_alert_id", ondelete="CASCADE"), index=True)
    source_event_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # TRIGGERED, ACKNOWLEDGED, ASSIGNED, INVESTIGATION_NOTE, ESCALATED, RESOLVED, CLOSED, REOPENED
    actor_type: Mapped[str] = mapped_column(String(32), default="SYSTEM")  # SYSTEM, USER, ADMIN
    actor_id: Mapped[str] = mapped_column(String(64), default="system")
    source_module: Mapped[str] = mapped_column(String(64), default="M12.06")
    
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    effective_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    event_sequence: Mapped[int] = mapped_column(Integer, default=1)
    
    event_summary: Mapped[str] = mapped_column(String(255), nullable=False)
    event_details: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    source_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    indexed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    alert_index: Mapped["HistoricalAlertIndex"] = relationship("HistoricalAlertIndex", back_populates="events")


class AlertRecurrenceGroup(Base):
    """
    Analytical grouping of repeated alert occurrences.
    """
    __tablename__ = "alert_recurrence_groups"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    grouping_key: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    source_rule_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    alert_category: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    instrument_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    
    first_occurrence_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_occurrence_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    average_interarrival_seconds: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    recurrence_window_days: Mapped[int] = mapped_column(Integer, default=30)
    
    grouping_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    members: Mapped[List["AlertRecurrenceMember"]] = relationship(
        "AlertRecurrenceMember", back_populates="group", cascade="all, delete-orphan", order_by="AlertRecurrenceMember.occurrence_timestamp"
    )


class AlertRecurrenceMember(Base):
    """
    Individual alert occurrence in a recurrence group.
    """
    __tablename__ = "alert_recurrence_members"
    __table_args__ = (
        UniqueConstraint("recurrence_group_id", "source_alert_id", name="uq_rec_group_alert"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    recurrence_group_id: Mapped[str] = mapped_column(String(64), ForeignKey("alert_recurrence_groups.id", ondelete="CASCADE"), index=True)
    source_alert_id: Mapped[str] = mapped_column(String(64), ForeignKey("historical_alert_index.source_alert_id", ondelete="CASCADE"), index=True)
    occurrence_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    membership_reason: Mapped[str] = mapped_column(String(128), default="SAME_RULE_AND_PORTFOLIO_SCOPE")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    group: Mapped["AlertRecurrenceGroup"] = relationship("AlertRecurrenceGroup", back_populates="members")
    alert_index: Mapped["HistoricalAlertIndex"] = relationship("HistoricalAlertIndex", back_populates="recurrence_memberships")


class AlertRuleAnalytics(Base):
    """
    Rule noise indicators and statistical evaluation over an observation window.
    """
    __tablename__ = "alert_rule_analytics"
    __table_args__ = (
        UniqueConstraint("source_rule_id", "rule_version", "observation_start", "observation_end", name="uq_rule_analytic_period"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_rule_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    rule_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rule_version: Mapped[int] = mapped_column(Integer, default=1)
    
    observation_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    observation_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    observation_days: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("30.00"))
    
    trigger_count: Mapped[int] = mapped_column(Integer, default=0)
    recurrence_count: Mapped[int] = mapped_column(Integer, default=0)
    affected_portfolio_count: Mapped[int] = mapped_column(Integer, default=0)
    affected_instrument_count: Mapped[int] = mapped_column(Integer, default=0)
    
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    critical_count: Mapped[int] = mapped_column(Integer, default=0)
    emergency_count: Mapped[int] = mapped_column(Integer, default=0)
    
    trigger_frequency_per_day: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0.0000"))
    average_interarrival_seconds: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    noise_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("0.00"))  # 0 to 100
    is_noisy: Mapped[bool] = mapped_column(Boolean, default=False)
    score_components_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    
    score_configuration_version: Mapped[str] = mapped_column(String(32), default="1.0")
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class AlertExportJob(Base):
    """
    Controlled asynchronous export jobs for audit and operational review.
    """
    __tablename__ = "alert_export_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    requested_by: Mapped[str] = mapped_column(String(64), nullable=False)
    export_type: Mapped[str] = mapped_column(String(32), default="HISTORICAL_ALERTS")  # HISTORICAL_ALERTS, TIMELINE, RECURRENCE, RULE_ANALYTICS
    export_format: Mapped[str] = mapped_column(String(16), default="CSV")  # CSV, XLSX, PDF
    requested_filters_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    
    export_status: Mapped[str] = mapped_column(String(32), default="REQUESTED", index=True)  # REQUESTED, PROCESSING, COMPLETED, FAILED, CANCELLED, EXPIRED
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    file_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_checksum_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    downloads: Mapped[List["AlertExportDownloadHistory"]] = relationship(
        "AlertExportDownloadHistory", back_populates="export_job", cascade="all, delete-orphan", order_by="desc(AlertExportDownloadHistory.downloaded_at)"
    )


class AlertExportDownloadHistory(Base):
    """
    Audit log of export downloads.
    """
    __tablename__ = "alert_export_download_history"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    export_job_id: Mapped[str] = mapped_column(String(64), ForeignKey("alert_export_jobs.id", ondelete="CASCADE"), index=True)
    downloaded_by: Mapped[str] = mapped_column(String(64), nullable=False)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    download_result: Mapped[str] = mapped_column(String(32), default="SUCCESS")
    access_context: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)

    export_job: Mapped["AlertExportJob"] = relationship("AlertExportJob", back_populates="downloads")


class AlertHistoryIntegrityIssue(Base):
    """
    Detected timeline gaps, sequencing anomalies, or orphaned references.
    """
    __tablename__ = "alert_history_integrity_issues"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_alert_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source_event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    issue_type: Mapped[str] = mapped_column(String(64), nullable=False)  # MISSING_TRIGGER, INVALID_SEQUENCE, ORPHANED_EVENT, TIMESTAMP_DISCREPANCY
    issue_description: Mapped[Text] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="WARNING")  # WARNING, CRITICAL
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    investigation_status: Mapped[str] = mapped_column(String(32), default="DETECTED")  # DETECTED, INVESTIGATING, RESOLVED, WAIVED
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolution_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

