"""
M09.03 Liquidity Estimation - Core Mathematical and Statistical Formulations.
Provides deterministic calculations for:
- Trade Volume Aggregation (interval, session, rolling ADV, median, CV, percentiles, intraday pace)
- Turnover Aggregation (interval, session, rolling ADTV, median, CV, percentiles, intraday pace)
- Component Normalization (peer-group percentile ranks, winsorization, log transform)
- Composite Liquidity Scoring (weighted arithmetic, coverage gates, contribution breakdown)
- Liquidity Bucket Classification (score-based, relative percentiles, absolute thresholds)
"""

from datetime import datetime, timezone
from decimal import Decimal
import math
from typing import List, Dict, Any, Optional, Tuple
import numpy as np


def _normalize_tz(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensures datetime is timezone-aware UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ============================================================================
# 1. VOLUME & TURNOVER CALCULATIONS
# ============================================================================

def compute_traded_volume_and_turnover(
    trades: List[Dict[str, Any]],
    instrument_multiplier: Decimal = Decimal("1.0")
) -> Dict[str, Any]:
    """
    Computes executed volume and monetary turnover from a sequence of eligible trades.
    Filters out canceled or invalid trades if status flag is present.
    De-duplicates based on trade_id/event_id if duplicates are present.

    Each trade dict expects:
    - 'trade_id' or 'event_id': str
    - 'price': Decimal or float or str
    - 'quantity': Decimal or float or str
    - 'status': Optional[str] ('ACTIVE', 'CANCELED', 'CORRECTED')
    - 'timestamp': datetime
    """
    seen_ids = set()
    total_volume = Decimal("0.0")
    total_turnover = Decimal("0.0")
    eligible_count = 0

    for tr in trades:
        tid = tr.get("trade_id") or tr.get("event_id")
        if tid:
            if tid in seen_ids:
                continue
            seen_ids.add(tid)

        # Check status
        status = tr.get("status", "ACTIVE")
        if status in ("CANCELED", "CANCELLED", "INVALID", "EXCLUDED"):
            continue

        price = Decimal(str(tr["price"]))
        qty = Decimal(str(tr["quantity"]))

        if qty <= Decimal("0.0") or price <= Decimal("0.0"):
            continue

        trade_val = price * qty * instrument_multiplier

        total_volume += qty
        total_turnover += trade_val
        eligible_count += 1

    return {
        "eligible_trade_count": eligible_count,
        "traded_volume": total_volume,
        "turnover": total_turnover
    }


def compute_series_statistics(values: List[float]) -> Dict[str, Optional[float]]:
    """
    Computes mean (ADV / ADTV), median, stddev, coefficient of variation (CV),
    min, max, and percentiles (10th, 25th, 50th, 75th, 90th, 95th).
    """
    if not values:
        return {
            "mean": None,
            "median": None,
            "std_dev": None,
            "cv": None,
            "min": None,
            "max": None,
            "p10": None,
            "p25": None,
            "p50": None,
            "p75": None,
            "p90": None,
            "p95": None,
            "sample_count": 0
        }

    arr = np.array(values, dtype=np.float64)
    mean_val = float(np.mean(arr))
    median_val = float(np.median(arr))
    std_val = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
    cv_val = (std_val / mean_val) if mean_val > 0.0 else None

    return {
        "mean": mean_val,
        "median": median_val,
        "std_dev": std_val,
        "cv": cv_val,
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "p10": float(np.percentile(arr, 10)),
        "p25": float(np.percentile(arr, 25)),
        "p50": median_val,
        "p75": float(np.percentile(arr, 75)),
        "p90": float(np.percentile(arr, 90)),
        "p95": float(np.percentile(arr, 95)),
        "sample_count": len(arr)
    }


def compute_intraday_pace(
    current_cumulative: float,
    historical_cumulative_at_same_time: List[float]
) -> Optional[float]:
    """
    Computes intraday volume or turnover pace relative to historical median at same session-relative time:
    Pace = current_cum / median(historical_cum)
    Returns None if denominator is zero or sample is empty.
    """
    if not historical_cumulative_at_same_time:
        return None
    hist_med = float(np.median(historical_cumulative_at_same_time))
    if hist_med <= 0.0:
        return None
    return float(current_cumulative / hist_med)


# ============================================================================
# 2. NORMALIZATION & PERCENTILE RANKING
# ============================================================================

def compute_percentile_rank(
    value: float,
    reference_population: List[float],
    winsor_bounds: Optional[Tuple[float, float]] = None
) -> Optional[float]:
    """
    Computes empirical cumulative distribution percentile rank PR(x) in [0.0, 100.0]
    using standard average-tie rank convention.
    Optionally applies winsorization at (lower_pct, upper_pct) before ranking.
    """
    if value is None or not reference_population:
        return None

    pop = np.array(reference_population, dtype=np.float64)
    target = float(value)

    if winsor_bounds:
        low_p, high_p = winsor_bounds
        low_val = np.percentile(pop, low_p)
        high_val = np.percentile(pop, high_p)
        pop = np.clip(pop, low_val, high_val)
        target = float(np.clip(target, low_val, high_val))

    # Average tie handling:
    # rank = (count(pop < target) + 0.5 * count(pop == target)) / N * 100.0
    n = len(pop)
    less = np.sum(pop < target)
    equal = np.sum(pop == target)
    pr = float((less + 0.5 * equal) / n * 100.0)
    return min(max(pr, 0.0), 100.0)


def compute_subscores(
    spread_bps: Optional[float],
    depth_notional: Optional[float],
    turnover_val: Optional[float],
    peer_spreads: List[float],
    peer_depths: List[float],
    peer_turnovers: List[float],
    winsor_bounds: Optional[Tuple[float, float]] = None
) -> Dict[str, Optional[float]]:
    """
    Calculates 0-100 subscores:
    - S_spread = 100 * (1 - PR(Spread)) (lower spread = higher subscore)
    - S_depth = PR(Depth) (higher depth = higher subscore)
    - S_turnover = PR(Turnover) (higher turnover = higher subscore)
    """
    s_spread = None
    if spread_bps is not None and peer_spreads:
        pr_spread = compute_percentile_rank(spread_bps, peer_spreads, winsor_bounds)
        if pr_spread is not None:
            s_spread = 100.0 - pr_spread

    s_depth = None
    if depth_notional is not None and peer_depths:
        s_depth = compute_percentile_rank(depth_notional, peer_depths, winsor_bounds)

    s_turnover = None
    if turnover_val is not None and peer_turnovers:
        s_turnover = compute_percentile_rank(turnover_val, peer_turnovers, winsor_bounds)

    return {
        "spread_subscore": s_spread,
        "depth_subscore": s_depth,
        "turnover_subscore": s_turnover
    }


# ============================================================================
# 3. COMPOSITE LIQUIDITY SCORING & AVAILABILITY
# ============================================================================

def compute_data_availability_score(
    spread_coverage: Optional[float],
    depth_coverage: Optional[float],
    turnover_coverage: Optional[float],
    alpha: float = 0.33,
    beta: float = 0.33,
    gamma: float = 0.34
) -> Tuple[Optional[float], Dict[str, Optional[float]]]:
    """
    Availability score S_avail = 100 * (alpha * C_spread + beta * C_depth + gamma * C_turnover).
    Each C_k is in [0.0, 1.0]. Returns (S_avail, components).
    """
    c_s = min(max(spread_coverage, 0.0), 1.0) if spread_coverage is not None else 0.0
    c_d = min(max(depth_coverage, 0.0), 1.0) if depth_coverage is not None else 0.0
    c_t = min(max(turnover_coverage, 0.0), 1.0) if turnover_coverage is not None else 0.0

    s_avail = 100.0 * (alpha * c_s + beta * c_d + gamma * c_t)
    return round(s_avail, 4), {
        "spread_coverage": spread_coverage,
        "depth_coverage": depth_coverage,
        "turnover_coverage": turnover_coverage,
        "alpha": alpha,
        "beta": beta,
        "gamma": gamma
    }


def compute_composite_liquidity_score(
    spread_subscore: Optional[float],
    depth_subscore: Optional[float],
    turnover_subscore: Optional[float],
    availability_subscore: Optional[float],
    weights: Dict[str, float],
    min_spread_coverage: float = 0.50,
    min_depth_coverage: float = 0.50,
    min_turnover_coverage: float = 0.50,
    actual_spread_cov: Optional[float] = 1.0,
    actual_depth_cov: Optional[float] = 1.0,
    actual_turnover_cov: Optional[float] = 1.0
) -> Dict[str, Any]:
    """
    Computes composite liquidity score L = w_s * S_s + w_d * S_d + w_t * S_t + w_a * S_a.
    Subject to sum(w_i) == 1.0.
    Enforces strict hard eligibility gates:
    If coverage < min_coverage or required subscores are None, returns status='INSUFFICIENT_DATA', score=None.
    Never silently renormalizes weights.
    """
    w_s = weights.get("spread_weight", 0.25)
    w_d = weights.get("depth_weight", 0.30)
    w_t = weights.get("turnover_weight", 0.30)
    w_a = weights.get("availability_weight", 0.15)

    total_weight = w_s + w_d + w_t + w_a
    if not math.isclose(total_weight, 1.0, rel_tol=1e-4):
        raise ValueError(f"Score weights must sum to 1.0, got {total_weight}")

    # Check eligibility gates
    failed_reasons = []
    if (actual_spread_cov is None) or (actual_spread_cov < min_spread_coverage):
        failed_reasons.append(f"Spread coverage {actual_spread_cov} < {min_spread_coverage}")
    if (actual_depth_cov is None) or (actual_depth_cov < min_depth_coverage):
        failed_reasons.append(f"Depth coverage {actual_depth_cov} < {min_depth_coverage}")
    if (actual_turnover_cov is None) or (actual_turnover_cov < min_turnover_coverage):
        failed_reasons.append(f"Turnover coverage {actual_turnover_cov} < {min_turnover_coverage}")

    if w_s > 0.0 and spread_subscore is None:
        failed_reasons.append("Missing spread subscore")
    if w_d > 0.0 and depth_subscore is None:
        failed_reasons.append("Missing depth subscore")
    if w_t > 0.0 and turnover_subscore is None:
        failed_reasons.append("Missing turnover subscore")
    if w_a > 0.0 and availability_subscore is None:
        failed_reasons.append("Missing availability subscore")

    if failed_reasons:
        return {
            "composite_score": None,
            "status": "INSUFFICIENT_DATA",
            "reason": "; ".join(failed_reasons),
            "spread_contribution": None,
            "depth_contribution": None,
            "turnover_contribution": None,
            "availability_contribution": None,
            "spread_subscore": spread_subscore,
            "depth_subscore": depth_subscore,
            "turnover_subscore": turnover_subscore,
            "availability_subscore": availability_subscore,
        }

    # All required present and passed gates
    spread_contrib = w_s * spread_subscore
    depth_contrib = w_d * depth_subscore
    turnover_contrib = w_t * turnover_subscore
    avail_contrib = w_a * availability_subscore

    comp_score = spread_contrib + depth_contrib + turnover_contrib + avail_contrib

    return {
        "composite_score": round(comp_score, 4),
        "status": "ACTIVE",
        "reason": "Eligibility criteria and coverage gates fully satisfied",
        "spread_contribution": round(spread_contrib, 4),
        "depth_contribution": round(depth_contrib, 4),
        "turnover_contribution": round(turnover_contrib, 4),
        "availability_contribution": round(avail_contrib, 4),
        "spread_subscore": spread_subscore,
        "depth_subscore": depth_subscore,
        "turnover_subscore": turnover_subscore,
        "availability_subscore": availability_subscore,
    }


# ============================================================================
# 4. BUCKET CLASSIFICATION
# ============================================================================

DEFAULT_BUCKET_THRESHOLDS = [
    {"bucket": "VERY_HIGH_LIQUIDITY", "min_score": 80.0, "max_score": 100.0, "rank": 1},
    {"bucket": "HIGH_LIQUIDITY", "min_score": 60.0, "max_score": 80.0, "rank": 2},
    {"bucket": "MODERATE_LIQUIDITY", "min_score": 40.0, "max_score": 60.0, "rank": 3},
    {"bucket": "LOW_LIQUIDITY", "min_score": 20.0, "max_score": 40.0, "rank": 4},
    {"bucket": "VERY_LOW_LIQUIDITY", "min_score": 0.0, "max_score": 20.0, "rank": 5},
]


def classify_liquidity_bucket(
    composite_score: Optional[float],
    scoring_status: str,
    thresholds: Optional[List[Dict[str, Any]]] = None,
    percentile_rank: Optional[float] = None,
    method: str = "SCORE_THRESHOLD"
) -> Dict[str, Any]:
    """
    Classifies instrument into liquidity bucket:
    - VERY_HIGH_LIQUIDITY
    - HIGH_LIQUIDITY
    - MODERATE_LIQUIDITY
    - LOW_LIQUIDITY
    - VERY_LOW_LIQUIDITY
    - INSUFFICIENT_DATA (distinct data status, never assigned as lowest liquidity)
    """
    if scoring_status != "ACTIVE" or composite_score is None:
        return {
            "bucket_name": "INSUFFICIENT_DATA",
            "bucket_rank": 6,
            "classification_reason": "Data coverage gates or scoring prerequisites not met",
            "classification_method": method
        }

    if method == "PERCENTILE_RELATIVE" and percentile_rank is not None:
        pr = percentile_rank
        if pr >= 80.0:
            return {"bucket_name": "VERY_HIGH_LIQUIDITY", "bucket_rank": 1, "classification_reason": "Top 20th percentile", "classification_method": method}
        elif pr >= 60.0:
            return {"bucket_name": "HIGH_LIQUIDITY", "bucket_rank": 2, "classification_reason": "60th to 80th percentile", "classification_method": method}
        elif pr >= 40.0:
            return {"bucket_name": "MODERATE_LIQUIDITY", "bucket_rank": 3, "classification_reason": "40th to 60th percentile", "classification_method": method}
        elif pr >= 20.0:
            return {"bucket_name": "LOW_LIQUIDITY", "bucket_rank": 4, "classification_reason": "20th to 40th percentile", "classification_method": method}
        else:
            return {"bucket_name": "VERY_LOW_LIQUIDITY", "bucket_rank": 5, "classification_reason": "Bottom 20th percentile", "classification_method": method}

    # Default score threshold method
    active_thresholds = thresholds or DEFAULT_BUCKET_THRESHOLDS

    score = float(composite_score)
    for b in active_thresholds:
        min_s = float(b["min_score"])
        max_s = float(b["max_score"])
        rank = int(b.get("rank", 99))
        name = b["bucket"]

        # Upper bound inclusive for top bucket (100.0)
        if min_s <= score <= max_s if max_s >= 100.0 else (min_s <= score < max_s):
            return {
                "bucket_name": name,
                "bucket_rank": rank,
                "classification_reason": f"Score {score:.2f} within range [{min_s:.1f}, {max_s:.1f})",
                "classification_method": "SCORE_THRESHOLD"
            }

    # Fallback if edge case rounding
    if score >= 100.0:
        return {"bucket_name": "VERY_HIGH_LIQUIDITY", "bucket_rank": 1, "classification_reason": "Score >= 100.0", "classification_method": "SCORE_THRESHOLD"}
    return {"bucket_name": "VERY_LOW_LIQUIDITY", "bucket_rank": 5, "classification_reason": "Score <= 0.0", "classification_method": "SCORE_THRESHOLD"}

