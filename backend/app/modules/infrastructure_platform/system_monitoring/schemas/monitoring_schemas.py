from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from backend.app.modules.infrastructure_platform.system_monitoring.models.monitoring_models import (
    HealthStatus,
    IncidentSeverity,
    IncidentStatus,
)


class LivenessResponse(BaseModel):
    status: str = "ALIVE"
    service: str = "Institutional Portfolio Risk Dashboard"
    uptime_seconds: float
    timestamp: datetime


class DependencyHealthDetail(BaseModel):
    status: HealthStatus
    latency_ms: float
    is_required: bool
    details: Optional[Dict[str, Any]] = None


class ReadinessResponse(BaseModel):
    status: HealthStatus
    service: str
    ready: bool
    dependencies: Dict[str, DependencyHealthDetail]
    timestamp: datetime


class CpuMetricsResponse(BaseModel):
    system_cpu_utilization_pct: float
    process_cpu_utilization_pct: float
    core_count_logical: int
    core_count_physical: Optional[int] = None
    per_core_utilization_pct: List[float] = Field(default_factory=list)
    timestamp: datetime


class MemoryMetricsResponse(BaseModel):
    total_physical_mb: float
    available_mb: float
    used_mb: float
    utilization_pct: float
    process_rss_mb: float
    process_vms_mb: float
    swap_used_mb: Optional[float] = None
    swap_utilization_pct: Optional[float] = None
    timestamp: datetime


class DatabaseMetricsResponse(BaseModel):
    status: HealthStatus
    pool_size: int
    checked_out_connections: int
    idle_connections: int
    pool_utilization_pct: float
    query_latency_avg_ms: float
    query_latency_p95_ms: float
    query_latency_p99_ms: float
    slow_query_count_last_hour: int
    active_locks_count: int
    database_size_mb: float
    timestamp: datetime


class ProcessDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    component_id: str
    process_instance_id: str
    process_name: str
    process_id: Optional[int] = None
    process_type: str
    status: HealthStatus
    restart_count: int
    uptime_seconds: float
    started_at: datetime
    last_heartbeat_at: datetime


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    incident_id: str
    event_type: str
    component_id: str
    severity: IncidentSeverity
    status: IncidentStatus
    observed_value: float
    threshold_value: float
    unit: str
    details: Optional[Dict[str, Any]] = None
    opened_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


class SystemMonitoringOverview(BaseModel):
    overall_status: HealthStatus
    service_uptime_seconds: float
    cpu: CpuMetricsResponse
    memory: MemoryMetricsResponse
    database: DatabaseMetricsResponse
    active_incidents_count: int
    timestamp: datetime
