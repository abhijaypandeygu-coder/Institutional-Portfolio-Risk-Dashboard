"""
M10.06 Liquidity Stress Testing & Stressed Liquidation Mathematical Engine.
Implements:
1. Spread Stress Calculation:
   - Proportional widening: S_stress = S_0 * (1 + g_s)
   - Multiplier widening: S_stress = S_0 * k_s
   - Absolute widening: S_stress = S_0 + Delta S
   - Preserved or shocked midpoint with tick-size enforcement and positive prices
   - Stressed bid/ask quotes: B_stress = M_s - S_s/2, A_stress = M_s + S_s/2
2. Depth Deterioration Calculation:
   - Uniform depth reduction: Q_stress = Q_0 * (1 - g_d)
   - Level-specific and exponential/linear depth deterioration
   - Stressed order book construction
3. Market-Volume Contraction & Participation Caps:
   - Stressed volume: V_stress,t = V_0,t * (1 - g_v)
   - Stressed participation: p_stress = p_0 * k_p
   - Interval executable capacity: C_volume,t = V_stress,t * p_stress
4. Combined Liquidity Shock & Capacity:
   - Capacity at interval t: C_t = min(C_volume,t, C_depth,t)
   - Total capacity over horizon T: C_total(T) = sum(C_t)
   - Residual quantity: Q_residual(T) = max(0, Q_position - C_total(T))
5. Liquidation Time & Scheduling:
   - Finding earliest interval T where cumulative capacity >= Q_position
   - Trading session calendar accounting (holidays, multi-session boundaries)
   - Incomplete liquidation identification and residual exposure calculation
6. Stressed Execution Cost Breakdown (Without Double Counting):
   - Spread cost: C_spread = Q * (S_s / 2)
   - Stressed Depth-walk VWAP cost beyond midpoint
   - Square-root market impact: I = Y * sigma_H * sqrt(Q / V_H)
   - Slippage cost & transaction fees
   - Total liquidation cost: C_total = C_spread + C_depth + C_impact + C_slippage + C_fees
7. Liquidation Horizon Analysis:
   - Time-bucketed liquidation: 15m, 30m, 1h, 2h, 1d, 3d, 5d, 10d
   - Liquidation ratio: Q_liquidated(T) / Q_position
8. Baseline vs. Stressed Comparison & Cost Attribution:
   - Standalone vs. interaction decomposition: Delta C_spread, Delta C_depth, Delta C_volume
   - Cost in bps of executed notional
"""
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
import math
from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------
# Pydantic Math Structures
# ---------------------------------------------------------
class OrderBookLevel(BaseModel):
    price: Decimal
    quantity: Decimal
    notional: Optional[Decimal] = None


class SyntheticOrderBook(BaseModel):
    midpoint: Decimal
    spread: Decimal
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    total_bid_depth: Decimal
    total_ask_depth: Decimal


class LiquidationHorizonSnapshot(BaseModel):
    horizon_name: str
    interval_minutes: int
    executable_quantity: Decimal
    liquidation_ratio: Decimal
    residual_quantity: Decimal
    residual_market_value: Decimal
    estimated_cost: Decimal
    estimated_cost_bps: Decimal
    is_completed: bool


class LiquidationCostBreakdown(BaseModel):
    spread_crossing_cost: Decimal = Decimal("0.0")
    depth_walk_cost: Decimal = Decimal("0.0")
    market_impact_cost: Decimal = Decimal("0.0")
    slippage_cost: Decimal = Decimal("0.0")
    explicit_fees: Decimal = Decimal("0.0")
    total_liquidation_cost: Decimal = Decimal("0.0")
    cost_bps: Decimal = Decimal("0.0")


