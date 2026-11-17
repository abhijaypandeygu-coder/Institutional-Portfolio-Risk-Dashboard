"""
Regression Comparison & Tolerance Verification Service.
Compares actual mathematical and system outputs against immutable reference baselines.
"""
from typing import Dict, Any, List, Optional
import math


class RegressionComparisonService:
    """Verifies that actual system outputs match approved analytical baselines within strict tolerances."""

    # Default tolerance policies per calculation category
    TOLERANCE_POLICIES: Dict[str, Dict[str, float]] = {
        "exposure": {"atol": 1e-4, "rtol": 1e-5},
        "volatility": {"atol": 1e-4, "rtol": 1e-4},
        "var_es": {"atol": 1e-4, "rtol": 1e-4},
        "drawdown": {"atol": 1e-4, "rtol": 1e-4},
        "spread_bps": {"atol": 1e-2, "rtol": 1e-3},
        "imbalance": {"atol": 1e-4, "rtol": 1e-4},
        "exact": {"atol": 0.0, "rtol": 0.0},
    }

    @classmethod
    def compare_numeric_value(
        cls,
        actual: float,
        expected: float,
        category: str = "exposure",
        custom_atol: Optional[float] = None,
        custom_rtol: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Compares actual float with expected baseline using absolute and relative tolerance.
        |actual - expected| <= atol + rtol * |expected|
        """
        tol = cls.TOLERANCE_POLICIES.get(category, {"atol": 1e-4, "rtol": 1e-4})
        atol = custom_atol if custom_atol is not None else tol["atol"]
        rtol = custom_rtol if custom_rtol is not None else tol["rtol"]

        abs_diff = abs(actual - expected)
        rel_diff = abs_diff / abs(expected) if abs(expected) > 1e-12 else abs_diff

        allowed_margin = atol + (rtol * abs(expected))
        passed = bool(abs_diff <= allowed_margin)

        return {
            "passed": passed,
            "actual": actual,
            "expected": expected,
            "absolute_diff": float(abs_diff),
            "relative_diff": float(rel_diff),
            "atol": atol,
            "rtol": rtol,
            "allowed_margin": float(allowed_margin),
        }

    @classmethod
    def compare_dictionary_metrics(
        cls,
        actual_dict: Dict[str, float],
        expected_dict: Dict[str, float],
        category: str = "exposure",
    ) -> Dict[str, Any]:
        """Compares a dictionary of quantitative metrics."""
        results = {}
        all_passed = True

        for key, exp_val in expected_dict.items():
            if key not in actual_dict:
                results[key] = {
                    "passed": False,
                    "error": f"Missing key in actual results: {key}",
                }
                all_passed = False
                continue

            cmp = cls.compare_numeric_value(
                actual=float(actual_dict[key]),
                expected=float(exp_val),
                category=category,
            )
            results[key] = cmp
            if not cmp["passed"]:
                all_passed = False

        return {
            "passed": all_passed,
            "metric_results": results,
            "total_metrics": len(expected_dict),
            "passed_metrics": sum(1 for v in results.values() if v.get("passed", False)),
        }
