from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from backend.app.modules.reporting_attribution_audit.audit_trail.models.audit_models import (
    ActorType,
    EventCategory,
    EventSeverity,
    EventOutcome,
    IntegrityVerificationStatus,
)


class AuditActorInput(BaseModel):
    type: ActorType = Field(default=ActorType.USER, description="Actor type: USER, SYSTEM, SERVICE, etc.")
    id: str = Field(..., description="Stable user ID or service name")
    role: Optional[str] = Field(None, description="Security role or authorization context")


class ConfigurationChangeInput(BaseModel):
    configuration_id: str
    configuration_type: str
    owning_module: str
    previous_version: int
    new_version: int
    effective_at: datetime
    changed_fields: List[str]
    old_values_redacted: Optional[Dict[str, Any]] = None
    new_values_redacted: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    approval_reference: Optional[str] = None


class ApprovalDetailsInput(BaseModel):
    approval_id: str
    target_type: str
    target_id: str
    requesting_actor_id: str
    approving_actor_id: Optional[str] = None
    decision: str
    reason: Optional[str] = None
    policy_version: str = "v1.0"


class AuditEventCreateRequest(BaseModel):
    event_type: str = Field(..., description="Event type identifier, e.g. RISK_LIMIT_CHANGED")
    event_category: EventCategory = Field(..., description="Category: USER_ACTION, SYSTEM_EVENT, etc.")
    severity: EventSeverity = Field(default=EventSeverity.INFO)
    actor: AuditActorInput
    source_module: str = Field(..., description="Producing module, e.g. M01, M05, M11")
    source_feature: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    action: str = Field(..., description="Action performed, e.g. UPDATE, EXECUTE, OVERRIDE")
    outcome: EventOutcome = Field(default=EventOutcome.SUCCESS)
    reason: Optional[str] = None
    occurred_at: Optional[datetime] = None
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    parent_event_id: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    configuration_change: Optional[ConfigurationChangeInput] = None
    approval_details: Optional[ApprovalDetailsInput] = None


class AuditConfigurationChangeResponse(BaseModel):
    configuration_id: str
    configuration_type: str
    owning_module: str
    previous_version: int
    new_version: int
    effective_at: datetime
    recorded_at: datetime
    changed_fields: List[str]
    old_values_redacted: Optional[Dict[str, Any]] = None
    new_values_redacted: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    approval_reference: Optional[str] = None


class AuditApprovalResponse(BaseModel):
    approval_id: str
    target_type: str
    target_id: str
    requesting_actor_id: str
    approving_actor_id: Optional[str] = None
    decision: str
    reason: Optional[str] = None
    policy_version: str
    approval_timestamp: datetime


class AuditEventResponse(BaseModel):
    id: int
    event_id: str
    event_type: str
    event_category: EventCategory
    severity: EventSeverity
    actor_type: ActorType
    actor_id: str
    actor_role: Optional[str] = None
    source_module: str
    source_feature: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    action: str
    outcome: EventOutcome
    reason: Optional[str] = None
    occurred_at: datetime
    recorded_at: datetime
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    parent_event_id: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    schema_version: str
    chain_id: str
    chain_sequence: int
    integrity_hash: str
    previous_hash: str
    verification_status: IntegrityVerificationStatus
    configuration_change: Optional[AuditConfigurationChangeResponse] = None
    approval_details: Optional[AuditApprovalResponse] = None


class AuditSearchResponse(BaseModel):
    items: List[AuditEventResponse]
    total: int
    page: int
    page_size: int


class AuditIntegrityRunResponse(BaseModel):
    run_id: int
    chain_id: str
    verification_status: IntegrityVerificationStatus
    events_checked: int
    mismatch_count: int
    missing_sequence_count: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    result_summary: Optional[str] = None


class AuditCheckpointResponse(BaseModel):
    id: int
    chain_id: str
    highest_sequence: int
    checkpoint_hash: str
    hash_algorithm: str
    event_count: int
    created_at: datetime
    verification_status: IntegrityVerificationStatus


class AuditRetentionPolicyResponse(BaseModel):
    id: int
    policy_code: str
    policy_name: str
    event_category: EventCategory
    retention_days: int
    archive_before_expiry: bool
    policy_version: str
    status: str
