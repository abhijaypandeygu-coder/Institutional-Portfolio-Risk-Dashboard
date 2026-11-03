"""
M09.01 Bid-Ask Spread - Pure Mathematical & Statistical Calculations Engine.
Implements:
- Absolute spread: S = A - B
- Midpoint: M = (A + B) / 2
- Relative spread: RS = (A - B) / Denominator
- Units: Decimal, Percentage (RS * 100), Basis Points (RS * 10,000)
- Spread in Ticks: S / TickSize
- Observation-weighted statistics: Mean, Median, Min, Max, Percentiles (P5, P25, P50, P75, P90, P95, P99)
- Time-weighted statistics: S_TW = sum(S_j * delta_t_j) / sum(delta_t_j)
- Time coverage & quality metrics
"""

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np


def compute_absolute_spread(
    best_bid: Optional[Decimal],
    best_ask: Optional[Decimal],
) -> Tuple[Optional[Decimal], str]:
    """
    Computes absolute spread: S_t = A_t - B_t in native price units.
    Validates finite, non-null, non-negative equity prices, crossed and locked books.
    Returns: (absolute_spread, status_code)
    """
    if best_bid is None and best_ask is None:
        return None, "MISSING_BOTH_SIDES"
    if best_bid is None:
        return None, "MISSING_BID"
    if best_ask is None:
        return None, "MISSING_ASK"

    if not isinstance(best_bid, Decimal):
        best_bid = Decimal(str(best_bid))
    if not isinstance(best_ask, Decimal):
        best_ask = Decimal(str(best_ask))

    if best_bid < Decimal("0") or best_ask < Decimal("0"):
        return None, "INVALID_PRICE"

    if best_ask < best_bid:
        # Crossed book: A_t < B_t (MUST NOT calculate negative spread)
        return None, "CROSSED_BOOK"

    if best_ask == best_bid:
        # Locked book: A_t = B_t -> S_t = 0
        return Decimal("0"), "LOCKED_BOOK"

    spread = best_ask - best_bid
    return spread, "VALID"


def compute_midpoint_price(
    best_bid: Decimal,
    best_ask: Decimal,
) -> Optional[Decimal]:
    """
    Computes quote midpoint: M_t = (A_t + B_t) / 2.
    Requires positive valid midpoint.
    """
    if not isinstance(best_bid, Decimal):
        best_bid = Decimal(str(best_bid))
    if not isinstance(best_ask, Decimal):
        best_ask = Decimal(str(best_ask))

    mid = (best_bid + best_ask) / Decimal("2")
    if mid <= Decimal("0"):
        return None
    return mid


def compute_relative_spread(
    absolute_spread: Decimal,
    reference_price: Decimal,
) -> Tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal], str]:
    """
    Normalizes absolute spread using reference price (midpoint, bid, ask, or approved reference).
    RS = S / P_ref
    RS_pct = RS * 100
    RS_bps = RS * 10,000

    Returns: (relative_decimal, relative_percentage, relative_bps, status)
    """
    if absolute_spread is None:
        return None, None, None, "UNAVAILABLE"

    if not isinstance(absolute_spread, Decimal):
        absolute_spread = Decimal(str(absolute_spread))
    if not isinstance(reference_price, Decimal):
        reference_price = Decimal(str(reference_price))

    if reference_price <= Decimal("0"):
        return None, None, None, "INVALID_REFERENCE_PRICE"

    rs_decimal = absolute_spread / reference_price
    rs_pct = rs_decimal * Decimal("100")
    rs_bps = rs_decimal * Decimal("10000")

    return rs_decimal, rs_pct, rs_bps, "VALID"


def compute_spread_in_ticks(
    absolute_spread: Decimal,
    tick_size: Optional[Decimal],
) -> Optional[Decimal]:
    """
    Computes spread in ticks: SpreadTicks = S_t / TickSize.
    """
    if absolute_spread is None or tick_size is None:
        return None
    if not isinstance(tick_size, Decimal):
        tick_size = Decimal(str(tick_size))
    if tick_size <= Decimal("0"):
        return None
    return absolute_spread / tick_size


def compute_observation_weighted_statistics(
    values: List[Decimal],
    percentiles: Optional[List[float]] = None,
) -> Dict[str, Optional[float]]:
    """
    Calculates observation-weighted statistics for a series of values:
    - Mean
    - Median
    - Standard Deviation
    - Minimum, Maximum
    - Percentiles (default: [5, 25, 50, 75, 90, 95, 99])
    """
    if percentiles is None:
        percentiles = [5.0, 25.0, 50.0, 75.0, 90.0, 95.0, 99.0]

    valid_floats = [float(v) for v in values if v is not None and not np.isnan(float(v))]
    count = len(valid_floats)
    if count == 0:
        res: Dict[str, Optional[float]] = {
            "count": 0,
            "mean": None,
            "median": None,
            "std": None,
            "min": None,
            "max": None,
        }
        for p in percentiles:
            p_label = f"p{int(p) if p.is_integer() else str(p).replace('.', '_')}"
            res[p_label] = None
        return res

    arr = np.array(valid_floats, dtype=np.float64)
    mean_val = float(np.mean(arr))
    median_val = float(np.median(arr))
    std_val = float(np.std(arr, ddof=1)) if count > 1 else 0.0
    min_val = float(np.min(arr))
    max_val = float(np.max(arr))

    res = {
        "count": count,
        "mean": mean_val,
        "median": median_val,
        "std": std_val,
        "min": min_val,
        "max": max_val,
    }

    for p in percentiles:
        p_val = float(np.percentile(arr, p))
        p_label = f"p{int(p) if p.is_integer() else str(p).replace('.', '_')}"
        res[p_label] = p_val

    return res


