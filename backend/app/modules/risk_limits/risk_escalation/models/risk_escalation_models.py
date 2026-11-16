"""
SQLAlchemy ORM models for M11.08 — Risk Escalation.

Tables:
1. `risk_breach_workflows`: Authoritative operational workflow state for breach events/episodes.
2. `risk_breach_acknowledgements`: Immutable records of breach reviews and acknowledgements.
3. `risk_breach_assignments`: Assignment and reassignment history across users, teams, and levels.
4. `risk_escalation_policies`: Configurable escalation policy containers.
5. `risk_escalation_policy_versions`: Immutable versioned rules and tier hierarchy.
6. `risk_escalation_levels`: Responsibility levels (Level 1 to Level 4+).
7. `risk_escalation_events`: Immutable log of automatic and manual escalation transitions.
8. `risk_escalation_execution_attempts`: Execution audit and delivery failure tracking.
9. `risk_resolution_plans`: Corrective action plan entities.
10. `risk_resolution_actions`: Granular mitigation action items.
11. `risk_mitigation_updates`: Progress updates and milestone completions.
12. `risk_mitigation_evidence`: Immutable evidence documents/references for risk reduction.
13. `risk_breach_lifecycle_events`: Append-only transition history of workflow states.
14. `risk_breach_closure_requests`: Formal closure submissions with justifications.
15. `risk_breach_closure_records`: Formally authorized closure records.
16. `risk_breach_reopen_events`: Audit trail of reopenings with triggers.
17. `risk_workflow_sla_instances`: Active and completed SLA monitoring records.
18. `risk_workflow_sla_pauses`: Authorized SLA pause records.
19. `risk_escalation_notifications`: Notification tasks and multi-channel delivery states.
20. `risk_escalation_audit_logs`: Administrative governance audit trail.
21. `risk_workflow_idempotency_keys`: Idempotency registry for duplicate prevention.
"""

from datetime import datetime, timezone
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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.utcnow()


class RiskBreachWorkflow(Base):
    """
    Authoritative workflow record managing the operational lifecycle of a breach.
    """
    __tablename__ = "risk_breach_workflows"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workflow_reference: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    breach_event_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    breach_episode_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    risk_limit_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    
    # Severity & classification reference from M11.07
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # WARNING, CRITICAL, EMERGENCY
    classification_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    classification_version: Mapped[int] = mapped_column(Integer, default=1)

    # Core Lifecycle & Workflow Dimensions
    current_lifecycle_state: Mapped[str] = mapped_column(String(32), default="OPEN", index=True)  # OPEN, ACKNOWLEDGED, MITIGATED, CLOSED, REOPENED
    current_assignment_status: Mapped[str] = mapped_column(String(32), default="UNASSIGNED", index=True)  # UNASSIGNED, ASSIGNED
    current_owner_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    current_owner_team_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    
    current_escalation_level_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    current_escalation_level_name: Mapped[str] = mapped_column(String(64), default="LEVEL_1", index=True)
    escalation_count: Mapped[int] = mapped_column(Integer, default=0)
    
    current_sla_status: Mapped[str] = mapped_column(String(32), default="ON_TRACK", index=True)  # ON_TRACK, AT_RISK, OVERDUE, PAUSED
    acknowledgement_status: Mapped[str] = mapped_column(String(32), default="PENDING_ACKNOWLEDGEMENT", index=True)
    resolution_plan_status: Mapped[str] = mapped_column(String(32), default="NOT_CREATED", index=True)
    closure_status: Mapped[str] = mapped_column(String(32), default="NOT_REQUESTED", index=True)

    # Key Milestones Timestamps (UTC)
    sla_start_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    acknowledgement_due_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolution_due_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    mitigated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reopened_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Concurrency control & versioning
    workflow_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    acknowledgements: Mapped[List["RiskBreachAcknowledgement"]] = relationship(
        "RiskBreachAcknowledgement", back_populates="workflow", cascade="all, delete-orphan", order_by="desc(RiskBreachAcknowledgement.created_at)"
    )
    assignments: Mapped[List["RiskBreachAssignment"]] = relationship(
        "RiskBreachAssignment", back_populates="workflow", cascade="all, delete-orphan", order_by="desc(RiskBreachAssignment.created_at)"
    )
    escalation_events: Mapped[List["RiskEscalationEvent"]] = relationship(
        "RiskEscalationEvent", back_populates="workflow", cascade="all, delete-orphan", order_by="desc(RiskEscalationEvent.created_at)"
    )
    resolution_plans: Mapped[List["RiskResolutionPlan"]] = relationship(
        "RiskResolutionPlan", back_populates="workflow", cascade="all, delete-orphan", order_by="desc(RiskResolutionPlan.created_at)"
    )
    lifecycle_events: Mapped[List["RiskBreachLifecycleEvent"]] = relationship(
        "RiskBreachLifecycleEvent", back_populates="workflow", cascade="all, delete-orphan", order_by="desc(RiskBreachLifecycleEvent.created_at)"
    )
    closure_records: Mapped[List["RiskBreachClosureRecord"]] = relationship(
        "RiskBreachClosureRecord", back_populates="workflow", cascade="all, delete-orphan"
    )
    reopen_events: Mapped[List["RiskBreachReopenEvent"]] = relationship(
        "RiskBreachReopenEvent", back_populates="workflow", cascade="all, delete-orphan", order_by="desc(RiskBreachReopenEvent.created_at)"
    )
    sla_instances: Mapped[List["RiskWorkflowSLAInstance"]] = relationship(
        "RiskWorkflowSLAInstance", back_populates="workflow", cascade="all, delete-orphan"
    )
    notifications: Mapped[List["RiskEscalationNotification"]] = relationship(
        "RiskEscalationNotification", back_populates="workflow", cascade="all, delete-orphan"
    )


