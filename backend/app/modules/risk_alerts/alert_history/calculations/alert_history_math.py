"""
Mathematical and analytical calculations for M12.08 — Alert History.

Formulas:
1. Alert Frequency:
   F_r = N_r / T
2. Recurrence Rate:
   RR = N_recurring / T
3. Average Interarrival Time:
   T_avg_interarrival = (1 / (n - 1)) * sum(t_i - t_{i-1})
4. Reopening Rate:
   ReopeningRate = (N_reopened / N_closed_at_least_once) * 100
5. Acknowledgement Rate:
   AckRate = (N_acknowledged / N_eligible_triggered) * 100
6. Average Lifecycle Durations:
   T_ack = t_ack - t_trigger
   T_closure = t_closed - t_trigger
7. Unresolved Alert Age:
   Age_i = t_now - t_trigger
8. Rule Noise Score:
   NoiseScore_r = w1 * F_r + w2 * R_r + w3 * D_r + w4 * Q_r
   Normalized to [0.0, 100.0] with configurable nonnegative weights.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple


def calculate_alert_frequency(
    occurrence_count: int,
    observation_period_days: float,
) -> float:
    """
    Alert frequency F_r = occurrences / days.
    """
    if observation_period_days <= 0:
        return float(occurrence_count)
    return round(float(occurrence_count) / float(observation_period_days), 4)


def calculate_interarrival_times(
    timestamps_utc: List[datetime],
) -> Tuple[List[float], float]:
    """
    Calculates list of interarrival intervals in seconds and average interarrival time.
    Requires timestamps in chronological order.
    """
    if len(timestamps_utc) < 2:
        return [], 0.0

    sorted_ts = sorted(timestamps_utc)
    intervals_sec: List[float] = []
    for i in range(1, len(sorted_ts)):
        dt = (sorted_ts[i] - sorted_ts[i - 1]).total_seconds()
        intervals_sec.append(max(0.0, dt))

    avg_interval = sum(intervals_sec) / len(intervals_sec)
    return intervals_sec, round(avg_interval, 2)


def calculate_lifecycle_duration_seconds(
    start_utc: datetime,
    end_utc: Optional[datetime],
) -> Optional[float]:
    """
    Calculates duration in seconds between start and end timestamps.
    Returns None if either timestamp is missing.
    """
    if start_utc is None or end_utc is None:
        return None
    delta = (end_utc - start_utc).total_seconds()
    return max(0.0, round(delta, 2))


def calculate_rates_percentage(
    numerator: int,
    denominator: int,
) -> Decimal:
    """
    Calculates percentage rate with safe zero handling.
    """
    if denominator <= 0:
        return Decimal("0.00")
    rate = (Decimal(str(numerator)) / Decimal(str(denominator))) * Decimal("100.0")
    return min(Decimal("100.00"), max(Decimal("0.00"), round(rate, 2)))


def calculate_rule_noise_score(
    trigger_frequency_per_day: float,
    recurrence_intensity: float,  # recurring occurrences / total occurrences in [0.0, 1.0]
    short_interval_duplicate_rate: float,  # proportion of occurrences <= 15m apart in [0.0, 1.0]
    low_severity_rapid_recovery_rate: float,  # proportion WARNING or recovered < 1h in [0.0, 1.0]
    w1: float = 0.30,
    w2: float = 0.30,
    w3: float = 0.25,
    w4: float = 0.15,
) -> Dict[str, Any]:
    """
    Computes explainable Rule Noise Score in [0.0, 100.0].
    
    NoiseScore_r = (w1*F_norm + w2*R_norm + w3*D_norm + w4*Q_norm) * 100
    Where F_norm saturates at 20 triggers/day.
    """
    # Normalize frequency (saturating at 20/day)
    f_norm = min(1.0, max(0.0, trigger_frequency_per_day / 20.0))
    r_norm = min(1.0, max(0.0, recurrence_intensity))
    d_norm = min(1.0, max(0.0, short_interval_duplicate_rate))
    q_norm = min(1.0, max(0.0, low_severity_rapid_recovery_rate))

    total_weight = w1 + w2 + w3 + w4
    if total_weight <= 0:
        total_weight = 1.0

    raw_score = (w1 * f_norm + w2 * r_norm + w3 * d_norm + w4 * q_norm) / total_weight
    noise_score = round(raw_score * 100.0, 2)

    return {
        "noise_score": noise_score,
        "is_noisy": noise_score >= 65.0,
        "components": {
            "frequency_norm": round(f_norm, 4),
            "recurrence_intensity_norm": round(r_norm, 4),
            "short_interval_rate_norm": round(d_norm, 4),
            "low_value_rapid_recovery_norm": round(q_norm, 4),
        },
        "weights": {
            "w_frequency": w1,
            "w_recurrence": w2,
            "w_short_interval": w3,
            "w_rapid_recovery": w4,
        },
        "version": "1.0",
    }


def generate_recurrence_grouping_key(
    source_rule_id: str,
    alert_category: str,
    portfolio_id: Optional[str] = None,
    instrument_id: Optional[str] = None,
) -> str:
    """
    Generates canonical grouping key for recurring condition grouping.
    """
    p = portfolio_id or "ALL_PORTFOLIOS"
    i = instrument_id or "ALL_INSTRUMENTS"
    return f"{source_rule_id.upper()}::{alert_category.upper()}::{p.upper()}::{i.upper()}"

