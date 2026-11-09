"""
M10.05 Correlation Shock Calculations Package.
"""
from backend.app.modules.scenario_analysis.correlation_shock.calculations.correlation_math import (
    MatrixValidationStatus,
    MatrixRepairMethod,
    CorrelationTransformationMethod,
    transform_correlation_pair,
    validate_correlation_matrix,
    repair_correlation_matrix,
    construct_stressed_covariance,
    calculate_portfolio_risk_and_contributions,
    calculate_diversification_metrics,
    compare_baseline_vs_stressed,
)

__all__ = [
    "MatrixValidationStatus",
    "MatrixRepairMethod",
    "CorrelationTransformationMethod",
    "transform_correlation_pair",
    "validate_correlation_matrix",
    "repair_correlation_matrix",
    "construct_stressed_covariance",
    "calculate_portfolio_risk_and_contributions",
    "calculate_diversification_metrics",
    "compare_baseline_vs_stressed",
]