class RiskBreachAcknowledgement(Base):
    """
    Formal record that an authorized actor has reviewed and acknowledged a breach.
    """
    __tablename__ = "risk_breach_acknowledgements"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String(64), ForeignKey("risk_breach_workflows.id", ondelete="CASCADE"), index=True)
    acknowledged_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_role: Mapped[str] = mapped_column(String(64), nullable=False)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity_at_acknowledgement: Mapped[str] = mapped_column(String(16), nullable=False)
    classification_version: Mapped[int] = mapped_column(Integer, default=1)
    is_reacknowledgement: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledgement_status: Mapped[str] = mapped_column(String(32), default="ACKNOWLEDGED")  # ACKNOWLEDGED, REVOKED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    workflow: Mapped["RiskBreachWorkflow"] = relationship("RiskBreachWorkflow", back_populates="acknowledgements")


class RiskBreachAssignment(Base):
    """
    Tracks accountability ownership history across individual users and teams.
    """
    __tablename__ = "risk_breach_assignments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String(64), ForeignKey("risk_breach_workflows.id", ondelete="CASCADE"), index=True)
    assigned_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    assigned_team_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    responsibility_level: Mapped[str] = mapped_column(String(64), default="LEVEL_1")  # LEVEL_1 (Analyst), LEVEL_2 (Manager), LEVEL_3 (Head), LEVEL_4 (CRO)
    assignment_type: Mapped[str] = mapped_column(String(32), default="INITIAL")  # INITIAL, REASSIGNMENT, ESCALATION, AUTO_ROUTED
    reassignment_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assigned_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    workflow: Mapped["RiskBreachWorkflow"] = relationship("RiskBreachWorkflow", back_populates="assignments")


class RiskEscalationPolicy(Base):
    """
    Master escalation policy governing routing matrices and deadlines.
    """
    __tablename__ = "risk_escalation_policies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scope_type: Mapped[str] = mapped_column(String(32), default="ALL")  # ALL, PORTFOLIO, ASSET_CLASS
    scope_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    risk_category: Mapped[str] = mapped_column(String(64), default="ALL")
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    versions: Mapped[List["RiskEscalationPolicyVersion"]] = relationship(
        "RiskEscalationPolicyVersion", back_populates="policy", cascade="all, delete-orphan", order_by="desc(RiskEscalationPolicyVersion.version_number)"
    )


