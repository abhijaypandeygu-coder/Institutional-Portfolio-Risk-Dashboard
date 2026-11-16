"""
Mathematical formulations and SLA metrics for M11.08 Risk Escalation.

Formulations:
1. Acknowledgement time: T_ack = t_acknowledged - t_breach_created (or SLA start)
2. Escalation delay: T_escalation = t_escalated - t_trigger
3. Resolution time: T_resolution = t_closed - t_breach_created
4. Mitigation time: T_mitigation = t_mitigated - t_breach_created
5. SLA compliance rate: (eligible actions completed within SLA / total eligible completed actions) * 100
6. Reopening rate: (closed breach episodes subsequently reopened / eligible closed breach episodes) * 100
7. Escalation frequency: escalation events / eligible breach episodes
8. Deadline and business hours computation helper.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any


def calculate_duration_seconds(start_time: datetime, end_time: datetime) -> float:
    """Calculate elapsed duration between two datetime objects in seconds."""
    if not start_time or not end_time:
        return 0.0
    # Ensure both are UTC or timezone comparable
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)
    delta = (end_time - start_time).total_seconds()
    return max(0.0, delta)


def calculate_acknowledgement_time(sla_start: datetime, acknowledged_at: datetime) -> float:
    """T_ack = t_acknowledged - t_sla_start (in seconds)."""
    return calculate_duration_seconds(sla_start, acknowledged_at)


def calculate_mitigation_time(sla_start: datetime, mitigated_at: datetime) -> float:
    """T_mitigation = t_mitigated - t_sla_start (in seconds)."""
    return calculate_duration_seconds(sla_start, mitigated_at)


def calculate_resolution_time(sla_start: datetime, closed_at: datetime) -> float:
    """T_resolution = t_closed - t_sla_start (in seconds)."""
    return calculate_duration_seconds(sla_start, closed_at)


def calculate_sla_compliance_rate(completed_within_sla: int, total_completed: int) -> Decimal:
    """
    SLA Compliance (%) = (completed_within_sla / total_completed) * 100.
    Returns 100.00 if total_completed is 0.
    """
    if total_completed <= 0:
        return Decimal("100.00")
    rate = (Decimal(str(completed_within_sla)) / Decimal(str(total_completed))) * Decimal("100.00")
    return rate.quantize(Decimal("0.01"))


def calculate_reopening_rate(reopened_count: int, total_closed_count: int) -> Decimal:
    """
    Reopening Rate (%) = (reopened_count / total_closed_count) * 100.
    Returns 0.00 if total_closed_count is 0.
    """
    if total_closed_count <= 0:
        return Decimal("0.00")
    rate = (Decimal(str(reopened_count)) / Decimal(str(total_closed_count))) * Decimal("100.00")
    return rate.quantize(Decimal("0.01"))


def calculate_escalation_frequency(escalation_events_count: int, eligible_episodes_count: int) -> Decimal:
    """
    Escalation Frequency = escalation_events_count / eligible_episodes_count.
    Returns 0.00 if eligible_episodes_count is 0.
    """
    if eligible_episodes_count <= 0:
        return Decimal("0.00")
    freq = Decimal(str(escalation_events_count)) / Decimal(str(eligible_episodes_count))
    return freq.quantize(Decimal("0.01"))


def is_sla_breached(
    deadline: datetime,
    actual_or_now: Optional[datetime] = None,
    total_paused_seconds: float = 0.0
) -> bool:
    """
    Evaluates whether an SLA deadline is breached, accounting for authorized pauses.
    """
    if not deadline:
        return False
    effective_now = actual_or_now or datetime.now(timezone.utc)
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    if effective_now.tzinfo is None:
        effective_now = effective_now.replace(tzinfo=timezone.utc)
    
    adjusted_deadline = deadline + timedelta(seconds=total_paused_seconds)
    return effective_now > adjusted_deadline
