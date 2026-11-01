"""
Pydantic 2.x schemas for M03.08 Exception Management.
Defines strict validation request/response payloads with Decimal preservation.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# Common Types
class FindingIntakeSchema(BaseModel):
    finding_id: str
    source_module: str = "M03"
    source_feature: str
    finding_code: str
    source_severity: str = "HIGH"
    feed_id: str
    instrument_id: str
    listing_id: Optional[str] = None
    exchange: Optional[str] = "NSE"
    data_origin: str = "REAL"  # REAL vs SIMULATED
    observation_id: str
    source_event_timestamp: datetime
    ingestion_timestamp: Optional[datetime] = None
    affected_fields: Optional[List[str]] = None
    observed_value: Optional[str] = None
    expected_value: Optional[str] = None
    rule_reference: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None
    raw_payload: Optional[Dict[str, Any]] = None


class ExceptionCreateRequest(BaseModel):
    category: str
    exception_type: str
    severity: str = "HIGH"
    priority: str = "P1"
    summary: str
    description: str
    creation_source: str = "AUTOMATED"
    findings: List[FindingIntakeSchema]
    policy_code: Optional[str] = None


class ExceptionAssignmentUpdate(BaseModel):
    assigned_user_id: str
    assigned_group: Optional[str] = None


class ExceptionPriorityUpdate(BaseModel):
    priority: str
    reason: str


class ExceptionNoteCreate(BaseModel):
    note_content: str
    note_type: str = "INVESTIGATION"
    evidence_reference: Optional[str] = None


class ExceptionResolveRequest(BaseModel):
    resolution_outcome: str
    justification: str


class ExceptionDismissRequest(BaseModel):
    justification: str


class ExceptionReopenRequest(BaseModel):
    reason: str


class QuarantineCreateRequest(BaseModel):
    observation_id: str
    quarantine_reason_code: str
    quarantine_reason: str
    original_payload_reference: Optional[str] = None
    payload_snapshot: Optional[Dict[str, Any]] = None


class QuarantineReleaseRequest(BaseModel):
    justification: str
    release_authorization_reference: str


class RejectionCreateRequest(BaseModel):
    observation_id: str
    reason_code: str
    reason_details: str
    recoverability: str = "RECOVERABLE"
    policy_reference: Optional[str] = None


class FieldChangeSchema(BaseModel):
    field_name: str
    before_value: str
    after_value: str
    field_data_type: str = "DECIMAL"
    change_reason: str
    provenance_reference: Optional[str] = None


class CorrectionProposalCreate(BaseModel):
    observation_id: str
    correction_category: str
    correction_reason: str
    provenance_reference: str
    provenance_source: str = "REAL_PROVIDER"  # REAL_PROVIDER vs AUTHORITATIVE_REF vs SYNTHETIC_SIM
    field_changes: List[FieldChangeSchema]
    resulting_payload_snapshot: Optional[Dict[str, Any]] = None


class CorrectionApprovalRequest(BaseModel):
    approval_reason: str
    policy_reference: Optional[str] = None


class CorrectionRejectRequest(BaseModel):
    rejection_reason: str


class ReplaySubmitRequest(BaseModel):
    replay_mode: str = "SINGLE_RECORD"
    correction_id: Optional[str] = None
    replay_reason: str
    idempotency_key: Optional[str] = None


class ReasonCodeCreate(BaseModel):
    code: str
    name: str
    description: str
    category: str
    severity: str = "HIGH"
    recoverability: str = "RECOVERABLE"
    is_active: bool = True


class ExceptionPolicyCreate(BaseModel):
    policy_code: str
    policy_name: str
    policy_version: str = "1.0.0"
    configuration: Dict[str, Any]
    effective_from: Optional[datetime] = None
    is_active: bool = True


# Response Schemas
class ExceptionRecordResponse(BaseModel):
    id: int
    exception_id: str
    exception_reference: str
    category: str
    exception_type: str
    severity: str
    priority: str
    workflow_status: str
    assigned_user_id: Optional[str]
    assigned_group: Optional[str]
    summary: str
    description: str
    creation_source: str
    correlation_key: str
    policy_version: str
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]
    resolved_by: Optional[str]
    resolution_outcome: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class ExceptionObservationResponse(BaseModel):
    id: int
    exception_id: str
    observation_id: str
    feed_id: str
    instrument_id: str
    exchange: Optional[str]
    data_origin: str
    record_disposition: str
    payload_hash: str
    source_event_timestamp: datetime
    ingestion_timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class QuarantineRecordResponse(BaseModel):
    id: int
    quarantine_id: str
    exception_id: str
    observation_id: str
    quarantine_reason_code: str
    quarantine_reason: str
    quarantined_at: datetime
    quarantined_by: str
    release_status: str
    released_at: Optional[datetime]
    released_by: Optional[str]
    release_authorization_reference: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class RejectionRecordResponse(BaseModel):
    id: int
    rejection_id: str
    exception_id: str
    observation_id: str
    reason_code: str
    reason_details: str
    recoverability: str
    rejected_at: datetime
    rejected_by: str
    policy_reference: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class CorrectionProposalResponse(BaseModel):
    id: int
    correction_id: str
    exception_id: str
    observation_id: str
    correction_version: int
    correction_category: str
    correction_reason: str
    proposed_by: str
    proposed_at: datetime
    approval_status: str
    correction_status: str
    provenance_reference: str
    provenance_source: str

    model_config = ConfigDict(from_attributes=True)


class ReplayRequestResponse(BaseModel):
    id: int
    replay_id: str
    exception_id: str
    replay_mode: str
    replay_status: str
    idempotency_key: str
    requested_by: str
    requested_at: datetime
    correction_id: Optional[str]
    replay_reason: str
    retry_count: int
    completed_at: Optional[datetime]
    integration_reference: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class ExceptionSummaryMetrics(BaseModel):
    total_exceptions: int
    open_exceptions: int
    in_review_exceptions: int
    awaiting_approval_exceptions: int
    resolved_exceptions: int
    quarantined_records: int
    rejected_records: int
    total_replays: int
    successful_replays: int
    failed_replays: int