class RiskEscalationPolicyVersion(Base):
    """
    Immutable versioned rules and tiers for risk escalation.
    """
    __tablename__ = "risk_escalation_policy_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_id: Mapped[str] = mapped_column(String(64), ForeignKey("risk_escalation_policies.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    severity_sla_minutes: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    escalation_matrix: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    auto_escalate_on_upgrade: Mapped[bool] = mapped_column(Boolean, default=True)
    approval_status: Mapped[str] = mapped_column(String(32), default="APPROVED")
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    policy: Mapped["RiskEscalationPolicy"] = relationship("RiskEscalationPolicy", back_populates="versions")
    levels: Mapped[List["RiskEscalationLevel"]] = relationship(
        "RiskEscalationLevel", back_populates="policy_version", cascade="all, delete-orphan", order_by="RiskEscalationLevel.level_rank"
    )


class RiskEscalationLevel(Base):
    """
    Configurable responsibility hierarchy tier within a policy version.
    """
    __tablename__ = "risk_escalation_levels"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_version_id: Mapped[str] = mapped_column(String(64), ForeignKey("risk_escalation_policy_versions.id", ondelete="CASCADE"), index=True)
    level_code: Mapped[str] = mapped_column(String(64), nullable=False)  # LEVEL_1, LEVEL_2, LEVEL_3, LEVEL_4
    level_name: Mapped[str] = mapped_column(String(128), nullable=False)  # Risk Analyst, Senior Risk Manager, Head of Risk, CRO
    level_rank: Mapped[int] = mapped_column(Integer, nullable=False)  # 1, 2, 3, 4
    default_team_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    max_duration_minutes: Mapped[int] = mapped_column(Integer, default=60)

    policy_version: Mapped["RiskEscalationPolicyVersion"] = relationship("RiskEscalationPolicyVersion", back_populates="levels")


class RiskEscalationEvent(Base):
    """
    Immutable audit record of an automatic or manual escalation event.
    """
    __tablename__ = "risk_escalation_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String(64), ForeignKey("risk_breach_workflows.id", ondelete="CASCADE"), index=True)
    policy_version_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    previous_level_name: Mapped[str] = mapped_column(String(64), nullable=False)
    new_level_name: Mapped[str] = mapped_column(String(64), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(64), nullable=False)  # TIME_EXPIRED, SEVERITY_UPGRADE, EMERGENCY_TRIGGER, MANUAL_ESCALATION, MITIGATION_FAILURE
    trigger_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    escalation_reason: Mapped[str] = mapped_column(Text, nullable=False)
    initiated_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)  # SYSTEM or user_id
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    execution_status: Mapped[str] = mapped_column(String(32), default="EXECUTED")  # EXECUTED, FAILED, RETRY_PENDING
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    workflow: Mapped["RiskBreachWorkflow"] = relationship("RiskBreachWorkflow", back_populates="escalation_events")


class RiskResolutionPlan(Base):
    """
    Documented corrective action plan associated with an open/reopened breach.
    """
    __tablename__ = "risk_resolution_plans"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String(64), ForeignKey("risk_breach_workflows.id", ondelete="CASCADE"), index=True)
    plan_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Text] = mapped_column(Text, nullable=False)
    root_cause_hypothesis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    proposed_actions_summary: Mapped[Text] = mapped_column(Text, nullable=False)
    owner_user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    owner_team_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    priority: Mapped[str] = mapped_column(String(16), default="HIGH")  # LOW, MEDIUM, HIGH, CRITICAL
    plan_status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True)  # DRAFT, ACTIVE, COMPLETED, BLOCKED, FAILED, SUPERSEDED
    
    target_start_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    due_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    original_due_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    approved_by_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    workflow: Mapped["RiskBreachWorkflow"] = relationship("RiskBreachWorkflow", back_populates="resolution_plans")
    actions: Mapped[List["RiskResolutionAction"]] = relationship(
        "RiskResolutionAction", back_populates="plan", cascade="all, delete-orphan", order_by="RiskResolutionAction.sequence_order"
    )


