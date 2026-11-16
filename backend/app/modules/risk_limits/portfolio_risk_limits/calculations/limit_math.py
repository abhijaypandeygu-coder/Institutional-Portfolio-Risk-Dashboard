"""
Mathematical and policy evaluation calculations for M11.01 Portfolio Risk Limits.
Implements:
1. VaR limit utilization and headroom (Absolute & NAV-relative).
2. Volatility limit utilization and headroom (Realized & Forecast).
3. Drawdown limit utilization and headroom (Positive drawdown magnitude).
4. Boundary state classification (WITHIN_LIMIT, WARNING, HARD_LIMIT_EXCEEDED).
5. Precedence resolution and fail-safe non-pass state handling.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional, Tuple


def evaluate_threshold_utilization(
    observed_value: Decimal,
    warning_threshold: Decimal,
    hard_threshold: Decimal,
    comparison_operator: str = "GREATER_THAN_OR_EQUAL"
) -> Tuple[Decimal, Decimal, Decimal, str]:
    """
    Evaluates observed risk metric against warning and hard thresholds:
    U_warning = observed / warning_threshold
    U_hard = observed / hard_threshold
    Headroom = hard_threshold - observed
    States:
    - HARD_LIMIT_EXCEEDED: if observed >= hard_threshold (for GREATER_THAN_OR_EQUAL)
    - WARNING: if hard_threshold > observed >= warning_threshold
    - WITHIN_LIMIT: if observed < warning_threshold
    """
    if warning_threshold <= Decimal("0") or hard_threshold <= Decimal("0"):
        raise ValueError("Warning and hard thresholds must be strictly positive.")

    if hard_threshold < warning_threshold:
        raise ValueError("Hard threshold cannot be less restrictive than warning threshold.")

    u_warning = (observed_value / warning_threshold * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    u_hard = (observed_value / hard_threshold * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    headroom = (hard_threshold - observed_value).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    if comparison_operator in ("GREATER_THAN_OR_EQUAL", "GREATER_THAN"):
        if observed_value >= hard_threshold:
            state = "HARD_LIMIT_EXCEEDED"
        elif observed_value >= warning_threshold:
            state = "WARNING"
        else:
            state = "WITHIN_LIMIT"
    else:
        # For lower-bounded metrics (e.g. minimum liquidity or return)
        if observed_value <= hard_threshold:
            state = "HARD_LIMIT_EXCEEDED"
        elif observed_value <= warning_threshold:
            state = "WARNING"
        else:
            state = "WITHIN_LIMIT"

    return u_warning, u_hard, headroom, state


def evaluate_var_limit(
    observed_var: Decimal,
    limit_type: str,                   # ABSOLUTE or NAV_RELATIVE
    warning_threshold: Decimal,        # Monetary or % NAV
    hard_threshold: Decimal,           # Monetary or % NAV
    portfolio_nav: Optional[Decimal] = None
) -> Dict[str, Any]:
    """
    Evaluates VaR utilization:
    - If ABSOLUTE: directly compares observed_var with thresholds.
    - If NAV_RELATIVE: computes implied monetary limits or relative % VaR:
      Relative VaR % = observed_var / NAV * 100
      Evaluates against percentage thresholds.
    """
    if limit_type == "NAV_RELATIVE":
        if portfolio_nav is None or portfolio_nav <= Decimal("0"):
            return {
                "observed_value": observed_var,
                "warning_threshold": warning_threshold,
                "hard_threshold": hard_threshold,
                "warning_utilization_pct": Decimal("0.0"),
                "hard_utilization_pct": Decimal("0.0"),
                "headroom": Decimal("0.0"),
                "evaluation_status": "INVALID",
                "error_reason": "Portfolio NAV must be strictly positive for NAV-relative VaR evaluation."
            }
        # Compute relative VaR percentage
        rel_var = (observed_var / portfolio_nav * Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        u_warn, u_hard, headroom, state = evaluate_threshold_utilization(
            observed_value=rel_var,
            warning_threshold=warning_threshold,
            hard_threshold=hard_threshold
        )
        # Implied monetary headroom
        implied_hard_monetary = (portfolio_nav * (hard_threshold / Decimal("100"))).quantize(Decimal("0.01"))
        monetary_headroom = implied_hard_monetary - observed_var

        return {
            "observed_value": rel_var,
            "observed_monetary_var": observed_var,
            "warning_threshold": warning_threshold,
            "hard_threshold": hard_threshold,
            "warning_utilization_pct": u_warn,
            "hard_utilization_pct": u_hard,
            "headroom": headroom,
            "monetary_headroom": monetary_headroom,
            "evaluation_status": state
        }
    else:
        # ABSOLUTE VaR in base currency
        u_warn, u_hard, headroom, state = evaluate_threshold_utilization(
            observed_value=observed_var,
            warning_threshold=warning_threshold,
            hard_threshold=hard_threshold
        )
        return {
            "observed_value": observed_var,
            "warning_threshold": warning_threshold,
            "hard_threshold": hard_threshold,
            "warning_utilization_pct": u_warn,
            "hard_utilization_pct": u_hard,
            "headroom": headroom,
            "evaluation_status": state
        }


def evaluate_volatility_limit(
    observed_volatility: Decimal,       # e.g. 0.185 (18.5% annualized)
    warning_threshold: Decimal,         # e.g. 0.200 (20.0%)
    hard_threshold: Decimal             # e.g. 0.250 (25.0%)
) -> Dict[str, Any]:
    """
    Evaluates realized or forecast annualized volatility.
    """
    u_warn, u_hard, headroom, state = evaluate_threshold_utilization(
        observed_value=observed_volatility,
        warning_threshold=warning_threshold,
        hard_threshold=hard_threshold
    )
    return {
        "observed_value": observed_volatility,
        "warning_threshold": warning_threshold,
        "hard_threshold": hard_threshold,
        "warning_utilization_pct": u_warn,
        "hard_utilization_pct": u_hard,
        "headroom": headroom,
        "evaluation_status": state
    }


def evaluate_drawdown_limit(
    observed_drawdown: Decimal,         # Positive magnitude e.g. 0.082 (8.2%)
    warning_threshold: Decimal,         # e.g. 0.100 (10.0%)
    hard_threshold: Decimal             # e.g. 0.150 (15.0%)
) -> Dict[str, Any]:
    """
    Evaluates peak-to-trough drawdown magnitude.
    Drawdown magnitude is positive: D_t = -DD_t = (H_t - V_t) / H_t.
    """
    pos_dd = abs(observed_drawdown)
    u_warn, u_hard, headroom, state = evaluate_threshold_utilization(
        observed_value=pos_dd,
        warning_threshold=warning_threshold,
        hard_threshold=hard_threshold
    )
    return {
        "observed_value": pos_dd,
        "warning_threshold": warning_threshold,
        "hard_threshold": hard_threshold,
        "warning_utilization_pct": u_warn,
        "hard_utilization_pct": u_hard,
        "headroom": headroom,
        "evaluation_status": state
    }

