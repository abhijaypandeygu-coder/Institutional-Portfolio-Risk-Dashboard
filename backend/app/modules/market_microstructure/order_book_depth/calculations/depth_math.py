"""
M09.02 Order Book Depth - Pure Mathematical & Statistical Calculations Engine.
Implements:
1. Bid-Side Depth: Descending sorting, summation across N levels, per-level notional, cumulative quantity & notional.
2. Ask-Side Depth: Ascending sorting, summation across N levels, per-level notional, cumulative quantity & notional.
3. Midpoint Distance: Absolute distance, bps distance (|P - M| / M * 10,000), tick distance (|P - M| / TickSize).
4. Depth Imbalance:
   - Quantity Imbalance: (D_b - D_a) / (D_b + D_a)
   - Notional Imbalance: (ND_b - ND_a) / (ND_b + ND_a)
   - Weighted Imbalance: sum(w_i * Q_i) with exponential decay w_i = exp(-lambda * d_i).
   - Guardrails: Non-positive denominator returns None (never fabricated zero).
5. Price-Band Depth: Aggregation of liquidity within distance bands from midpoint.
6. Depth Persistence & Stability:
   - Time-weighted mean depth: D_TW = sum(D_j * delta_t_j) / sum(delta_t_j)
   - Time-weighted depth variance and standard deviation: sigma_TW = sqrt(sum(delta_t_j * (D_j - D_TW)^2) / sum(delta_t_j))
   - Coefficient of Variation: CV = sigma_TW / D_TW
   - Threshold Persistence: % of valid time displayed depth >= D_min
   - Exact price-level persistence & price-band persistence
   - Valid coverage ratio against expected session duration.
"""

from datetime import datetime, timezone
from decimal import Decimal
import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np


