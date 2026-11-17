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


class HealthStatus(str, enum.Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"
    NOT_CONFIGURED = "NOT_CONFIGURED"


class IncidentSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


class IncidentStatus(str, enum.Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class SystemMetricSample(Base):
    """Normalized time-series operational measurement sample (CPU, Memory, DB, Latency)."""
    __tablename__ = "sys_metric_samples"
    __table_args__ = (
        Index("ix_sys_metric_name_time", "metric_name", "measured_at"),
        Index("ix_sys_metric_comp_time", "component_id", "measured_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_name = Column(String(64), nullable=False, index=True) # cpu_utilization_pct, memory_rss_mb, db_query_p95_ms
    component_id = Column(String(64), nullable=False, index=True) # system, app_main, postgres, market_worker
    component_type = Column(String(32), nullable=False, default="SERVICE") # HOST, PROCESS, DATABASE, WORKER
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String(16), nullable=False) # %, MB, ms, count
    measurement_status = Column(String(16), nullable=False, default="VALID") # VALID, STALE, DEGRADED
    source = Column(String(32), nullable=False, default="PSUTIL") # PSUTIL, SQLALCHEMY, PG_STAT, INTERNAL
    labels = Column(JSON, nullable=True)
    measured_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    collected_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class SystemHealthCheckRecord(Base):
    """Durable record of dependency health checks (DB, Storage, Config, Workers)."""
    __tablename__ = "sys_health_checks"
    __table_args__ = (
        Index("ix_health_check_comp_time", "component_id", "checked_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    check_name = Column(String(64), nullable=False, index=True)
    component_id = Column(String(64), nullable=False, index=True)
    component_type = Column(String(32), nullable=False, default="DEPENDENCY")
    status = Column(SQLEnum(HealthStatus), nullable=False, default=HealthStatus.HEALTHY, index=True)
    latency_ms = Column(Float, nullable=False, default=0.0)
    is_required = Column(Boolean, nullable=False, default=True)
    details = Column(JSON, nullable=True)
    error_code = Column(String(64), nullable=True)
    checked_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)


class MonitoredProcessRecord(Base):
    """Process and background worker registration with heartbeat and uptime tracking."""
    __tablename__ = "sys_monitored_processes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    component_id = Column(String(64), unique=True, nullable=False, index=True) # main_api, worker_key_rotation
    process_instance_id = Column(String(64), nullable=False)
    process_name = Column(String(128), nullable=False)
    process_id = Column(Integer, nullable=True)
    process_type = Column(String(32), nullable=False, default="APP_PROCESS") # APP_PROCESS, WORKER, SCHEDULER
    status = Column(SQLEnum(HealthStatus), nullable=False, default=HealthStatus.HEALTHY, index=True)
    restart_count = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_heartbeat_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_restart_at = Column(DateTime, nullable=True)


class MonitoringThresholdRecord(Base):
    """Operational resource thresholds with warning/critical limits and hysteresis."""
    __tablename__ = "sys_monitoring_thresholds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    threshold_id = Column(String(64), unique=True, nullable=False, index=True)
    threshold_name = Column(String(128), nullable=False)
    metric_name = Column(String(64), nullable=False, index=True)
    component_id = Column(String(64), nullable=False, default="system")
    warning_threshold = Column(Float, nullable=False)
    critical_threshold = Column(Float, nullable=False)
    recovery_threshold = Column(Float, nullable=False)
    evaluation_window_seconds = Column(Integer, nullable=False, default=60)
    enabled = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class OperationalIncidentRecord(Base):
    """Tracked operational saturation or outage incidents."""
    __tablename__ = "sys_operational_incidents"
    __table_args__ = (
        Index("ix_op_incident_status_time", "status", "opened_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String(64), unique=True, nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True) # HIGH_CPU, MEMORY_SATURATION, DB_POOL_EXHAUSTION
    component_id = Column(String(64), nullable=False, index=True)
    severity = Column(SQLEnum(IncidentSeverity), nullable=False, default=IncidentSeverity.WARNING, index=True)
    status = Column(SQLEnum(IncidentStatus), nullable=False, default=IncidentStatus.OPEN, index=True)
    observed_value = Column(Float, nullable=False)
    threshold_value = Column(Float, nullable=False)
    unit = Column(String(16), nullable=False)
    details = Column(JSON, nullable=True)
    opened_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    last_observed_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
