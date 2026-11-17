import os
import time
import psutil
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from backend.app.modules.infrastructure_platform.system_monitoring.schemas.monitoring_schemas import (
    CpuMetricsResponse,
    MemoryMetricsResponse,
)

START_TIME = time.time()


class SystemResourceCollector:
    """Collects OS-level and Process-level CPU and Memory metrics using psutil."""

    @classmethod
    def get_service_uptime_seconds(cls) -> float:
        return max(0.0, time.time() - START_TIME)

    @classmethod
    def collect_cpu_metrics(cls) -> CpuMetricsResponse:
        # Non-blocking snapshot
        sys_cpu = psutil.cpu_percent(interval=None)
        per_core = psutil.cpu_percent(interval=None, percpu=True)
        
        proc = psutil.Process(os.getpid())
        proc_cpu = proc.cpu_percent(interval=None)

        return CpuMetricsResponse(
            system_cpu_utilization_pct=round(sys_cpu, 2),
            process_cpu_utilization_pct=round(proc_cpu, 2),
            core_count_logical=psutil.cpu_count(logical=True) or 1,
            core_count_physical=psutil.cpu_count(logical=False),
            per_core_utilization_pct=[round(c, 2) for c in per_core],
            timestamp=datetime.now(timezone.utc),
        )

    @classmethod
    def collect_memory_metrics(cls) -> MemoryMetricsResponse:
        vm = psutil.virtual_memory()
        proc = psutil.Process(os.getpid())
        mem_info = proc.memory_info()

        swap = psutil.swap_memory() if hasattr(psutil, "swap_memory") else None

        return MemoryMetricsResponse(
            total_physical_mb=round(vm.total / (1024 * 1024), 2),
            available_mb=round(vm.available / (1024 * 1024), 2),
            used_mb=round(vm.used / (1024 * 1024), 2),
            utilization_pct=round(vm.percent, 2),
            process_rss_mb=round(mem_info.rss / (1024 * 1024), 2),
            process_vms_mb=round(mem_info.vms / (1024 * 1024), 2),
            swap_used_mb=round(swap.used / (1024 * 1024), 2) if swap else None,
            swap_utilization_pct=round(swap.percent, 2) if swap else None,
            timestamp=datetime.now(timezone.utc),
        )
