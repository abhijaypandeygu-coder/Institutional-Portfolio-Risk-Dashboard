"""
Calculations package for M10.07 Monte Carlo Scenarios.
"""

from backend.app.modules.scenario_analysis.monte_carlo.calculations.monte_carlo_math import (
    validate_and_repair_correlation_matrix,
    compute_cholesky_factor,
    generate_correlated_innovations,
    simulate_geometric_brownian_paths,
    calculate_portfolio_outcomes,
    compute_distribution_statistics,
    compute_var_and_cvar,
    to_decimal,
)

__all__ = [
    "validate_and_repair_correlation_matrix",
    "compute_cholesky_factor",
    "generate_correlated_innovations",
    "simulate_geometric_brownian_paths",
    "calculate_portfolio_outcomes",
    "compute_distribution_statistics",
    "compute_var_and_cvar",
    "to_decimal",
]