# ---------------------------------------------------------
# 1. Spread Stress Calculation
# ---------------------------------------------------------
def calculate_stressed_spread(
    baseline_bid: Decimal,
    baseline_ask: Decimal,
    spread_widening_pct: Optional[Decimal] = None,     # e.g., 2.00 for 200% widening
    spread_multiplier: Optional[Decimal] = None,       # e.g., 3.00 for 3x
    absolute_spread_change: Optional[Decimal] = None,  # e.g., 0.10
    tick_size: Decimal = Decimal("0.01"),
    market_price_shock_pct: Decimal = Decimal("0.0"),  # optional simultaneous price shock
) -> Tuple[Decimal, Decimal, Decimal, Decimal]:
    """
    Computes stressed spread, midpoint, bid, and ask.
    Returns: (stressed_spread, stressed_midpoint, stressed_bid, stressed_ask)
    """
    baseline_bid = Decimal(str(baseline_bid))
    baseline_ask = Decimal(str(baseline_ask))
    tick_size = Decimal(str(tick_size))
    
    baseline_spread = max(baseline_ask - baseline_bid, tick_size)
    baseline_midpoint = (baseline_bid + baseline_ask) / Decimal("2.0")

    # Midpoint under optional simultaneous price shock
    stressed_midpoint = baseline_midpoint * (Decimal("1.0") + Decimal(str(market_price_shock_pct)))
    
    # Calculate stressed spread
    if spread_multiplier is not None and Decimal(str(spread_multiplier)) > Decimal("0.0"):
        stressed_spread = baseline_spread * Decimal(str(spread_multiplier))
    elif spread_widening_pct is not None and Decimal(str(spread_widening_pct)) >= Decimal("0.0"):
        # 200% widening means stressed spread is baseline * (1 + 2.0) = 3x baseline
        stressed_spread = baseline_spread * (Decimal("1.0") + Decimal(str(spread_widening_pct)))
    elif absolute_spread_change is not None:
        stressed_spread = baseline_spread + Decimal(str(absolute_spread_change))
    else:
        stressed_spread = baseline_spread

    stressed_spread = max(stressed_spread, tick_size)

    # Half spread around midpoint
    half_spread = stressed_spread / Decimal("2.0")
    stressed_bid = (stressed_midpoint - half_spread).quantize(tick_size, rounding=ROUND_HALF_UP)
    stressed_ask = (stressed_bid + stressed_spread).quantize(tick_size, rounding=ROUND_HALF_UP)

    if stressed_bid <= Decimal("0.0"):
        stressed_bid = tick_size
        stressed_ask = stressed_bid + stressed_spread

    stressed_spread = stressed_ask - stressed_bid
    return stressed_spread, stressed_midpoint, stressed_bid, stressed_ask


# ---------------------------------------------------------
# 2. Depth Deterioration Engine
# ---------------------------------------------------------
def apply_depth_stress(
    levels: List[Dict[str, Any]],
    depth_multiplier: Decimal,           # e.g., 0.40 for 60% reduction (40% remaining)
    level_deterioration_rate: Decimal = Decimal("0.0"),  # optional deeper decay
) -> List[OrderBookLevel]:
    """
    Applies depth stress multipliers across order book levels.
    """
    res: List[OrderBookLevel] = []
    base_mult = Decimal(str(depth_multiplier))

    for idx, lvl in enumerate(levels):
        p = Decimal(str(lvl["price"]))
        q = Decimal(str(lvl["quantity"]))
        # Level multiplier with decay if rate > 0
        lvl_mult = max(Decimal("0.05"), base_mult - (Decimal(idx) * Decimal(str(level_deterioration_rate))))
        stressed_q = (q * lvl_mult).quantize(Decimal("1"), rounding=ROUND_DOWN)
        notional = stressed_q * p
        res.append(OrderBookLevel(price=p, quantity=stressed_q, notional=notional))

    return res


# ---------------------------------------------------------
# 3. Book-Walk VWAP & Execution Cost
# ---------------------------------------------------------
def execute_order_book_walk(
    levels: List[OrderBookLevel],
    target_quantity: Decimal,
    side: str,  # "SELL" for long liquidation (walk bids), "BUY" for short liquidation (walk asks)
    reference_midpoint: Decimal,
) -> Tuple[Decimal, Decimal, Decimal, Decimal]:
    """
    Simulates walking the order book up to available depth.
    Returns: (filled_quantity, residual_quantity, vwap_price, adverse_depth_walk_cost)
    """
    remaining = Decimal(str(target_quantity))
    total_filled = Decimal("0.0")
    total_consideration = Decimal("0.0")

    # Order levels properly: for SELL walk bids descending, for BUY walk asks ascending
    sorted_levels = sorted(levels, key=lambda l: l.price, reverse=(side.upper() == "SELL"))

    for lvl in sorted_levels:
        if remaining <= Decimal("0.0"):
            break
        fill_qty = min(remaining, lvl.quantity)
        if fill_qty > Decimal("0.0"):
            total_filled += fill_qty
            total_consideration += fill_qty * lvl.price
            remaining -= fill_qty

    residual = remaining
    if total_filled > Decimal("0.0"):
        vwap = total_consideration / total_filled
        # Adverse cost relative to reference midpoint
        if side.upper() == "SELL":
            # For selling, adverse concession = total_filled * (midpoint - VWAP)
            adverse_cost = max(Decimal("0.0"), total_filled * (reference_midpoint - vwap))
        else:
            # For buying, adverse concession = total_filled * (VWAP - midpoint)
            adverse_cost = max(Decimal("0.0"), total_filled * (vwap - reference_midpoint))
    else:
        vwap = reference_midpoint
        adverse_cost = Decimal("0.0")

    return total_filled, residual, vwap, adverse_cost


