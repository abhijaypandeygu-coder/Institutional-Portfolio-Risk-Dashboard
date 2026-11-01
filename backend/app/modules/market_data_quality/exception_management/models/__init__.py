"""
M03.08 Exception Management: SQLAlchemy 2.x Database Models.
Implements 14 persistent entities covering exceptions, observation links,
findings links, quarantine records, rejection records, correction proposals,
field changes, approvals, replay requests, per-record results, investigation notes,
audit events, reason codes, and policies.
"""
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from decimal import Decimal

from sqlalchemy import (
    String, Integer, BigInteger, DateTime, Numeric, JSON, Boolean, Text, Index, UniqueConstraint, ForeignKey
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def compute_payload_hash(payload_data: Any) -> str:
    """Computes a SHA-256 digest of payload for tamper detection."""
    import json
    if isinstance(payload_data, (dict, list)):
        serialized = json.dumps(payload_data, sort_keys=True, default=str)
    else:
        serialized = str(payload_data)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# 1. Exception Reason Codes
class ExceptionReasonCode(Base):
    __tablename__ = "m03_exception_reason_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(32), default="HIGH", nullable=False)
    recoverability: Mapped[str] = mapped_column(String(32), default="RECOVERABLE", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


# 2. Exception Policies
class ExceptionPolicy(Base):
    __tablename__ = "m03_exception_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    policy_name: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    configuration: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


# 3. Primary Exception Case
class ExceptionRecord(Base):
    __tablename__ = "m03_exception_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exception_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"EXC_{uuid.uuid4().hex[:12].upper()}")
    exception_reference: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    exception_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(32), default="HIGH", nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(16), default="P1", nullable=False, index=True)
    workflow_status: Mapped[str] = mapped_column(String(32), default="OPEN", nullable=False, index=True)
    
    assigned_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    assigned_group: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    summary: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    creation_source: Mapped[str] = mapped_column(String(32), default="AUTOMATED", nullable=False)
    correlation_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)

    policy_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("m03_exception_policies.id", ondelete="SET NULL"), nullable=True)
    policy_version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    resolution_outcome: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    resolution_justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# 4. Observation Links
class ExceptionObservation(Base):
    __tablename__ = "m03_exception_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exception_id: Mapped[str] = mapped_column(String(64), ForeignKey("m03_exception_records.exception_id", ondelete="CASCADE"), nullable=False, index=True)
    observation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    feed_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    exchange: Mapped[Optional[str]] = mapped_column(String(16), default="NSE", nullable=True)
    data_origin: Mapped[str] = mapped_column(String(32), default="REAL", nullable=False)  # REAL vs SIMULATED

    original_payload_reference: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    payload_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    record_disposition: Mapped[str] = mapped_column(String(32), default="QUARANTINED", nullable=False, index=True)

    source_event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ingestion_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("exception_id", "observation_id", name="uq_exc_observation"),
    )


# 5. Upstream Findings Links
class ExceptionFinding(Base):
    __tablename__ = "m03_exception_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exception_id: Mapped[str] = mapped_column(String(64), ForeignKey("m03_exception_records.exception_id", ondelete="CASCADE"), nullable=False, index=True)
    source_module: Mapped[str] = mapped_column(String(32), default="M03", nullable=False)
    source_feature: Mapped[str] = mapped_column(String(32), nullable=False)  # e.g. M03.02, M03.04
    finding_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    finding_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_severity: Mapped[str] = mapped_column(String(32), nullable=False)
    finding_reference: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    evidence: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("exception_id", "finding_id", name="uq_exc_finding"),
    )


# 6. Quarantine Records
class QuarantineRecord(Base):
    __tablename__ = "m03_quarantine_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quarantine_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"QRN_{uuid.uuid4().hex[:12].upper()}")
    exception_id: Mapped[str] = mapped_column(String(64), ForeignKey("m03_exception_records.exception_id", ondelete="CASCADE"), nullable=False, index=True)
    observation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    quarantine_reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    quarantine_reason: Mapped[str] = mapped_column(Text, nullable=False)
    quarantined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    quarantined_by: Mapped[str] = mapped_column(String(64), default="system", nullable=False)

    original_payload_reference: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    payload_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    release_status: Mapped[str] = mapped_column(String(32), default="QUARANTINED", nullable=False, index=True)
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    released_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    release_authorization_reference: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)


# 7. Rejection Records
class RejectionRecord(Base):
    __tablename__ = "m03_rejection_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rejection_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"REJ_{uuid.uuid4().hex[:12].upper()}")
    exception_id: Mapped[str] = mapped_column(String(64), ForeignKey("m03_exception_records.exception_id", ondelete="CASCADE"), nullable=False, index=True)
    observation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    reason_code_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("m03_exception_reason_codes.id", ondelete="SET NULL"), nullable=True)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_details: Mapped[str] = mapped_column(Text, nullable=False)
    recoverability: Mapped[str] = mapped_column(String(32), default="RECOVERABLE", nullable=False)

    rejected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    rejected_by: Mapped[str] = mapped_column(String(64), default="system", nullable=False)
    policy_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    original_payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    subsequent_remediation_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


