"""
Mathematical Baseline Regression Tests for M15.10.
Validates outputs against frozen numerical baselines and verifies that modifications
outside allowed tolerances are caught and flagged.
"""
import pytest
from backend.app.modules.infrastructure_platform.testing_infrastructure.reference.math_reference import (
    FinancialMathReference,
)
from backend.app.modules.infrastructure_platform.testing_infrastructure.datasets.deterministic_datasets import (
    PORTFOLIO_REFERENCE_DATASET_V1,
    MARKET_RETURNS_DATASET_V1,
)
from backend.app.modules.infrastructure_platform.testing_infrastructure.services.regression_service import (
    RegressionComparisonService,
)


@pytest.mark.regression
def test_portfolio_exposure_regression_baseline():
    """Compares calculated exposure against frozen baseline values."""
    res = FinancialMathReference.calculate_gross_and_net_exposure(PORTFOLIO_REFERENCE_DATASET_V1["positions"])
    actual_dict = {
        "gross_exposure": float(res["gross_exposure"]),
        "net_exposure": float(res["net_exposure"]),
    }
    expected_dict = {
        "gross_exposure": 5737500.0,
        "net_exposure": 4173500.0,
    }

    cmp = RegressionComparisonService.compare_dictionary_metrics(
        actual_dict=actual_dict,
        expected_dict=expected_dict,
        category="exposure",
    )

    assert cmp["passed"] is True
    assert cmp["passed_metrics"] == 2


@pytest.mark.regression
def test_regression_service_detects_deliberate_drift():
    """Verifies that the regression comparator flags unauthorized drifts outside tolerance."""
    # Deliberate 5% error introduced into actual calculation
    corrupted_val = 5737500.0 * 1.05
    cmp = RegressionComparisonService.compare_numeric_value(
        actual=corrupted_val,
        expected=5737500.0,
        category="exposure",
    )
    assert cmp["passed"] is False
    assert cmp["absolute_diff"] > cmp["allowed_margin"]