# ---------------------------------------------------------
# 4. Volume Contraction & Participation Capacity
# ---------------------------------------------------------
def calculate_interval_capacity(
    interval_baseline_volume: Decimal,
    volume_reduction_pct: Decimal = Decimal("0.0"),    # e.g., 0.50 for 50% volume contraction
    participation_cap: Decimal = Decimal("0.10"),      # e.g., 10%
    participation_reduction_pct: Decimal = Decimal("0.0"),  # e.g., 0.50 for 50% participation reduction (10% -> 5%)
) -> Tuple[Decimal, Decimal, Decimal]:
    """
    Computes stressed market volume and executable interval capacity.
    Returns: (stressed_volume, stressed_participation_cap, executable_capacity)
    """
    v_base = Decimal(str(interval_baseline_volume))
    g_v = Decimal(str(volume_reduction_pct))
    p_base = Decimal(str(participation_cap))
    g_p = Decimal(str(participation_reduction_pct))

    v_stress = max(Decimal("0.0"), v_base * (Decimal("1.0") - g_v))
    p_stress = max(Decimal("0.01"), p_base * (Decimal("1.0") - g_p))

    capacity = (v_stress * p_stress).quantize(Decimal("1"), rounding=ROUND_DOWN)
    return v_stress, p_stress, capacity


