"""
Financial calculations and mathematical specifications for M11.02 — Position Limits.

Implements:
1. Signed and absolute position weight calculation:
   W_i = (MV_i / NAV_p) * 100
   AW_i = (|MV_i| / NAV_p) * 100
2. Absolute notional calculation:
   N_i = |MV_i|
3. Long and short exposure isolation:
   MV_i^long = max(MV_i, 0),  W_i^long = (MV_i^long / NAV_p) * 100,  N_i^long = MV_i^long
   MV_i^short = max(-MV_i, 0), W_i^short = (MV_i^short / NAV_p) * 100, N_i^short = MV_i^short
4. Issuer-level aggregation:
   AMV_e = sum_{i in e} |MV_i| (Gross concentration)
   W_e = (AMV_e / NAV_p) * 100
   NMV_e = sum_{i in e} MV_i (Signed net exposure)
   LMV_e = sum_{i in e} max(MV_i, 0)
   SMV_e = sum_{i in e} max(-MV_i, 0)
5. Utilization & headroom:
   Utilization = (ActualExposure / LimitThreshold) * 100
   Capacity = LimitThreshold - ActualExposure
   BreachAmount = max(0, ActualExposure - LimitThreshold)
6. Proposed-order simulation:
   Q_post = Q_current + Q_order (signed)
   MV_post = Q_post * Price * FX
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional, Tuple


def calculate_position_weight(
    market_value: Decimal,
    portfolio_nav: Decimal,
    use_absolute: bool = True
) -> Tuple[Decimal, str]:
    """
    Calculates position weight as a percentage of portfolio NAV.
    If use_absolute is True, computes AW_i = (|MV_i| / NAV_p) * 100.
    Returns (weight_pct, status).
    Fail-safe: If portfolio_nav <= 0, returns (0, 'INVALID_NAV').
    """
    if portfolio_nav is None or portfolio_nav <= Decimal("0"):
        return Decimal("0.0000"), "INVALID_NAV"

    val = abs(market_value) if use_absolute else market_value
    weight = (val / portfolio_nav * Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return weight, "VALID"


def calculate_directional_exposure(
    signed_market_value: Decimal,
    direction: str = "NET"
) -> Decimal:
    """
    Isolates exposure by direction:
    - 'LONG': max(MV_i, 0)
    - 'SHORT': max(-MV_i, 0) (as positive magnitude)
    - 'ABSOLUTE' or 'GROSS': |MV_i|
    - 'NET': signed_market_value
    """
    if direction.upper() == "LONG":
        return max(signed_market_value, Decimal("0.0000"))
    elif direction.upper() == "SHORT":
        return max(-signed_market_value, Decimal("0.0000"))
    elif direction.upper() in ("ABSOLUTE", "GROSS"):
        return abs(signed_market_value)
    return signed_market_value


def calculate_limit_utilization(
    actual_exposure: Decimal,
    warning_threshold: Decimal,
    hard_threshold: Decimal,
    comparison_operator: str = "GREATER_THAN_OR_EQUAL"
) -> Dict[str, Any]:
    """
    Calculates utilization percentage, remaining capacity, breach amount, and evaluation status.
    Utilization_hard = (actual / hard_threshold) * 100
    Utilization_warn = (actual / warning_threshold) * 100
    Capacity = hard_threshold - actual
    Breach = max(0, actual - hard_threshold)
    """
    if hard_threshold <= Decimal("0") or warning_threshold <= Decimal("0"):
        raise ValueError("Warning and hard thresholds must be strictly positive.")

    if hard_threshold < warning_threshold:
        raise ValueError("Hard threshold cannot be lower than warning threshold.")

    u_hard = (actual_exposure / hard_threshold * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    u_warn = (actual_exposure / warning_threshold * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    capacity = (hard_threshold - actual_exposure).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    breach_amount = max(Decimal("0.0000"), (actual_exposure - hard_threshold)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    if comparison_operator in ("GREATER_THAN_OR_EQUAL", "GREATER_THAN"):
        if actual_exposure >= hard_threshold:
            status = "HARD_LIMIT_EXCEEDED"
        elif actual_exposure >= warning_threshold:
            status = "WARNING"
        else:
            status = "WITHIN_LIMIT"
    else:
        # Lower-bound limit
        if actual_exposure <= hard_threshold:
            status = "HARD_LIMIT_EXCEEDED"
        elif actual_exposure <= warning_threshold:
            status = "WARNING"
        else:
            status = "WITHIN_LIMIT"

    return {
        "actual_exposure": actual_exposure,
        "warning_threshold": warning_threshold,
        "hard_threshold": hard_threshold,
        "warning_utilization_pct": u_warn,
        "hard_utilization_pct": u_hard,
        "remaining_capacity": capacity,
        "breach_amount": breach_amount,
        "evaluation_status": status
    }


def aggregate_issuer_exposures(
    positions: List[Dict[str, Any]],
    portfolio_nav: Optional[Decimal] = None
) -> Dict[str, Any]:
    """
    Aggregates multi-instrument/multi-listing exposures for an issuer:
    - Gross Exposure (AMV_e) = sum |MV_i|
    - Net Exposure (NMV_e) = sum MV_i
    - Long Exposure (LMV_e) = sum max(MV_i, 0)
    - Short Exposure (SMV_e) = sum max(-MV_i, 0)
    - Gross Weight = (AMV_e / NAV) * 100
    - Net Weight = (NMV_e / NAV) * 100
    - Long Weight = (LMV_e / NAV) * 100
    - Short Weight = (SMV_e / NAV) * 100
    """
    gross_exp = Decimal("0.0000")
    net_exp = Decimal("0.0000")
    long_exp = Decimal("0.0000")
    short_exp = Decimal("0.0000")

    for pos in positions:
        mv = Decimal(str(pos.get("market_value", 0)))
        gross_exp += abs(mv)
        net_exp += mv
        long_exp += max(mv, Decimal("0.0000"))
        short_exp += max(-mv, Decimal("0.0000"))

    gross_weight = Decimal("0.0000")
    net_weight = Decimal("0.0000")
    long_weight = Decimal("0.0000")
    short_weight = Decimal("0.0000")

    if portfolio_nav and portfolio_nav > Decimal("0"):
        gross_weight = (gross_exp / portfolio_nav * Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        net_weight = (net_exp / portfolio_nav * Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        long_weight = (long_exp / portfolio_nav * Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        short_weight = (short_exp / portfolio_nav * Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    return {
        "gross_exposure": gross_exp.quantize(Decimal("0.01")),
        "net_exposure": net_exp.quantize(Decimal("0.01")),
        "long_exposure": long_exp.quantize(Decimal("0.01")),
        "short_exposure": short_exp.quantize(Decimal("0.01")),
        "gross_weight_pct": gross_weight,
        "net_weight_pct": net_weight,
        "long_weight_pct": long_weight,
        "short_weight_pct": short_weight,
        "constituent_count": len(positions)
    }


def simulate_proposed_order(
    current_quantity: Decimal,
    current_market_value: Decimal,
    order_side: str,                 # BUY or SELL
    order_quantity: Decimal,
    reference_price: Decimal,
    fx_rate: Decimal = Decimal("1.0"),
    portfolio_nav: Optional[Decimal] = None
) -> Dict[str, Any]:
    """
    Simulates hypothetical post-trade position:
    BUY: Q_post = Q_current + Q_order
    SELL: Q_post = Q_current - Q_order
    Post Market Value = Q_post * reference_price * fx_rate
    """
    order_qty = abs(order_quantity)
    if order_side.upper() == "BUY":
        signed_order_qty = order_qty
    elif order_side.upper() == "SELL":
        signed_order_qty = -order_qty
    else:
        raise ValueError(f"Unsupported order side: {order_side}. Must be BUY or SELL.")

    post_quantity = current_quantity + signed_order_qty
    post_market_value = (post_quantity * reference_price * fx_rate).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    post_notional = abs(post_market_value)
    post_long = max(post_market_value, Decimal("0.0000"))
    post_short = max(-post_market_value, Decimal("0.0000"))

    post_weight = Decimal("0.0000")
    if portfolio_nav and portfolio_nav > Decimal("0"):
        post_weight = (post_notional / portfolio_nav * Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    return {
        "current_quantity": current_quantity,
        "order_side": order_side.upper(),
        "order_quantity": order_qty,
        "post_quantity": post_quantity,
        "reference_price": reference_price,
        "fx_rate": fx_rate,
        "current_market_value": current_market_value,
        "post_market_value": post_market_value,
        "post_notional": post_notional,
        "post_long_exposure": post_long,
        "post_short_exposure": post_short,
        "post_weight_pct": post_weight,
    }
