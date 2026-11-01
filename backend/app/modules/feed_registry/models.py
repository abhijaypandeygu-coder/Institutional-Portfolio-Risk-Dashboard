"""SQLAlchemy 2.x Database Models for Module 01 — Feed Registry & Configuration.

Tables:
1. feed_registry (UUID PK, feed_code unique, classification, desired_state, record_status)
2. feed_config_versions (UUID PK, feed_id FK, version_number, config_payload, schema_version)
3. feed_schedules (id, feed_id, timezone, sessions, active_days, polling_interval)
4. feed_failover_groups (id, group_name, description, required_capabilities)
5. feed_priority_members (id, group_id, feed_id, priority, enabled)
6. feed_health_events (id, feed_id, runtime_state, latency_ms, heartbeat_at, error_code)
7. feed_lifecycle_commands (Transactional Outbox: id, feed_id, command_type, status, idempotency_key)
8. feed_audit_logs (actor, operation, resource_id, success, timestamp, details)
"""
import uuid
from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, ForeignKey, Text, JSON, Float, BigInteger, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


# ============================================================================
# Enums
# ============================================================================

class AssetClass(str, Enum):
    EQUITIES = "EQUITIES"
    FUTURES = "FUTURES"
    OPTIONS = "OPTIONS"
    FX = "FX"
    COMMODITIES = "COMMODITIES"


class FeedCategory(str, Enum):
    DIRECT_EXCHANGE = "DIRECT_EXCHANGE"
    BROKER_FEED = "BROKER_FEED"
    VENDOR_CONSOLIDATED = "VENDOR_CONSOLIDATED"
    SIMULATED = "SIMULATED"


class TransportProtocol(str, Enum):
    WEBSOCKET = "WEBSOCKET"
    TCP_SOCKET = "TCP_SOCKET"
    UDP_MULTICAST = "UDP_MULTICAST"
    HTTP_REST = "HTTP_REST"
    SIMULATED = "SIMULATED"