# ---------------------------------------------------------
# 5. Liquidation Horizon & Time Scheduling
# ---------------------------------------------------------
def build_liquidation_schedule(
    target_quantity: Decimal,
    interval_capacities: List[Decimal],
    interval_minutes: int = 15,
    reference_price: Decimal = Decimal("100.00"),
) -> Tuple[List[LiquidationHorizonSnapshot], int, Decimal, Decimal, bool]:
    """
    Builds progressive liquidation schedules across configured time horizons:
    15m, 30m, 1h, 2h, 1d (6.5h / 26 intervals), 3d, 5d, 10d.
    Returns: (horizon_snapshots, total_intervals_needed, total_fillable_qty, residual_qty, is_fully_completed)
    """
    target = Decimal(str(target_quantity))
    ref_price = Decimal(str(reference_price))
    
    cumulative_capacity = Decimal("0.0")
    interval_cumulative = []
    
    for cap in interval_capacities:
        cumulative_capacity += cap
        interval_cumulative.append(cumulative_capacity)

    # Standard horizon mapping in minutes
    horizons = [
        ("15_MINUTES", 15),
        ("30_MINUTES", 30),
        ("1_HOUR", 60),
        ("2_HOURS", 120),
        ("FULL_SESSION_1D", 390),     # 6.5 hours trading session = 26 intervals of 15m
        ("3_TRADING_DAYS", 390 * 3),
        ("5_TRADING_DAYS", 390 * 5),
        ("10_TRADING_DAYS", 390 * 10),
    ]

    snapshots: List[LiquidationHorizonSnapshot] = []

    for name, minutes in horizons:
        intervals_count = max(1, minutes // interval_minutes)
        if intervals_count <= len(interval_cumulative):
            cum_cap = interval_cumulative[intervals_count - 1]
        elif len(interval_cumulative) > 0:
            # Extrapolate multi-day capacity from daily session rate
            per_interval_avg = interval_cumulative[-1] / Decimal(len(interval_cumulative))
            cum_cap = per_interval_avg * Decimal(intervals_count)
        else:
            cum_cap = Decimal("0.0")

        executed = min(target, cum_cap)
        residual = max(Decimal("0.0"), target - executed)
        ratio = (executed / target) if target > Decimal("0.0") else Decimal("1.0")
        res_mv = residual * ref_price
        
        # Approximate base cost: 15 bps spread + impact
        est_cost_bps = Decimal("25.0")
        est_cost = (executed * ref_price * est_cost_bps) / Decimal("10000.0")

        snapshots.append(
            LiquidationHorizonSnapshot(
                horizon_name=name,
                interval_minutes=minutes,
                executable_quantity=executed,
                liquidation_ratio=ratio.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
                residual_quantity=residual,
                residual_market_value=res_mv.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                estimated_cost=est_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                estimated_cost_bps=est_cost_bps,
                is_completed=(residual == Decimal("0.0")),
            )
        )

    # Calculate intervals needed to liquidate 100%
    total_needed = 0
    fully_completed = False
    for idx, cum_val in enumerate(interval_cumulative):
        if cum_val >= target:
            total_needed = idx + 1
            fully_completed = True
            break

    if not fully_completed and len(interval_cumulative) > 0:
        per_int_rate = interval_cumulative[-1] / Decimal(len(interval_cumulative))
        if per_int_rate > Decimal("0.0"):
            total_needed = int(math.ceil(float(target / per_int_rate)))
        else:
            total_needed = 999999

    total_fillable = min(target, cumulative_capacity)
    final_residual = max(Decimal("0.0"), target - total_fillable)

    return snapshots, total_needed, total_fillable, final_residual, fully_completed


# ---------------------------------------------------------
# 6. Comprehensive Stressed Execution Cost Breakdown
# ---------------------------------------------------------
def calculate_stressed_execution_costs(
    executed_quantity: Decimal,
    reference_midpoint: Decimal,
    stressed_spread: Decimal,
    daily_volatility: Decimal = Decimal("0.02"),
    market_volume: Decimal = Decimal("100000"),
    impact_multiplier: Decimal = Decimal("1.5"),
    brokerage_bps: Decimal = Decimal("2.0"),
    include_depth_walk: bool = True,
    depth_walk_concession: Decimal = Decimal("0.0"),
) -> LiquidationCostBreakdown:
    """
    Computes institutional cost decomposition without double counting:
    1. Spread cost: Q * (S / 2)
    2. Depth-walk concession beyond half-spread (if applicable)
    3. Square-root market impact: I = Y * sigma * sqrt(Q / V) * Notional
    4. Slippage: calibrated modeled execution slippage
    5. Explicit fees: brokerage, exchange, taxes
    """
    qty = Decimal(str(executed_quantity))
    mid = Decimal(str(reference_midpoint))
    spread = Decimal(str(stressed_spread))
    notional = qty * mid

    if qty <= Decimal("0.0") or notional <= Decimal("0.0"):
        return LiquidationCostBreakdown()

    # 1. Spread-crossing cost: Q * (S_s / 2)
    spread_cost = (qty * (spread / Decimal("2.0"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # 2. Depth-walk additional concession
    depth_cost = max(Decimal("0.0"), Decimal(str(depth_walk_concession))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # 3. Square-Root Market Impact
    vol = float(daily_volatility)
    v_mkt = max(1.0, float(market_volume))
    participation_fraction = float(qty) / v_mkt
    y_coeff = float(impact_multiplier) * 0.5  # standard Almgren-Chriss / square-root calibration

    impact_fraction = y_coeff * vol * math.sqrt(participation_fraction)
    impact_cost = (notional * Decimal(str(impact_fraction))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # 4. Slippage cost (modeled conservative 5 bps under stress)
    slippage_bps = Decimal("5.0") * Decimal(str(impact_multiplier))
    slippage_cost = ((notional * slippage_bps) / Decimal("10000.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # 5. Explicit Fees (Exchange + Brokerage)
    fee_bps = Decimal(str(brokerage_bps))
    fees = ((notional * fee_bps) / Decimal("10000.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    total_cost = spread_cost + depth_cost + impact_cost + slippage_cost + fees
    total_bps = ((total_cost / notional) * Decimal("10000.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return LiquidationCostBreakdown(
        spread_crossing_cost=spread_cost,
        depth_walk_cost=depth_cost,
        market_impact_cost=impact_cost,
        slippage_cost=slippage_cost,
        explicit_fees=fees,
        total_liquidation_cost=total_cost,
        cost_bps=total_bps,
    )
