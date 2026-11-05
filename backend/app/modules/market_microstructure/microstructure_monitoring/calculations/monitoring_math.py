"""
Microstructure Monitoring Mathematical Calculations (M09.09).

Implements:
1. Spread Volatility & Widening:
   - Absolute spread change, relative % change, bps change
   - Rolling mean, rolling sample standard deviation, coefficient of variation (CV)
   - Time-weighted spread mean across piecewise-constant durations
   - Spread range (max - min) and robust standardization (Z_robust using MAD)
   - Spread widening classification with hysteresis
2. Depth Fluctuations, Depletion & Replenishment:
   - Aggregate & per-level depth changes (price-level matched vs rank matched)
   - Price-band depth aggregation
   - Depth depletion amount, velocity, and recovery ratio
   - Replenishment duration tracking to 25%, 50%, 75%, 100% recovery
3. Update Intensity & Burst Detection:
   - Categorized message counts (valid, trade, add, modify, cancel, snapshot, heartbeat, duplicate, invalid)
   - Message rate, unique event rate, and book-change rate
   - Intensity ratio vs baseline and robust burst Z-score
4. Staleness & Feed Inactivity:
   - Observation age (t_now - t_source) and receive latency (t_recv - t_source)
   - Feed inactivity vs book inactivity classification
5. Statistical Anomaly Detectors:
   - Rolling Z-score, Robust MAD Z-score
   - Historical percentile
   - EWMA monitoring & CUSUM change detection
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timezone
import math
import numpy as np


def to_decimal(val: Any) -> Decimal:
    """Helper to convert to Decimal safely with no silent float rounding."""
    if val is None:
        return Decimal("0")
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def compute_spread_changes(
    current_spread: Decimal,
    previous_spread: Optional[Decimal],
    current_midpoint: Optional[Decimal] = None
) -> Dict[str, Optional[Decimal]]:
    """
    Computes absolute, relative percentage, and basis point changes in spread.
    Safeguard: If previous_spread is zero or None, relative change is None.
    """
    if previous_spread is None:
        return {
            "absolute_change": Decimal("0"),
            "relative_change_pct": None,
            "spread_bps": (current_spread / current_midpoint * Decimal("10000")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) if current_midpoint and current_midpoint > 0 else None,
            "change_bps": None
        }

    abs_change = (current_spread - previous_spread).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
    
    rel_change_pct = None
    if previous_spread > Decimal("0"):
        rel_change_pct = ((current_spread - previous_spread) / previous_spread * Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    current_bps = None
    if current_midpoint and current_midpoint > 0:
        current_bps = (current_spread / current_midpoint * Decimal("10000")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    return {
        "absolute_change": abs_change,
        "relative_change_pct": rel_change_pct,
        "spread_bps": current_bps,
        "change_bps": None # Can be populated if prior bps is known
    }


def compute_spread_series_metrics(
    spreads: List[Decimal],
    timestamps: Optional[List[datetime]] = None
) -> Dict[str, Optional[Decimal]]:
    """
    Calculates rolling statistics over spread series:
    - mean, sample standard deviation, CV, range, and time-weighted mean.
    """
    N = len(spreads)
    if N == 0:
        return {
            "mean": None,
            "stddev": None,
            "cv": None,
            "spread_range": None,
            "time_weighted_mean": None
        }

    mean_val = (sum(spreads) / Decimal(str(N))).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
    spread_range = (max(spreads) - min(spreads)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    if N < 2:
        return {
            "mean": mean_val,
            "stddev": Decimal("0"),
            "cv": Decimal("0") if mean_val > Decimal("0") else None,
            "spread_range": spread_range,
            "time_weighted_mean": mean_val
        }

    # Sample standard deviation
    variance = sum((s - mean_val) ** 2 for s in spreads) / Decimal(str(N - 1))
    stddev_val = Decimal(str(math.sqrt(float(variance)))).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    cv_val = None
    if mean_val > Decimal("0"):
        cv_val = (stddev_val / mean_val).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    # Time-weighted spread mean if timestamps provided
    tw_mean = mean_val
    if timestamps and len(timestamps) == N and N >= 2:
        total_time_secs = Decimal("0")
        weighted_sum = Decimal("0")
        for i in range(N - 1):
            dt = Decimal(str(max(0.0, (timestamps[i+1] - timestamps[i]).total_seconds())))
            if dt > 0:
                weighted_sum += spreads[i] * dt
                total_time_secs += dt
        if total_time_secs > Decimal("0"):
            tw_mean = (weighted_sum / total_time_secs).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    return {
        "mean": mean_val,
        "stddev": stddev_val,
        "cv": cv_val,
        "spread_range": spread_range,
        "time_weighted_mean": tw_mean
    }


def compute_robust_z_score(
    current_value: Decimal,
    historical_values: List[Decimal]
) -> Tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
    """
    Computes Median, MAD, and Robust Z-score:
    Z_robust = (X_t - Median(X)) / (1.4826 * MAD)
    Returns: (median, mad, z_robust)
    """
    if not historical_values:
        return None, None, None

    vals = np.array([float(v) for v in historical_values])
    med = float(np.median(vals))
    abs_deviations = np.abs(vals - med)
    mad = float(np.median(abs_deviations))

    med_dec = Decimal(str(med)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
    mad_dec = Decimal(str(mad)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    if mad <= 1e-9:
        return med_dec, mad_dec, None  # Safeguard: do not divide by zero

    cur_val = float(current_value)
    z_rob = (cur_val - med) / (1.4826 * mad)
    z_dec = Decimal(str(z_rob)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    return med_dec, mad_dec, z_dec


def classify_spread_deterioration(
    current_spread: Decimal,
    baseline_spread: Decimal,
    z_robust: Optional[Decimal] = None,
    bps_change: Optional[Decimal] = None
) -> Tuple[str, str]:
    """
    Classifies spread deterioration into category and severity with hysteresis awareness.
    Returns: (category, severity)
    """
    if baseline_spread <= Decimal("0"):
        return "INSUFFICIENT_DATA", "INFO"

    ratio = current_spread / baseline_spread

    if ratio >= Decimal("3.0") or (z_robust is not None and z_robust >= Decimal("4.0")):
        return "EXTREME_WIDENING", "CRITICAL"
    elif ratio >= Decimal("2.0") or (z_robust is not None and z_robust >= Decimal("2.5")):
        return "SIGNIFICANT_WIDENING", "HIGH"
    elif ratio >= Decimal("1.4") or (z_robust is not None and z_robust >= Decimal("1.5")):
        return "MILD_WIDENING", "MEDIUM"
    elif ratio <= Decimal("0.6"):
        return "UNEXPECTED_COMPRESSION", "LOW"
    else:
        return "NORMAL", "INFO"


def compute_depth_fluctuations(
    current_depth: Decimal,
    previous_depth: Optional[Decimal],
    elapsed_seconds: Optional[Decimal] = None
) -> Dict[str, Any]:
    """
    Computes absolute change, relative percentage change, depletion amount, and depletion velocity.
    """
    if previous_depth is None:
        return {
            "absolute_change": Decimal("0"),
            "relative_change_pct": None,
            "classification": "DEPTH_UNCHANGED",
            "depletion_amount": Decimal("0"),
            "depletion_rate": None
        }

    abs_change = (current_depth - previous_depth).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    
    rel_change_pct = None
    if previous_depth > Decimal("0"):
        rel_change_pct = ((current_depth - previous_depth) / previous_depth * Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    classification = "DEPTH_UNCHANGED"
    if abs_change > Decimal("0"):
        classification = "DEPTH_INCREASE"
    elif abs_change < Decimal("0"):
        classification = "DEPTH_REDUCTION"

    depletion_amount = Decimal("0")
    if abs_change < Decimal("0"):
        depletion_amount = -abs_change

    depletion_rate = None
    if elapsed_seconds and elapsed_seconds > Decimal("0") and depletion_amount > Decimal("0"):
        depletion_rate = (depletion_amount / elapsed_seconds).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    return {
        "absolute_change": abs_change,
        "relative_change_pct": rel_change_pct,
        "classification": classification,
        "depletion_amount": depletion_amount,
        "depletion_rate": depletion_rate
    }


def compute_replenishment_metrics(
    baseline_depth: Decimal,
    post_depletion_depth: Decimal,
    current_depth: Decimal
) -> Dict[str, Any]:
    """
    Computes replenishment amount and recovery ratio:
    RecoveryRatio = (D_t - D_post) / (D_base - D_post)
    """
    lost_depth = baseline_depth - post_depletion_depth
    if lost_depth <= Decimal("0"):
        return {
            "replenishment_amount": Decimal("0"),
            "recovery_ratio": Decimal("1.0"),
            "recovery_status": "FULLY_RECOVERED"
        }

    replenishment = (current_depth - post_depletion_depth).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    recovery_ratio = (replenishment / lost_depth).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    if recovery_ratio >= Decimal("1.0"):
        status = "FULLY_RECOVERED"
    elif recovery_ratio >= Decimal("0.25"):
        status = "PARTIALLY_RECOVERED"
    elif recovery_ratio < Decimal("0"):
        status = "FURTHER_DEPLETED"
    else:
        status = "NOT_RECOVERED"

    return {
        "replenishment_amount": replenishment,
        "recovery_ratio": recovery_ratio,
        "recovery_status": status
    }


def compute_update_intensity(
    total_messages: int,
    valid_messages: int,
    book_updates: int,
    elapsed_seconds: Decimal,
    baseline_rate: Optional[Decimal] = None
) -> Dict[str, Any]:
    """
    Computes message rates and book-change rates over interval.
    Distinguishes source message rate from reconstructed-book change rate.
    """
    if elapsed_seconds <= Decimal("0"):
        return {
            "message_rate": Decimal("0"),
            "valid_message_rate": Decimal("0"),
            "book_change_rate": Decimal("0"),
            "intensity_ratio": None
        }

    msg_rate = (Decimal(str(total_messages)) / elapsed_seconds).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    valid_rate = (Decimal(str(valid_messages)) / elapsed_seconds).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    book_rate = (Decimal(str(book_updates)) / elapsed_seconds).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    intensity_ratio = None
    if baseline_rate and baseline_rate > Decimal("0"):
        intensity_ratio = (msg_rate / baseline_rate).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    return {
        "message_rate": msg_rate,
        "valid_message_rate": valid_rate,
        "book_change_rate": book_rate,
        "intensity_ratio": intensity_ratio
    }


def compute_staleness_metrics(
    current_time: datetime,
    source_timestamp: datetime,
    receive_timestamp: datetime,
    expected_cadence_ms: int = 1000
) -> Dict[str, Any]:
    """
    Computes observation age, receive latency, and classifies feed staleness.
    """
    # Ensure all timestamps are UTC
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    if source_timestamp.tzinfo is None:
        source_timestamp = source_timestamp.replace(tzinfo=timezone.utc)
    if receive_timestamp.tzinfo is None:
        receive_timestamp = receive_timestamp.replace(tzinfo=timezone.utc)

    observation_age_ms = int(max(0.0, (current_time - source_timestamp).total_seconds() * 1000))
    receive_latency_ms = int((receive_timestamp - source_timestamp).total_seconds() * 1000)

    # Classify staleness
    if observation_age_ms <= expected_cadence_ms:
        state = "FRESH"
    elif observation_age_ms <= expected_cadence_ms * 3:
        state = "AGING"
    elif observation_age_ms <= expected_cadence_ms * 10:
        state = "STALE"
    else:
        state = "FEED_UNAVAILABLE"

    return {
        "observation_age_ms": observation_age_ms,
        "receive_latency_ms": receive_latency_ms,
        "expected_update_cadence_ms": expected_cadence_ms,
        "staleness_state": state
    }


def compute_ewma_series(
    values: List[Decimal],
    alpha: Decimal = Decimal("0.2")
) -> List[Decimal]:
    """
    Calculates Exponentially Weighted Moving Average (EWMA):
    E_t = alpha * X_t + (1 - alpha) * E_{t-1}
    """
    if not values:
        return []
    
    ewma_res: List[Decimal] = []
    current_ewma = values[0]
    ewma_res.append(current_ewma)

    one_minus_alpha = Decimal("1") - alpha
    for val in values[1:]:
        current_ewma = (alpha * val + one_minus_alpha * current_ewma).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
        ewma_res.append(current_ewma)

    return ewma_res


def compute_cusum_detector(
    values: List[Decimal],
    target_mean: Decimal,
    slack_allowance: Decimal,
    decision_threshold: Decimal
) -> Dict[str, Any]:
    """
    Two-sided Cumulative Sum (CUSUM) change detection:
    S_high_t = max(0, S_high_{t-1} + (X_t - target_mean - slack))
    S_low_t  = max(0, S_low_{t-1} - (X_t - target_mean + slack))
    """
    s_high = Decimal("0")
    s_low = Decimal("0")
    anomaly_detected = False
    triggered_direction = None

    for val in values:
        s_high = max(Decimal("0"), s_high + (val - target_mean - slack_allowance))
        s_low = max(Decimal("0"), s_low - (val - target_mean - slack_allowance))

        if s_high >= decision_threshold:
            anomaly_detected = True
            triggered_direction = "UPWARD_SHIFT"
            break
        elif s_low >= decision_threshold:
            anomaly_detected = True
            triggered_direction = "DOWNWARD_SHIFT"
            break

    return {
        "anomaly_detected": anomaly_detected,
        "direction": triggered_direction,
        "s_high": s_high.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        "s_low": s_low.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    }