def sort_and_validate_levels(
    levels: List[Dict[str, Any]],
    side: str,  # 'BID' or 'ASK'
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Validates and sorts price levels:
    - Bids: sorted descending by price (P_b,1 > P_b,2 > ...)
    - Asks: sorted ascending by price (P_a,1 < P_a,2 < ...)
    - Checks for positive prices, non-negative quantities.
    Returns: (sorted_levels, status_code)
    """
    if not levels:
        return [], f"EMPTY_{side}_SIDE"

    parsed_levels = []
    seen_prices = set()

    for idx, lvl in enumerate(levels):
        raw_p = lvl.get("price")
        raw_q = lvl.get("quantity")
        if raw_p is None or raw_q is None:
            continue

        p = Decimal(str(raw_p))
        q = Decimal(str(raw_q))

        if p <= Decimal("0"):
            return [], "INVALID_PRICE"
        if q < Decimal("0"):
            return [], "INVALID_QUANTITY"

        if p in seen_prices:
            # Duplicate price level detected
            return [], "DUPLICATE_PRICE_LEVEL"
        seen_prices.add(p)

        parsed_levels.append({
            "price": p,
            "quantity": q,
            "order_count": lvl.get("order_count") or lvl.get("orders_count"),
        })

    if not parsed_levels:
        return [], f"EMPTY_{side}_SIDE"

    # Sort
    if side.upper() == "BID":
        parsed_levels.sort(key=lambda x: x["price"], reverse=True)
    else:
        parsed_levels.sort(key=lambda x: x["price"])

    return parsed_levels, "VALID"


def compute_depth_by_level(
    bids: List[Dict[str, Any]],
    asks: List[Dict[str, Any]],
    contract_multiplier: Decimal = Decimal("1.0"),
    tick_size: Optional[Decimal] = None,
    max_levels: Optional[int] = None,
) -> Tuple[Optional[Decimal], List[Dict[str, Any]], List[Dict[str, Any]], str]:
    """
    Computes per-level depth, cumulative quantity, cumulative notional, and distance from midpoint.
    Returns: (midpoint, processed_bids, processed_asks, status)
    """
    sorted_bids, bid_status = sort_and_validate_levels(bids, "BID")
    sorted_asks, ask_status = sort_and_validate_levels(asks, "ASK")

    if bid_status != "VALID" or ask_status != "VALID":
        status = bid_status if bid_status != "VALID" else ask_status
        return None, [], [], status

    best_bid = sorted_bids[0]["price"]
    best_ask = sorted_asks[0]["price"]

    if best_ask < best_bid:
        return None, [], [], "CROSSED_BOOK"

    midpoint = (best_bid + best_ask) / Decimal("2")

    if max_levels:
        sorted_bids = sorted_bids[:max_levels]
        sorted_asks = sorted_asks[:max_levels]

    # Process Bids
    processed_bids = []
    cum_q = Decimal("0")
    cum_n = Decimal("0")
    for idx, b in enumerate(sorted_bids):
        lvl_idx = idx + 1
        p = b["price"]
        q = b["quantity"]
        notional = p * q * contract_multiplier
        cum_q += q
        cum_n += notional

        d_abs = midpoint - p
        d_bps = (abs(d_abs) / midpoint) * Decimal("10000") if midpoint > Decimal("0") else None
        d_ticks = (abs(d_abs) / tick_size) if tick_size and tick_size > Decimal("0") else None

        processed_bids.append({
            "side": "BID",
            "level_index": lvl_idx,
            "price": p,
            "quantity": q,
            "notional": notional,
            "cumulative_quantity": cum_q,
            "cumulative_notional": cum_n,
            "distance_from_midpoint": d_abs,
            "distance_bps": d_bps,
            "distance_ticks": d_ticks,
            "order_count": b.get("order_count"),
        })

    # Process Asks
    processed_asks = []
    cum_q = Decimal("0")
    cum_n = Decimal("0")
    for idx, a in enumerate(sorted_asks):
        lvl_idx = idx + 1
        p = a["price"]
        q = a["quantity"]
        notional = p * q * contract_multiplier
        cum_q += q
        cum_n += notional

        d_abs = p - midpoint
        d_bps = (abs(d_abs) / midpoint) * Decimal("10000") if midpoint > Decimal("0") else None
        d_ticks = (abs(d_abs) / tick_size) if tick_size and tick_size > Decimal("0") else None

        processed_asks.append({
            "side": "ASK",
            "level_index": lvl_idx,
            "price": p,
            "quantity": q,
            "notional": notional,
            "cumulative_quantity": cum_q,
            "cumulative_notional": cum_n,
            "distance_from_midpoint": d_abs,
            "distance_bps": d_bps,
            "distance_ticks": d_ticks,
            "order_count": a.get("order_count"),
        })

    return midpoint, processed_bids, processed_asks, "VALID"


def compute_cumulative_depth(
    levels: List[Dict[str, Any]],
    n_levels: int,
    contract_multiplier: Decimal = Decimal("1.0"),
) -> Tuple[Decimal, Decimal]:
    """
    Computes total displayed quantity and notional across top N levels.
    Returns: (total_quantity, total_notional)
    """
    top_n = levels[:n_levels]
    tot_q = sum((lvl["quantity"] for lvl in top_n), Decimal("0"))
    tot_n = sum((lvl["price"] * lvl["quantity"] * contract_multiplier for lvl in top_n), Decimal("0"))
    return tot_q, tot_n


def compute_depth_imbalance(
    bid_quantity: Decimal,
    ask_quantity: Decimal,
    bid_notional: Decimal,
    ask_notional: Decimal,
    weighted_bids: Optional[Decimal] = None,
    weighted_asks: Optional[Decimal] = None,
) -> Dict[str, Optional[Decimal]]:
    """
    Calculates:
    - Quantity Imbalance: I_Q = (D_b - D_a) / (D_b + D_a)
    - Notional Imbalance: I_N = (ND_b - ND_a) / (ND_b + ND_a)
    - Weighted Imbalance: I_W = (WD_b - WD_a) / (WD_b + WD_a)
    - Imbalance percentages
    Guardrail: If denominator is zero or missing, returns None.
    """
    q_denom = bid_quantity + ask_quantity
    n_denom = bid_notional + ask_notional

    q_imb = (bid_quantity - ask_quantity) / q_denom if q_denom > Decimal("0") else None
    n_imb = (bid_notional - ask_notional) / n_denom if n_denom > Decimal("0") else None

    q_imb_pct = q_imb * Decimal("100") if q_imb is not None else None
    n_imb_pct = n_imb * Decimal("100") if n_imb is not None else None

    w_imb = None
    w_imb_pct = None
    if weighted_bids is not None and weighted_asks is not None:
        w_denom = weighted_bids + weighted_asks
        if w_denom > Decimal("0"):
            w_imb = (weighted_bids - weighted_asks) / w_denom
            w_imb_pct = w_imb * Decimal("100")

    return {
        "quantity_imbalance": q_imb,
        "notional_imbalance": n_imb,
        "quantity_imbalance_percentage": q_imb_pct,
        "notional_imbalance_percentage": n_imb_pct,
        "weighted_imbalance": w_imb,
        "weighted_imbalance_percentage": w_imb_pct,
    }


def compute_distance_weighted_depth(
    levels: List[Dict[str, Any]],
    decay_lambda: float = 0.05,
    distance_key: str = "distance_bps",
) -> Decimal:
    """
    Computes exponential distance-weighted depth: WD = sum(w_i * Q_i)
    where w_i = exp(-decay_lambda * d_i).
    """
    tot_weighted = Decimal("0")
    for lvl in levels:
        dist = lvl.get(distance_key)
        q = lvl["quantity"]
        if dist is not None:
            dist_flt = float(dist)
            weight = math.exp(-decay_lambda * dist_flt)
            tot_weighted += q * Decimal(str(weight))
        else:
            tot_weighted += q
    return tot_weighted


def compute_price_band_depth(
    bid_levels: List[Dict[str, Any]],
    ask_levels: List[Dict[str, Any]],
    bands: List[Tuple[float, float, str]],  # (lower_bps, upper_bps, band_id)
    contract_multiplier: Decimal = Decimal("1.0"),
) -> List[Dict[str, Any]]:
    """
    Aggregates liquidity within distance bands from midpoint (e.g. 0-5 bps, 5-10 bps).
    Each band contains:
    - band_id, lower, upper
    - bid_quantity, ask_quantity, bid_notional, ask_notional
    - bid_level_count, ask_level_count
    - quantity_imbalance, notional_imbalance
    """
    results = []
    for lower, upper, band_id in bands:
        b_in_band = [
            b for b in bid_levels
            if b["distance_bps"] is not None and lower <= float(b["distance_bps"]) < upper
        ]
        a_in_band = [
            a for a in ask_levels
            if a["distance_bps"] is not None and lower <= float(a["distance_bps"]) < upper
        ]

        b_q = sum((b["quantity"] for b in b_in_band), Decimal("0"))
        a_q = sum((a["quantity"] for a in a_in_band), Decimal("0"))
        b_n = sum((b["price"] * b["quantity"] * contract_multiplier for b in b_in_band), Decimal("0"))
        a_n = sum((a["price"] * a["quantity"] * contract_multiplier for a in a_in_band), Decimal("0"))

        q_denom = b_q + a_q
        n_denom = b_n + a_n
        q_imb = (b_q - a_q) / q_denom if q_denom > Decimal("0") else None
        n_imb = (b_n - a_n) / n_denom if n_denom > Decimal("0") else None

        results.append({
            "band_id": band_id,
            "band_lower_bound": lower,
            "band_upper_bound": upper,
            "distance_unit": "BPS",
            "bid_quantity": b_q,
            "ask_quantity": a_q,
            "bid_notional": b_n,
            "ask_notional": a_n,
            "bid_level_count": len(b_in_band),
            "ask_level_count": len(a_in_band),
            "quantity_imbalance": q_imb,
            "notional_imbalance": n_imb,
        })
    return results


def compute_depth_persistence(
    observations: List[Dict[str, Any]],
    session_start: datetime,
    session_end: datetime,
    minimum_depth_threshold: Optional[Decimal] = None,
    max_state_age_seconds: float = 300.0,
    target_price: Optional[Decimal] = None,
) -> Dict[str, Any]:
    """
    Computes time-weighted depth statistics, variability, coefficient of variation,
    and threshold persistence over a time window [session_start, session_end].

    Each observation in `observations` is expected to have:
      - 'timestamp': datetime
      - 'bid_depth': Decimal (e.g. cumulative bid quantity across top N levels)
      - 'ask_depth': Decimal
      - 'bid_prices': Optional[List[Decimal]]
      - 'quality_status': str ('VALID', 'STALE', etc.)

    Formulas:
      - D_TW = sum(D_j * delta_t_j) / sum(delta_t_j)
      - sigma_TW = sqrt(sum(delta_t_j * (D_j - D_TW)^2) / sum(delta_t_j))
      - CV = sigma_TW / D_TW
      - P_threshold = sum(delta_t_j * 1(D_j >= D_min)) / T_valid
      - P_level = sum(delta_t_j * 1(price exists)) / T_valid
    """
    expected_duration = (session_end - session_start).total_seconds()
    if expected_duration <= 0:
        return {
            "bid_time_weighted_mean": None,
            "ask_time_weighted_mean": None,
            "bid_time_weighted_stddev": None,
            "ask_time_weighted_stddev": None,
            "bid_depth_cv": None,
            "ask_depth_cv": None,
            "bid_threshold_persistence": None,
            "ask_threshold_persistence": None,
            "price_level_persistence": None,
            "valid_duration_seconds": 0.0,
            "expected_duration_seconds": 0.0,
            "coverage_ratio": 0.0,
            "coverage_percentage": 0.0,
            "valid_state_count": 0,
        }

    # Normalize tz awareness between session boundaries and observations
    def _normalize_tz(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    s_start = _normalize_tz(session_start)
    s_end = _normalize_tz(session_end)
    expected_duration = (s_end - s_start).total_seconds()

    # Filter & sort observations in [session_start, session_end]
    valid_obs = [
        o for o in observations
        if s_start <= _normalize_tz(o["timestamp"]) <= s_end
    ]
    valid_obs.sort(key=lambda x: _normalize_tz(x["timestamp"]))

    if not valid_obs:
        return {
            "bid_time_weighted_mean": None,
            "ask_time_weighted_mean": None,
            "bid_time_weighted_stddev": None,
            "ask_time_weighted_stddev": None,
            "bid_depth_cv": None,
            "ask_depth_cv": None,
            "bid_threshold_persistence": None,
            "ask_threshold_persistence": None,
            "price_level_persistence": None,
            "valid_duration_seconds": 0.0,
            "expected_duration_seconds": expected_duration,
            "coverage_ratio": 0.0,
            "coverage_percentage": 0.0,
            "valid_state_count": 0,
        }

    intervals: List[Dict[str, Any]] = []
    num_obs = len(valid_obs)
    total_valid_sec = 0.0

    for i in range(num_obs):
        cur = valid_obs[i]
        cur_ts = _normalize_tz(cur["timestamp"])
        next_ts = _normalize_tz(valid_obs[i + 1]["timestamp"]) if i + 1 < num_obs else s_end

        raw_dur = (next_ts - cur_ts).total_seconds()
        clamped_dur = min(raw_dur, max_state_age_seconds)
        if clamped_dur <= 0:
            continue

        q_status = cur.get("quality_status", "VALID")
        is_valid = q_status in ("VALID", "VALID_WITH_WARNINGS")

        b_depth = cur.get("bid_depth")
        a_depth = cur.get("ask_depth")

        if is_valid and b_depth is not None and a_depth is not None:
            intervals.append({
                "duration": clamped_dur,
                "bid_depth": float(b_depth),
                "ask_depth": float(a_depth),
                "bid_prices": cur.get("bid_prices", []),
            })
            total_valid_sec += clamped_dur

    if total_valid_sec <= 0:
        return {
            "bid_time_weighted_mean": None,
            "ask_time_weighted_mean": None,
            "bid_time_weighted_stddev": None,
            "ask_time_weighted_stddev": None,
            "bid_depth_cv": None,
            "ask_depth_cv": None,
            "bid_threshold_persistence": None,
            "ask_threshold_persistence": None,
            "price_level_persistence": None,
            "valid_duration_seconds": 0.0,
            "expected_duration_seconds": expected_duration,
            "coverage_ratio": 0.0,
            "coverage_percentage": 0.0,
            "valid_state_count": 0,
        }

    # Time-weighted means
    sum_b_dur = sum(item["bid_depth"] * item["duration"] for item in intervals)
    sum_a_dur = sum(item["ask_depth"] * item["duration"] for item in intervals)

    b_mean = sum_b_dur / total_valid_sec
    a_mean = sum_a_dur / total_valid_sec

    # Time-weighted variances & stddev
    var_b = sum(item["duration"] * ((item["bid_depth"] - b_mean) ** 2) for item in intervals) / total_valid_sec
    var_a = sum(item["duration"] * ((item["ask_depth"] - a_mean) ** 2) for item in intervals) / total_valid_sec

    std_b = math.sqrt(max(0.0, var_b))
    std_a = math.sqrt(max(0.0, var_a))

    # Coefficient of variation
    cv_b = (std_b / b_mean) if b_mean > 0 else None
    cv_a = (std_a / a_mean) if a_mean > 0 else None

    # Threshold persistence
    b_thresh_dur = 0.0
    a_thresh_dur = 0.0
    if minimum_depth_threshold is not None:
        thresh_flt = float(minimum_depth_threshold)
        b_thresh_dur = sum(item["duration"] for item in intervals if item["bid_depth"] >= thresh_flt)
        a_thresh_dur = sum(item["duration"] for item in intervals if item["ask_depth"] >= thresh_flt)

    b_thresh_pct = (b_thresh_dur / total_valid_sec * 100.0) if minimum_depth_threshold is not None else None
    a_thresh_pct = (a_thresh_dur / total_valid_sec * 100.0) if minimum_depth_threshold is not None else None

    # Exact price-level persistence
    level_persistence_pct = None
    if target_price is not None:
        lvl_dur = sum(
            item["duration"] for item in intervals
            if target_price in item.get("bid_prices", [])
        )
        level_persistence_pct = (lvl_dur / total_valid_sec) * 100.0

    cov_ratio = total_valid_sec / expected_duration
    cov_pct = cov_ratio * 100.0

    # Composite stability score (higher is more stable, capped [0, 100])
    # Composite: 50% coverage + 30% CV stability (1 - min(1, CV)) + 20% threshold persistence
    stability_score = None
    if cv_b is not None and cv_a is not None:
        avg_cv = (cv_b + cv_a) / 2.0
        cv_term = max(0.0, 1.0 - min(1.0, avg_cv)) * 30.0
        cov_term = min(1.0, cov_ratio) * 50.0
        thresh_term = ((b_thresh_pct + a_thresh_pct) / 200.0 * 20.0) if b_thresh_pct is not None and a_thresh_pct is not None else 10.0
        stability_score = round(cov_term + cv_term + thresh_term, 2)

    return {
        "bid_time_weighted_mean": round(b_mean, 4),
        "ask_time_weighted_mean": round(a_mean, 4),
        "bid_time_weighted_stddev": round(std_b, 4),
        "ask_time_weighted_stddev": round(std_a, 4),
        "bid_depth_cv": round(cv_b, 6) if cv_b is not None else None,
        "ask_depth_cv": round(cv_a, 6) if cv_a is not None else None,
        "bid_threshold_persistence": round(b_thresh_pct, 4) if b_thresh_pct is not None else None,
        "ask_threshold_persistence": round(a_thresh_pct, 4) if a_thresh_pct is not None else None,
        "price_level_persistence": round(level_persistence_pct, 4) if level_persistence_pct is not None else None,
        "depth_stability_score": stability_score,
        "valid_duration_seconds": round(total_valid_sec, 2),
        "expected_duration_seconds": round(expected_duration, 2),
        "coverage_ratio": round(cov_ratio, 6),
        "coverage_percentage": round(cov_pct, 4),
        "valid_state_count": len(intervals),
    }
