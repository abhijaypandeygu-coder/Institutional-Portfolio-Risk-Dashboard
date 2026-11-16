"""
Mathematical and analytical calculation engine for M10.08 Scenario Comparison.
Implements:
1. Baseline performance comparison (NAV, absolute P&L, percentage return, loss convention).
2. Risk metric normalization (Min-Max, Z-score, Robust Median/MAD, Percentile ranking).
3. Configurable multi-metric scenario ranking engine with tie handling and weighted composite scores.
4. Assumption-level configuration difference analysis and finite-difference / elasticity sensitivity.
5. Scenario difference attribution across instruments, sectors, liquidity, and residual tracking.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Optional, Tuple
import numpy as np


def compute_baseline_performance(
    baseline_nav: Decimal,
    scenario_nav: Decimal,
    base_currency: str = "USD"
) -> Dict[str, Any]:
    """
    Computes scenario performance relative to a common baseline:
    - P_s = V_s - V_0
    - R_s = (V_s - V_0) / V_0
    - L_s = V_0 - V_s (loss is positive for losses)
    - L_{s,%} = (V_0 - V_s) / V_0 * 100
    """
    if baseline_nav <= Decimal("0"):
        raise ValueError("Baseline NAV must be strictly positive for return and loss calculations.")

    pnl = scenario_nav - baseline_nav
    return_pct = (pnl / baseline_nav) * Decimal("100")
    loss_amount = baseline_nav - scenario_nav
    loss_pct = (loss_amount / baseline_nav) * Decimal("100")

    return {
        "baseline_nav": baseline_nav,
        "scenario_nav": scenario_nav,
        "pnl": pnl,
        "return_pct": return_pct.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        "loss_amount": loss_amount,
        "loss_pct": loss_pct.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        "base_currency": base_currency
    }


def normalize_metrics(
    values: List[float],
    method: str = "MIN_MAX",
    direction: str = "DESCENDING"
) -> List[float]:
    """
    Normalizes a list of metric values across scenarios into [0, 1] scores.
    direction="DESCENDING": higher metric value => higher normalized score (worse or better as configured).
    direction="ASCENDING": lower metric value => higher normalized score.
    """
    arr = np.array(values, dtype=np.float64)
    n = len(arr)
    if n == 0:
        return []
    if n == 1 or np.all(arr == arr[0]):
        return [1.0] * n

    if method == "MIN_MAX":
        min_val = np.min(arr)
        max_val = np.max(arr)
        if max_val - min_val < 1e-12:
            scores = np.ones(n)
        else:
            scores = (arr - min_val) / (max_val - min_val)
    elif method == "Z_SCORE":
        mean = np.mean(arr)
        std = np.std(arr, ddof=1) if n > 1 else 1.0
        if std < 1e-12:
            scores = np.zeros(n)
        else:
            z = (arr - mean) / std
            # Sigmoid map to [0, 1]
            scores = 1.0 / (1.0 + np.exp(-z))
    elif method == "ROBUST_MAD":
        med = np.median(arr)
        mad = np.median(np.abs(arr - med))
        if mad < 1e-12:
            scores = np.ones(n) * 0.5
        else:
            norm_dev = (arr - med) / (1.4826 * mad)
            scores = 1.0 / (1.0 + np.exp(-norm_dev))
    elif method == "PERCENTILE":
        ranks = np.argsort(np.argsort(arr))
        scores = ranks / float(n - 1) if n > 1 else np.ones(n)
    else:
        # Default Min-Max fallback
        min_val = np.min(arr)
        max_val = np.max(arr)
        scores = (arr - min_val) / (max_val - min_val) if max_val - min_val > 1e-12 else np.ones(n)

    if direction == "ASCENDING":
        scores = 1.0 - scores

    return [float(np.clip(s, 0.0, 1.0)) for s in scores]


def rank_scenarios(
    scenario_items: List[Dict[str, Any]],
    primary_metric: str = "loss_amount",
    direction: str = "DESCENDING",
    weights: Optional[Dict[str, float]] = None,
    normalization_method: str = "MIN_MAX"
) -> List[Dict[str, Any]]:
    """
    Ranks scenarios based on primary metric or weighted composite score.
    Deterministic tie handling: assigns equal rank for equal scores, with stable ordering.
    """
    if not scenario_items:
        return []

    # If composite ranking requested with multiple weights
    if weights and len(weights) > 1:
        # Normalize each metric across all scenarios
        total_weight = sum(weights.values())
        norm_weights = {k: v / total_weight for k, v in weights.items()}
        composite_scores = np.zeros(len(scenario_items), dtype=np.float64)

        for metric, w in norm_weights.items():
            vals = [float(item.get(metric, 0.0) or 0.0) for item in scenario_items]
            # Higher loss/VaR/ES/drawdown is considered more severe (DESCENDING)
            norm_vals = normalize_metrics(vals, method=normalization_method, direction=direction)
            composite_scores += w * np.array(norm_vals)

        for i, item in enumerate(scenario_items):
            item["ranking_score"] = float(composite_scores[i])
            item["composite_score"] = float(composite_scores[i])
    else:
        # Single metric ranking
        raw_vals = [float(item.get(primary_metric, 0.0) or 0.0) for item in scenario_items]
        norm_scores = normalize_metrics(raw_vals, method=normalization_method, direction=direction)
        for i, item in enumerate(scenario_items):
            item["ranking_score"] = raw_vals[i]
            item["normalized_score"] = norm_scores[i]

    # Sort items based on direction
    reverse_sort = True if direction == "DESCENDING" else False
    sorted_items = sorted(
        scenario_items,
        key=lambda x: (x["ranking_score"], x.get("scenario_run_id", "")),
        reverse=reverse_sort
    )

    # Assign deterministic ranks and tie groups
    current_rank = 1
    for idx, item in enumerate(sorted_items):
        if idx > 0 and sorted_items[idx]["ranking_score"] == sorted_items[idx - 1]["ranking_score"]:
            item["rank_position"] = sorted_items[idx - 1]["rank_position"]
            item["tie_group"] = sorted_items[idx - 1]["tie_group"]
        else:
            item["rank_position"] = idx + 1
            item["tie_group"] = idx + 1

    return sorted_items


def compute_configuration_differences(
    config_a: Dict[str, Any],
    config_b: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Compares parameter dictionaries between two scenario runs.
    Calculates absolute and relative differences for numeric values.
    """
    all_keys = sorted(set(config_a.keys()) | set(config_b.keys()))
    diffs = []

    for k in all_keys:
        val_a = config_a.get(k)
        val_b = config_b.get(k)

        # Check if values are numeric
        is_numeric = isinstance(val_a, (int, float, Decimal)) and isinstance(val_b, (int, float, Decimal))
        if is_numeric:
            fa = float(val_a)
            fb = float(val_b)
            abs_diff = fb - fa
            rel_diff = (abs_diff / abs(fa)) if abs(fa) > 1e-12 else None
            is_material = abs(abs_diff) > 1e-6
        else:
            abs_diff = None
            rel_diff = None
            is_material = (val_a != val_b)

        diffs.append({
            "parameter_code": k,
            "parameter_name": k.replace("_", " ").title(),
            "scenario_a_value": str(val_a) if val_a is not None else None,
            "scenario_b_value": str(val_b) if val_b is not None else None,
            "absolute_difference": abs_diff,
            "relative_difference": rel_diff,
            "is_material": is_material
        })

    return diffs


def compute_scenario_difference_attribution(
    scenario_a_breakdown: Dict[str, Decimal], # e.g. {"AAPL": Decimal("-500"), "MSFT": Decimal("200")}
    scenario_b_breakdown: Dict[str, Decimal],
    headline_diff: Decimal
) -> Tuple[List[Dict[str, Any]], Decimal]:
    """
    Computes difference attribution between Scenario A and Scenario B.
    Delta P&L_i = P&L_{i,B} - P&L_{i,A}.
    Reconciliation residual: epsilon = Headline_Diff - sum(Delta P&L_i).
    """
    all_components = sorted(set(scenario_a_breakdown.keys()) | set(scenario_b_breakdown.keys()))
    attributions = []
    sum_comp_diff = Decimal("0")

    for comp in all_components:
        val_a = scenario_a_breakdown.get(comp, Decimal("0"))
        val_b = scenario_b_breakdown.get(comp, Decimal("0"))
        diff = val_b - val_a
        sum_comp_diff += diff

        attributions.append({
            "component_reference": comp,
            "scenario_a_value": val_a,
            "scenario_b_value": val_b,
            "difference_value": diff
        })

    residual = headline_diff - sum_comp_diff
    return attributions, residual