def compute_time_weighted_spread(
    observations: List[Dict[str, Any]],
    session_start: datetime,
    session_end: datetime,
    max_quote_age_seconds: float = 300.0,
    include_locked_as_zero: bool = True,
) -> Dict[str, Any]:
    """
    Calculates time-weighted spread: S_TW = sum(S_j * delta_t_j) / sum(delta_t_j)
    and time coverage: Coverage_time = (ValidBookDuration / ExpectedEligibleMarketDuration) * 100

    Each observation in `observations` is expected to have:
      - 'timestamp': datetime (UTC or tz-aware)
      - 'absolute_spread': Optional[Decimal]
      - 'relative_spread': Optional[Decimal]
      - 'quality_status': str ('VALID', 'VALID_LOCKED', 'LOCKED_BOOK', 'STALE_QUOTE', etc.)

    Guarantees:
      - Quotes are strictly sorted by timestamp.
      - State duration ends at next observation timestamp, session_end, or when quote expires (max_quote_age).
      - Stale/invalid states are not carried forward indefinitely.
      - Intervals where book is invalid or missing are excluded from the numerator and valid duration.
      - Does not double count overlapping intervals.
    """
    expected_duration = (session_end - session_start).total_seconds()
    if expected_duration <= 0:
        return {
            "time_weighted_spread": None,
            "time_weighted_relative_spread": None,
            "valid_book_duration_seconds": 0.0,
            "expected_duration_seconds": 0.0,
            "coverage_percentage": 0.0,
            "valid_intervals_count": 0,
        }

    # Filter and sort observations within [session_start, session_end]
    valid_obs = []
    for obs in observations:
        ts = obs["timestamp"]
        if session_start <= ts <= session_end:
            valid_obs.append(obs)

    valid_obs.sort(key=lambda x: x["timestamp"])

    if not valid_obs:
        return {
            "time_weighted_spread": None,
            "time_weighted_relative_spread": None,
            "valid_book_duration_seconds": 0.0,
            "expected_duration_seconds": expected_duration,
            "coverage_percentage": 0.0,
            "valid_intervals_count": 0,
        }

    total_weighted_abs = Decimal("0")
    total_weighted_rel = Decimal("0")
    total_valid_seconds = Decimal("0")
    valid_intervals = 0

    num_obs = len(valid_obs)
    for i in range(num_obs):
        cur = valid_obs[i]
        cur_ts = cur["timestamp"]
        next_ts = valid_obs[i + 1]["timestamp"] if i + 1 < num_obs else session_end

        # Duration of this state
        raw_duration = (next_ts - cur_ts).total_seconds()
        # Cap at max_quote_age_seconds
        clamped_duration = min(raw_duration, max_quote_age_seconds)
        if clamped_duration <= 0:
            continue

        q_status = cur.get("quality_status", "VALID")
        is_locked = q_status in ("LOCKED_BOOK", "VALID_LOCKED")
        is_valid = q_status in ("VALID", "VALID_LOCKED") or (is_locked and include_locked_as_zero)

        abs_s = cur.get("absolute_spread")
        rel_s = cur.get("relative_spread")

        if is_valid and abs_s is not None:
            dur_dec = Decimal(str(clamped_duration))
            total_weighted_abs += abs_s * dur_dec
            if rel_s is not None:
                total_weighted_rel += rel_s * dur_dec
            total_valid_seconds += dur_dec
            valid_intervals += 1

    valid_secs_float = float(total_valid_seconds)
    coverage_pct = (valid_secs_float / expected_duration) * 100.0

    tw_abs = float(total_weighted_abs / total_valid_seconds) if total_valid_seconds > Decimal("0") else None
    tw_rel = float(total_weighted_rel / total_valid_seconds) if total_valid_seconds > Decimal("0") else None

    return {
        "time_weighted_spread": tw_abs,
        "time_weighted_relative_spread": tw_rel,
        "valid_book_duration_seconds": valid_secs_float,
        "expected_duration_seconds": expected_duration,
        "coverage_percentage": round(coverage_pct, 4),
        "valid_intervals_count": valid_intervals,
    }

