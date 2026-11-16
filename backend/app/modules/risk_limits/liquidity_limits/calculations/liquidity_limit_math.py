"""
Financial calculations and mathematical specifications for M11.04 — Liquidity Limits.

Implements:
1. Minimum Liquidity Score:
   - Breach = max(0, L_min - L_actual)
   - U_min = (L_min / L_actual) * 100 (when L_actual > 0)
2. Minimum Order Book Depth (Side-Aware):
   - Long liquidation: Sell-side / bid depth
   - Short covering: Buy-side / ask depth
   - Breach_D = max(0, D_min - D_actual)
   - U_D = (D_min / D_actual) * 100
3. Minimum Traded Volume & Turnover:
   - ADV = (1 / N) * sum_{d=1}^N Volume_d
   - ADTV = (1 / N) * sum_{d=1}^N Turnover_d
   - Breach_ADV = max(0, ADV_min - ADV_actual)
   - Breach_ADTV = max(0, ADTV_min - ADTV_actual)
4. Liquidation Horizon:
   - DailyCapacity = ADV * p
   - LiquidationDays = |Q| / DailyCapacity
   - Breach_H = max(0, H_actual - H_max)
   - U_H = (H_actual / H_max) * 100
5. Liquidation Cost:
   - Cost_bps = (C_total / Notional_liquidated) * 10,000
   - Cost_%NAV = (C_total_base / NAV_p) * 100
   - Breach_C = max(0, C_actual - C_max)
   - U_C = (C_actual / C_max) * 100
6. Stressed Liquidity Transformations:
   - ADV_stress = ADV_base * (1 - v)
   - Depth_stress = Depth_base * (1 - d)
   - Spread_stress = Spread_base * (1 + s)
   - p_stress = p_base * (1 - r)
   - H_stress = |Q| / (ADV_stress * p_stress)
7. Liquidity Capacity & Headroom Analysis:
   - Cost-constrained capacity
   - Horizon-constrained capacity: Capacity_H = H_max * ADV * p
   - Volume-based capacity: ADV * p * T
   - Binding constraint identification
8. Proposed-Order Simulation:
   - Post-trade position quantity & side
   - Projected horizon & cost
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional, Tuple


def calculate_adv(daily_volumes: List[Decimal]) -> Decimal:
    """
    Computes Average Daily Volume (ADV):
    ADV = (1 / N) * sum(daily_volumes)
    """
    if not daily_volumes:
        return Decimal("0.0000")
    total = sum(daily_volumes)
    return (total / Decimal(len(daily_volumes))).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def calculate_adtv(daily_turnovers: List[Decimal]) -> Decimal:
    """
    Computes Average Daily Traded Value (ADTV / Turnover):
    ADTV = (1 / N) * sum(daily_turnovers)
    """
    if not daily_turnovers:
        return Decimal("0.0000")
    total = sum(daily_turnovers)
    return (total / Decimal(len(daily_turnovers))).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def calculate_liquidation_horizon(
    position_quantity: Decimal,
    adv: Optional[Decimal],
    participation_rate: Decimal,
) -> Dict[str, Any]:
    """
    Calculates simplified liquidation horizon:
    DailyCapacity = ADV * p
    LiquidationDays = |Q| / DailyCapacity
    """
    abs_qty = abs(position_quantity)
    if abs_qty == Decimal("0"):
        return {
            "daily_capacity": Decimal("0.0000"),
            "liquidation_horizon_days": Decimal("0.0000"),
            "status": "VALID",
        }

    if adv is None:
        return {
            "daily_capacity": Decimal("0.0000"),
            "liquidation_horizon_days": None,
            "status": "UNAVAILABLE",
            "reason": "MISSING_ADV",
        }

    if adv <= Decimal("0"):
        return {
            "daily_capacity": Decimal("0.0000"),
            "liquidation_horizon_days": None,
            "status": "INVALID",
            "reason": "ZERO_OR_NEGATIVE_ADV",
        }

    if participation_rate <= Decimal("0") or participation_rate > Decimal("1.0"):
        return {
            "daily_capacity": Decimal("0.0000"),
            "liquidation_horizon_days": None,
            "status": "INVALID",
            "reason": "INVALID_PARTICIPATION_RATE",
        }

    daily_capacity = (adv * participation_rate).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    horizon_days = (abs_qty / daily_capacity).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    return {
        "daily_capacity": daily_capacity,
        "liquidation_horizon_days": horizon_days,
        "status": "VALID",
    }


def calculate_liquidation_cost_metrics(
    estimated_cost: Decimal,
    liquidated_notional: Decimal,
    portfolio_nav: Optional[Decimal] = None,
) -> Dict[str, Any]:
    """
    Computes liquidation cost representations:
    Cost_bps = (estimated_cost / liquidated_notional) * 10,000
    Cost_%NAV = (estimated_cost / portfolio_nav) * 100
    """
    if liquidated_notional <= Decimal("0"):
        cost_bps = Decimal("0.0000")
    else:
        cost_bps = ((estimated_cost / liquidated_notional) * Decimal("10000")).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

    cost_pct_nav = None
    if portfolio_nav is not None:
        if portfolio_nav <= Decimal("0"):
            cost_pct_nav = None
        else:
            cost_pct_nav = ((estimated_cost / portfolio_nav) * Decimal("100")).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )

    return {
        "cost_amount": estimated_cost,
        "cost_bps": cost_bps,
        "cost_pct_nav": cost_pct_nav,
    }


def evaluate_minimum_limit(
    actual_value: Optional[Decimal],
    min_threshold: Decimal,
    warning_threshold: Optional[Decimal] = None,
    unit: str = "POINTS",
) -> Dict[str, Any]:
    """
    Evaluates minimum threshold (Score, Depth, ADV, Turnover):
    Breach = max(0, min_threshold - actual_value)
    U = (min_threshold / actual_value) * 100 (when actual_value > 0)
    """
    if actual_value is None:
        return {
            "actual_value": None,
            "min_threshold": min_threshold,
            "warning_threshold": warning_threshold,
            "utilization_pct": None,
            "breach_amount": None,
            "headroom": None,
            "status": "UNAVAILABLE",
            "unit": unit,
        }

    breach_amount = max(Decimal("0.0000"), min_threshold - actual_value).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )
    headroom = (actual_value - min_threshold).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    utilization_pct = None
    if actual_value > Decimal("0"):
        utilization_pct = ((min_threshold / actual_value) * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    if actual_value < min_threshold:
        status = "HARD_LIMIT_EXCEEDED"
    elif warning_threshold is not None and actual_value <= warning_threshold:
        status = "WARNING"
    else:
        status = "WITHIN_LIMIT"

    return {
        "actual_value": actual_value,
        "min_threshold": min_threshold,
        "warning_threshold": warning_threshold,
        "utilization_pct": utilization_pct,
        "breach_amount": breach_amount,
        "headroom": headroom,
        "status": status,
        "unit": unit,
    }


def evaluate_maximum_limit(
    actual_value: Optional[Decimal],
    max_threshold: Decimal,
    warning_threshold: Optional[Decimal] = None,
    unit: str = "DAYS",
) -> Dict[str, Any]:
    """
    Evaluates maximum threshold (Cost, Horizon, Spread):
    Breach = max(0, actual_value - max_threshold)
    U = (actual_value / max_threshold) * 100
    Capacity = max_threshold - actual_value
    """
    if actual_value is None:
        return {
            "actual_value": None,
            "max_threshold": max_threshold,
            "warning_threshold": warning_threshold,
            "utilization_pct": None,
            "breach_amount": None,
            "remaining_capacity": None,
            "status": "UNAVAILABLE",
            "unit": unit,
        }

    if max_threshold <= Decimal("0"):
        raise ValueError("Maximum threshold must be strictly positive.")

    breach_amount = max(Decimal("0.0000"), actual_value - max_threshold).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )
    remaining_capacity = (max_threshold - actual_value).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    utilization_pct = ((actual_value / max_threshold) * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    if actual_value > max_threshold:
        status = "HARD_LIMIT_EXCEEDED"
    elif warning_threshold is not None and actual_value >= warning_threshold:
        status = "WARNING"
    else:
        status = "WITHIN_LIMIT"

    return {
        "actual_value": actual_value,
        "max_threshold": max_threshold,
        "warning_threshold": warning_threshold,
        "utilization_pct": utilization_pct,
        "breach_amount": breach_amount,
        "remaining_capacity": remaining_capacity,
        "status": status,
        "unit": unit,
    }


def apply_stressed_liquidity_shocks(
    baseline_adv: Optional[Decimal],
    baseline_depth: Optional[Decimal],
    baseline_spread_bps: Optional[Decimal],
    baseline_participation_rate: Decimal,
    volume_contraction_pct: Decimal = Decimal("0.0"),  # e.g. 40% -> 0.40
    depth_reduction_pct: Decimal = Decimal("0.0"),    # e.g. 30% -> 0.30
    spread_widening_pct: Decimal = Decimal("0.0"),    # e.g. 50% -> 0.50
    participation_reduction_pct: Decimal = Decimal("0.0"), # e.g. 20% -> 0.20
) -> Dict[str, Any]:
    """
    Applies synthetic multiplicative stress shocks to baseline liquidity parameters:
    ADV_stress = ADV_base * (1 - v)
    Depth_stress = Depth_base * (1 - d)
    Spread_stress = Spread_base * (1 + s)
    p_stress = p_base * (1 - r)
    """
    stressed_adv = None
    if baseline_adv is not None:
        factor_v = max(Decimal("0.0000"), Decimal("1.0") - (volume_contraction_pct / Decimal("100.0")))
        stressed_adv = (baseline_adv * factor_v).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    stressed_depth = None
    if baseline_depth is not None:
        factor_d = max(Decimal("0.0000"), Decimal("1.0") - (depth_reduction_pct / Decimal("100.0")))
        stressed_depth = (baseline_depth * factor_d).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    stressed_spread = None
    if baseline_spread_bps is not None:
        factor_s = max(Decimal("0.0000"), Decimal("1.0") + (spread_widening_pct / Decimal("100.0")))
        stressed_spread = (baseline_spread_bps * factor_s).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    factor_r = max(Decimal("0.0000"), Decimal("1.0") - (participation_reduction_pct / Decimal("100.0")))
    stressed_p = (baseline_participation_rate * factor_r).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    return {
        "stressed_adv": stressed_adv,
        "stressed_depth": stressed_depth,
        "stressed_spread_bps": stressed_spread,
        "stressed_participation_rate": stressed_p,
    }


def calculate_liquidity_headroom_and_capacity(
    position_quantity: Decimal,
    adv: Optional[Decimal],
    participation_rate: Decimal,
    max_horizon_days: Optional[Decimal],
    available_depth: Optional[Decimal],
) -> Dict[str, Any]:
    """
    Computes remaining liquidity capacity and identifies the binding liquidity constraint:
    - Horizon-constrained capacity: H_max * ADV * p
    - Depth-constrained capacity: available_depth
    - Headroom: Max capacity - Current position size
    """
    abs_qty = abs(position_quantity)
    constraints: Dict[str, Decimal] = {}

    if adv is not None and adv > Decimal("0") and max_horizon_days is not None and participation_rate > Decimal("0"):
        horizon_capacity = (max_horizon_days * adv * participation_rate).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        constraints["HORIZON_LIMIT"] = horizon_capacity

    if available_depth is not None and available_depth >= Decimal("0"):
        constraints["DEPTH_LIMIT"] = available_depth

    if not constraints:
        return {
            "current_position_quantity": abs_qty,
            "max_supported_quantity": None,
            "headroom_quantity": None,
            "binding_constraint": None,
            "status": "UNCONSTRAINED_OR_UNAVAILABLE",
        }

    binding_constraint = min(constraints, key=constraints.get)
    max_supported = constraints[binding_constraint]
    headroom = (max_supported - abs_qty).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    return {
        "current_position_quantity": abs_qty,
        "max_supported_quantity": max_supported,
        "headroom_quantity": headroom,
        "binding_constraint": binding_constraint,
        "all_constraints": constraints,
        "status": "WITHIN_LIMIT" if headroom >= Decimal("0") else "CAPACITY_EXCEEDED",
    }


def simulate_proposed_order(
    current_quantity: Decimal,
    proposed_quantity: Decimal,
    order_side: str,  # BUY or SELL
    adv: Optional[Decimal],
    participation_rate: Decimal,
    estimated_cost_per_share: Decimal = Decimal("0.0"),
) -> Dict[str, Any]:
    """
    Simulates projected post-trade position and its prospective liquidity metrics:
    - Projected quantity = current_quantity + (proposed if BUY else -proposed)
    - Projected horizon & cost
    """
    delta = proposed_quantity if order_side.upper() == "BUY" else -proposed_quantity
    projected_quantity = current_quantity + delta
    projected_side = "LONG" if projected_quantity > Decimal("0") else ("SHORT" if projected_quantity < Decimal("0") else "FLAT")

    proj_horizon = calculate_liquidation_horizon(
        position_quantity=projected_quantity,
        adv=adv,
        participation_rate=participation_rate,
    )

    projected_cost = (abs(projected_quantity) * estimated_cost_per_share).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )

    return {
        "current_quantity": current_quantity,
        "proposed_quantity": proposed_quantity,
        "order_side": order_side.upper(),
        "projected_quantity": projected_quantity,
        "projected_side": projected_side,
        "projected_horizon_days": proj_horizon.get("liquidation_horizon_days"),
        "projected_cost": projected_cost,
        "status": proj_horizon.get("status"),
    }

