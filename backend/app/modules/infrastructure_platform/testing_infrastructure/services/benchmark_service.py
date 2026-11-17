"""
Benchmark execution and performance measurement service.
Provides repeatable latency, throughput, and hardware measurement routines.
"""
import time
import os
import psutil
from typing import Dict, Any, Callable, List


class PerformanceBenchmarkService:
    """Executes controlled performance benchmarks and measures execution latency & resource consumption."""

    @staticmethod
    def measure_function_performance(
        func: Callable,
        *args,
        warmup_iterations: int = 5,
        measured_iterations: int = 50,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Runs warmup passes, then executes measured runs to record latency percentiles (p50, p95, p99),
        ops/sec, and resource usage.
        """
        # Warmup
        for _ in range(warmup_iterations):
            func(*args, **kwargs)

        durations_ms: List[float] = []
        process = psutil.Process(os.getpid())
        mem_before = process.memory_info().rss / (1024 * 1024)

        start_total = time.perf_counter()
        for _ in range(measured_iterations):
            t0 = time.perf_counter()
            func(*args, **kwargs)
            t1 = time.perf_counter()
            durations_ms.append((t1 - t0) * 1000.0)
        end_total = time.perf_counter()

        mem_after = process.memory_info().rss / (1024 * 1024)
        total_time_sec = end_total - start_total
        ops_per_sec = measured_iterations / total_time_sec if total_time_sec > 0 else 0.0

        durations_ms.sort()
        p50 = durations_ms[int(0.50 * len(durations_ms))]
        p95 = durations_ms[min(int(0.95 * len(durations_ms)), len(durations_ms) - 1)]
        p99 = durations_ms[min(int(0.99 * len(durations_ms)), len(durations_ms) - 1)]
        mean_ms = sum(durations_ms) / len(durations_ms)

        return {
            "iterations": measured_iterations,
            "total_time_sec": round(total_time_sec, 4),
            "ops_per_sec": round(ops_per_sec, 2),
            "latency_ms": {
                "min": round(min(durations_ms), 4),
                "mean": round(mean_ms, 4),
                "p50": round(p50, 4),
                "p95": round(p95, 4),
                "p99": round(p99, 4),
                "max": round(max(durations_ms), 4),
            },
            "resource_metrics": {
                "mem_before_mb": round(mem_before, 2),
                "mem_after_mb": round(mem_after, 2),
                "mem_delta_mb": round(mem_after - mem_before, 2),
            },
        }
