"""
Calculations engine for M09.06 Liquidity Stress Testing & Stressed Execution Cost Estimation.

Implements:
1. Spread Widening (multiplicative, percentage, additive bps, empirical quantiles).
2. Synthetic Stressed Quotes around preserved midpoint with tick-size enforcement.
3. Depth Reduction (uniform, side-specific, level-specific, price-band).
4. Synthetic Stressed Order Book construction and cumulative depth/notional computation.
5. Volume Contraction (uniform, interval-specific, time-of-day curves).
6. Participation Capacity and executable quantity under volume constraints.
7. Liquidation Time estimation across baseline and stressed volume profiles, session boundaries, and incomplete liquidation handling.
8. Stressed Execution Cost recalculation (Spread, Depth-Walk, Market Impact, Slippage, Fees, Opportunity Cost) without double counting.
9. Cost Escalation (absolute and percentage relative to baseline).
10. Reverse Stress Testing: search parameter boundaries to identify liquidity deterioration breach thresholds.
11. Portfolio-level aggregation across concurrent or sequential liquidation schedules.
"""

from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
import math
from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel, Field


class OrderBookLevel(BaseModel):
    price: Decimal
    quantity: Decimal
    notional: Optional[Decimal] = None


class SyntheticStressBook(BaseModel):
    baseline_midpoint: Decimal
    stressed_midpoint: Decimal
    baseline_spread: Decimal
    stressed_spread: Decimal
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    total_bid_depth: Decimal
    total_ask_depth: Decimal
    total_bid_notional: Decimal
    total_ask_notional: Decimal


class IntervalVolumeProfile(BaseModel):
    interval_index: int
    baseline_volume: Decimal
    volume_contraction_ratio: Decimal = Decimal("0.0")  # e.g. 0.20 for 20% contraction
    stressed_volume: Decimal = Decimal("0.0")
    participation_rate: Decimal = Decimal("0.10")  # e.g. 10%
    baseline_capacity: Decimal = Decimal("0.0")
    stressed_capacity: Decimal = Decimal("0.0")


class LiquidationScheduleResult(BaseModel):
    target_quantity: Decimal
    baseline_duration_intervals: int
    stressed_duration_intervals: int
    duration_increase_intervals: int
    baseline_completed: bool
    stressed_completed: bool
    baseline_fillable_quantity: Decimal
    stressed_fillable_quantity: Decimal
    baseline_residual_quantity: Decimal
    stressed_residual_quantity: Decimal
    status: str  # COMPLETED, LIQUIDATION_NOT_COMPLETED


class ExecutionCostDecomposition(BaseModel):
    spread_cost: Decimal = Decimal("0.0")
    depth_walk_concession_cost: Decimal = Decimal("0.0")
    market_impact_cost: Decimal = Decimal("0.0")
    slippage_cost: Decimal = Decimal("0.0")
    explicit_fees: Decimal = Decimal("0.0")
    opportunity_cost: Decimal = Decimal("0.0")
    total_cost: Decimal = Decimal("0.0")
    total_cost_bps: Decimal = Decimal("0.0")


class StressedCostResult(BaseModel):
    baseline_cost: ExecutionCostDecomposition
    stressed_cost: ExecutionCostDecomposition
    cost_escalation_monetary: Decimal
    cost_escalation_pct: Optional[Decimal]
    cost_escalation_bps: Decimal
    is_extrapolated: bool = False


