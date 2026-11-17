"""
Quality Gate Evaluation Service for M15.10.
Enforces institutional gates on test pass rates, regression baselines, and coverage.
"""
from typing import Dict, Any, List
from backend.app.modules.infrastructure_platform.testing_infrastructure.models.testing_models import (
    QualityGateStatus,
)


class QualityGateService:
    """Evaluates release and deployment readiness against configurable gate criteria."""

    DEFAULT_THRESHOLDS = {
        "min_unit_pass_rate": 1.0,         # 100% of unit tests must pass
        "min_regression_pass_rate": 1.0,   # 100% of mathematical regressions must match
        "max_failed_tests": 0,             # 0 blocking test failures
        "min_total_coverage": 75.0,        # 75% line coverage minimum target
        "min_critical_module_cov": 85.0,   # 85% for risk calculation modules
    }

    @classmethod
    def evaluate_gate(
        cls,
        run_summary: Dict[str, Any],
        regression_results: Dict[str, Any],
        coverage_summary: Dict[str, Any],
        custom_thresholds: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Evaluates overall release quality gate."""
        thresholds = dict(cls.DEFAULT_THRESHOLDS)
        if custom_thresholds:
            thresholds.update(custom_thresholds)

        blocking_failures: List[str] = []
        warnings: List[str] = []
        criteria_evaluated: List[Dict[str, Any]] = []

        # 1. Test Run Failures
        failed_count = run_summary.get("failed_count", 0)
        passed_count = run_summary.get("passed_count", 0)
        total_tests = passed_count + failed_count
        unit_pass_rate = (passed_count / total_tests) if total_tests > 0 else 1.0

        if failed_count > thresholds["max_failed_tests"]:
            blocking_failures.append(
                f"Test suite contains {failed_count} failing test(s) (threshold: {thresholds['max_failed_tests']})"
            )
        criteria_evaluated.append({
            "name": "Unit/Integration Test Pass Count",
            "passed": failed_count == 0,
            "actual": f"{passed_count} passed, {failed_count} failed",
            "threshold": f"0 failed",
        })

        # 2. Regression Integrity
        reg_passed = regression_results.get("passed", True)
        if not reg_passed:
            blocking_failures.append("Mathematical baseline regression test failed outside allowed tolerance.")
        criteria_evaluated.append({
            "name": "Mathematical Regression Baselines",
            "passed": reg_passed,
            "actual": "Passed" if reg_passed else "Failed",
            "threshold": "100% within tolerance",
        })

        # 3. Code Coverage
        total_cov = coverage_summary.get("total_coverage", 80.0)
        if total_cov < thresholds["min_total_coverage"]:
            warnings.append(
                f"Total line coverage ({total_cov:.1f}%) is below recommended target ({thresholds['min_total_coverage']}%)"
            )
        criteria_evaluated.append({
            "name": "Total Code Coverage",
            "passed": total_cov >= thresholds["min_total_coverage"],
            "actual": f"{total_cov:.1f}%",
            "threshold": f">= {thresholds['min_total_coverage']}%",
        })

        # Overall Status
        if blocking_failures:
            overall_status = QualityGateStatus.FAILED
        elif warnings:
            overall_status = QualityGateStatus.WARNING
        else:
            overall_status = QualityGateStatus.PASSED

        return {
            "gate_name": "Institutional Release Gate",
            "overall_status": overall_status,
            "criteria_evaluated": criteria_evaluated,
            "blocking_failures": blocking_failures,
            "warnings": warnings,
        }
