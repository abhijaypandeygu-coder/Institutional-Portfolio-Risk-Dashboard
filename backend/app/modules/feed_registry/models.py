"""SQLAlchemy Database Models for Module 01 — Feed Registry & Configuration.

Tables:
1. feed_registry (UUID PK, feed_code unique, classification, desired_state, record_status)
2. feed_config_versions (UUID PK, feed_id FK, version_number, config_json, schema_version)
3. feed_schedules (id, feed_id, timezone, session_start/end, active_days, polling_interval)
4. feed_failover_groups (id, group_name, description, required_capabilities)
5. feed_priority_members (id, group_id, feed_id, priority, enabled)
6. feed_health_events (id, feed_id, runtime_state, latency_ms, heartbeat_at, error_code)
7. feed_lifecycle_commands (Transactional Outbox: id, feed_id, command_type, status, idempotency_key)
8. feed_audit_logs (actor, operation, resource_id, success, timestamp, details)
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, ForeignKey, Text, JSON, Float, BigInteger, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class FeedRegistry(Base):
    __tablename__ = "feed_registry"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    feed_code = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(String(512), nullable=True)
    provider_name = Column(String(128), nullable=False)
    provider_type = Column(String(64), nullable=False)  # BROKER_FEED, DIRECT_EXCHANGE, VENDOR, SIMULATOR
    feed_category = Column(String(64), nullable=False)  # MARKET_DATA, ORDER_BOOK, TRADE_DATA, HISTORICAL
    asset_class = Column(String(32), default="EQUITIES", nullable=False)
    transport = Column(String(32), default="WEBSOCKET", nullable=False)  # WEBSOCKET, TCP, UDP_MULTICAST, REST
    capabilities = Column(JSON, default=list, nullable=False)  # ["LTP", "OHLCV", "LEVEL_1", "LEVEL_2", "TRADE_TICKS"]
    desired_state = Column(String(32), default="DISABLED", nullable=False)  # ENABLED, DISABLED
    record_status = Column(String(32), default="ACTIVE", nullable=False)  # ACTIVE, ARCHIVED
    current_version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(String(128), default="system", nullable=False)
    updated_by = Column(String(128), default="system", nullable=False)
    archived_at = Column(DateTime, nullable=True)

    # Relationships
    config_versions = relationship("FeedConfigVersion", back_populates="feed", cascade="all, delete-orphan")
    schedules = relationship("FeedSchedule", back_populates="feed", cascade="all, delete-orphan")
    priority_memberships = relationship("FeedPriorityMember", back_populates="feed", cascade="all, delete-orphan")
    health_events = relationship("FeedHealthEvent", back_populates="feed", cascade="all, delete-orphan")
    lifecycle_commands = relationship("FeedLifecycleCommand", back_populates="feed", cascade="all, delete-orphan")


class FeedConfigVersion(Base):
    __tablename__ = "feed_config_versions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    feed_id = Column(String(36), ForeignKey("feed_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    config_json = Column(JSON, nullable=False)
    schema_version = Column(String(32), default="1.0.0", nullable=False)
    change_description = Column(String(255), nullable=False)
    created_by = Column(String(128), default="system", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    feed = relationship("FeedRegistry", back_populates="config_versions")

    __table_args__ = (
        UniqueConstraint("feed_id", "version_number", name="uq_feed_config_version"),
        Index("ix_feed_version", "feed_id", "version_number"),
    )


class FeedSchedule(Base):
    __tablename__ = "feed_schedules"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    feed_id = Column(String(36), ForeignKey("feed_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    schedule_name = Column(String(128), nullable=False)
    timezone = Column(String(64), default="Asia/Kolkata", nullable=False)
    schedule_type = Column(String(32), default="MARKET_SESSION", nullable=False)  # MARKET_SESSION, CONTINUOUS, POLLING
    session_start = Column(String(8), default="09:15:00", nullable=False)
    session_end = Column(String(8), default="15:30:00", nullable=False)
    polling_interval_seconds = Column(Integer, nullable=True)
    active_days = Column(JSON, default=lambda: ["MON", "TUE", "WED", "THU", "FRI"], nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    feed = relationship("FeedRegistry", back_populates="schedules")


class FeedFailoverGroup(Base):
    __tablename__ = "feed_failover_groups"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    group_name = Column(String(128), unique=True, nullable=False)
    description = Column(String(512), nullable=True)
    required_capabilities = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    members = relationship("FeedPriorityMember", back_populates="group", cascade="all, delete-orphan")


class FeedPriorityMember(Base):
    __tablename__ = "feed_priority_members"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    group_id = Column(String(36), ForeignKey("feed_failover_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    feed_id = Column(String(36), ForeignKey("feed_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    priority = Column(Integer, default=1, nullable=False)  # 1 = primary, 2 = secondary, etc.
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    group = relationship("FeedFailoverGroup", back_populates="members")
    feed = relationship("FeedRegistry", back_populates="priority_memberships")

    __table_args__ = (
        UniqueConstraint("group_id", "feed_id", name="uq_group_feed_membership"),
        UniqueConstraint("group_id", "priority", name="uq_group_priority_slot"),
    )


class FeedHealthEvent(Base):
    __tablename__ = "feed_health_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    feed_id = Column(String(36), ForeignKey("feed_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    runtime_state = Column(String(32), default="STOPPED", nullable=False)  # STOPPED, CONNECTING, CONNECTED, DEGRADED, ERROR, UNKNOWN
    latency_ms = Column(Float, nullable=True)
    heartbeat_at = Column(DateTime, nullable=True)
    last_data_at = Column(DateTime, nullable=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(String(512), nullable=True)
    observed_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    feed = relationship("FeedRegistry", back_populates="health_events")


class FeedLifecycleCommand(Base):
    """Transactional Outbox for reliable event dispatch to M02."""
    __tablename__ = "feed_lifecycle_commands"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    feed_id = Column(String(36), ForeignKey("feed_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    command_type = Column(String(32), nullable=False)  # START, STOP, RESTART, ENABLE, DISABLE
    command_status = Column(String(32), default="PENDING", nullable=False)  # PENDING, DISPATCHED, COMPLETED, FAILED
    idempotency_key = Column(String(128), unique=True, nullable=False, index=True)
    requested_by = Column(String(128), nullable=False)
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    dispatched_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(String(512), nullable=True)

    feed = relationship("FeedRegistry", back_populates="lifecycle_commands")


class FeedAuditLog(Base):
    __tablename__ = "feed_audit_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    actor = Column(String(128), nullable=False)
    operation = Column(String(64), nullable=False)
    resource_type = Column(String(64), default="FEED", nullable=False)
    resource_id = Column(String(64), nullable=False, index=True)
    success = Column(Boolean, default=True, nullable=False)
    details = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

