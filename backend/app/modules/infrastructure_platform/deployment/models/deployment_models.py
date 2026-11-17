import enum
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Boolean,
    Text,
    JSON,
    Enum as SQLEnum,
    Index,
)
from backend.app.core.database import Base


class ServiceLifecycleStatus(str, enum.Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    STOPPING = "STOPPING"


class ReleaseActivationStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVATED = "ACTIVATED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class DeploymentProfileRecord(Base):
    """Institutional deployment runtime environment profile."""
    __tablename__ = "deployment_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_code = Column(String(64), unique=True, nullable=False, index=True) # development, testing, production_local
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=False)
    configuration_snapshot = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class ReleaseHistoryRecord(Base):
    """Immutable institutional release ledger."""
    __tablename__ = "deployment_releases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    release_id = Column(String(64), unique=True, nullable=False, index=True)
    application_version = Column(String(32), nullable=False, index=True)
    build_identifier = Column(String(64), nullable=False)
    source_revision = Column(String(64), nullable=False, default="HEAD")
    schema_revision = Column(String(64), nullable=False, default="head")
    status = Column(SQLEnum(ReleaseActivationStatus), nullable=False, default=ReleaseActivationStatus.PENDING)
    manifest_payload = Column(JSON, nullable=False, default=dict)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    activated_by = Column(String(128), nullable=False, default="operator")
    validation_results = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ServiceRuntimeState(Base):
    """Current tracked operational state of application sub-services."""
    __tablename__ = "deployment_service_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    service_code = Column(String(64), unique=True, nullable=False, index=True) # backend_api, database, workers, frontend
    service_name = Column(String(128), nullable=False)
    status = Column(SQLEnum(ServiceLifecycleStatus), nullable=False, default=ServiceLifecycleStatus.STOPPED)
    endpoint = Column(String(256), nullable=True)
    process_pid = Column(Integer, nullable=True)
    is_mandatory = Column(Boolean, nullable=False, default=True)
    last_health_check = Column(DateTime(timezone=True), nullable=True)
    health_details = Column(JSON, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
