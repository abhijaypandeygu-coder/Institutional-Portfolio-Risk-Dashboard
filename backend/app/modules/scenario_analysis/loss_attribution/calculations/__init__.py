"""
Calculations package for M10.09 Stress Loss Attribution.
"""

from backend.app.modules.scenario_analysis.loss_attribution.calculations.attribution_math import (
    compute_position_pnl_and_decomposition,
    aggregate_by_dimension,
    compute_factor_shock_attribution,
    compute_interaction_effect,
    compute_loss_concentration_metrics,
    compute_reconciliation_residual,
)

__all__ = [
    "compute_position_pnl_and_decomposition",
    "aggregate_by_dimension",
    "compute_factor_shock_attribution",
    "compute_interaction_effect",
    "compute_loss_concentration_metrics",
    "compute_reconciliation_residual",
]

