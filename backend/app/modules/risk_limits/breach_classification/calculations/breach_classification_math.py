"""
Mathematical specifications and classification evaluation logic for M11.07 — Breach Classification.

Implements institutional severity determination:
1. Target Severities:
   - WARNING: Proximity to boundary, soft-threshold violation, transient condition.
   - CRITICAL: Material hard violation, high excess, sustained breach, material portfolio exposure.
   - EMERGENCY: Zero-tolerance violation, severe excess, immediate operational urgency, extreme concentration.
2. Materiality Assessment:
   - Materiality% = (Absolute Impact / Portfolio NAV) * 100
   - Exposure Weight% = (Exposure Value / Portfolio NAV) * 100
   - Unavailable handling when NAV <= 0 or missing.
3. Precedence Hierarchy:
   - EMERGENCY > CRITICAL > WARNING
   - Mandatory emergency triggers bypass persistence when configured.
   - Lower severity condition cannot downgrade active higher severity without explicit recovery evidence.
4. Classification Dimensions:
   - Breach Magnitude & Utilization (from M11.06)
   - Persistence & Recurrence (from M11.06)
   - Materiality & Scope (Portfolio, Sector, Instrument)
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional, Tuple


# Severity constants
SEVERITY_WARNING = "WARNING"
SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_EMERGENCY = "EMERGENCY"

# Internal processing states
STATUS_UNCLASSIFIED = "UNCLASSIFIED"
STATUS_CLASSIFICATION_PENDING = "CLASSIFICATION_PENDING"
STATUS_CLASSIFIED = "CLASSIFIED"
STATUS_CLASSIFICATION_UNAVAILABLE = "CLASSIFICATION_UNAVAILABLE"
STATUS_CLASSIFICATION_ERROR = "CLASSIFICATION_ERROR"

# Precedence rank (higher number = higher severity)
SEVERITY_RANKS = {
    SEVERITY_WARNING: 1,
    SEVERITY_CRITICAL: 2,
    SEVERITY_EMERGENCY: 3,
}


def to_decimal(val: Any) -> Decimal:
    """Safely converts value to Decimal."""
    if val is None:
        return Decimal("0")
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def calculate_portfolio_materiality(
    impact_amount: Decimal,
    portfolio_nav: Optional[Decimal]
) -> Tuple[Optional[Decimal], str]:
    """
    Computes portfolio materiality percentage:
      Materiality% = (impact_amount / portfolio_nav) * 100
    Returns (materiality_pct, status) where status is 'VALID', 'UNAVAILABLE', or 'INVALID_NAV'.
    """
    if portfolio_nav is None:
        return (None, "UNAVAILABLE")
    
    nav = to_decimal(portfolio_nav)
    if nav <= Decimal("0"):
        return (None, "INVALID_NAV")

    impact = to_decimal(impact_amount)
    pct = ((impact / nav) * Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return (pct, "VALID")


def resolve_higher_severity(severity_a: str, severity_b: str) -> str:
    """
    Returns the higher severity based on deterministic precedence:
    EMERGENCY > CRITICAL > WARNING
    """
    rank_a = SEVERITY_RANKS.get(severity_a.upper(), 0)
    rank_b = SEVERITY_RANKS.get(severity_b.upper(), 0)
    if rank_a >= rank_b:
        return severity_a.upper()
    return severity_b.upper()


def evaluate_severity_rule(
    rule_operator: str,
    metric_value: Decimal,
    threshold_low: Decimal,
    threshold_high: Optional[Decimal] = None
) -> bool:
    """
    Evaluates rule criteria against numeric values (magnitude, utilization, or materiality).
    """
    op = rule_operator.upper()
    v = to_decimal(metric_value)
    t_low = to_decimal(threshold_low)
    t_high = to_decimal(threshold_high) if threshold_high is not None else t_low

    if op in ("GREATER_THAN", "GT"):
        return v > t_low
    elif op in ("GREATER_EQUAL", "GTE"):
        return v >= t_low
    elif op in ("LESS_THAN", "LT"):
        return v < t_low
    elif op in ("LESS_EQUAL", "LTE"):
        return v <= t_low
    elif op in ("EQUAL", "EQ"):
        return v == t_low
    elif op in ("BETWEEN",):
        return t_low <= v <= t_high
    elif op in ("OUTSIDE_RANGE",):
        return v < t_low or v > t_high
    else:
        raise ValueError(f"Unsupported rule operator: {rule_operator}")