class FeedDesiredState(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    PAUSED = "PAUSED"
    DRAINING = "DRAINING"


class FeedRuntimeState(str, Enum):
    STOPPED = "STOPPED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    DEGRADED = "DEGRADED"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"


class FeedRecordStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"


class FeedCommandType(str, Enum):
    START = "START"
    STOP = "STOP"
    RESTART = "RESTART"
    PAUSE = "PAUSE"
    DRAIN = "DRAIN"


class CommandStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================================
# SQLAlchemy Models
# ============================================================================

class FeedRegistry(Base):
    __tablename__ = "feed_registry"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feed_code = Column(String(64), unique=True, nullable=False, index=True)
    feed_name = Column(String(128), nullable=False)
    description = Column(String(512), nullable=True)
    category = Column(String(64), nullable=False)
    asset_class = Column(String(32), default=AssetClass.EQUITIES.value, nullable=False)
    transport_protocol = Column(String(32), nullable=False)
    capabilities = Column(JSON, default=dict, nullable=False)
    desired_state = Column(String(32), default=FeedDesiredState.INACTIVE.value, nullable=False)
    record_status = Column(String(32), default=FeedRecordStatus.ACTIVE.value, nullable=False)
    current_version = Column(Integer, default=0, nullable=False)
    is_primary_eligible = Column(Boolean, default=True, nullable=False)
    is_backup_eligible = Column(Boolean, default=True, nullable=False)
    metadata_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    config_versions = relationship("FeedConfigVersion", back_populates="feed", cascade="all, delete-orphan")
    schedule = relationship("FeedSchedule", back_populates="feed", uselist=False, cascade="all, delete-orphan")
    priority_memberships = relationship("FeedPriorityMember", back_populates="feed", cascade="all, delete-orphan")
    health_events = relationship("FeedHealthEvent", back_populates="feed", cascade="all, delete-orphan")
    lifecycle_commands = relationship("FeedLifecycleCommand", back_populates="feed", cascade="all, delete-orphan")


class FeedConfigVersion(Base):
    __tablename__ = "feed_config_versions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feed_id = Column(PG_UUID(as_uuid=True), ForeignKey("feed_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    schema_version = Column(String(32), default="1.0.0", nullable=False)
    config_payload = Column(JSON, nullable=False)
    config_hash = Column(String(64), nullable=False)
    change_reason = Column(String(256), nullable=False)
    author = Column(String(128), default="system", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    feed = relationship("FeedRegistry", back_populates="config_versions")

    __table_args__ = (
        UniqueConstraint("feed_id", "version_number", name="uq_feed_config_version"),
        Index("ix_feed_version", "feed_id", "version_number"),
    )


class FeedSchedule(Base):
    __tablename__ = "feed_schedules"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feed_id = Column(PG_UUID(as_uuid=True), ForeignKey("feed_registry.id", ondelete="CASCADE"), unique=True, nullable=False)
    timezone = Column(String(64), default="Asia/Kolkata", nullable=False)
    auto_start_stop_enabled = Column(Boolean, default=True, nullable=False)
    sessions = Column(JSON, default=list, nullable=False)
    polling_interval_ms = Column(Integer, default=1000, nullable=False)
    active_days = Column(JSON, default=lambda: [0, 1, 2, 3, 4], nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    feed = relationship("FeedRegistry", back_populates="schedule")


class FeedFailoverGroup(Base):
    __tablename__ = "feed_failover_groups"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_name = Column(String(64), unique=True, nullable=False)
    description = Column(String(256), nullable=True)
    required_capabilities = Column(JSON, default=dict, nullable=False)
    failover_latency_threshold_ms = Column(Float, default=500.0, nullable=False)
    consecutive_error_threshold = Column(Integer, default=3, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    priority_members = relationship("FeedPriorityMember", back_populates="group", cascade="all, delete-orphan")


class FeedPriorityMember(Base):
    __tablename__ = "feed_priority_members"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id = Column(PG_UUID(as_uuid=True), ForeignKey("feed_failover_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    feed_id = Column(PG_UUID(as_uuid=True), ForeignKey("feed_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    priority_rank = Column(Integer, default=1, nullable=False)
    is_active_in_group = Column(Boolean, default=True, nullable=False)
    custom_weight = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    group = relationship("FeedFailoverGroup", back_populates="priority_members")
    feed = relationship("FeedRegistry", back_populates="priority_memberships")

    __table_args__ = (
        UniqueConstraint("group_id", "feed_id", name="uq_group_feed_membership"),
        UniqueConstraint("group_id", "priority_rank", name="uq_group_priority_rank"),
    )


class FeedHealthEvent(Base):
    __tablename__ = "feed_health_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    feed_id = Column(PG_UUID(as_uuid=True), ForeignKey("feed_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    runtime_state = Column(String(32), default=FeedRuntimeState.STOPPED.value, nullable=False)
    latency_ms = Column(Float, nullable=True)
    messages_received_delta = Column(BigInteger, default=0, nullable=False)
    bytes_received_delta = Column(BigInteger, default=0, nullable=False)
    error_count_delta = Column(Integer, default=0, nullable=False)
    last_heartbeat_timestamp = Column(DateTime(timezone=True), nullable=True)
    last_data_timestamp = Column(DateTime(timezone=True), nullable=True)
    error_code = Column(String(64), nullable=True)
    error_details = Column(JSON, nullable=True)

    feed = relationship("FeedRegistry", back_populates="health_events")


class FeedLifecycleCommand(Base):
    """Transactional Outbox for reliable event dispatch to M02."""
    __tablename__ = "feed_lifecycle_commands"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feed_id = Column(PG_UUID(as_uuid=True), ForeignKey("feed_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    command_type = Column(String(32), nullable=False)
    parameters = Column(JSON, default=dict, nullable=False)
    idempotency_key = Column(String(128), unique=True, nullable=False, index=True)
    status = Column(String(32), default=CommandStatus.PENDING.value, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    feed = relationship("FeedRegistry", back_populates="lifecycle_commands")


class FeedAuditLog(Base):
    __tablename__ = "feed_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor = Column(String(128), nullable=False)
    operation = Column(String(64), nullable=False)
    resource_type = Column(String(64), default="feed_registry", nullable=False)
    resource_id = Column(String(64), nullable=True, index=True)
    success = Column(Boolean, default=True, nullable=False)
    details = Column(JSON, default=dict, nullable=False)
    client_ip = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