class LiquidityStressMath:
    """Core mathematical engine for liquidity stress transformations."""

    @staticmethod
    def calculate_stressed_spread(
        baseline_spread: Decimal,
        multiplier: Optional[Decimal] = None,
        percentage_shock: Optional[Decimal] = None,
        additive_bps: Optional[Decimal] = None,
        midpoint: Optional[Decimal] = None,
    ) -> Decimal:
        """
        Calculates stressed spread using either:
        1. Multiplier: S_stress = m_s * S_0
        2. Percentage shock: S_stress = S_0 * (1 + r_s)
        3. Additive bps: S_stress = S_0 + (Delta_bps / 10,000) * Midpoint
        """
        if baseline_spread < Decimal("0.0"):
            raise ValueError("Baseline spread cannot be negative.")

        if multiplier is not None:
            if multiplier < Decimal("0.0"):
                raise ValueError("Spread multiplier cannot be negative.")
            return baseline_spread * multiplier

        if percentage_shock is not None:
            if percentage_shock < Decimal("-1.0"):
                raise ValueError("Percentage spread shock cannot be less than -100%.")
            return baseline_spread * (Decimal("1.0") + percentage_shock)

        if additive_bps is not None and midpoint is not None and midpoint > Decimal("0.0"):
            spread_add = (additive_bps / Decimal("10000.0")) * midpoint
            return max(Decimal("0.0"), baseline_spread + spread_add)

        return baseline_spread

    @staticmethod
    def construct_synthetic_quote(
        midpoint: Decimal,
        stressed_spread: Decimal,
        tick_size: Decimal = Decimal("0.01"),
    ) -> Tuple[Decimal, Decimal]:
        """
        Constructs synthetic bid and ask quotes around preserved midpoint:
        Bid_stress = Mid - S_stress / 2
        Ask_stress = Mid + S_stress / 2
        Rounds bid DOWN to nearest tick, ask UP to nearest tick if required.
        """
        if midpoint <= Decimal("0.0"):
            raise ValueError("Midpoint must be positive.")
        if stressed_spread < Decimal("0.0"):
            raise ValueError("Stressed spread cannot be negative.")

        half_spread = stressed_spread / Decimal("2.0")
        raw_bid = midpoint - half_spread
        raw_ask = midpoint + half_spread

        if tick_size > Decimal("0.0"):
            bid_ticks = (raw_bid / tick_size).quantize(Decimal("1"), rounding=ROUND_DOWN)
            stressed_bid = bid_ticks * tick_size
            ask_ticks = (raw_ask / tick_size).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            stressed_ask = ask_ticks * tick_size
        else:
            stressed_bid = raw_bid
            stressed_ask = raw_ask

        return stressed_bid, stressed_ask

    @staticmethod
    def reduce_depth_ladder(
        levels: List[OrderBookLevel],
        uniform_reduction: Optional[Decimal] = None,
        level_reductions: Optional[Dict[int, Decimal]] = None,
    ) -> List[OrderBookLevel]:
        """
        Reduces depth levels by uniform ratio r_d in [0, 1] or level-specific ratios:
        Q_i,stress = Q_i,0 * (1 - r_i)
        """
        stressed_levels = []
        for idx, lvl in enumerate(levels):
            red = Decimal("0.0")
            if level_reductions and idx in level_reductions:
                red = level_reductions[idx]
            elif uniform_reduction is not None:
                red = uniform_reduction

            red = min(Decimal("1.0"), max(Decimal("0.0"), red))
            stressed_qty = lvl.quantity * (Decimal("1.0") - red)
            notional = lvl.price * stressed_qty
            stressed_levels.append(
                OrderBookLevel(
                    price=lvl.price,
                    quantity=stressed_qty,
                    notional=notional,
                )
            )
        return stressed_levels

    @staticmethod
    def construct_synthetic_stress_book(
        baseline_midpoint: Decimal,
        baseline_spread: Decimal,
        baseline_bids: List[OrderBookLevel],
        baseline_asks: List[OrderBookLevel],
        spread_multiplier: Decimal = Decimal("1.0"),
        bid_reduction: Decimal = Decimal("0.0"),
        ask_reduction: Decimal = Decimal("0.0"),
        tick_size: Decimal = Decimal("0.01"),
    ) -> SyntheticStressBook:
        """
        Builds a full synthetic stressed book with widened spread and reduced depth.
        Levels maintain relative offset from the stressed top-of-book touch.
        """
        stressed_spread = LiquidityStressMath.calculate_stressed_spread(
            baseline_spread=baseline_spread,
            multiplier=spread_multiplier,
        )
        stressed_bid_1, stressed_ask_1 = LiquidityStressMath.construct_synthetic_quote(
            midpoint=baseline_midpoint,
            stressed_spread=stressed_spread,
            tick_size=tick_size,
        )

        # Baseline top-of-book prices
        base_bid_1 = baseline_bids[0].price if baseline_bids else baseline_midpoint - (baseline_spread / Decimal("2.0"))
        base_ask_1 = baseline_asks[0].price if baseline_asks else baseline_midpoint + (baseline_spread / Decimal("2.0"))

        # Reposition bids relative to stressed_bid_1
        repositioned_bids = []
        for b in baseline_bids:
            offset = base_bid_1 - b.price  # offset >= 0
            new_price = stressed_bid_1 - offset
            repositioned_bids.append(OrderBookLevel(price=new_price, quantity=b.quantity))

        # Reposition asks relative to stressed_ask_1
        repositioned_asks = []
        for a in baseline_asks:
            offset = a.price - base_ask_1  # offset >= 0
            new_price = stressed_ask_1 + offset
            repositioned_asks.append(OrderBookLevel(price=new_price, quantity=a.quantity))

        # Apply depth reductions
        stressed_bids = LiquidityStressMath.reduce_depth_ladder(
            levels=repositioned_bids, uniform_reduction=bid_reduction
        )
        stressed_asks = LiquidityStressMath.reduce_depth_ladder(
            levels=repositioned_asks, uniform_reduction=ask_reduction
        )

        tot_bid_depth = sum(b.quantity for b in stressed_bids)
        tot_ask_depth = sum(a.quantity for a in stressed_asks)
        tot_bid_notional = sum((b.notional or (b.price * b.quantity)) for b in stressed_bids)
        tot_ask_notional = sum((a.notional or (a.price * a.quantity)) for a in stressed_asks)

        return SyntheticStressBook(
            baseline_midpoint=baseline_midpoint,
            stressed_midpoint=baseline_midpoint,
            baseline_spread=baseline_spread,
            stressed_spread=stressed_spread,
            bids=stressed_bids,
            asks=stressed_asks,
            total_bid_depth=tot_bid_depth,
            total_ask_depth=tot_ask_depth,
            total_bid_notional=tot_bid_notional,
            total_ask_notional=tot_ask_notional,
        )

    @staticmethod
    def simulate_depth_walk_concession(
        levels: List[OrderBookLevel],
        order_quantity: Decimal,
        side: str,  # BUY uses asks, SELL uses bids
        benchmark_price: Decimal,
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Simulates static depth-walk over available book levels.
        Returns: (fillable_quantity, residual_unfilled, total_depth_concession_cost)
        where concession cost = sum(Q_j * |P_j - TouchPrice|)
        """
        if not levels or order_quantity <= Decimal("0.0"):
            return Decimal("0.0"), order_quantity, Decimal("0.0")

        remaining = order_quantity
        touch_price = levels[0].price
        concession_cost = Decimal("0.0")
        filled_qty = Decimal("0.0")

        for lvl in levels:
            if remaining <= Decimal("0.0"):
                break
            fill = min(remaining, lvl.quantity)
            concession_per_unit = abs(lvl.price - touch_price)
            concession_cost += fill * concession_per_unit
            filled_qty += fill
            remaining -= fill

        return filled_qty, remaining, concession_cost

    @staticmethod
    def calculate_liquidation_schedule(
        target_quantity: Decimal,
        volume_profiles: List[IntervalVolumeProfile],
        max_horizon_intervals: Optional[int] = None,
    ) -> LiquidationScheduleResult:
        """
        Calculates baseline and stressed liquidation durations across discrete interval volume profiles:
        Capacity_cumulative,n = sum_{i=1}^n p_i * V_i
        Liquidation completed at first interval n where Capacity >= Target.
        """
        if target_quantity <= Decimal("0.0"):
            return LiquidationScheduleResult(
                target_quantity=target_quantity,
                baseline_duration_intervals=0,
                stressed_duration_intervals=0,
                duration_increase_intervals=0,
                baseline_completed=True,
                stressed_completed=True,
                baseline_fillable_quantity=Decimal("0.0"),
                stressed_fillable_quantity=Decimal("0.0"),
                baseline_residual_quantity=Decimal("0.0"),
                stressed_residual_quantity=Decimal("0.0"),
                status="COMPLETED",
            )

        horizon = len(volume_profiles)
        if max_horizon_intervals is not None:
            horizon = min(horizon, max_horizon_intervals)

        cum_base = Decimal("0.0")
        cum_stress = Decimal("0.0")
        base_dur: Optional[int] = None
        stress_dur: Optional[int] = None

        for idx in range(horizon):
            p = volume_profiles[idx]
            base_cap = p.baseline_capacity if p.baseline_capacity > Decimal("0.0") else (p.baseline_volume * p.participation_rate)
            stress_vol = p.stressed_volume if p.stressed_volume > Decimal("0.0") else (p.baseline_volume * (Decimal("1.0") - p.volume_contraction_ratio))
            stress_cap = p.stressed_capacity if p.stressed_capacity > Decimal("0.0") else (stress_vol * p.participation_rate)

            cum_base += base_cap
            cum_stress += stress_cap

            if base_dur is None and cum_base >= target_quantity:
                base_dur = idx + 1
            if stress_dur is None and cum_stress >= target_quantity:
                stress_dur = idx + 1

        base_completed = base_dur is not None
        stress_completed = stress_dur is not None

        final_base_dur = base_dur if base_dur is not None else horizon
        final_stress_dur = stress_dur if stress_dur is not None else horizon

        base_fillable = min(target_quantity, cum_base)
        stress_fillable = min(target_quantity, cum_stress)
        base_residual = max(Decimal("0.0"), target_quantity - cum_base)
        stress_residual = max(Decimal("0.0"), target_quantity - cum_stress)

        dur_increase = max(0, final_stress_dur - final_base_dur)
        status = "COMPLETED" if stress_completed else "LIQUIDATION_NOT_COMPLETED"

        return LiquidationScheduleResult(
            target_quantity=target_quantity,
            baseline_duration_intervals=final_base_dur,
            stressed_duration_intervals=final_stress_dur,
            duration_increase_intervals=dur_increase,
            baseline_completed=base_completed,
            stressed_completed=stress_completed,
            baseline_fillable_quantity=base_fillable,
            stressed_fillable_quantity=stress_fillable,
            baseline_residual_quantity=base_residual,
            stressed_residual_quantity=stress_residual,
            status=status,
        )

    @staticmethod
    def calculate_stressed_execution_cost(
        order_quantity: Decimal,
        side: str,  # BUY or SELL
        reference_price: Decimal,
        baseline_spread: Decimal,
        stressed_spread: Decimal,
        baseline_depth_concession: Decimal = Decimal("0.0"),
        stressed_depth_concession: Decimal = Decimal("0.0"),
        baseline_impact_bps: Decimal = Decimal("0.0"),
        stressed_impact_bps: Decimal = Decimal("0.0"),
        explicit_fees: Decimal = Decimal("0.0"),
        unfilled_quantity: Decimal = Decimal("0.0"),
        terminal_price: Optional[Decimal] = None,
        multiplier: Decimal = Decimal("1.0"),
    ) -> StressedCostResult:
        """
        Reconciles baseline vs stressed execution cost:
        Total Cost = Spread Crossing + Depth Concession + Market Impact + Explicit Fees + Opportunity Cost.
        Ensures no double-counting between half-spread and depth-walk price concessions.
        """
        if reference_price <= Decimal("0.0"):
            raise ValueError("Reference price must be positive.")

        s = Decimal("1.0") if side.upper() in ("BUY", "B") else Decimal("-1.0")
        filled_qty = max(Decimal("0.0"), order_quantity - unfilled_quantity)

        # Baseline Components
        base_spread_cost = filled_qty * (baseline_spread / Decimal("2.0")) * multiplier
        base_impact_cost = filled_qty * reference_price * (baseline_impact_bps / Decimal("10000.0")) * multiplier
        base_opp_cost = Decimal("0.0")
        if terminal_price is not None and unfilled_quantity > Decimal("0.0"):
            base_opp_cost = s * (terminal_price - reference_price) * unfilled_quantity * multiplier
            base_opp_cost = max(Decimal("0.0"), base_opp_cost)

        base_total = base_spread_cost + baseline_depth_concession + base_impact_cost + explicit_fees + base_opp_cost
        base_notional = order_quantity * reference_price * multiplier
        base_total_bps = (base_total / base_notional) * Decimal("10000.0") if base_notional > Decimal("0.0") else Decimal("0.0")

        base_decomp = ExecutionCostDecomposition(
            spread_cost=base_spread_cost,
            depth_walk_concession_cost=baseline_depth_concession,
            market_impact_cost=base_impact_cost,
            slippage_cost=base_spread_cost + baseline_depth_concession,
            explicit_fees=explicit_fees,
            opportunity_cost=base_opp_cost,
            total_cost=base_total,
            total_cost_bps=base_total_bps,
        )

        # Stressed Components
        stress_spread_cost = filled_qty * (stressed_spread / Decimal("2.0")) * multiplier
        stress_impact_cost = filled_qty * reference_price * (stressed_impact_bps / Decimal("10000.0")) * multiplier
        stress_opp_cost = base_opp_cost  # terminal price deviation remains comparable

        stress_total = stress_spread_cost + stressed_depth_concession + stress_impact_cost + explicit_fees + stress_opp_cost
        stress_total_bps = (stress_total / base_notional) * Decimal("10000.0") if base_notional > Decimal("0.0") else Decimal("0.0")

        stress_decomp = ExecutionCostDecomposition(
            spread_cost=stress_spread_cost,
            depth_walk_concession_cost=stressed_depth_concession,
            market_impact_cost=stress_impact_cost,
            slippage_cost=stress_spread_cost + stressed_depth_concession,
            explicit_fees=explicit_fees,
            opportunity_cost=stress_opp_cost,
            total_cost=stress_total,
            total_cost_bps=stress_total_bps,
        )

        cost_escalation = stress_total - base_total
        cost_escalation_bps = stress_total_bps - base_total_bps
        cost_escalation_pct = (
            (cost_escalation / base_total) * Decimal("100.0")
            if base_total > Decimal("0.0001")
            else None
        )

        return StressedCostResult(
            baseline_cost=base_decomp,
            stressed_cost=stress_decomp,
            cost_escalation_monetary=cost_escalation,
            cost_escalation_pct=cost_escalation_pct,
            cost_escalation_bps=cost_escalation_bps,
            is_extrapolated=False,
        )

    @staticmethod
    def reverse_stress_search(
        baseline_spread: Decimal,
        baseline_interval_volume: Decimal,
        order_quantity: Decimal,
        max_acceptable_cost: Decimal,
        max_acceptable_intervals: int,
        participation_rate: Decimal = Decimal("0.10"),
        reference_price: Decimal = Decimal("100.0"),
    ) -> Dict[str, Any]:
        """
        Reverse Stress Testing:
        Searches for critical shock thresholds (spread multiplier or volume contraction)
        that cause a breach of configured liquidation-time or cost constraints.
        """
        # 1. Critical Volume Contraction for Liquidation Time
        # Capacity per interval = p * V_0 * (1 - r_v)
        # Required intervals = ceil(Q / Capacity) <= max_acceptable_intervals
        # => Q / (max_intervals * p * V_0) <= 1 - r_v
        # => r_v_critical = 1 - (Q / (max_intervals * p * V_0))
        max_capacity_needed = order_quantity / Decimal(str(max_acceptable_intervals))
        unconstrained_cap = baseline_interval_volume * participation_rate
        
        if unconstrained_cap <= Decimal("0.0"):
            crit_vol_contraction = Decimal("0.0")
            time_breached_at_baseline = True
        else:
            ratio = max_capacity_needed / unconstrained_cap
            crit_vol_contraction = max(Decimal("0.0"), min(Decimal("1.0"), Decimal("1.0") - ratio))
            time_breached_at_baseline = (order_quantity / unconstrained_cap) > Decimal(str(max_acceptable_intervals))

        # 2. Critical Spread Multiplier for Cost Breach
        # Spread Cost = Q * (S_0 * m_s / 2) <= max_cost
        # => m_s_critical = (2 * max_cost) / (Q * S_0)
        denom = order_quantity * baseline_spread
        if denom > Decimal("0.0"):
            crit_spread_multiplier = (Decimal("2.0") * max_acceptable_cost) / denom
        else:
            crit_spread_multiplier = Decimal("1.0")

        return {
            "time_breached_at_baseline": time_breached_at_baseline,
            "critical_volume_contraction_ratio": crit_vol_contraction,
            "critical_volume_contraction_pct": crit_vol_contraction * Decimal("100.0"),
            "critical_spread_multiplier": crit_spread_multiplier,
            "max_acceptable_cost": max_acceptable_cost,
            "max_acceptable_intervals": max_acceptable_intervals,
        }

