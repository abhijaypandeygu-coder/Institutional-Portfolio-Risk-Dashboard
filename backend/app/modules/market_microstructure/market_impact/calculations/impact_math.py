"""
M09.04 Market Impact - Mathematical and Algorithmic Engine.
Provides deterministic implementations for:
1. Static Displayed-Book Depth Walk (Buy & Sell side level consumption, VWAP average execution price, marginal price, fillable quantity, residual quantity, monetary cost, cost in bps).
2. Cost Decomposition: Spread crossing (half-spread), additional depth-walk concession, explicit fees.
3. Order-Size Sensitivity & Marginal Cost: Evaluation across multiple quantities, marginal cost between sizes: (Cost(Q2) - Cost(Q1)) / (Q2 - Q1).
4. Participation-Rate Constraints & Horizon Schedules: Volume cap Q_fillable = min(Q_prop, PR_max * V_horizon), uniform and volume-proportional schedules.
5. Empirical Impact Models:
   - Square-Root Impact: I_bps = Y * sigma_H * sqrt(Q / V_H) * 10,000
   - Log-Linear / Empirical Regression: Impact_bps = beta0 + beta1 * log(1 + PR) + beta2 * Spread_bps + beta3 * Depth^-1 + beta4 * Volatility
   - Kyle-Style OFI Response: Delta_P = lambda * OFI
6. Prediction Intervals & Uncertainty: Standard error of prediction, lower and upper confidence bounds.
"""

from datetime import datetime, timezone
from decimal import Decimal
import math
from typing import List, Dict, Any, Optional, Tuple
import numpy as np


