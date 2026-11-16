"""
Calculations package for M10.08 Scenario Comparison.
"""

from backend.app.modules.scenario_analysis.scenario_comparison.calculations.comparison_math import (
    compute_baseline_performance,
    normalize_metrics,
    rank_scenarios,
    compute_configuration_differences,
    compute_scenario_difference_attribution,
)

__all__ = [
    "compute_baseline_performance",
    "normalize_metrics",
    "rank_scenarios",
    "compute_configuration_differences",
    "compute_scenario_difference_attribution",
]

