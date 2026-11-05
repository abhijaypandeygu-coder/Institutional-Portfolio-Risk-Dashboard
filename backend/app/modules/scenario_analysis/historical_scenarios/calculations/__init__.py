"""Historical Scenarios calculation package."""
from .scenario_math import (
    to_decimal,
    compute_simple_return,
    compute_cumulative_compounded_return,
    compute_currency_adjusted_return,
    estimate_factor_shock,
    revalue_position,
    aggregate_portfolio_replay
)

__all__ = [
    "to_decimal",
    "compute_simple_return",
    "compute_cumulative_compounded_return",
    "compute_currency_adjusted_return",
    "estimate_factor_shock",
    "revalue_position",
    "aggregate_portfolio_replay"
]

