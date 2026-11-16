"""
Mathematical specifications and calculation engine for M11.06 — Breach Detection.

Implements institutional quantitative breach logic:
1. Utilization & Breach Magnitude:
   - For Maximum-type limits (CAP):
     * U = x / T (when T > 0)
     * Breach = x > T (or x >= T)
     * Magnitude = max(0, x - T)
     * Excess% = ((x - T) / |T|) * 100
   - For Minimum-type limits (FLOOR):
     * U = T / x (when x > 0)
     * Breach = x < T (or x <= T)
     * Magnitude = max(0, T - x)
     * Shortfall% = ((T - x) / |T|) * 100
   - For Range limits [T_min, T_max]:
     * Breach = x < T_min or x > T_max
     * Magnitude = max(0, T_min - x) if x < T_min else max(0, x - T_max)
2. Comparison Operators:
   - GREATER_THAN, GREATER_EQUAL, LESS_THAN, LESS_EQUAL, EQUAL, OUTSIDE_RANGE, INSIDE_RANGE
3. Input Quality & Freshness Assessment:
   - Metric Age = t_evaluation - t_metric
   - Stale threshold enforcement (Age > max_age_seconds)
   - Quality states: VALID, STALE, MISSING, INVALID
4. Persistence Models:
   - Immediate Breach (zero tolerance / immediate flag)
   - Duration-based: (t_current - t_first_violation) >= D_required
   - Consecutive observations: count >= N_required
   - Window-based: K out of N observations violating within window
5. Hysteresis & Recovery Detection:
   - Separate entry threshold vs recovery threshold
   - Recovery persistence confirmation
6. Severity Classification:
   - LOW, MEDIUM, HIGH, CRITICAL based on excess magnitude and policy rules.
"""

from decimal import Decimal, ROUND_HALF_UP, DivisionByZero, InvalidOperation
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple


# Comparison operators
OP_GREATER_THAN = "GREATER_THAN"
OP_GREATER_EQUAL = "GREATER_EQUAL"
OP_LESS_THAN = "LESS_THAN"
OP_LESS_EQUAL = "LESS_EQUAL"
OP_EQUAL = "EQUAL"
OP_OUTSIDE_RANGE = "OUTSIDE_RANGE"
OP_INSIDE_RANGE = "INSIDE_RANGE"

# Threshold nature
THRESHOLD_TYPE_MAX = "MAX"
THRESHOLD_TYPE_MIN = "MIN"
THRESHOLD_TYPE_RANGE = "RANGE"

# Severity levels
SEVERITY_LOW = "LOW"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_HIGH = "HIGH"
SEVERITY_CRITICAL = "CRITICAL"

# Status values
STATUS_WITHIN_LIMIT = "WITHIN_LIMIT"
STATUS_WARNING = "WARNING"
STATUS_HARD_BREACH = "HARD_BREACH"
STATUS_TRANSIENT_BREACH = "TRANSIENT_BREACH"
STATUS_PERSISTENCE_PENDING = "PERSISTENCE_PENDING"
STATUS_PERSISTENT_BREACH = "PERSISTENT_BREACH"
STATUS_RECOVERY_PENDING = "RECOVERY_PENDING"
STATUS_RECOVERED = "RECOVERED"
STATUS_STALE_INPUT = "STALE_INPUT"
STATUS_INVALID_INPUT = "INVALID_INPUT"
STATUS_LIMIT_UNAVAILABLE = "LIMIT_UNAVAILABLE"
STATUS_CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
STATUS_EVALUATION_FAILED = "EVALUATION_FAILED"
STATUS_NOT_APPLICABLE = "NOT_APPLICABLE"


