"""
Pydantic v2 schemas for M12.06 — Alert Management.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


# ------------------ Acknowledgement ------------------
class AlertAcknowledgeRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reviewer_user_id: str = Field(..., max_length=64)
    reviewer_role_snapshot: Optional[str] = Field("RISK_ANALYST", max_length=64)
    acknowledgement_comment: Optional[str] = None
    priority_snapshot: Optional[str] = "MEDIUM"
    severity_snapshot: Optional[str] = "WARNING"
    urgency_snapshot: Optional[str] = "U3_NORMAL"
    request_id: Optional[str] = None


class AlertAcknowledgementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    alert_id: str
    workflow_cycle: int
    reviewer_user_id: str
    reviewer_role_snapshot: Optional[str]
    acknowledgement_comment: Optional[str]
    priority_snapshot: str
    severity_snapshot: str
    urgency_snapshot: str
    acknowledged_at: datetime
    request_id: Optional[str]


# ------------------ Assignment ------------------
class AlertAssignRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assignment_type: str = Field("USER", max_length=32)  # USER, ROLE, TEAM
    assigned_user_id: Optional[str] = Field(None, max_length=64)
    assigned_role_id: Optional[str] = Field(None, max_length=64)
    assigned_team_id: Optional[str] = Field(None, max_length=64)
    assigned_by_user_id: str = Field(..., max_length=64)
    assignment_reason: str = Field(..., max_length=255)
    assignment_comment: Optional[str] = None
    due_at: Optional[datetime] = None


class AlertAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    alert_id: str
    workflow_cycle: int
    assignment_type: str
    assigned_user_id: Optional[str]
    assigned_role_id: Optional[str]
    assigned_team_id: Optional[str]
    assigned_by_user_id: str
    assignment_reason: str
    assignment_comment: Optional[str]
    effective_from: datetime
    effective_to: Optional[datetime]
    due_at: Optional[datetime]
    assignment_status: str
    created_at: datetime


# ------------------ Workflow State & Events ------------------
class AlertWorkflowTransitionRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_state: str = Field(..., max_length=32)
    # OPEN, ACKNOWLEDGED, ASSIGNED, INVESTIGATING, PENDING_INFORMATION, PENDING_ACTION, RESOLVED, CLOSED, REOPENED
    actor_user_id: str = Field(..., max_length=64)
    actor_role_snapshot: Optional[str] = "RISK_ANALYST"
    reason: Optional[str] = Field(None, max_length=255)
    event_metadata: Dict[str, Any] = Field(default_factory=dict)
    expected_version: Optional[int] = None  # Optimistic concurrency check


class AlertWorkflowStateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    alert_id: str
    workflow_cycle: int
    current_state: str
    acknowledgement_state: str
    resolution_state: str
    current_owner_user_id: Optional[str]
    current_owner_role_id: Optional[str]
    current_disposition: Optional[str]
    version: int
    opened_at: datetime
    acknowledged_at: Optional[datetime]
    assigned_at: Optional[datetime]
    investigation_started_at: Optional[datetime]
    resolved_at: Optional[datetime]
    closed_at: Optional[datetime]
    updated_at: datetime


class AlertWorkflowEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    alert_id: str
    workflow_cycle: int
    sequence_number: int
    event_type: str
    actor_user_id: str
    actor_role_snapshot: Optional[str]
    previous_state: Optional[str]
    new_state: Optional[str]
    previous_owner_reference: Optional[str]
    new_owner_reference: Optional[str]
    reason: Optional[str]
    event_metadata: Dict[str, Any]
    correlation_id: Optional[str]
    request_id: Optional[str]
    created_at: datetime


# ------------------ Comments & Revisions ------------------
class AlertCommentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    author_user_id: str = Field(..., max_length=64)
    comment_category: str = Field("INVESTIGATION_UPDATE", max_length=64)
    comment_content: str = Field(..., min_length=1)
    visibility: str = Field("INTERNAL", max_length=32)


class AlertCommentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    revised_by_user_id: str = Field(..., max_length=64)
    revised_content: str = Field(..., min_length=1)
    revision_reason: str = Field(..., max_length=255)


class AlertCommentRevisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    comment_id: str
    previous_content: str
    revised_content: str
    revised_by_user_id: str
    revision_reason: str
    created_at: datetime


class AlertCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    alert_id: str
    workflow_cycle: int
    author_user_id: str
    comment_category: str
    comment_content: str
    visibility: str
    is_edited: bool
    created_at: datetime
    updated_at: datetime
    revisions: List[AlertCommentRevisionResponse] = Field(default_factory=list)


# ------------------ Evidence ------------------
class AlertEvidenceCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    evidence_type: str = Field("MARKET_SNAPSHOT", max_length=64)
    source_module: str = Field("M12.06", max_length=32)
    source_record_id: Optional[str] = None
    file_reference: Optional[str] = None
    file_name: Optional[str] = None
    content_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    checksum: Optional[str] = None
    description: str = Field(..., max_length=255)
    evidence_payload: Dict[str, Any] = Field(default_factory=dict)
    uploaded_by_user_id: str = Field(..., max_length=64)
    comment_id: Optional[str] = None


class AlertEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    alert_id: str
    workflow_cycle: int
    comment_id: Optional[str]
    evidence_type: str
    source_module: str
    source_record_id: Optional[str]
    file_reference: Optional[str]
    file_name: Optional[str]
    content_type: Optional[str]
    file_size_bytes: Optional[int]
    checksum: Optional[str]
    description: str
    evidence_payload: Dict[str, Any]
    uploaded_by_user_id: str
    uploaded_at: datetime


# ------------------ Disposition & Resolution ------------------
class AlertDispositionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    disposition: str = Field(..., max_length=64)
    # CONFIRMED_ISSUE, FALSE_POSITIVE, EXPECTED_MARKET_ACTIVITY, DATA_QUALITY_ISSUE,
    # SOURCE_DISCREPANCY, ACTION_REQUIRED, MONITORING_REQUIRED, ESCALATED, RESOLVED, NOT_ACTIONABLE
    disposition_reason: str = Field(..., min_length=5)
    selected_action: str = Field("CONTINUE_MONITORING", max_length=64)
    selected_by_user_id: str = Field(..., max_length=64)
    related_m11_breach_id: Optional[str] = None


class AlertDispositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    alert_id: str
    workflow_cycle: int
    disposition: str
    disposition_reason: str
    selected_action: str
    selected_by_user_id: str
    related_m11_breach_id: Optional[str]
    created_at: datetime


class AlertResolutionAssessmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    resolution_status: str = Field("RESOLVED", max_length=32)  # RESOLVED, NOT_RESOLVED
    resolution_reason: str = Field(..., min_length=5)
    assessed_by_user_id: str = Field(..., max_length=64)
    evidence_reference_id: Optional[str] = None
    related_breach_status_snapshot: Optional[str] = None


class AlertResolutionAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    alert_id: str
    workflow_cycle: int
    resolution_status: str
    resolution_reason: str
    assessed_by_user_id: str
    evidence_reference_id: Optional[str]
    related_breach_status_snapshot: Optional[str]
    assessed_at: datetime


# ------------------ Closure & Reopening ------------------
class AlertCloseRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    closed_by_user_id: str = Field(..., max_length=64)
    closure_reason: str = Field(..., max_length=64)
    # ISSUE_RESOLVED, FALSE_POSITIVE_CONFIRMED, EXPECTED_EVENT_CONFIRMED,
    # DATA_QUALITY_ISSUE_RESOLVED, SOURCE_DISCREPANCY_RESOLVED, INVESTIGATION_COMPLETED,
    # NO_FURTHER_ACTION_REQUIRED, DUPLICATE_ALERT_LINKED
    closure_notes: Optional[str] = None


class AlertClosureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    alert_id: str
    workflow_cycle: int
    closed_by_user_id: str
    closure_reason: str
    closure_notes: Optional[str]
    final_disposition: str
    final_priority_snapshot: str
    final_severity_snapshot: str
    final_owner_snapshot: Optional[str]
    resolution_reference: Optional[str]
    closed_at: datetime


class AlertReopenRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reopened_by_user_id: str = Field(..., max_length=64)
    reopening_reason: str = Field(..., min_length=5)
    triggering_event_id: Optional[str] = None


class AlertReopeningResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    alert_id: str
    previous_workflow_cycle: int
    new_workflow_cycle: int
    reopened_by_user_id: str
    reopening_reason: str
    triggering_event_id: Optional[str]
    previous_closure_id: Optional[str]
    reopened_at: datetime


# ------------------ Dashboard & Queue ------------------
class AlertWorkQueueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    alert_id: str
    title: str
    category: str
    portfolio_id: str
    priority: str
    severity: str
    urgency: str
    workflow_status: str
    acknowledgement_state: str
    assigned_owner: Optional[str]
    assigned_role: Optional[str]
    assigned_at: Optional[datetime]
    last_activity_at: datetime
    due_at: Optional[datetime]
    workflow_cycle: int


class AlertManagementSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_alerts: int
    unacknowledged_count: int
    acknowledged_count: int
    unassigned_count: int
    assigned_count: int
    investigating_count: int
    pending_info_or_action_count: int
    resolved_pending_closure_count: int
    closed_count: int
    reopened_count: int
    status_distribution: Dict[str, int]
    avg_acknowledgement_seconds: Optional[float]
    avg_resolution_seconds: Optional[float]

