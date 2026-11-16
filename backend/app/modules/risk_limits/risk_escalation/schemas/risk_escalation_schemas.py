"""
Pydantic schemas for M11.08 Risk Escalation.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class RiskWorkflowCreateInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    breach_event_id: str = Field(..., description="Unique ID of the M11.06 BreachEvent")
    breach_episode_id: Optional[str] = Field(None, description="Optional M11.06 Episode ID")
    portfolio_id: str = Field(..., description="Target portfolio identifier")
    risk_limit_id: str = Field(..., description="Violated risk limit identifier")
    severity: str = Field(..., description="WARNING, CRITICAL, or EMERGENCY from M11.07")
    classification_id: Optional[str] = Field(None, description="Classification record ID from M11.07")
    classification_version: int = Field(1, description="Policy version used in M11.07")
    initial_owner_user_id: Optional[str] = Field(None, description="Initial owner user ID")
    initial_owner_team_id: Optional[str] = Field(None, description="Initial owner team ID")


class BreachAcknowledgeInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    acknowledged_by_user_id: str = Field(..., description="User performing the formal review")
    user_role: str = Field(..., description="Role of the acknowledging user e.g. RISK_ANALYST, RISK_MANAGER")
    review_notes: Optional[str] = Field(None, description="Optional review documentation")


class BreachAssignInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assigned_user_id: Optional[str] = Field(None, description="New owner user ID")
    assigned_team_id: Optional[str] = Field(None, description="New owner team ID")
    responsibility_level: str = Field("LEVEL_1", description="LEVEL_1, LEVEL_2, LEVEL_3, LEVEL_4")
    assignment_type: str = Field("REASSIGNMENT", description="INITIAL, REASSIGNMENT, ESCALATION, AUTO_ROUTED")
    reassignment_reason: str = Field(..., description="Mandatory reason for assignment change")
    assigned_by_user_id: str = Field(..., description="User authorizing the assignment")


class ManualEscalateInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_level_name: str = Field(..., description="Target level e.g. LEVEL_2, LEVEL_3, LEVEL_4")
    escalation_reason: str = Field(..., description="Documented reason for manual escalation")
    initiated_by_user_id: str = Field(..., description="Authorized user initiating escalation")
    idempotency_key: Optional[str] = Field(None, description="Optional unique trigger key")


class ResolutionActionCreateInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    action_title: str
    description: str
    assigned_to_user_id: str
    due_at: datetime


class ResolutionPlanCreateInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    description: str
    root_cause_hypothesis: Optional[str] = None
    proposed_actions_summary: str
    owner_user_id: str
    owner_team_id: Optional[str] = None
    priority: str = Field("HIGH", description="LOW, MEDIUM, HIGH, CRITICAL")
    due_at: datetime
    created_by: str
    actions: List[ResolutionActionCreateInput] = Field(default_factory=list)


class ResolutionActionProgressInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    action_status: str = Field(..., description="IN_PROGRESS, COMPLETED, BLOCKED, FAILED")
    progress_percentage: Decimal = Field(..., description="Percentage complete (0 - 100)")
    notes: str
    updated_by_user_id: str


class MitigationEvidenceInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    evidence_type: str = Field(..., description="TRADE_EXECUTION, HEDGE_ORDER, MODEL_RECERTIFICATION, METRIC_SNAPSHOT")
    document_reference: str
    description: str
    verified_risk_reduction: bool = Field(False)
    submitted_by_user_id: str


class BreachTransitionInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_state: str = Field(..., description="OPEN, ACKNOWLEDGED, MITIGATED, CLOSED, REOPENED")
    transition_reason: str = Field(..., description="Documented reason for state transition")
    actor_user_id: str
    evidence_reference: Optional[str] = None


class ClosureRequestInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    closure_reason: str = Field(..., description="RISK_REDUCED, EXPOSURE_REMOVED, LIMIT_CONFIGURATION_CORRECTED, FALSE_POSITIVE_CONFIRMED, DUPLICATE_BREACH")
    closure_description: str
    closure_evidence_ref: Optional[str] = None
    requested_by_user_id: str


class ClosureApproveInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    approved_by_user_id: str
    notes: Optional[str] = None


class ClosureRejectInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rejected_by_user_id: str
    rejection_reason: str


class BreachReopenInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reopen_trigger: str = Field(..., description="RECURRENCE_DETECTED, RECOVERY_INVALIDATED, AUDIT_CORRECTION, MANUAL_REOPEN")
    reopen_reason: str
    reopened_by_user_id: str


class SLAPauseInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pause_reason: str
    paused_by_user_id: str


class SLAResumeInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    resumed_by_user_id: str


class RiskEscalationPolicyCreateInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    policy_code: str
    name: str
    description: Optional[str] = None
    scope_type: str = "ALL"
    scope_id: Optional[str] = None
    risk_category: str = "ALL"
    created_by: str
    severity_sla_minutes: Dict[str, Any] = Field(default_factory=lambda: {
        "WARNING": {"ack": 60, "res": 1440},
        "CRITICAL": {"ack": 15, "res": 240},
        "EMERGENCY": {"ack": 5, "res": 60}
    })
    escalation_matrix: Dict[str, Any] = Field(default_factory=lambda: {
        "WARNING": ["LEVEL_1", "LEVEL_2", "LEVEL_3"],
        "CRITICAL": ["LEVEL_2", "LEVEL_3", "LEVEL_4"],
        "EMERGENCY": ["LEVEL_3", "LEVEL_4"]
    })


# Response Schemas

class RiskBreachAcknowledgementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workflow_id: str
    acknowledged_by_user_id: str
    user_role: str
    review_notes: Optional[str] = None
    severity_at_acknowledgement: str
    classification_version: int
    is_reacknowledgement: bool
    acknowledgement_status: str
    created_at: datetime


class RiskBreachAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workflow_id: str
    assigned_user_id: Optional[str] = None
    assigned_team_id: Optional[str] = None
    responsibility_level: str
    assignment_type: str
    reassignment_reason: Optional[str] = None
    assigned_by_user_id: str
    created_at: datetime


class RiskEscalationEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workflow_id: str
    previous_level_name: str
    new_level_name: str
    trigger_type: str
    escalation_reason: str
    initiated_by_user_id: str
    execution_status: str
    created_at: datetime


class RiskResolutionActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    plan_id: str
    sequence_order: int
    action_title: str
    description: str
    assigned_to_user_id: str
    action_status: str
    progress_percentage: Decimal
    due_at: datetime
    completed_at: Optional[datetime] = None


class RiskResolutionPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workflow_id: str
    plan_code: str
    title: str
    description: str
    root_cause_hypothesis: Optional[str] = None
    proposed_actions_summary: str
    owner_user_id: str
    owner_team_id: Optional[str] = None
    priority: str
    plan_status: str
    due_at: datetime
    actions: List[RiskResolutionActionResponse] = Field(default_factory=list)


class RiskWorkflowSLAInstanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workflow_id: str
    sla_type: str
    severity: str
    start_time: datetime
    deadline: datetime
    completed_time: Optional[datetime] = None
    sla_status: str
    total_paused_seconds: float


class RiskBreachWorkflowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workflow_reference: str
    breach_event_id: str
    breach_episode_id: Optional[str] = None
    portfolio_id: str
    risk_limit_id: str
    severity: str
    classification_id: Optional[str] = None
    current_lifecycle_state: str
    current_assignment_status: str
    current_owner_user_id: Optional[str] = None
    current_owner_team_id: Optional[str] = None
    current_escalation_level_name: str
    escalation_count: int
    current_sla_status: str
    acknowledgement_status: str
    resolution_plan_status: str
    closure_status: str
    sla_start_at: datetime
    acknowledgement_due_at: Optional[datetime] = None
    resolution_due_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    mitigated_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    reopened_at: Optional[datetime] = None
    workflow_version: int
    created_at: datetime
    updated_at: datetime


class EscalationDashboardSummary(BaseModel):
    total_active_breaches: int
    open_count: int
    acknowledged_count: int
    mitigated_count: int
    closed_count: int
    reopened_count: int
    escalated_count: int
    overdue_count: int
    unassigned_count: int
    severity_breakdown: Dict[str, int]
    sla_compliance_rate: Decimal
    reopening_rate: Decimal
    escalation_frequency: Decimal
