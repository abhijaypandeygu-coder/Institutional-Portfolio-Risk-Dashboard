"""Hypothetical Scenarios calculations package."""
from .hypothetical_math import (
    to_decimal,
    apply_price_shock,
    apply_factor_shock,
    apply_volatility_shock,
    validate_and_repair_correlation_matrix,
    reconstruct_covariance_matrix,
    compute_stressed_risk_metrics,
    revalue_hypothetical_position,
    apply_liquidity_overlay
)

__all__ = [
    "to_decimal",
    "apply_price_shock",
    "apply_factor_shock",
    "apply_volatility_shock",
    "validate_and_repair_correlation_matrix",
    "reconstruct_covariance_matrix",
    "compute_stressed_risk_metrics",
    "revalue_hypothetical_position",
    "apply_liquidity_overlay"
]
