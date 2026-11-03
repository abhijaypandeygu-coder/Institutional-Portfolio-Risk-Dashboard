"""
Mathematical and statistical algorithms for M09.08 Order Book Imbalance.

Features:
- Best-level and multi-level quantity & notional imbalance
- Bid / ask liquidity shares
- Weighted imbalance:
  * Equal weighting
  * Exponential level decay: w_i = exp(-lambda * (i - 1))
  * Linear level decay: w_i = max(1 - (i - 1)/N, 0)
  * Distance weighting: w_i = exp(-lambda * d_i)
  * User-specified custom weights
- Microprice and microprice deviation from midpoint
- Time-series tracking:
  * Time-weighted average imbalance
  * Rolling mean, standard deviation, and momentum
  * EWMA
  * Historical standardization (z-score and robust MAD-based z-score)
- Persistence analytics:
  * Bid-dominant, ask-dominant, and neutral state proportions
  * Consecutive run durations (current, max, average)
- Reversal analytics:
  * Sign reversals & threshold-confirmed transitions with hysteresis
  * Reversal magnitude and rate
- Imbalance regime classification:
  * STRONG_BID, MODERATE_BID, NEUTRAL, MODERATE_ASK, STRONG_ASK, INSUFFICIENT_DATA
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import math
from typing import List, Optional, Tuple, Dict, Any


@dataclass
class OrderBookLevelData:
    level_index: int  # 1-indexed: 1 = top of book
    bid_price: Decimal
    ask_price: Decimal
    bid_quantity: Decimal
    ask_quantity: Decimal
    bid_notional: Optional[Decimal] = None
    ask_notional: Optional[Decimal] = None

    def __post_init__(self):
        if self.bid_notional is None:
            self.bid_notional = self.bid_price * self.bid_quantity
        if self.ask_notional is None:
            self.ask_notional = self.ask_price * self.ask_quantity


@dataclass
class ImbalanceSnapshotResult:
    best_level_imbalance: Optional[Decimal]
    multi_level_quantity_imbalance: Optional[Decimal]
    multi_level_notional_imbalance: Optional[Decimal]
    weighted_quantity_imbalance: Optional[Decimal]
    weighted_notional_imbalance: Optional[Decimal]
    bid_share: Optional[Decimal]
    ask_share: Optional[Decimal]
    total_bid_quantity: Decimal
    total_ask_quantity: Decimal
    total_bid_notional: Decimal
    total_ask_notional: Decimal
    microprice: Optional[Decimal]
    midpoint: Optional[Decimal]
    microprice_deviation_bps: Optional[Decimal]
    actual_level_count: int


@dataclass
class TimeSeriesObservation:
    timestamp: datetime
    imbalance: Decimal
    duration_seconds: float = 1.0


class OrderBookImbalanceMath:
    """Mathematical calculations for M09.08 Order Book Imbalance."""

    @staticmethod
    def calculate_normalized_imbalance(
        bid_measure: Decimal,
        ask_measure: Decimal,
    ) -> Tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
        """
        Calculates normalized imbalance: (B - A) / (B + A)
        Also returns (bid_share, ask_share).
        Range is strictly [-1.0, 1.0].
        If B + A == 0 or negative, returns (None, None, None).
        """
        total = bid_measure + ask_measure
        if total <= Decimal("0.0"):
            return None, None, None

        imbalance = (bid_measure - ask_measure) / total
        bid_share = bid_measure / total
        ask_share = ask_measure / total
        return imbalance, bid_share, ask_share

    @staticmethod
    def calculate_microprice(
        best_bid_price: Decimal,
        best_ask_price: Decimal,
        best_bid_qty: Decimal,
        best_ask_qty: Decimal,
    ) -> Tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
        """
        Calculates microprice:
        Microprice = (Ask_1 * Q_b1 + Bid_1 * Q_a1) / (Q_b1 + Q_a1)
        Midpoint = (Bid_1 + Ask_1) / 2
        Deviation in bps = (Microprice - Midpoint) / Midpoint * 10,000
        """
        total_qty = best_bid_qty + best_ask_qty
        if total_qty <= Decimal("0.0"):
            return None, None, None

        midpoint = (best_bid_price + best_ask_price) / Decimal("2.0")
        microprice = (best_ask_price * best_bid_qty + best_bid_price * best_ask_qty) / total_qty
        if midpoint > Decimal("0.0"):
            dev_bps = ((microprice - midpoint) / midpoint) * Decimal("10000.0")
        else:
            dev_bps = Decimal("0.0")

        return microprice, midpoint, dev_bps

    @staticmethod
    def generate_level_weights(
        level_count: int,
        weighting_method: str = "EQUAL",
        decay_parameter: float = 0.5,
        custom_weights: Optional[List[float]] = None,
        levels: Optional[List[OrderBookLevelData]] = None,
        midpoint: Optional[Decimal] = None,
        distance_unit: str = "PRICE",  # PRICE, TICK, or BPS
        tick_size: Decimal = Decimal("0.01"),
    ) -> Tuple[List[Decimal], List[Decimal]]:
        """
        Generates per-level bid and ask weights.
        Methods:
        - EQUAL: w_i = 1.0
        - EXPONENTIAL_LEVEL: w_i = exp(-decay * (i - 1))
        - LINEAR_LEVEL: w_i = max(1.0 - (i - 1)/N, 0.0)
        - DISTANCE_DECAY: w_i = exp(-decay * dist_i)
        - CUSTOM: user-specified array
        Returns (bid_weights, ask_weights).
        """
        if level_count <= 0:
            return [], []

        bid_weights: List[Decimal] = []
        ask_weights: List[Decimal] = []

        if weighting_method == "CUSTOM" and custom_weights and len(custom_weights) >= level_count:
            b_w = [Decimal(str(max(w, 0.0))) for w in custom_weights[:level_count]]
            return b_w, list(b_w)

        if weighting_method == "EXPONENTIAL_LEVEL":
            for i in range(1, level_count + 1):
                val = math.exp(-decay_parameter * (i - 1))
                w = Decimal(str(round(val, 6)))
                bid_weights.append(w)
                ask_weights.append(w)
            return bid_weights, ask_weights

        if weighting_method == "LINEAR_LEVEL":
            for i in range(1, level_count + 1):
                val = max(1.0 - float(i - 1) / float(level_count), 0.0)
                w = Decimal(str(round(val, 6)))
                bid_weights.append(w)
                ask_weights.append(w)
            return bid_weights, ask_weights

        if weighting_method == "DISTANCE_DECAY" and levels and midpoint and midpoint > Decimal("0.0"):
            for lvl in levels[:level_count]:
                b_dist = max(midpoint - lvl.bid_price, Decimal("0.0"))
                a_dist = max(lvl.ask_price - midpoint, Decimal("0.0"))

                if distance_unit == "TICK" and tick_size > Decimal("0.0"):
                    b_d = float(b_dist / tick_size)
                    a_d = float(a_dist / tick_size)
                elif distance_unit == "BPS":
                    b_d = float((b_dist / midpoint) * Decimal("10000.0"))
                    a_d = float((a_dist / midpoint) * Decimal("10000.0"))
                else:  # PRICE
                    b_d = float(b_dist)
                    a_d = float(a_dist)

                wb = Decimal(str(round(math.exp(-decay_parameter * b_d), 6)))
                wa = Decimal(str(round(math.exp(-decay_parameter * a_d), 6)))
                bid_weights.append(wb)
                ask_weights.append(wa)
            return bid_weights, ask_weights

        # Default EQUAL weighting
        w_eq = Decimal("1.0")
        return [w_eq] * level_count, [w_eq] * level_count

    @staticmethod
    def calculate_snapshot_imbalance(
        levels: List[OrderBookLevelData],
        requested_levels: int = 5,
        weighting_method: str = "EQUAL",
        decay_parameter: float = 0.5,
        custom_weights: Optional[List[float]] = None,
        distance_unit: str = "PRICE",
        tick_size: Decimal = Decimal("0.01"),
    ) -> ImbalanceSnapshotResult:
        """
        Computes all snapshot-level order book imbalance indicators from ordered depth levels.
        """
        if not levels:
            return ImbalanceSnapshotResult(
                best_level_imbalance=None,
                multi_level_quantity_imbalance=None,
                multi_level_notional_imbalance=None,
                weighted_quantity_imbalance=None,
                weighted_notional_imbalance=None,
                bid_share=None,
                ask_share=None,
                total_bid_quantity=Decimal("0.0"),
                total_ask_quantity=Decimal("0.0"),
                total_bid_notional=Decimal("0.0"),
                total_ask_notional=Decimal("0.0"),
                microprice=None,
                midpoint=None,
                microprice_deviation_bps=None,
                actual_level_count=0,
            )

        # 1. Best-level imbalance & microprice
        top = levels[0]
        i1, b1_share, a1_share = OrderBookImbalanceMath.calculate_normalized_imbalance(
            top.bid_quantity, top.ask_quantity
        )
        microprice, midpoint, dev_bps = OrderBookImbalanceMath.calculate_microprice(
            top.bid_price, top.ask_price, top.bid_quantity, top.ask_quantity
        )

        # 2. Multi-level aggregate quantities & notionals
        clamped_levels = levels[:requested_levels]
        actual_count = len(clamped_levels)

        total_b_qty = sum((lvl.bid_quantity for lvl in clamped_levels), Decimal("0.0"))
        total_a_qty = sum((lvl.ask_quantity for lvl in clamped_levels), Decimal("0.0"))
        total_b_notional = sum((lvl.bid_notional for lvl in clamped_levels), Decimal("0.0"))
        total_a_notional = sum((lvl.ask_notional for lvl in clamped_levels), Decimal("0.0"))

        i_n_qty, b_share, a_share = OrderBookImbalanceMath.calculate_normalized_imbalance(
            total_b_qty, total_a_qty
        )
        i_n_notional, _, _ = OrderBookImbalanceMath.calculate_normalized_imbalance(
            total_b_notional, total_a_notional
        )

        # 3. Weighted imbalance
        b_w, a_w = OrderBookImbalanceMath.generate_level_weights(
            level_count=actual_count,
            weighting_method=weighting_method,
            decay_parameter=decay_parameter,
            custom_weights=custom_weights,
            levels=clamped_levels,
            midpoint=midpoint,
            distance_unit=distance_unit,
            tick_size=tick_size,
        )

        w_b_qty = sum((clamped_levels[i].bid_quantity * b_w[i] for i in range(actual_count)), Decimal("0.0"))
        w_a_qty = sum((clamped_levels[i].ask_quantity * a_w[i] for i in range(actual_count)), Decimal("0.0"))
        w_b_notional = sum((clamped_levels[i].bid_notional * b_w[i] for i in range(actual_count)), Decimal("0.0"))
        w_a_notional = sum((clamped_levels[i].ask_notional * a_w[i] for i in range(actual_count)), Decimal("0.0"))

        weighted_qty_imb, _, _ = OrderBookImbalanceMath.calculate_normalized_imbalance(w_b_qty, w_a_qty)
        weighted_notional_imb, _, _ = OrderBookImbalanceMath.calculate_normalized_imbalance(w_b_notional, w_a_notional)

        return ImbalanceSnapshotResult(
            best_level_imbalance=i1,
            multi_level_quantity_imbalance=i_n_qty,
            multi_level_notional_imbalance=i_n_notional,
            weighted_quantity_imbalance=weighted_qty_imb,
            weighted_notional_imbalance=weighted_notional_imb,
            bid_share=b_share,
            ask_share=a_share,
            total_bid_quantity=total_b_qty,
            total_ask_quantity=total_a_qty,
            total_bid_notional=total_b_notional,
            total_ask_notional=total_a_notional,
            microprice=microprice,
            midpoint=midpoint,
            microprice_deviation_bps=dev_bps,
            actual_level_count=actual_count,
        )

    @staticmethod
    def calculate_persistence_and_runs(
        observations: List[TimeSeriesObservation],
        threshold: Decimal = Decimal("0.20"),
    ) -> Dict[str, Any]:
        """
        Measures state persistence (BID_DOMINANT, ASK_DOMINANT, NEUTRAL) and run durations.
        """
        if not observations:
            return {
                "bid_persistence_ratio": Decimal("0.0"),
                "ask_persistence_ratio": Decimal("0.0"),
                "neutral_persistence_ratio": Decimal("1.0"),
                "total_valid_duration_seconds": 0.0,
                "current_state": "NEUTRAL",
                "current_run_duration_seconds": 0.0,
                "max_bid_run_seconds": 0.0,
                "max_ask_run_seconds": 0.0,
                "average_bid_run_seconds": 0.0,
                "average_ask_run_seconds": 0.0,
            }

        total_dur = sum(obs.duration_seconds for obs in observations)
        if total_dur <= 0.0:
            total_dur = float(len(observations))

        bid_dur = 0.0
        ask_dur = 0.0
        neutral_dur = 0.0

        current_state = "NEUTRAL"
        current_run = 0.0

        bid_runs: List[float] = []
        ask_runs: List[float] = []

        cur_bid_run = 0.0
        cur_ask_run = 0.0

        for obs in observations:
            imb = obs.imbalance
            dt = obs.duration_seconds

            if imb >= threshold:
                state = "BID_DOMINANT"
                bid_dur += dt
                cur_bid_run += dt
                if cur_ask_run > 0.0:
                    ask_runs.append(cur_ask_run)
                    cur_ask_run = 0.0
            elif imb <= -threshold:
                state = "ASK_DOMINANT"
                ask_dur += dt
                cur_ask_run += dt
                if cur_bid_run > 0.0:
                    bid_runs.append(cur_bid_run)
                    cur_bid_run = 0.0
            else:
                state = "NEUTRAL"
                neutral_dur += dt
                if cur_bid_run > 0.0:
                    bid_runs.append(cur_bid_run)
                    cur_bid_run = 0.0
                if cur_ask_run > 0.0:
                    ask_runs.append(cur_ask_run)
                    cur_ask_run = 0.0

            if state == current_state:
                current_run += dt
            else:
                current_state = state
                current_run = dt

        if cur_bid_run > 0.0:
            bid_runs.append(cur_bid_run)
        if cur_ask_run > 0.0:
            ask_runs.append(cur_ask_run)

        bid_p = Decimal(str(round(bid_dur / total_dur, 4)))
        ask_p = Decimal(str(round(ask_dur / total_dur, 4)))
        neutral_p = Decimal("1.0000") - bid_p - ask_p

        return {
            "bid_persistence_ratio": bid_p,
            "ask_persistence_ratio": ask_p,
            "neutral_persistence_ratio": max(neutral_p, Decimal("0.0")),
            "total_valid_duration_seconds": total_dur,
            "current_state": current_state,
            "current_run_duration_seconds": current_run,
            "max_bid_run_seconds": max(bid_runs, default=0.0),
            "max_ask_run_seconds": max(ask_runs, default=0.0),
            "average_bid_run_seconds": (sum(bid_runs) / len(bid_runs)) if bid_runs else 0.0,
            "average_ask_run_seconds": (sum(ask_runs) / len(ask_runs)) if ask_runs else 0.0,
        }

    @staticmethod
    def detect_reversals(
        observations: List[TimeSeriesObservation],
        entry_threshold: Decimal = Decimal("0.20"),
        exit_threshold: Decimal = Decimal("0.05"),
    ) -> List[Dict[str, Any]]:
        """
        Detects threshold-based reversals with hysteresis.
        Transitions tracked: BID_DOMINANT -> ASK_DOMINANT, ASK_DOMINANT -> BID_DOMINANT, or return to NEUTRAL.
        """
        reversals: List[Dict[str, Any]] = []
        if len(observations) < 2:
            return reversals

        current_state = "NEUTRAL"
        prev_imb = observations[0].imbalance

        for i in range(1, len(observations)):
            obs = observations[i]
            cur_imb = obs.imbalance

            new_state = current_state
            if current_state == "NEUTRAL":
                if cur_imb >= entry_threshold:
                    new_state = "BID_DOMINANT"
                elif cur_imb <= -entry_threshold:
                    new_state = "ASK_DOMINANT"
            elif current_state == "BID_DOMINANT":
                if cur_imb <= -entry_threshold:
                    new_state = "ASK_DOMINANT"
                elif cur_imb < exit_threshold:
                    new_state = "NEUTRAL"
            elif current_state == "ASK_DOMINANT":
                if cur_imb >= entry_threshold:
                    new_state = "BID_DOMINANT"
                elif cur_imb > -exit_threshold:
                    new_state = "NEUTRAL"

            if new_state != current_state:
                mag = abs(cur_imb - prev_imb)
                dt = obs.duration_seconds
                rate = (mag / Decimal(str(dt))) if dt > 0.0 else Decimal("0.0")
                reversals.append({
                    "timestamp": obs.timestamp,
                    "previous_state": current_state,
                    "new_state": new_state,
                    "previous_imbalance": prev_imb,
                    "current_imbalance": cur_imb,
                    "reversal_magnitude": mag,
                    "reversal_rate_per_sec": rate,
                    "duration_seconds": dt,
                })
                current_state = new_state

            prev_imb = cur_imb

        return reversals

    @staticmethod
    def classify_regime(imbalance: Decimal) -> str:
        """
        Classifies current displayed-liquidity state using standard thresholds:
        - I >= 0.60: STRONG_BID
        - 0.20 <= I < 0.60: MODERATE_BID
        - -0.20 < I < 0.20: NEUTRAL
        - -0.60 < I <= -0.20: MODERATE_ASK
        - I <= -0.60: STRONG_ASK
        """
        if imbalance >= Decimal("0.60"):
            return "STRONG_BID"
        elif imbalance >= Decimal("0.20"):
            return "MODERATE_BID"
        elif imbalance <= Decimal("-0.60"):
            return "STRONG_ASK"
        elif imbalance <= Decimal("-0.20"):
            return "MODERATE_ASK"
        else:
            return "NEUTRAL"

    @staticmethod
    def compute_historical_zscore(
        current_imbalance: Decimal,
        historical_imbalances: List[Decimal],
    ) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        """
        Computes standard z-score and robust MAD-based z-score against historical distribution.
        """
        if len(historical_imbalances) < 3:
            return None, None

        float_vals = [float(x) for x in historical_imbalances]
        n = len(float_vals)
        mean_val = sum(float_vals) / n
        variance = sum((x - mean_val) ** 2 for x in float_vals) / (n - 1)
        std_val = math.sqrt(variance)

        z_standard = (
            Decimal(str(round((float(current_imbalance) - mean_val) / std_val, 4)))
            if std_val > 1e-6
            else None
        )

        # Robust standardization using median and MAD
        sorted_vals = sorted(float_vals)
        median_val = sorted_vals[n // 2]
        abs_devs = sorted([abs(x - median_val) for x in float_vals])
        mad_val = abs_devs[n // 2]
        robust_denom = 1.4826 * mad_val

        z_robust = (
            Decimal(str(round((float(current_imbalance) - median_val) / robust_denom, 4)))
            if robust_denom > 1e-6
            else None
        )

        return z_standard, z_robust