class RiskResolutionAction(Base):
    """
    Granular task within a resolution plan.
    """
    __tablename__ = "risk_resolution_actions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    plan_id: Mapped[str] = mapped_column(String(64), ForeignKey("risk_resolution_plans.id", ondelete="CASCADE"), index=True)
    sequence_order: Mapped[int] = mapped_column(Integer, default=1)
    action_title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Text] = mapped_column(Text, nullable=False)
    assigned_to_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action_status: Mapped[str] = mapped_column(String(32), default="NOT_STARTED", index=True)  # NOT_STARTED, IN_PROGRESS, COMPLETED, BLOCKED, FAILED, CANCELLED
    progress_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"))
    due_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    plan: Mapped["RiskResolutionPlan"] = relationship("RiskResolutionPlan", back_populates="actions")
    updates: Mapped[List["RiskMitigationUpdate"]] = relationship(
        "RiskMitigationUpdate", back_populates="action", cascade="all, delete-orphan", order_by="desc(RiskMitigationUpdate.created_at)"
    )


class RiskMitigationUpdate(Base):
    """
    Progress update on an individual corrective action.
    """
    __tablename__ = "risk_mitigation_updates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    action_id: Mapped[str] = mapped_column(String(64), ForeignKey("risk_resolution_actions.id", ondelete="CASCADE"), index=True)
    previous_status: Mapped[str] = mapped_column(String(32), nullable=False)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    progress_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    notes: Mapped[Text] = mapped_column(Text, nullable=False)
    updated_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    action: Mapped["RiskResolutionAction"] = relationship("RiskResolutionAction", back_populates="updates")


class RiskMitigationEvidence(Base):
    """
    Immutable document reference / metric evidence verifying risk reduction.
    """
    __tablename__ = "risk_mitigation_evidence"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String(64), ForeignKey("risk_breach_workflows.id", ondelete="CASCADE"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)  # TRADE_EXECUTION, HEDGE_ORDER, MODEL_RECERTIFICATION, METRIC_SNAPSHOT
    document_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Text] = mapped_column(Text, nullable=False)
    verified_risk_reduction: Mapped[bool] = mapped_column(Boolean, default=False)
    submitted_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class RiskBreachLifecycleEvent(Base):
    """
    Append-only state machine transition log.
    """
    __tablename__ = "risk_breach_lifecycle_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String(64), ForeignKey("risk_breach_workflows.id", ondelete="CASCADE"), index=True)
    previous_state: Mapped[str] = mapped_column(String(32), nullable=False)
    new_state: Mapped[str] = mapped_column(String(32), nullable=False)
    transition_reason: Mapped[Text] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), default="USER")  # USER, SYSTEM, POLICY_ENGINE
    evidence_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    workflow: Mapped["RiskBreachWorkflow"] = relationship("RiskBreachWorkflow", back_populates="lifecycle_events")


class RiskBreachClosureRequest(Base):
    """
    Submission requesting formal closure of a breach workflow.
    """
    __tablename__ = "risk_breach_closure_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String(64), ForeignKey("risk_breach_workflows.id", ondelete="CASCADE"), index=True)
    closure_reason: Mapped[str] = mapped_column(String(64), nullable=False)  # RISK_REDUCED, EXPOSURE_REMOVED, LIMIT_CONFIGURATION_CORRECTED, FALSE_POSITIVE_CONFIRMED, DUPLICATE_BREACH
    closure_description: Mapped[Text] = mapped_column(Text, nullable=False)
    closure_evidence_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    requested_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    request_status: Mapped[str] = mapped_column(String(32), default="PENDING_APPROVAL", index=True)  # PENDING_APPROVAL, APPROVED, REJECTED
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class RiskBreachClosureRecord(Base):
    """
    Approved and finalized closure record.
    """
    __tablename__ = "risk_breach_closure_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String(64), ForeignKey("risk_breach_workflows.id", ondelete="CASCADE"), index=True)
    closure_request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    closure_reason: Mapped[str] = mapped_column(String(64), nullable=False)
    closure_description: Mapped[Text] = mapped_column(Text, nullable=False)
    closed_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    closed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    workflow: Mapped["RiskBreachWorkflow"] = relationship("RiskBreachWorkflow", back_populates="closure_records")


