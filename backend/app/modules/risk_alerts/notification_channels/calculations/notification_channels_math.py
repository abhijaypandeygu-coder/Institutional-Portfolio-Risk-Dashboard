"""
Mathematical and policy algorithms for M12.07 — Notification Channels.

Covers:
1. Exponential backoff with bounded pseudo-random or deterministic jitter:
   d_n = min(d_max, d_0 * 2^(n-1)) + J_n
2. Timezone-aware quiet period evaluation (including midnight crossing and DST awareness).
3. Deterministic SHA-256 idempotency key generation for delivery requests.
4. Channel and recipient severity/category eligibility logic.
5. Delivery latency and success-rate metric calculations.
"""

from datetime import datetime, time
from decimal import Decimal
import hashlib
import json
from typing import Optional, Tuple, Dict, Any
import zoneinfo


def calculate_retry_delay(
    attempt_n: int,
    initial_delay_seconds: float = 30.0,
    max_delay_seconds: float = 3600.0,
    jitter_factor: float = 0.1,
    deterministic_seed: Optional[int] = None,
) -> float:
    """
    Calculate backoff delay for retry attempt n (1-indexed):
    d_n = min(d_max, d_0 * 2^(n-1)) + J_n
    Where J_n is bounded jitter in [0, jitter_factor * base_delay].
    If deterministic_seed is provided, jitter is calculated deterministically.
    """
    if attempt_n <= 0:
        attempt_n = 1

    # Exponential factor: 2^(n-1)
    exp_factor = 2 ** (attempt_n - 1)
    base_delay = min(max_delay_seconds, initial_delay_seconds * exp_factor)

    # Compute bounded jitter
    max_jitter = base_delay * jitter_factor
    if deterministic_seed is not None:
        # Deterministic pseudo-random fraction in [0, 1) using simple hash
        hash_val = int(hashlib.sha256(f"{deterministic_seed}:{attempt_n}".encode()).hexdigest()[:8], 16)
        jitter = (hash_val % 10000) / 10000.0 * max_jitter
    else:
        import random
        jitter = random.uniform(0, max_jitter)

    total_delay = min(max_delay_seconds, base_delay + jitter)
    return round(total_delay, 2)


def is_in_quiet_period(
    now_utc: datetime,
    quiet_start_time_str: str,  # "HH:MM" e.g. "22:00"
    quiet_end_time_str: str,    # "HH:MM" e.g. "07:00"
    recipient_timezone_str: str = "UTC",
) -> Tuple[bool, Optional[datetime]]:
    """
    Determine if now_utc falls inside recipient's quiet period.
    Also calculates the scheduled exit time (in UTC) when quiet period ends if currently active.
    
    Handles:
    - Same-day quiet periods (e.g. 01:00 to 05:00)
    - Overnight quiet periods crossing midnight (e.g. 22:00 to 07:00)
    - Timezone resolution with zoneinfo
    """
    try:
        tz = zoneinfo.ZoneInfo(recipient_timezone_str)
    except Exception:
        tz = zoneinfo.ZoneInfo("UTC")

    # Localize current time in recipient timezone
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
    now_local = now_utc.astimezone(tz)

    start_h, start_m = map(int, quiet_start_time_str.strip().split(":"))
    end_h, end_m = map(int, quiet_end_time_str.strip().split(":"))

    start_t = time(start_h, start_m)
    end_t = time(end_h, end_m)
    current_t = now_local.time()

    # Case 1: Quiet period spans across midnight (e.g. 22:00 to 07:00)
    if start_t > end_t:
        in_quiet = current_t >= start_t or current_t < end_t
        if in_quiet:
            # End time is next morning or today's morning
            if current_t >= start_t:
                # End is tomorrow at end_t
                from datetime import timedelta
                next_day = now_local.date() + timedelta(days=1)
                end_local = datetime.combine(next_day, end_t, tzinfo=tz)
            else:
                # End is today at end_t
                end_local = datetime.combine(now_local.date(), end_t, tzinfo=tz)
            return True, end_local.astimezone(zoneinfo.ZoneInfo("UTC"))
        return False, None

    # Case 2: Same-day quiet period (e.g. 13:00 to 14:00)
    elif start_t < end_t:
        in_quiet = start_t <= current_t < end_t
        if in_quiet:
            end_local = datetime.combine(now_local.date(), end_t, tzinfo=tz)
            return True, end_local.astimezone(zoneinfo.ZoneInfo("UTC"))
        return False, None

    # Case 3: Start == End (empty quiet window)
    return False, None


def generate_delivery_idempotency_key(
    notification_id: str,
    channel_code: str,
    recipient_user_id: str,
    cycle_or_sequence: int = 1,
) -> str:
    """
    Generates a deterministic SHA-256 idempotency key for notification-recipient-channel delivery.
    """
    raw = f"{notification_id}:{channel_code}:{recipient_user_id}:{cycle_or_sequence}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def evaluate_severity_eligibility(
    channel_allowed_severities: list[str],
    user_allowed_severities: Optional[list[str]],
    alert_severity: str,
) -> bool:
    """
    Evaluates whether alert severity is allowed by both channel configuration and user preference.
    Severity values: 'WARNING', 'CRITICAL', 'EMERGENCY'.
    """
    severity_norm = alert_severity.strip().upper()
    ch_norm = [s.strip().upper() for s in channel_allowed_severities]
    if severity_norm not in ch_norm:
        return False

    if user_allowed_severities is not None and len(user_allowed_severities) > 0:
        u_norm = [s.strip().upper() for s in user_allowed_severities]
        return severity_norm in u_norm

    return True


def evaluate_category_eligibility(
    channel_allowed_categories: list[str],
    user_allowed_categories: Optional[list[str]],
    alert_category: str,
) -> bool:
    """
    Evaluates whether alert category is allowed by both channel and user preference.
    """
    cat_norm = alert_category.strip().upper()
    ch_norm = [c.strip().upper() for c in channel_allowed_categories]
    if "ALL" not in ch_norm and cat_norm not in ch_norm:
        return False

    if user_allowed_categories is not None and len(user_allowed_categories) > 0:
        u_norm = [c.strip().upper() for c in user_allowed_categories]
        if "ALL" in u_norm:
            return True
        return cat_norm in u_norm

    return True


def calculate_delivery_latency_ms(
    creation_timestamp: datetime,
    outcome_timestamp: datetime,
) -> float:
    """
    Calculate delivery latency in milliseconds:
    L_delivery = (t_outcome - t_creation) in ms
    """
    delta = outcome_timestamp - creation_timestamp
    return max(0.0, delta.total_seconds() * 1000.0)


def calculate_delivery_success_rate(
    successful_deliveries: int,
    eligible_deliveries: int,
) -> Decimal:
    """
    Calculate success rate as a percentage:
    SuccessRate = (Successful terminal deliveries / Eligible delivery requests) * 100
    """
    if eligible_deliveries <= 0:
        return Decimal("100.00")
    rate = (Decimal(str(successful_deliveries)) / Decimal(str(eligible_deliveries))) * Decimal("100.0")
    return min(Decimal("100.00"), max(Decimal("0.00"), round(rate, 2)))

