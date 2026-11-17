"""
Performance Benchmark Suite for M15.10.
Measures latency, throughput, and memory consumption for core quantitative routines.
"""
import pytest
from backend.app.modules.infrastructure_platform.testing_infrastructure.reference.math_reference import (
    FinancialMathReference,
)
from backend.app.modules.infrastructure_platform.testing_infrastructure.datasets.deterministic_datasets import (
    PORTFOLIO_REFERENCE_DATASET_V1,
    MARKET_RETURNS_DATASET_V1,
)
from backend.app.modules.infrastructure_platform.testing_infrastructure.services.benchmark_service import (
    PerformanceBenchmarkService,
)


@pytest.mark.performance
def test_exposure_calculation_benchmark():
    """Measures latency and throughput of gross/net exposure calculation."""
    positions = PORTFOLIO_REFERENCE_DATASET_V1["positions"]

    def run_exposure():
        return FinancialMathReference.calculate_gross_and_net_exposure(positions)

    metrics = PerformanceBenchmarkService.measure_function_performance(
        run_exposure,
        warmup_iterations=10,
        measured_iterations=100,
    )

    assert metrics["ops_per_sec"] > 500.0 # High throughput requirement
    assert metrics["latency_ms"]["p95"] < 5.0 # Sub-5ms p95 latency


@pytest.mark.performance
def test_volatility_calculation_benchmark():
    """Measures latency of sample volatility calculation."""
    returns = MARKET_RETURNS_DATASET_V1["returns"]

    def run_vol():
        return FinancialMathReference.calculate_sample_volatility(returns, annualization_factor=252.0)

    metrics = PerformanceBenchmarkService.measure_function_performance(
        run_vol,
        warmup_iterations=10,
        measured_iterations=100,
    )

    assert metrics["ops_per_sec"] > 1000.0
    assert metrics["latency_ms"]["p95"] < 2.0