def to_decimal(val: Any) -> Decimal:
    """Safely converts input to Decimal."""
    if val is None:
        return Decimal("0")
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def evaluate_boundary_violation(
    observed_value: Decimal,
    threshold: Decimal,
    operator: str,
    threshold_high: Optional[Decimal] = None
) -> bool:
    """
    Evaluates whether observed value violates the boundary defined by operator.
    """
    op = operator.upper()
    if op == OP_GREATER_THAN:
        return observed_value > threshold
    elif op == OP_GREATER_EQUAL:
        return observed_value >= threshold
    elif op == OP_LESS_THAN:
        return observed_value < threshold
    elif op == OP_LESS_EQUAL:
        return observed_value <= threshold
    elif op == OP_EQUAL:
        return observed_value == threshold
    elif op == OP_OUTSIDE_RANGE:
        high = threshold_high if threshold_high is not None else threshold
        return observed_value < threshold or observed_value > high
    elif op == OP_INSIDE_RANGE:
        high = threshold_high if threshold_high is not None else threshold
        return threshold <= observed_value <= high
    else:
        raise ValueError(f"Unsupported comparison operator: {operator}")


def calculate_utilization_and_magnitude(
    observed_value: Decimal,
    threshold: Decimal,
    limit_type: str = THRESHOLD_TYPE_MAX,
    threshold_high: Optional[Decimal] = None
) -> Tuple[Decimal, Decimal, Decimal]:
    """
    Computes (utilization_ratio, breach_magnitude, excess_or_shortfall_percentage).
    
    Returns:
        (utilization, magnitude, excess_pct)
    """
    l_type = limit_type.upper()
    obs = to_decimal(observed_value)
    thresh = to_decimal(threshold)
    high = to_decimal(threshold_high) if threshold_high is not None else thresh
    
    if l_type == THRESHOLD_TYPE_MAX:
        # Maximum-type limit
        if thresh > 0:
            utilization = (obs / thresh).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        elif thresh == 0:
            utilization = Decimal("999.0000") if obs > 0 else Decimal("0.0000")
        else:
            utilization = Decimal("0.0000")

        if obs > thresh:
            magnitude = (obs - thresh).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            if abs(thresh) > 0:
                excess_pct = (((obs - thresh) / abs(thresh)) * Decimal("100")).quantize(
                    Decimal("0.0001"), rounding=ROUND_HALF_UP
                )
            else:
                excess_pct = Decimal("100.0000")
        else:
            magnitude = Decimal("0.0000")
            excess_pct = Decimal("0.0000")

    elif l_type == THRESHOLD_TYPE_MIN:
        # Minimum-type limit (Floor)
        if obs > 0:
            utilization = (thresh / obs).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        else:
            utilization = Decimal("999.0000") if thresh > 0 else Decimal("0.0000")

        if obs < thresh:
            magnitude = (thresh - obs).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            if abs(thresh) > 0:
                excess_pct = (((thresh - obs) / abs(thresh)) * Decimal("100")).quantize(
                    Decimal("0.0001"), rounding=ROUND_HALF_UP
                )
            else:
                excess_pct = Decimal("100.0000")
        else:
            magnitude = Decimal("0.0000")
            excess_pct = Decimal("0.0000")

    elif l_type == THRESHOLD_TYPE_RANGE:
        if obs < thresh:
            magnitude = (thresh - obs).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            utilization = (thresh / obs).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) if obs > 0 else Decimal("999.0000")
            excess_pct = (((thresh - obs) / abs(thresh)) * Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) if abs(thresh) > 0 else Decimal("100.0000")
        elif obs > high:
            magnitude = (obs - high).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            utilization = (obs / high).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) if high > 0 else Decimal("999.0000")
            excess_pct = (((obs - high) / abs(high)) * Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) if abs(high) > 0 else Decimal("100.0000")
        else:
            magnitude = Decimal("0.0000")
            utilization = Decimal("1.0000")
            excess_pct = Decimal("0.0000")
    else:
        raise ValueError(f"Unsupported limit type: {limit_type}")

    return (utilization, magnitude, excess_pct)


def check_input_freshness(
    metric_timestamp: datetime,
    evaluation_timestamp: datetime,
    max_permitted_age_seconds: int = 3600
) -> Tuple[bool, int]:
    """
    Checks if metric timestamp is sufficiently fresh relative to evaluation timestamp.
    Returns (is_fresh, age_seconds).
    """
    # Normalize tzinfo if mixed
    t_eval = evaluation_timestamp.replace(tzinfo=None)
    t_met = metric_timestamp.replace(tzinfo=None)
    
    age = int((t_eval - t_met).total_seconds())
    if age < 0:
        # Future timestamp or minor clock skew: treat as 0 age, valid
        age = 0
        
    is_fresh = age <= max_permitted_age_seconds
    return (is_fresh, age)


