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
from backend.app.core.database import Base


class SafetyStateCategory(str, enum.Enum):
    NORMAL = "NORMAL"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    UNKNOWN = "UNKNOWN"


class KillSwitchScopeType(str, enum.Enum):
    GLOBAL = "GLOBAL"
    ADAPTER = "ADAPTER"
    ROUTE = "ROUTE"
    INSTRUMENT = "INSTRUMENT"
    INTEGRATION = "INTEGRATION"


class KillSwitchState(str, enum.Enum):
    INACTIVE = "INACTIVE"
    ACTIVE = "ACTIVE"
    REACTIVATION_PENDING = "REACTIVATION_PENDING"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


class IncidentSeverity(str, enum.Enum):
    SEV1_CRITICAL = "SEV1_CRITICAL"
    SEV2_HIGH = "SEV2_HIGH"
    SEV3_MEDIUM = "SEV3_MEDIUM"
    SEV4_LOW = "SEV4_LOW"


class IncidentStatus(str, enum.Enum):
    DETECTED = "DETECTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    CONTAINMENT_IN_PROGRESS = "CONTAINMENT_IN_PROGRESS"
    CONTAINED = "CONTAINED"
    INVESTIGATION = "INVESTIGATION"
    RECOVERY_IN_PROGRESS = "RECOVERY_IN_PROGRESS"
    MONITORING = "MONITORING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class ExecutionDecisionOutcome(str, enum.Enum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNKNOWN = "UNKNOWN"


class KillSwitchRecord(Base):
    """Authoritative persistent record of global and scoped emergency kill switches."""
    __tablename__ = "safety_kill_switches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    switch_code = Column(String(64), unique=True, nullable=False, index=True)
    switch_name = Column(String(128), nullable=False)
    scope_type = Column(SQLEnum(KillSwitchScopeType), nullable=False, default=KillSwitchScopeType.GLOBAL)
    scope_id = Column(String(128), nullable=True, index=True)
    state = Column(SQLEnum(KillSwitchState), nullable=False, default=KillSwitchState.INACTIVE)
    activation_reason = Column(Text, nullable=True)
    activated_by = Column(String(128), nullable=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    reactivation_requested_by = Column(String(128), nullable=True)
    reactivation_requested_at = Column(DateTime(timezone=True), nullable=True)
    approved_by = Column(String(128), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class SafetyStateRecord(Base):
    """Component-level and operation-level operational safety state registry."""
    __tablename__ = "safety_component_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    component_id = Column(String(128), unique=True, nullable=False, index=True)
    scope_type = Column(String(64), nullable=False, default="COMPONENT")
    scope_id = Column(String(128), nullable=True)
    state = Column(SQLEnum(SafetyStateCategory), nullable=False, default=SafetyStateCategory.NORMAL)
    reason_code = Column(String(64), nullable=False, default="NOMINAL_OPERATION")
    description = Column(Text, nullable=True)
    source_module = Column(String(64), nullable=False, default="M15.12")
    policy_version = Column(String(32), nullable=False, default="1.0.0")
    revision = Column(Integer, nullable=False, default=1)
    effective_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_validated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class IncidentRecord(Base):
    """Institutional operational safety incident log."""
    __tablename__ = "safety_incidents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_reference = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(SQLEnum(IncidentSeverity), nullable=False, default=IncidentSeverity.SEV3_MEDIUM)
    status = Column(SQLEnum(IncidentStatus), nullable=False, default=IncidentStatus.DETECTED)
    affected_scope = Column(String(128), nullable=False, default="GLOBAL")
    detection_source = Column(String(128), nullable=False, default="automated_monitor")
    assigned_to = Column(String(128), nullable=True)
    detected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    contained_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    correlation_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ExecutionSafetyDecisionRecord(Base):
    """Immutable audit log of pre-dispatch safety gateway decisions."""
    __tablename__ = "safety_execution_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(64), unique=True, nullable=False, index=True)
    order_reference = Column(String(128), nullable=True, index=True)
    instrument_id = Column(String(64), nullable=False)
    adapter_id = Column(String(64), nullable=False)
    decision = Column(SQLEnum(ExecutionDecisionOutcome), nullable=False)
    reason_codes = Column(JSON, nullable=False, default=list)
    safety_state_revision = Column(Integer, nullable=False, default=1)
    policy_version = Column(String(32), nullable=False, default="1.0.0")
    risk_decision_reference = Column(String(64), nullable=True)
    evaluated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    valid_until = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
