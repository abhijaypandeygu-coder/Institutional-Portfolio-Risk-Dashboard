import os
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.core.database import get_db
from backend.app.modules.infrastructure_platform.authorization.dependencies import (
    require_permission,
)
from backend.app.modules.infrastructure_platform.system_monitoring.models.monitoring_models import (
    MonitoredProcessRecord,
    OperationalIncidentRecord,
    HealthStatus,
)
from backend.app.modules.infrastructure_platform.system_monitoring.schemas.monitoring_schemas import (
    LivenessResponse,
    ReadinessResponse,
    CpuMetricsResponse,
    MemoryMetricsResponse,
    DatabaseMetricsResponse,
    ProcessDetailResponse,
    IncidentResponse,
    SystemMonitoringOverview,
)
from backend.app.modules.infrastructure_platform.system_monitoring.services.resource_collector import (
    SystemResourceCollector,
)
from backend.app.modules.infrastructure_platform.system_monitoring.services.database_collector import (
    DatabaseMonitoringCollector,
)
from backend.app.modules.infrastructure_platform.system_monitoring.services.health_check_service import (
    HealthCheckService,
)

router = APIRouter(tags=["M15.07 System Monitoring"])


# --- Lightweight Health Probes ---

@router.get("/health/live", response_model=LivenessResponse)
async def check_liveness():
    """Liveness probe confirming the application process is running (does not query database)."""
    return LivenessResponse(
        status="ALIVE",
        service="Institutional Portfolio Risk Dashboard",
        uptime_seconds=SystemResourceCollector.get_service_uptime_seconds(),
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def check_readiness(db: AsyncSession = Depends(get_db)):
    """Readiness probe evaluating critical dependencies (database, encryption KEK)."""
    service = HealthCheckService(db)
    return await service.evaluate_readiness()


# --- System Monitoring APIs (RBAC Protected) ---

@router.get("/api/v1/monitoring/overview", response_model=SystemMonitoringOverview)
async def get_system_monitoring_overview(
    admin_user=Depends(require_permission("admin.roles.read")),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves full operational snapshot of CPU, Memory, DB, and Active Incidents."""
    cpu = SystemResourceCollector.collect_cpu_metrics()
    mem = SystemResourceCollector.collect_memory_metrics()
    
    db_collector = DatabaseMonitoringCollector(db)
    db_metrics = await db_collector.collect_database_metrics()

    inc_res = await db.execute(
        select(OperationalIncidentRecord).where(OperationalIncidentRecord.status == "OPEN")
    )
    open_incidents = len(inc_res.scalars().all())

    overall = HealthStatus.HEALTHY
    if db_metrics.status != HealthStatus.HEALTHY:
        overall = HealthStatus.DEGRADED

    return SystemMonitoringOverview(
        overall_status=overall,
        service_uptime_seconds=SystemResourceCollector.get_service_uptime_seconds(),
        cpu=cpu,
        memory=mem,
        database=db_metrics,
        active_incidents_count=open_incidents,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/api/v1/monitoring/cpu", response_model=CpuMetricsResponse)
async def get_cpu_metrics(
    admin_user=Depends(require_permission("admin.roles.read")),
):
    """Retrieves detailed system and process CPU utilization."""
    return SystemResourceCollector.collect_cpu_metrics()


@router.get("/api/v1/monitoring/memory", response_model=MemoryMetricsResponse)
async def get_memory_metrics(
    admin_user=Depends(require_permission("admin.roles.read")),
):
    """Retrieves physical, virtual, process RSS, and swap memory utilization."""
    return SystemResourceCollector.collect_memory_metrics()


@router.get("/api/v1/monitoring/database", response_model=DatabaseMetricsResponse)
async def get_database_metrics(
    admin_user=Depends(require_permission("admin.roles.read")),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves database connection pool utilization, latency, and storage stats."""
    collector = DatabaseMonitoringCollector(db)
    return await collector.collect_database_metrics()


@router.get("/api/v1/monitoring/processes", response_model=List[ProcessDetailResponse])
async def list_monitored_processes(
    admin_user=Depends(require_permission("admin.roles.read")),
    db: AsyncSession = Depends(get_db),
):
    """Lists registered application processes and background workers."""
    # Register current process if not recorded
    pid = os.getpid()
    stmt = select(MonitoredProcessRecord).where(MonitoredProcessRecord.component_id == "main_api")
    res = await db.execute(stmt)
    proc_record = res.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    uptime = SystemResourceCollector.get_service_uptime_seconds()

    if not proc_record:
        proc_record = MonitoredProcessRecord(
            component_id="main_api",
            process_instance_id=f"inst-{pid}",
            process_name="uvicorn_main",
            process_id=pid,
            process_type="APP_PROCESS",
            status=HealthStatus.HEALTHY,
            restart_count=0,
            started_at=now,
            last_heartbeat_at=now,
        )
        db.add(proc_record)
        await db.commit()
        await db.refresh(proc_record)

    return [
        ProcessDetailResponse(
            component_id=proc_record.component_id,
            process_instance_id=proc_record.process_instance_id,
            process_name=proc_record.process_name,
            process_id=proc_record.process_id,
            process_type=proc_record.process_type,
            status=proc_record.status,
            restart_count=proc_record.restart_count,
            uptime_seconds=uptime,
            started_at=proc_record.started_at,
            last_heartbeat_at=proc_record.last_heartbeat_at,
        )
    ]
