"""
Mathematical formulations and threshold evaluation logic for M12 Risk Alerts.

Formulations:
1. VaR Threshold Evaluation & Proximity:
   Proximity (%) = (VaR_current / Threshold_warning) * 100
   Relative VaR (% NAV) = (VaR_absolute / NAV) * 100
2. Volatility Change:
   Delta_sigma = sigma_t - sigma_{t-1}
   Delta_sigma_% = ((sigma_t - sigma_{t-1}) / |sigma_{t-1}|) * 100
3. Drawdown Convention:
   Positive Drawdown Magnitude D_t = |DD_t| where DD_t = (V_t - HWM_t) / HWM_t
4. Threshold Evaluation:
   Upper bound:
     Warning triggered if X_t >= T_warning
     Critical triggered if X_t >= T_critical
     Recovery triggered if X_t <= T_recovery (where T_recovery < T_warning)
   Lower bound:
     Warning triggered if X_t <= T_warning
     Critical triggered if X_t <= T_critical
     Recovery triggered if X_t >= T_recovery (where T_recovery > T_warning)
5. Deduplication Key:
   Hash or deterministic string: f"{alert_type}:{portfolio_id}:{metric_id}:{threshold_type}"
"""

from decimal import Decimal
from typing import Optional, Dict, Any, Tuple


def to_decimal(val: Any) -> Decimal:
    if val is None:
        return Decimal("0.00")
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def calculate_threshold_proximity(current_value: Decimal, warning_threshold: Decimal) -> Decimal:
    """
    Proximity (%) = (current_value / warning_threshold) * 100
    """
    curr = to_decimal(current_value)
    warn = to_decimal(warning_threshold)
    if warn <= Decimal("0.00"):
        return Decimal("100.00") if curr > 0 else Decimal("0.00")
    prox = (curr / warn) * Decimal("100.00")
    return prox.quantize(Decimal("0.01"))


def calculate_relative_var_pct(var_absolute: Decimal, portfolio_nav: Decimal) -> Decimal:
    """
    VaR (% NAV) = (VaR_absolute / NAV) * 100
    """
    nav = to_decimal(portfolio_nav)
    if nav <= Decimal("0.00"):
        return Decimal("100.00")
    rel_var = (to_decimal(var_absolute) / nav) * Decimal("100.00")
    return rel_var.quantize(Decimal("0.01"))


def calculate_volatility_change(current_vol: Decimal, previous_vol: Decimal) -> Tuple[Decimal, Decimal]:
    """
    Returns: (Delta_vol, Delta_vol_pct)
    """
    curr = to_decimal(current_vol)
    prev = to_decimal(previous_vol)
    delta = curr - prev
    if prev <= Decimal("0.00"):
        delta_pct = Decimal("0.00")
    else:
        delta_pct = ((delta / abs(prev)) * Decimal("100.00")).quantize(Decimal("0.01"))
    return delta.quantize(Decimal("0.0001")), delta_pct


def calculate_drawdown_magnitude(signed_drawdown: Decimal) -> Decimal:
    """
    Returns positive drawdown magnitude D_t = |DD_t|.
    """
    return abs(to_decimal(signed_drawdown)).quantize(Decimal("0.0001"))


def evaluate_threshold_state(
    current_value: Decimal,
    warning_threshold: Decimal,
    critical_threshold: Decimal,
    recovery_threshold: Optional[Decimal] = None,
    current_state: str = "NORMAL",
    operator: str = "GREATER_THAN_OR_EQUAL",
) -> Tuple[str, bool]:
    """
    Evaluates threshold state with hysteresis.
    Returns (new_state, state_changed).
    States: NORMAL, APPROACHING, WARNING, CRITICAL, RECOVERING, RECOVERED.
    """
    curr = to_decimal(current_value)
    warn = to_decimal(warning_threshold)
    crit = to_decimal(critical_threshold)
    rec = to_decimal(recovery_threshold) if recovery_threshold is not None else (warn * Decimal("0.90"))

    new_state = current_state

    if operator in ["GREATER_THAN", "GREATER_THAN_OR_EQUAL"]:
        # Upper bound
        if curr >= crit:
            new_state = "CRITICAL"
        elif curr >= warn:
            new_state = "WARNING"
        elif curr >= (warn * Decimal("0.80")) and current_state == "NORMAL":
            new_state = "APPROACHING"
        elif current_state in ["WARNING", "CRITICAL"]:
            # Check recovery with hysteresis
            if curr <= rec:
                new_state = "RECOVERED"
            else:
                new_state = "RECOVERING"
        elif current_state == "RECOVERED" and curr < (warn * Decimal("0.80")):
            new_state = "NORMAL"
    else:
        # Lower bound
        if curr <= crit:
            new_state = "CRITICAL"
        elif curr <= warn:
            new_state = "WARNING"
        elif curr <= (warn * Decimal("1.20")) and current_state == "NORMAL":
            new_state = "APPROACHING"
        elif current_state in ["WARNING", "CRITICAL"]:
            rec_low = to_decimal(recovery_threshold) if recovery_threshold is not None else (warn * Decimal("1.10"))
            if curr >= rec_low:
                new_state = "RECOVERED"
            else:
                new_state = "RECOVERING"
        elif current_state == "RECOVERED" and curr > (warn * Decimal("1.20")):
            new_state = "NORMAL"

    state_changed = (new_state != current_state)
    return new_state, state_changed


def build_deduplication_key(
    alert_type: str,
    portfolio_id: str,
    metric_id: str,
    entity_id: Optional[str] = None
) -> str:
    """Creates a deterministic deduplication key."""
    ent = entity_id or "NONE"
    return f"{alert_type.upper()}:{portfolio_id}:{metric_id}:{ent}"