class RiskBreachReopenEvent(Base):
    """
    Audit record of reopening a previously closed breach.
    """
    __tablename__ = "risk_breach_reopen_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String(64), ForeignKey("risk_breach_workflows.id", ondelete="CASCADE"), index=True)
    reopen_trigger: Mapped[str] = mapped_column(String(64), nullable=False)  # RECURRENCE_DETECTED, RECOVERY_INVALIDATED, AUDIT_CORRECTION, MANUAL_REOPEN
    reopen_reason: Mapped[Text] = mapped_column(Text, nullable=False)
    reopened_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_closure_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    workflow: Mapped["RiskBreachWorkflow"] = relationship("RiskBreachWorkflow", back_populates="reopen_events")


class RiskWorkflowSLAInstance(Base):
    """
    Tracks an individual SLA commitment (Acknowledgement, Mitigation, Closure).
    """
    __tablename__ = "risk_workflow_sla_instances"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String(64), ForeignKey("risk_breach_workflows.id", ondelete="CASCADE"), index=True)
    sla_type: Mapped[str] = mapped_column(String(64), nullable=False)  # ACKNOWLEDGEMENT, RESOLUTION, MITIGATION
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sla_status: Mapped[str] = mapped_column(String(32), default="ON_TRACK", index=True)  # ON_TRACK, AT_RISK, BREACHED, COMPLETED_ON_TIME, COMPLETED_LATE, PAUSED
    total_paused_seconds: Mapped[float] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    workflow: Mapped["RiskBreachWorkflow"] = relationship("RiskBreachWorkflow", back_populates="sla_instances")
    pauses: Mapped[List["RiskWorkflowSLAPause"]] = relationship(
        "RiskWorkflowSLAPause", back_populates="sla_instance", cascade="all, delete-orphan"
    )


class RiskWorkflowSLAPause(Base):
    """
    Authorized pause on an SLA clock.
    """
    __tablename__ = "risk_workflow_sla_pauses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sla_instance_id: Mapped[str] = mapped_column(String(64), ForeignKey("risk_workflow_sla_instances.id", ondelete="CASCADE"), index=True)
    pause_reason: Mapped[Text] = mapped_column(Text, nullable=False)
    paused_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    paused_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    resumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resumed_by_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    paused_duration_seconds: Mapped[float] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))

    sla_instance: Mapped["RiskWorkflowSLAInstance"] = relationship("RiskWorkflowSLAInstance", back_populates="pauses")


class RiskEscalationNotification(Base):
    """
    Outbound notification task across app/email/webhook.
    """
    __tablename__ = "risk_escalation_notifications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String(64), ForeignKey("risk_breach_workflows.id", ondelete="CASCADE"), index=True)
    notification_type: Mapped[str] = mapped_column(String(64), nullable=False)  # ASSIGNMENT, ACKNOWLEDGEMENT_DUE, ESCALATED, RESOLUTION_OVERDUE, CLOSURE_REQUEST
    recipient_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    recipient_team_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    channel: Mapped[str] = mapped_column(String(32), default="IN_APP")  # IN_APP, EMAIL, WEBHOOK
    delivery_status: Mapped[str] = mapped_column(String(32), default="SENT", index=True)  # PENDING, SENT, DELIVERED, FAILED
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message_body: Mapped[Text] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    workflow: Mapped["RiskBreachWorkflow"] = relationship("RiskBreachWorkflow", back_populates="notifications")


class RiskEscalationAuditLog(Base):
    """
    Administrative and operational audit trail.
    """
    __tablename__ = "risk_escalation_audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workflow_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)  # POLICY_CHANGE, WORKFLOW_INITIATED, ACKNOWLEDGED, ESCALATED, CLOSED, REOPENED
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class RiskWorkflowIdempotencyKey(Base):
    """
    Idempotency registry preventing duplicate execution across events.
    """
    __tablename__ = "risk_workflow_idempotency_keys"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