def _normalize_tz(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensures datetime is timezone-aware UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ============================================================================
# 1. STATIC DISPLAYED-BOOK DEPTH WALK
# ============================================================================

def simulate_depth_walk(
    side: str,  # "BUY" or "SELL"
    proposed_quantity: Decimal,
    levels: List[Dict[str, Any]],  # For BUY: asks sorted ascending by price; For SELL: bids sorted descending
    reference_price: Decimal,  # Usually arrival midpoint or arrival best quote
    instrument_multiplier: Decimal = Decimal("1.0"),
    tick_size: Optional[Decimal] = None
) -> Dict[str, Any]:
    """
    Simulates consuming displayed liquidity level-by-level.

    For BUY: consumes asks in ascending price order.
    For SELL: consumes bids in descending price order.

    Each level dict:
    - 'price': Decimal or float or str
    - 'quantity': Decimal or float or str
    - 'level': Optional[int]

    Returns level-by-level consumption details, VWAP average price, marginal price,
    visible filled quantity, residual unfilled quantity, cost in monetary units and bps,
    and half-spread / additional depth cost decomposition.
    """
    side_upper = side.upper()
    if side_upper not in ("BUY", "SELL"):
        raise ValueError(f"Invalid side: {side}. Must be 'BUY' or 'SELL'.")

    if proposed_quantity <= Decimal("0.0"):
        raise ValueError(f"Proposed quantity must be > 0, got {proposed_quantity}")

    if reference_price <= Decimal("0.0"):
        raise ValueError(f"Reference price must be > 0, got {reference_price}")

    # Ensure levels are appropriately ordered
    parsed_levels = []
    for idx, lvl in enumerate(levels):
        p = Decimal(str(lvl["price"]))
        q = Decimal(str(lvl["quantity"]))
        if q > Decimal("0.0") and p > Decimal("0.0"):
            parsed_levels.append({
                "level_index": idx + 1,
                "price": p,
                "available_quantity": q
            })

    if side_upper == "BUY":
        # Ascending ask prices
        parsed_levels.sort(key=lambda x: x["price"])
    else:
        # Descending bid prices
        parsed_levels.sort(key=lambda x: x["price"], reverse=True)

    remaining_qty = proposed_quantity
    total_filled_qty = Decimal("0.0")
    total_executed_value = Decimal("0.0")
    consumed_levels = []
    marginal_price = None

    for lvl in parsed_levels:
        if remaining_qty <= Decimal("0.0"):
            break

        avail = lvl["available_quantity"]
        consumed = min(remaining_qty, avail)
        rem_at_level = avail - consumed
        val = consumed * lvl["price"] * instrument_multiplier

        total_filled_qty += consumed
        total_executed_value += val
        remaining_qty -= consumed
        marginal_price = lvl["price"]

        consumed_levels.append({
            "level_index": lvl["level_index"],
            "price": lvl["price"],
            "available_quantity": avail,
            "consumed_quantity": consumed,
            "remaining_quantity": rem_at_level,
            "executed_value": val
        })

    residual_unfilled_qty = remaining_qty
    fill_pct = float(total_filled_qty / proposed_quantity * Decimal("100.0"))

    if total_filled_qty > Decimal("0.0"):
        avg_execution_price = total_executed_value / (total_filled_qty * instrument_multiplier)
    else:
        avg_execution_price = None

    # Calculate price deviation and execution cost relative to reference price
    cost_amount = None
    cost_bps = None
    spread_crossing_bps = None
    additional_depth_bps = None

    if avg_execution_price is not None and reference_price is not None:
        if side_upper == "BUY":
            cost_amount = total_executed_value - (total_filled_qty * reference_price * instrument_multiplier)
        else:
            cost_amount = (total_filled_qty * reference_price * instrument_multiplier) - total_executed_value

        ref_notional = total_filled_qty * reference_price * instrument_multiplier
        if ref_notional > Decimal("0.0"):
            cost_bps = float(cost_amount / ref_notional * Decimal("10000.0"))

        # Decompose if at least 1 level consumed
        first_level_price = parsed_levels[0]["price"] if parsed_levels else None
        if first_level_price is not None:
            if side_upper == "BUY":
                spread_dev = first_level_price - reference_price
                depth_dev = avg_execution_price - first_level_price
            else:
                spread_dev = reference_price - first_level_price
                depth_dev = first_level_price - avg_execution_price

            spread_crossing_bps = float(spread_dev / reference_price * Decimal("10000.0"))
            additional_depth_bps = float(depth_dev / reference_price * Decimal("10000.0"))

    return {
        "side": side_upper,
        "proposed_quantity": proposed_quantity,
        "reference_price": reference_price,
        "visible_fill_quantity": total_filled_qty,
        "residual_unfilled_quantity": residual_unfilled_qty,
        "fill_percentage": fill_pct,
        "average_execution_price": avg_execution_price,
        "marginal_execution_price": marginal_price,
        "gross_execution_value": total_executed_value,
        "estimated_cost_amount": cost_amount,
        "estimated_cost_bps": cost_bps,
        "spread_crossing_bps": spread_crossing_bps,
        "additional_depth_bps": additional_depth_bps,
        "consumed_level_count": len(consumed_levels),
        "available_level_count": len(parsed_levels),
        "consumed_levels": consumed_levels
    }


# ============================================================================
# 2. ORDER-SIZE SENSITIVITY & MARGINAL COST
# ============================================================================

def compute_order_size_sensitivity(
    side: str,
    sizes: List[Decimal],
    levels: List[Dict[str, Any]],
    reference_price: Decimal,
    instrument_multiplier: Decimal = Decimal("1.0")
) -> List[Dict[str, Any]]:
    """
    Evaluates depth walk across a list of proposed sizes.
    Computes marginal cost between successive size increments:
    MarginalCost(Q1, Q2) = (Cost(Q2) - Cost(Q1)) / (Q2 - Q1).
    """
    sorted_sizes = sorted([Decimal(str(s)) for s in sizes])
    results = []
    prev_size = None
    prev_cost = None

    for sz in sorted_sizes:
        res = simulate_depth_walk(
            side=side,
            proposed_quantity=sz,
            levels=levels,
            reference_price=reference_price,
            instrument_multiplier=instrument_multiplier
        )

        marginal_unit_cost = None
        if prev_size is not None and prev_cost is not None and res["estimated_cost_amount"] is not None:
            delta_q = sz - prev_size
            if delta_q > Decimal("0.0"):
                marginal_unit_cost = float((res["estimated_cost_amount"] - prev_cost) / delta_q)

        res["marginal_incremental_unit_cost"] = marginal_unit_cost
        results.append(res)

        if res["estimated_cost_amount"] is not None:
            prev_size = sz
            prev_cost = res["estimated_cost_amount"]

    return results


# ============================================================================
# 3. PARTICIPATION & HORIZON EXECUTION SCHEDULES
# ============================================================================

def compute_participation_cap(
    proposed_quantity: Decimal,
    expected_market_volume: Decimal,
    max_participation_rate: float = 0.10
) -> Dict[str, Any]:
    """
    Volume-limited execution:
    Q_fillable = min(Q_proposed, PR_max * V_market)
    Q_residual = Q_proposed - Q_fillable
    """
    max_pr = Decimal(str(max_participation_rate))
    max_fillable = expected_market_volume * max_pr
    fillable_qty = min(proposed_quantity, max_fillable)
    residual_qty = proposed_quantity - fillable_qty
    actual_pr = float(proposed_quantity / expected_market_volume) if expected_market_volume > Decimal("0.0") else None

    return {
        "proposed_quantity": proposed_quantity,
        "expected_market_volume": expected_market_volume,
        "max_participation_rate": max_participation_rate,
        "target_participation_rate": actual_pr,
        "expected_fillable_quantity": fillable_qty,
        "residual_quantity": residual_qty,
        "is_volume_constrained": bool(residual_qty > Decimal("0.0"))
    }


def compute_execution_schedule(
    total_quantity: Decimal,
    horizon_intervals: int,
    schedule_type: str = "UNIFORM",
    volume_profile: Optional[List[float]] = None
) -> List[Decimal]:
    """
    Generates interval slices for execution:
    - UNIFORM: q_i = Q / N
    - VOLUME_PROPORTIONAL: q_i = Q * (V_i / sum(V))
    """
    if horizon_intervals <= 0:
        return [total_quantity]

    if schedule_type.upper() == "UNIFORM" or not volume_profile or len(volume_profile) != horizon_intervals:
        slice_qty = total_quantity / Decimal(str(horizon_intervals))
        return [slice_qty] * horizon_intervals

    tot_prof = Decimal(str(sum(volume_profile)))
    if tot_prof <= Decimal("0.0"):
        slice_qty = total_quantity / Decimal(str(horizon_intervals))
        return [slice_qty] * horizon_intervals

    slices = []
    for v in volume_profile:
        ratio = Decimal(str(v)) / tot_prof
        slices.append(total_quantity * ratio)
    return slices


# ============================================================================
# 4. EMPIRICAL IMPACT MODELS
# ============================================================================

def compute_square_root_impact(
    order_quantity: float,
    expected_horizon_volume: float,
    horizon_volatility: float,  # daily or horizon return volatility (e.g. 0.02 = 2%)
    impact_coefficient_y: float = 0.50
) -> Dict[str, Any]:
    """
    Square-Root Impact Law:
    I_bps = Y * sigma_H * sqrt(Q / V_H) * 10,000

    Where:
    - Y = calibrated parameter (typically 0.4 - 0.7)
    - sigma_H = volatility over horizon
    - Q = order quantity
    - V_H = market volume over same horizon
    """
    if expected_horizon_volume <= 0.0 or order_quantity <= 0.0 or horizon_volatility < 0.0:
        return {
            "impact_bps": None,
            "participation_rate": None,
            "status": "INVALID_INPUT"
        }

    pr = order_quantity / expected_horizon_volume
    impact_bps = impact_coefficient_y * horizon_volatility * math.sqrt(pr) * 10000.0

    # Uncertainty estimation (approx 20% model error stddev)
    se = 0.20 * impact_bps
    lower_bound = max(impact_bps - 1.96 * se, 0.0)
    upper_bound = impact_bps + 1.96 * se

    return {
        "impact_bps": round(impact_bps, 4),
        "participation_rate": round(pr, 6),
        "standard_error_bps": round(se, 4),
        "prediction_lower_bps": round(lower_bound, 4),
        "prediction_upper_bps": round(upper_bound, 4),
        "model_type": "SQUARE_ROOT",
        "impact_coefficient_y": impact_coefficient_y,
        "status": "VALID"
    }


def compute_empirical_regression_impact(
    participation_rate: float,
    spread_bps: float,
    depth_notional: float,
    volatility: float,
    regime_multiplier: float = 1.0,
    coefficients: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Interpretable Log-Linear Empirical Regression Model:
    Impact_bps = (beta_0 + beta_1 * log(1 + PR) + beta_2 * Spread_bps + beta_3 * Depth^-1 + beta_4 * Vol) * Regime_multiplier
    """
    coefs = coefficients or {
        "beta_0": 0.50,
        "beta_1": 15.0,  # sensitivity to participation
        "beta_2": 0.20,  # spread sensitivity
        "beta_3": 50000.0,  # depth inverse sensitivity
        "beta_4": 50.0   # volatility sensitivity
    }

    inv_depth = (1.0 / depth_notional) if depth_notional > 0.0 else 0.0

    raw_pred = (
        coefs["beta_0"]
        + coefs["beta_1"] * math.log(1.0 + max(participation_rate, 0.0))
        + coefs["beta_2"] * max(spread_bps, 0.0)
        + coefs["beta_3"] * inv_depth
        + coefs["beta_4"] * max(volatility, 0.0)
    ) * regime_multiplier

    impact_bps = max(raw_pred, 0.0)
    se = 0.25 * impact_bps
    lower_bound = max(impact_bps - 1.96 * se, 0.0)
    upper_bound = impact_bps + 1.96 * se

    # Split into temporary (70%) and permanent (30%) heuristic breakdown
    temp_bps = 0.70 * impact_bps
    perm_bps = 0.30 * impact_bps

    return {
        "impact_bps": round(impact_bps, 4),
        "temporary_impact_bps": round(temp_bps, 4),
        "permanent_impact_bps": round(perm_bps, 4),
        "standard_error_bps": round(se, 4),
        "prediction_lower_bps": round(lower_bound, 4),
        "prediction_upper_bps": round(upper_bound, 4),
        "model_type": "EMPIRICAL_REGRESSION",
        "coefficients": coefs,
        "regime_multiplier": regime_multiplier,
        "status": "VALID"
    }


def compute_kyle_order_flow_impact(
    signed_order_flow: float,  # positive for net buy, negative for net sell
    lambda_coefficient: float = 0.0001
) -> Dict[str, Any]:
    """
    Kyle (1985) Style Price Response Model:
    Delta_P = lambda * OFI
    """
    delta_p = lambda_coefficient * signed_order_flow
    return {
        "price_change": delta_p,
        "lambda_coefficient": lambda_coefficient,
        "signed_order_flow": signed_order_flow,
        "model_type": "KYLE_OFI",
        "status": "VALID"
    }
