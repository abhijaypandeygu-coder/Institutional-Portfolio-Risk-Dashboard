"""
SQLAlchemy ORM models for M12.06 — Alert Management.

Tables:
1. `alert_acknowledgements`: Full reviewer identity, context snapshots, cycle-aware acknowledgement.
2. `alert_assignments`: Individual user and role/team ownership assignments with duration & history.
3. `alert_workflow_states`: Current workflow state projection with optimistic locking & cycle tracking.
4. `alert_workflow_events`: Immutable chronological audit log of all state and ownership changes.
5. `alert_investigation_comments`: Notes, findings, categories, and audit visibility.
6. `alert_comment_revisions`: Revision history when comments are updated.
7. `alert_management_evidence`: Attached documents, data snapshots, checksums, and references.
8. `alert_dispositions`: Documented outcome conclusions, selected actions, and M11 breach links.
9. `alert_resolution_assessments`: Resolution criteria evaluation before closure.
10. `alert_closures`: Formal closure record with mandatory reason, final snapshots, and closing user.
11. `alert_reopenings`: Formal reopening record with reason, cycle increment, and previous closure link.
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
    Float,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.utcnow()


class AlertAcknowledgement(Base):
    """
    Reviewer acknowledgement record per workflow cycle.
    """
    __tablename__ = "alert_acknowledgements"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(64), ForeignKey("alert_events.id", ondelete="CASCADE"), index=True)
    workflow_cycle: Mapped[int] = mapped_column(Integer, default=1, index=True)
    reviewer_user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reviewer_role_snapshot: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    acknowledgement_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    priority_snapshot: Mapped[str] = mapped_column(String(32), default="MEDIUM")
    severity_snapshot: Mapped[str] = mapped_column(String(32), default="WARNING")
    urgency_snapshot: Mapped[str] = mapped_column(String(32), default="U3_NORMAL")

    acknowledged_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class AlertAssignment(Base):
    """
    Ownership assignment record for users or operational roles.
    """
    __tablename__ = "alert_assignments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(64), ForeignKey("alert_events.id", ondelete="CASCADE"), index=True)
    workflow_cycle: Mapped[int] = mapped_column(Integer, default=1, index=True)
    assignment_type: Mapped[str] = mapped_column(String(32), default="USER")  # USER, ROLE, TEAM
    assigned_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    assigned_role_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    assigned_team_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    assigned_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)

    assignment_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    assignment_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    assignment_status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)  # ACTIVE, REASSIGNED, UNASSIGNED, COMPLETED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class AlertWorkflowState(Base):
    """
    Current operational workflow state projection per alert.
    """
    __tablename__ = "alert_workflow_states"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(64), ForeignKey("alert_events.id", ondelete="CASCADE"), unique=True, index=True)
    workflow_cycle: Mapped[int] = mapped_column(Integer, default=1, index=True)
    current_state: Mapped[str] = mapped_column(String(32), default="OPEN", index=True)
    # OPEN, ACKNOWLEDGED, ASSIGNED, INVESTIGATING, PENDING_INFORMATION, PENDING_ACTION, RESOLVED, CLOSED, REOPENED

    acknowledgement_state: Mapped[str] = mapped_column(String(32), default="UNACKNOWLEDGED", index=True)  # UNACKNOWLEDGED, ACKNOWLEDGED
    resolution_state: Mapped[str] = mapped_column(String(32), default="NOT_ASSESSED", index=True)  # NOT_ASSESSED, RESOLUTION_PENDING, RESOLVED, NOT_RESOLVED
    current_owner_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    current_owner_role_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    current_disposition: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    version: Mapped[int] = mapped_column(Integer, default=1)  # Optimistic concurrency lock
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    investigation_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class AlertWorkflowEvent(Base):
    """
    Immutable chronological operational timeline of all workflow events.
    """
    __tablename__ = "alert_workflow_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(64), ForeignKey("alert_events.id", ondelete="CASCADE"), index=True)
    workflow_cycle: Mapped[int] = mapped_column(Integer, default=1)
    sequence_number: Mapped[int] = mapped_column(Integer, default=1)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # ALERT_ACKNOWLEDGED, ALERT_ASSIGNED, ALERT_REASSIGNED, ALERT_UNASSIGNED, ALERT_INVESTIGATION_STARTED,
    # ALERT_STATUS_CHANGED, ALERT_COMMENT_ADDED, ALERT_EVIDENCE_ADDED, ALERT_DISPOSITION_SELECTED,
    # ALERT_RESOLVED, ALERT_CLOSED, ALERT_REOPENED

    actor_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_role_snapshot: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    previous_state: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    new_state: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    previous_owner_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    new_owner_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    event_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class AlertInvestigationComment(Base):
    """
    Investigation notes, operational findings, and discussion.
    """
    __tablename__ = "alert_investigation_comments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(64), ForeignKey("alert_events.id", ondelete="CASCADE"), index=True)
    workflow_cycle: Mapped[int] = mapped_column(Integer, default=1)
    author_user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    comment_category: Mapped[str] = mapped_column(String(64), default="INVESTIGATION_UPDATE")
    # INITIAL_REVIEW, INVESTIGATION_UPDATE, TECHNICAL_FINDING, FINANCIAL_ASSESSMENT,
    # RISK_ASSESSMENT, OPERATIONAL_FINDING, RESOLUTION_NOTE, CLOSURE_NOTE, REOPENING_EXPLANATION

    comment_content: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(String(32), default="INTERNAL")  # INTERNAL, AUDIT_ONLY, PUBLIC
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    revisions: Mapped[List["AlertCommentRevision"]] = relationship(
        "AlertCommentRevision", back_populates="comment", cascade="all, delete-orphan", lazy="selectin"
    )


class AlertCommentRevision(Base):
    """
    Immutable revision history for edited comments.
    """
    __tablename__ = "alert_comment_revisions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    comment_id: Mapped[str] = mapped_column(String(64), ForeignKey("alert_investigation_comments.id", ondelete="CASCADE"), index=True)
    previous_content: Mapped[str] = mapped_column(Text, nullable=False)
    revised_content: Mapped[str] = mapped_column(Text, nullable=False)
    revised_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    revision_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    comment: Mapped["AlertInvestigationComment"] = relationship("AlertInvestigationComment", back_populates="revisions")


class AlertManagementEvidence(Base):
    """
    Supporting evidence, data snapshots, or uploaded attachments.
    """
    __tablename__ = "alert_management_evidence"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(64), ForeignKey("alert_events.id", ondelete="CASCADE"), index=True)
    workflow_cycle: Mapped[int] = mapped_column(Integer, default=1)
    comment_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    evidence_type: Mapped[str] = mapped_column(String(64), default="MARKET_SNAPSHOT")
    # MARKET_SNAPSHOT, PORTFOLIO_VALUATION, RISK_REPORT, RECONCILIATION_REPORT, TRANSACTION_REF, LOG_OUTPUT, DOCUMENT
    source_module: Mapped[str] = mapped_column(String(32), default="M12.06")
    source_record_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    file_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)

    uploaded_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class AlertDisposition(Base):
    """
    Documented conclusion and selected operational outcome.
    """
    __tablename__ = "alert_dispositions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(64), ForeignKey("alert_events.id", ondelete="CASCADE"), index=True)
    workflow_cycle: Mapped[int] = mapped_column(Integer, default=1)
    disposition: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # CONFIRMED_ISSUE, FALSE_POSITIVE, EXPECTED_MARKET_ACTIVITY, DATA_QUALITY_ISSUE,
    # SOURCE_DISCREPANCY, ACTION_REQUIRED, MONITORING_REQUIRED, ESCALATED, RESOLVED, NOT_ACTIONABLE

    disposition_reason: Mapped[str] = mapped_column(Text, nullable=False)
    selected_action: Mapped[str] = mapped_column(String(64), default="CONTINUE_MONITORING")
    # CONTINUE_MONITORING, REQUEST_DATA, REQUEST_RECONCILIATION, REFER_MARKET_RISK,
    # REFER_OPERATIONS, REFER_TRADING, ESCALATE_M11, NO_ACTION

    selected_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    related_m11_breach_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class AlertResolutionAssessment(Base):
    """
    Pre-closure validation of whether alert conditions have cleared.
    """
    __tablename__ = "alert_resolution_assessments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(64), ForeignKey("alert_events.id", ondelete="CASCADE"), index=True)
    workflow_cycle: Mapped[int] = mapped_column(Integer, default=1)
    resolution_status: Mapped[str] = mapped_column(String(32), default="RESOLVED")  # RESOLVED, NOT_RESOLVED
    resolution_reason: Mapped[str] = mapped_column(Text, nullable=False)
    assessed_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_reference_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    related_breach_status_snapshot: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    assessed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class AlertClosure(Base):
    """
    Formal closure record terminating the active review workflow.
    """
    __tablename__ = "alert_closures"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(64), ForeignKey("alert_events.id", ondelete="CASCADE"), index=True)
    workflow_cycle: Mapped[int] = mapped_column(Integer, default=1)
    closed_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    closure_reason: Mapped[str] = mapped_column(String(64), nullable=False)
    # ISSUE_RESOLVED, FALSE_POSITIVE_CONFIRMED, EXPECTED_EVENT_CONFIRMED,
    # DATA_QUALITY_ISSUE_RESOLVED, SOURCE_DISCREPANCY_RESOLVED, INVESTIGATION_COMPLETED,
    # NO_FURTHER_ACTION_REQUIRED, DUPLICATE_ALERT_LINKED

    closure_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    final_disposition: Mapped[str] = mapped_column(String(64), nullable=False)
    final_priority_snapshot: Mapped[str] = mapped_column(String(32), default="MEDIUM")
    final_severity_snapshot: Mapped[str] = mapped_column(String(32), default="WARNING")
    final_owner_snapshot: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    resolution_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    closed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class AlertReopening(Base):
    """
    Audit record created when a closed or resolved alert is reopened.
    """
    __tablename__ = "alert_reopenings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(64), ForeignKey("alert_events.id", ondelete="CASCADE"), index=True)
    previous_workflow_cycle: Mapped[int] = mapped_column(Integer, nullable=False)
    new_workflow_cycle: Mapped[int] = mapped_column(Integer, nullable=False)
    reopened_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reopening_reason: Mapped[str] = mapped_column(Text, nullable=False)
    triggering_event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    previous_closure_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reopened_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