# 8. Correction Proposals
class CorrectionProposal(Base):
    __tablename__ = "m03_correction_proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    correction_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"COR_{uuid.uuid4().hex[:12].upper()}")
    exception_id: Mapped[str] = mapped_column(String(64), ForeignKey("m03_exception_records.exception_id", ondelete="CASCADE"), nullable=False, index=True)
    observation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    correction_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    correction_category: Mapped[str] = mapped_column(String(64), nullable=False)
    correction_reason: Mapped[str] = mapped_column(Text, nullable=False)
    
    proposed_by: Mapped[str] = mapped_column(String(64), nullable=False)
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    approval_status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False, index=True)
    correction_status: Mapped[str] = mapped_column(String(32), default="DRAFT", nullable=False, index=True)

    source_payload_reference: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    resulting_payload_reference: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    resulting_payload_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    provenance_reference: Mapped[str] = mapped_column(String(256), nullable=False)
    provenance_source: Mapped[str] = mapped_column(String(64), nullable=False)  # REAL_PROVIDER vs AUTHORITATIVE_REF vs SYNTHETIC_SIM

    __table_args__ = (
        UniqueConstraint("exception_id", "observation_id", "correction_version", name="uq_exc_obs_cor_version"),
    )


# 9. Correction Field Changes (Before-and-After Values)
class CorrectionFieldChange(Base):
    __tablename__ = "m03_correction_field_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    correction_id: Mapped[str] = mapped_column(String(64), ForeignKey("m03_correction_proposals.correction_id", ondelete="CASCADE"), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(64), nullable=False)
    before_value: Mapped[str] = mapped_column(Text, nullable=False)
    after_value: Mapped[str] = mapped_column(Text, nullable=False)
    field_data_type: Mapped[str] = mapped_column(String(32), default="DECIMAL", nullable=False)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    provenance_reference: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)


# 10. Correction Approvals
class CorrectionApproval(Base):
    __tablename__ = "m03_correction_approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    correction_id: Mapped[str] = mapped_column(String(64), ForeignKey("m03_correction_proposals.correction_id", ondelete="CASCADE"), nullable=False, index=True)
    approval_status: Mapped[str] = mapped_column(String(32), nullable=False)
    approver_id: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_reason: Mapped[str] = mapped_column(Text, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    policy_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


# 11. Replay Requests
class ReplayRequest(Base):
    __tablename__ = "m03_replay_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    replay_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: f"RPL_{uuid.uuid4().hex[:12].upper()}")
    exception_id: Mapped[str] = mapped_column(String(64), ForeignKey("m03_exception_records.exception_id", ondelete="CASCADE"), nullable=False, index=True)
    replay_mode: Mapped[str] = mapped_column(String(32), default="SINGLE_RECORD", nullable=False)
    replay_status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)

    requested_by: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    correction_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    correction_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    replay_reason: Mapped[str] = mapped_column(Text, nullable=False)

    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    integration_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


# 12. Replay Record Results (Per-Record Batch Results)
class ReplayRecordResult(Base):
    __tablename__ = "m03_replay_record_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    replay_id: Mapped[str] = mapped_column(String(64), ForeignKey("m03_replay_requests.replay_id", ondelete="CASCADE"), nullable=False, index=True)
    observation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    execution_status: Mapped[str] = mapped_column(String(32), nullable=False)  # SUCCEEDED, FAILED, WARNING
    downstream_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    result_details: Mapped[str] = mapped_column(Text, nullable=False)
    failure_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


# 13. Investigation Notes
class ExceptionNote(Base):
    __tablename__ = "m03_exception_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    note_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=lambda: f"NOT_{uuid.uuid4().hex[:12].upper()}")
    exception_id: Mapped[str] = mapped_column(String(64), ForeignKey("m03_exception_records.exception_id", ondelete="CASCADE"), nullable=False, index=True)
    author_id: Mapped[str] = mapped_column(String(64), nullable=False)
    note_type: Mapped[str] = mapped_column(String(32), default="INVESTIGATION", nullable=False)
    note_content: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_reference: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


# 14. Append-Only Audit Events
class ExceptionAuditEvent(Base):
    __tablename__ = "m03_exception_audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audit_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=lambda: f"AUD_{uuid.uuid4().hex[:12].upper()}")
    exception_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    observation_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    previous_state: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    new_state: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    metadata_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
