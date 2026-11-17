import enum
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Boolean,
    Text,
    JSON,
    ForeignKey,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class ActorType(str, enum.Enum):
    USER = "USER"
    SYSTEM = "SYSTEM"
    SERVICE = "SERVICE"
    SCHEDULED_JOB = "SCHEDULED_JOB"
    EXTERNAL_INTEGRATION = "EXTERNAL_INTEGRATION"


class EventCategory(str, enum.Enum):
    USER_ACTION = "USER_ACTION"
    SYSTEM_EVENT = "SYSTEM_EVENT"
    CONFIGURATION_CHANGE = "CONFIGURATION_CHANGE"
    APPROVAL = "APPROVAL"
    AUTHORIZATION_DECISION = "AUTHORIZATION_DECISION"
    OPERATIONAL_COMMAND = "OPERATIONAL_COMMAND"
    CONTROL_DECISION = "CONTROL_DECISION"
    DATA_ACCESS = "DATA_ACCESS"
    REPORTING_EVENT = "REPORTING_EVENT"
    SECURITY_EVENT = "SECURITY_EVENT"
    INTEGRITY_EVENT = "INTEGRITY_EVENT"
    RETENTION_EVENT = "RETENTION_EVENT"


class EventSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class EventOutcome(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    REJECTED = "REJECTED"
    DENIED = "DENIED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class IntegrityVerificationStatus(str, enum.Enum):
    VERIFIED = "VERIFIED"
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    INTEGRITY_UNKNOWN = "INTEGRITY_UNKNOWN"


class AuditEvent(Base):
    __tablename__ = "m14_audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(100), unique=True, nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    event_category = Column(SQLEnum(EventCategory), nullable=False, index=True)
    severity = Column(SQLEnum(EventSeverity), nullable=False, default=EventSeverity.INFO, index=True)
    
    # Actor Context
    actor_type = Column(SQLEnum(ActorType), nullable=False, default=ActorType.USER, index=True)
    actor_id = Column(String(100), nullable=False, index=True)
    actor_role = Column(String(100), nullable=True)

    # Source & Target
    source_module = Column(String(50), nullable=False, index=True) # e.g. M01, M05, M11, M14
    source_feature = Column(String(50), nullable=True)
    target_type = Column(String(100), nullable=True, index=True)   # e.g. PORTFOLIO, RISK_LIMIT, FEED
    target_id = Column(String(100), nullable=True, index=True)
    
    # Action & Outcome
    action = Column(String(100), nullable=False)
    outcome = Column(SQLEnum(EventOutcome), nullable=False, default=EventOutcome.SUCCESS, index=True)
    reason = Column(Text, nullable=True)

    # Time Semantics (Event occurrence vs recorded time)
    occurred_at = Column(DateTime(timezone=True), nullable=False, index=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    # Correlation & Causation
    correlation_id = Column(String(100), nullable=True, index=True)
    causation_id = Column(String(100), nullable=True, index=True)
    parent_event_id = Column(String(100), nullable=True, index=True)

    # Payload & Schema Version
    payload = Column(JSON, nullable=True)
    schema_version = Column(String(50), nullable=False, default="v1.0")

    # Cryptographic Hash Chain & Tamper Resistance
    chain_id = Column(String(100), nullable=False, default="GLOBAL_CHAIN", index=True)
    chain_sequence = Column(Integer, nullable=False, index=True)
    integrity_hash = Column(String(64), nullable=False) # SHA-256 of canonical event representation
    previous_hash = Column(String(64), nullable=False)  # Prior event's SHA-256
    verification_status = Column(SQLEnum(IntegrityVerificationStatus), nullable=False, default=IntegrityVerificationStatus.VERIFIED)

    # Relationships
    config_change = relationship("AuditConfigurationChange", back_populates="event", uselist=False, cascade="all, delete-orphan")
    approval_details = relationship("AuditApprovalEvent", back_populates="event", uselist=False, cascade="all, delete-orphan")


class AuditConfigurationChange(Base):
    __tablename__ = "m14_audit_configuration_changes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(100), ForeignKey("m14_audit_events.event_id", ondelete="CASCADE"), nullable=False, index=True)
    configuration_id = Column(String(100), nullable=False, index=True)
    configuration_type = Column(String(100), nullable=False) # e.g. RISK_LIMIT, FEED_CONFIG, PORTFOLIO_MANDATE
    owning_module = Column(String(50), nullable=False)
    previous_version = Column(Integer, nullable=False, default=0)
    new_version = Column(Integer, nullable=False, default=1)
    effective_at = Column(DateTime(timezone=True), nullable=False)
    recorded_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    changed_fields = Column(JSON, nullable=False) # List[str]
    old_values_redacted = Column(JSON, nullable=True)
    new_values_redacted = Column(JSON, nullable=True)
    reason = Column(Text, nullable=True)
    approval_reference = Column(String(100), nullable=True)

    event = relationship("AuditEvent", back_populates="config_change")


class AuditApprovalEvent(Base):
    __tablename__ = "m14_audit_approval_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(100), ForeignKey("m14_audit_events.event_id", ondelete="CASCADE"), nullable=False, index=True)
    approval_id = Column(String(100), nullable=False, index=True)
    target_type = Column(String(100), nullable=False)
    target_id = Column(String(100), nullable=False)
    requesting_actor_id = Column(String(100), nullable=False)
    approving_actor_id = Column(String(100), nullable=True)
    decision = Column(String(50), nullable=False) # APPROVED, REJECTED, WITHDRAWN, EXPIRED, PENDING
    reason = Column(Text, nullable=True)
    policy_version = Column(String(50), nullable=False, default="v1.0")
    approval_timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    event = relationship("AuditEvent", back_populates="approval_details")


class AuditChainCheckpoint(Base):
    __tablename__ = "m14_audit_chain_checkpoints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chain_id = Column(String(100), nullable=False, index=True)
    highest_sequence = Column(Integer, nullable=False)
    checkpoint_hash = Column(String(64), nullable=False)
    hash_algorithm = Column(String(50), nullable=False, default="SHA-256")
    checkpoint_version = Column(String(50), nullable=False, default="v1.0")
    event_count = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    external_checkpoint_reference = Column(String(500), nullable=True)
    verification_status = Column(SQLEnum(IntegrityVerificationStatus), nullable=False, default=IntegrityVerificationStatus.VERIFIED)


class AuditIntegrityRun(Base):
    __tablename__ = "m14_audit_integrity_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chain_id = Column(String(100), nullable=False, index=True)
    verification_scope = Column(String(100), nullable=False, default="FULL_CHAIN")
    start_sequence = Column(Integer, nullable=False, default=1)
    end_sequence = Column(Integer, nullable=False)
    verification_status = Column(SQLEnum(IntegrityVerificationStatus), nullable=False)
    events_checked = Column(Integer, nullable=False, default=0)
    mismatch_count = Column(Integer, nullable=False, default=0)
    missing_sequence_count = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
    result_summary = Column(Text, nullable=True)


class AuditRetentionPolicy(Base):
    __tablename__ = "m14_audit_retention_policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    policy_code = Column(String(100), unique=True, nullable=False, index=True)
    policy_name = Column(String(200), nullable=False)
    event_category = Column(SQLEnum(EventCategory), nullable=False)
    retention_days = Column(Integer, nullable=False, default=2555) # 7 years default
    archive_before_expiry = Column(Boolean, nullable=False, default=True)
    policy_version = Column(String(50), nullable=False, default="v1.0")
    status = Column(String(50), nullable=False, default="ACTIVE")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class AuditLegalHold(Base):
    __tablename__ = "m14_audit_legal_holds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hold_reference = Column(String(100), unique=True, nullable=False, index=True)
    scope = Column(String(200), nullable=False)
    reason = Column(Text, nullable=False)
    created_by = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    released_by = Column(String(100), nullable=True)
    released_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), nullable=False, default="ACTIVE")
