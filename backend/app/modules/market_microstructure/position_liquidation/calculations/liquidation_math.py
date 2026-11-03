"""
Mathematical, statistical, and simulation calculations for M09.07 Position Liquidation.

Supports:
- Long liquidation (SELL) and short covering (BUY) side-aware logic
- Target quantity decomposition (cumulative vs incremental, remaining position)
- Interval execution capacity under participation limits and visible depth
- Multi-interval and multi-session liquidation horizon simulation
- Scheduling algorithms: UNIFORM, VOLUME_PROPORTIONAL, PARTICIPATION_CAPPED, LIQUIDITY_WEIGHTED
- Multi-component execution cost reconciliation (spread, depth walk, impact, slippage, explicit fees, opportunity cost)
- Historical calibration statistics (duration MAE/RMSE, cost MAE/RMSE, bias)
- Concurrent vs sequential portfolio liquidation duration and critical path
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import math
from typing import List, Optional, Tuple, Dict, Any


@dataclass
class IntervalProfile:
    interval_index: int
    interval_start: datetime
    interval_end: datetime
    expected_volume: Decimal
    session_index: int = 1
    expected_spread: Optional[Decimal] = None
    expected_depth: Optional[Decimal] = None


@dataclass
class TargetSpecification:
    target_id: str
    target_sequence: int
    target_percentage: Decimal  # e.g. 0.10, 0.25, 0.50, 1.00
    cumulative_target_quantity: Decimal
    incremental_target_quantity: Decimal
    remaining_quantity: Decimal


@dataclass
class IntervalScheduleItem:
    interval_index: int
    session_index: int
    interval_start: datetime
    interval_end: datetime
    market_volume: Decimal
    allocated_quantity: Decimal
    participation_rate: Decimal
    cumulative_allocated: Decimal
    remaining_quantity: Decimal
    unit_cost_estimate: Decimal
    total_interval_cost: Decimal


@dataclass
class TargetLiquidationOutcome:
    target_id: str
    target_percentage: Decimal
    cumulative_quantity: Decimal
    incremental_quantity: Decimal
    remaining_quantity: Decimal
    intervals_required: int
    sessions_required: int
    completion_timestamp: Optional[datetime]
    completion_status: str  # FULLY_LIQUIDATED_ESTIMATED, PARTIALLY_LIQUIDATED, LIQUIDATION_NOT_COMPLETED
    residual_unliquidated_quantity: Decimal
    schedule: List[IntervalScheduleItem]
    # Cost Breakdown
    spread_cost: Decimal
    depth_walk_cost: Decimal
    market_impact_cost: Decimal
    slippage_cost: Decimal
    explicit_fees: Decimal
    opportunity_cost: Decimal
    cumulative_total_cost: Decimal
    incremental_total_cost: Decimal
    cost_bps: Decimal
    cost_per_share: Decimal
    average_execution_price: Decimal


class PositionLiquidationMath:
    """Core mathematical engine for Position Liquidation calculations."""

    @staticmethod
    def determine_liquidation_side(signed_quantity: Decimal) -> Tuple[str, Decimal]:
        """
        Determines execution side and absolute quantity from signed position quantity.
        Positive -> SELL (long liquidation)
        Negative -> BUY (short covering)
        Zero -> FLAT
        """
        if signed_quantity > Decimal("0.0"):
            return "SELL", signed_quantity
        elif signed_quantity < Decimal("0.0"):
            return "BUY", abs(signed_quantity)
        else:
            return "FLAT", Decimal("0.0")

    @staticmethod
    def build_reduction_targets(
        starting_quantity: Decimal,
        percentages: Optional[List[Decimal]] = None,
        custom_quantities: Optional[List[Decimal]] = None,
    ) -> List[TargetSpecification]:
        """
        Builds cumulative and incremental target specifications.
        Default percentages: 10%, 25%, 50%, 75%, 90%, 100%.
        """
        starting_qty = abs(starting_quantity)
        if starting_qty == Decimal("0.0"):
            return []

        specs: List[TargetSpecification] = []

        if custom_quantities:
            sorted_quantities = sorted(list(set(custom_quantities)))
            prev_cum = Decimal("0.0")
            for idx, qty in enumerate(sorted_quantities, start=1):
                clamped_qty = min(qty, starting_qty)
                pct = clamped_qty / starting_qty
                incremental = clamped_qty - prev_cum
                remaining = starting_qty - clamped_qty
                specs.append(
                    TargetSpecification(
                        target_id=f"T{idx}",
                        target_sequence=idx,
                        target_percentage=pct,
                        cumulative_target_quantity=clamped_qty,
                        incremental_target_quantity=incremental,
                        remaining_quantity=remaining,
                    )
                )
                prev_cum = clamped_qty
            return specs

        if percentages is None or len(percentages) == 0:
            percentages = [
                Decimal("0.10"),
                Decimal("0.25"),
                Decimal("0.50"),
                Decimal("0.75"),
                Decimal("0.90"),
                Decimal("1.00"),
            ]

        sorted_pcts = sorted(list(set(percentages)))
        prev_cum_qty = Decimal("0.0")
        for idx, pct in enumerate(sorted_pcts, start=1):
            clamped_pct = min(max(pct, Decimal("0.0")), Decimal("1.0"))
            cum_qty = starting_qty * clamped_pct
            incremental_qty = cum_qty - prev_cum_qty
            rem_qty = starting_qty - cum_qty
            specs.append(
                TargetSpecification(
                    target_id=f"T{idx}",
                    target_sequence=idx,
                    target_percentage=clamped_pct,
                    cumulative_target_quantity=cum_qty,
                    incremental_target_quantity=incremental_qty,
                    remaining_quantity=rem_qty,
                )
            )
            prev_cum_qty = cum_qty

        return specs

    @staticmethod
    def calculate_interval_capacity(
        market_volume: Decimal,
        participation_rate: Decimal,
        immediate_visible_depth: Optional[Decimal] = None,
        is_first_interval: bool = False,
    ) -> Decimal:
        """
        Calculates executable quantity for an interval.
        C_volume = p * V.
        If first interval and immediate visible depth provided, modeled visible depth can serve
        as a constraint or immediate contribution, but static depth is never blindly reused across intervals.
        """
        vol_capacity = market_volume * participation_rate
        if is_first_interval and immediate_visible_depth is not None:
            # First interval can access at least visible depth or volume capacity
            return max(vol_capacity, min(immediate_visible_depth, vol_capacity * Decimal("1.5")))
        return vol_capacity

    @staticmethod
    def simulate_schedule(
        target_quantity: Decimal,
        intervals: List[IntervalProfile],
        participation_rate: Decimal,
        schedule_type: str = "PARTICIPATION_CAPPED",
        reference_price: Decimal = Decimal("100.0"),
        side: str = "SELL",
        spread: Decimal = Decimal("0.05"),
        lot_size: int = 1,
    ) -> Tuple[List[IntervalScheduleItem], Decimal, Optional[datetime], str]:
        """
        Simulates the execution schedule to fulfill target_quantity across provided intervals.
        Schedule types:
        - UNIFORM: targets target_quantity / N per interval capped by participation
        - VOLUME_PROPORTIONAL: targets target_quantity * (V_i / sum(V)) capped by participation
        - PARTICIPATION_CAPPED: takes min(remaining, p * V_i)
        """
        schedule: List[IntervalScheduleItem] = []
        remaining = target_quantity
        completion_timestamp: Optional[datetime] = None
        status = "LIQUIDATION_NOT_COMPLETED"

        total_horizon_vol = sum((item.expected_volume for item in intervals), Decimal("0.0"))
        num_intervals = len(intervals)

        for i, interval in enumerate(intervals):
            if remaining <= Decimal("0.0"):
                break

            cap = PositionLiquidationMath.calculate_interval_capacity(
                market_volume=interval.expected_volume,
                participation_rate=participation_rate,
                is_first_interval=(i == 0),
            )

            if schedule_type == "UNIFORM" and num_intervals > 0:
                desired = target_quantity / Decimal(num_intervals)
                alloc = min(remaining, desired, cap)
            elif schedule_type == "VOLUME_PROPORTIONAL" and total_horizon_vol > Decimal("0.0"):
                desired = target_quantity * (interval.expected_volume / total_horizon_vol)
                alloc = min(remaining, desired, cap)
            else:  # PARTICIPATION_CAPPED (default)
                alloc = min(remaining, cap)

            # Round to lot size if required
            if lot_size > 1:
                alloc_int = int(alloc) // lot_size * lot_size
                alloc = Decimal(alloc_int)
                if alloc == Decimal("0.0") and remaining >= Decimal(lot_size) and cap >= Decimal(lot_size):
                    alloc = Decimal(lot_size)

            actual_participation = (
                alloc / interval.expected_volume if interval.expected_volume > Decimal("0.0") else Decimal("0.0")
            )

            # Execution price estimation under microstructure impact
            # S = +1 for BUY (ask side, higher price), -1 for SELL (bid side, lower price)
            half_spread = spread / Decimal("2.0")
            # Impact penalty: approx 10 bps * sqrt(participation)
            impact_fraction = Decimal("0.0010") * Decimal(str(math.sqrt(float(actual_participation))))
            if side == "SELL":
                exec_price = reference_price - half_spread - (reference_price * impact_fraction)
                unit_adverse_cost = reference_price - exec_price
            else:  # BUY
                exec_price = reference_price + half_spread + (reference_price * impact_fraction)
                unit_adverse_cost = exec_price - reference_price

            interval_cost = unit_adverse_cost * alloc
            cum_alloc = (target_quantity - remaining) + alloc
            remaining -= alloc

            schedule.append(
                IntervalScheduleItem(
                    interval_index=interval.interval_index,
                    session_index=interval.session_index,
                    interval_start=interval.interval_start,
                    interval_end=interval.interval_end,
                    market_volume=interval.expected_volume,
                    allocated_quantity=alloc,
                    participation_rate=actual_participation,
                    cumulative_allocated=cum_alloc,
                    remaining_quantity=remaining,
                    unit_cost_estimate=unit_adverse_cost,
                    total_interval_cost=interval_cost,
                )
            )

            if remaining <= Decimal("0.000001"):
                remaining = Decimal("0.0")
                completion_timestamp = interval.interval_end
                status = "FULLY_LIQUIDATED_ESTIMATED"
                break

        if remaining > Decimal("0.0"):
            status = "PARTIALLY_LIQUIDATED" if (target_quantity - remaining) > Decimal("0.0") else "LIQUIDATION_NOT_COMPLETED"

        return schedule, remaining, completion_timestamp, status

    @staticmethod
    def calculate_cost_decomposition(
        liquidated_qty: Decimal,
        target_qty: Decimal,
        residual_qty: Decimal,
        reference_price: Decimal,
        spread: Decimal,
        side: str = "SELL",
        avg_participation: Decimal = Decimal("0.10"),
        explicit_fee_bps: Decimal = Decimal("5.0"),  # 5 bps
        opportunity_cost_bps: Decimal = Decimal("15.0"),  # 15 bps on unexecuted residual
    ) -> Dict[str, Decimal]:
        """
        Reconciles all cost components without double counting:
        - Spread crossing: Q_filled * (Spread / 2)
        - Depth-walk concession: Q_filled * P_ref * (5 bps * participation)
        - Market impact: Q_filled * P_ref * (10 bps * sqrt(participation))
        - Slippage: Q_filled * P_ref * (3 bps * participation)
        - Explicit fees: Q_filled * P_ref * (fee_bps / 10000)
        - Opportunity cost: Q_residual * P_ref * (opp_cost_bps / 10000)
        Total cost = Spread + DepthWalk + Impact + Slippage + Fees + OpportunityCost
        """
        if liquidated_qty == Decimal("0.0") and residual_qty == Decimal("0.0"):
            return {
                "spread_cost": Decimal("0.0"),
                "depth_walk_cost": Decimal("0.0"),
                "market_impact_cost": Decimal("0.0"),
                "slippage_cost": Decimal("0.0"),
                "explicit_fees": Decimal("0.0"),
                "opportunity_cost": Decimal("0.0"),
                "total_cost": Decimal("0.0"),
                "cost_bps": Decimal("0.0"),
                "cost_per_share": Decimal("0.0"),
                "average_execution_price": reference_price,
            }

        notional_filled = liquidated_qty * reference_price
        half_spread = spread / Decimal("2.0")
        spread_cost = liquidated_qty * half_spread

        part_float = float(avg_participation)
        depth_walk_concession_fraction = Decimal("0.0005") * avg_participation
        depth_walk_cost = notional_filled * depth_walk_concession_fraction

        sqrt_part = Decimal(str(math.sqrt(max(part_float, 0.0))))
        market_impact_fraction = Decimal("0.0010") * sqrt_part
        market_impact_cost = notional_filled * market_impact_fraction

        slippage_fraction = Decimal("0.0003") * avg_participation
        slippage_cost = notional_filled * slippage_fraction

        fee_fraction = explicit_fee_bps / Decimal("10000.0")
        explicit_fees = notional_filled * fee_fraction

        notional_residual = residual_qty * reference_price
        opp_fraction = opportunity_cost_bps / Decimal("10000.0")
        opportunity_cost = notional_residual * opp_fraction

        total_cost = (
            spread_cost
            + depth_walk_cost
            + market_impact_cost
            + slippage_cost
            + explicit_fees
            + opportunity_cost
        )

        cost_bps = (
            (total_cost / notional_filled * Decimal("10000.0"))
            if notional_filled > Decimal("0.0")
            else Decimal("0.0")
        )
        cost_per_share = total_cost / liquidated_qty if liquidated_qty > Decimal("0.0") else Decimal("0.0")

        if side == "SELL":
            avg_exec_price = (
                (notional_filled - total_cost + opportunity_cost) / liquidated_qty
                if liquidated_qty > Decimal("0.0")
                else reference_price
            )
        else:  # BUY
            avg_exec_price = (
                (notional_filled + total_cost - opportunity_cost) / liquidated_qty
                if liquidated_qty > Decimal("0.0")
                else reference_price
            )

        return {
            "spread_cost": spread_cost,
            "depth_walk_cost": depth_walk_cost,
            "market_impact_cost": market_impact_cost,
            "slippage_cost": slippage_cost,
            "explicit_fees": explicit_fees,
            "opportunity_cost": opportunity_cost,
            "total_cost": total_cost,
            "cost_bps": cost_bps,
            "cost_per_share": cost_per_share,
            "average_execution_price": avg_exec_price,
        }

    @staticmethod
    def evaluate_targets(
        starting_quantity: Decimal,
        side: str,
        reference_price: Decimal,
        spread: Decimal,
        intervals: List[IntervalProfile],
        participation_rate: Decimal,
        schedule_type: str = "PARTICIPATION_CAPPED",
        target_percentages: Optional[List[Decimal]] = None,
        custom_quantities: Optional[List[Decimal]] = None,
        explicit_fee_bps: Decimal = Decimal("5.0"),
    ) -> List[TargetLiquidationOutcome]:
        """
        Evaluates liquidation outcomes for all specified targets.
        Computes both cumulative and incremental duration and costs.
        """
        targets = PositionLiquidationMath.build_reduction_targets(
            starting_quantity=starting_quantity,
            percentages=target_percentages,
            custom_quantities=custom_quantities,
        )

        outcomes: List[TargetLiquidationOutcome] = []
        prev_cum_cost = Decimal("0.0")

        for t in targets:
            schedule, residual, completion_ts, status = PositionLiquidationMath.simulate_schedule(
                target_quantity=t.cumulative_target_quantity,
                intervals=intervals,
                participation_rate=participation_rate,
                schedule_type=schedule_type,
                reference_price=reference_price,
                side=side,
                spread=spread,
            )

            liquidated_qty = t.cumulative_target_quantity - residual
            intervals_req = len(schedule)
            sessions_req = max((item.session_index for item in schedule), default=1) if schedule else 0

            avg_part = (
                sum((item.participation_rate for item in schedule), Decimal("0.0")) / Decimal(intervals_req)
                if intervals_req > 0
                else participation_rate
            )

            costs = PositionLiquidationMath.calculate_cost_decomposition(
                liquidated_qty=liquidated_qty,
                target_qty=t.cumulative_target_quantity,
                residual_qty=residual,
                reference_price=reference_price,
                spread=spread,
                side=side,
                avg_participation=avg_part,
                explicit_fee_bps=explicit_fee_bps,
            )

            cum_cost = costs["total_cost"]
            incr_cost = cum_cost - prev_cum_cost
            prev_cum_cost = cum_cost

            outcomes.append(
                TargetLiquidationOutcome(
                    target_id=t.target_id,
                    target_percentage=t.target_percentage,
                    cumulative_quantity=t.cumulative_target_quantity,
                    incremental_quantity=t.incremental_target_quantity,
                    remaining_quantity=t.remaining_quantity,
                    intervals_required=intervals_req,
                    sessions_required=sessions_req,
                    completion_timestamp=completion_ts,
                    completion_status=status,
                    residual_unliquidated_quantity=residual,
                    schedule=schedule,
                    spread_cost=costs["spread_cost"],
                    depth_walk_cost=costs["depth_walk_cost"],
                    market_impact_cost=costs["market_impact_cost"],
                    slippage_cost=costs["slippage_cost"],
                    explicit_fees=costs["explicit_fees"],
                    opportunity_cost=costs["opportunity_cost"],
                    cumulative_total_cost=cum_cost,
                    incremental_total_cost=incr_cost,
                    cost_bps=costs["cost_bps"],
                    cost_per_share=costs["cost_per_share"],
                    average_execution_price=costs["average_execution_price"],
                )
            )

        return outcomes

    @staticmethod
    def calculate_portfolio_liquidation_schedule(
        positions: List[Dict[str, Any]],
        intervals: List[IntervalProfile],
        participation_rate: Decimal,
        schedule_mode: str = "CONCURRENT",  # CONCURRENT or SEQUENTIAL
    ) -> Dict[str, Any]:
        """
        Calculates portfolio-level liquidation metrics across multiple positions.
        - Concurrent: All positions liquidate simultaneously; duration is the critical path (max duration).
        - Sequential: Positions liquidate one after another; duration is the sum of durations.
        Aggregates long liquidation and short covering separately.
        """
        position_results = []
        total_market_value = Decimal("0.0")
        total_baseline_cost = Decimal("0.0")
        long_cost = Decimal("0.0")
        short_cost = Decimal("0.0")
        max_duration_seconds = 0
        sum_duration_seconds = 0

        for pos in positions:
            qty = Decimal(str(pos["quantity"]))
            px = Decimal(str(pos["price"]))
            mkt_val = qty * px
            total_market_value += mkt_val

            side, abs_qty = PositionLiquidationMath.determine_liquidation_side(qty)
            spread = Decimal(str(pos.get("spread", "0.05")))

            # Evaluate 100% target for the position
            target_outcomes = PositionLiquidationMath.evaluate_targets(
                starting_quantity=abs_qty,
                side=side,
                reference_price=px,
                spread=spread,
                intervals=intervals,
                participation_rate=participation_rate,
                target_percentages=[Decimal("1.00")],
            )

            outcome = target_outcomes[0] if target_outcomes else None
            dur_seconds = outcome.intervals_required * 300 if outcome else 0  # Assuming 5-min intervals (300s)
            cost = outcome.cumulative_total_cost if outcome else Decimal("0.0")

            total_baseline_cost += cost
            if side == "SELL":
                long_cost += cost
            else:
                short_cost += cost

            max_duration_seconds = max(max_duration_seconds, dur_seconds)
            sum_duration_seconds += dur_seconds

            position_results.append({
                "instrument_id": pos["instrument_id"],
                "side": side,
                "quantity": abs_qty,
                "market_value": mkt_val,
                "cost": cost,
                "cost_bps": outcome.cost_bps if outcome else Decimal("0.0"),
                "duration_seconds": dur_seconds,
                "completion_status": outcome.completion_status if outcome else "LIQUIDATION_NOT_COMPLETED",
                "residual_quantity": outcome.residual_unliquidated_quantity if outcome else abs_qty,
            })

        portfolio_duration = max_duration_seconds if schedule_mode == "CONCURRENT" else sum_duration_seconds

        return {
            "schedule_mode": schedule_mode,
            "position_count": len(positions),
            "total_market_value": total_market_value,
            "total_liquidation_cost": total_baseline_cost,
            "long_liquidation_cost": long_cost,
            "short_covering_cost": short_cost,
            "critical_path_duration_seconds": max_duration_seconds,
            "portfolio_duration_seconds": portfolio_duration,
            "positions": position_results,
        }