def classify_breach_severity(
    breach_magnitude: Decimal,
    threshold: Decimal,
    excess_pct: Decimal,
    is_hard_breach: bool,
    immediate_breach: bool = False
) -> str:
    """
    Classifies breach severity deterministically based on excess magnitude and breach nature.
    """
    if not is_hard_breach:
        return SEVERITY_LOW

    if immediate_breach:
        return SEVERITY_CRITICAL

    if excess_pct >= Decimal("50.0"):
        return SEVERITY_CRITICAL
    elif excess_pct >= Decimal("20.0"):
        return SEVERITY_HIGH
    elif excess_pct >= Decimal("5.0"):
        return SEVERITY_MEDIUM
    else:
        return SEVERITY_LOW


def evaluate_persistence(
    observations: List[Tuple[datetime, bool]],  # list of (timestamp, is_violating)
    first_violation_at: Optional[datetime],
    current_time: datetime,
    persistence_mode: str = "DURATION",         # "DURATION", "CONSECUTIVE", "WINDOW", "IMMEDIATE"
    required_duration_seconds: int = 300,
    required_consecutive_count: int = 3,
    window_observations_count: int = 5,
    window_required_violating: int = 3,
    immediate_breach: bool = False
) -> Tuple[bool, str]:
    """
    Evaluates whether violating observations qualify as a sustained/persistent breach.
    
    Returns:
        (is_persistent, persistence_status)
    """
    if immediate_breach or persistence_mode == "IMMEDIATE":
        return (True, STATUS_PERSISTENT_BREACH)

    if not observations:
        return (False, STATUS_PERSISTENCE_PENDING)

    if persistence_mode == "DURATION":
        if not first_violation_at:
            return (False, STATUS_PERSISTENCE_PENDING)
        duration_sec = int((current_time.replace(tzinfo=None) - first_violation_at.replace(tzinfo=None)).total_seconds())
        if duration_sec >= required_duration_seconds:
            return (True, STATUS_PERSISTENT_BREACH)
        else:
            return (False, STATUS_PERSISTENCE_PENDING)

    elif persistence_mode == "CONSECUTIVE":
        # Check trailing consecutive violating observations
        consecutive_violations = 0
        for _, is_violating in reversed(observations):
            if is_violating:
                consecutive_violations += 1
            else:
                break
        if consecutive_violations >= required_consecutive_count:
            return (True, STATUS_PERSISTENT_BREACH)
        else:
            return (False, STATUS_PERSISTENCE_PENDING)

    elif persistence_mode == "WINDOW":
        recent_obs = observations[-window_observations_count:] if len(observations) >= window_observations_count else observations
        violating_count = sum(1 for _, is_v in recent_obs if is_v)
        if violating_count >= window_required_violating:
            return (True, STATUS_PERSISTENT_BREACH)
        else:
            return (False, STATUS_PERSISTENCE_PENDING)

    else:
        # Default fallback to duration
        return (False, STATUS_PERSISTENCE_PENDING)


def check_recovery_hysteresis(
    observed_value: Decimal,
    threshold: Decimal,
    recovery_threshold: Optional[Decimal],
    limit_type: str = THRESHOLD_TYPE_MAX
) -> bool:
    """
    Checks if an observation has cleared the recovery threshold under hysteresis.
    For MAX limits: recovered when observed_value <= recovery_threshold (where recovery_threshold <= threshold).
    For MIN limits: recovered when observed_value >= recovery_threshold (where recovery_threshold >= threshold).
    """
    l_type = limit_type.upper()
    effective_recovery = recovery_threshold if recovery_threshold is not None else threshold

    if l_type == THRESHOLD_TYPE_MAX:
        return observed_value <= effective_recovery
    elif l_type == THRESHOLD_TYPE_MIN:
        return observed_value >= effective_recovery
    else:
        return observed_value <= effective_recovery
