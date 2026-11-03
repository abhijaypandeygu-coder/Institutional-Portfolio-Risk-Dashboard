"""
Calculations engine for M09.05 Slippage Estimation.

Implements institutional execution-quality analytics:
1. Benchmark price definition and validation (Arrival Midpoint, Decision, Arrival, Best Bid/Ask, Custom).
2. VWAP and executed value calculation over eligible fills.
3. Realized slippage calculation:
   - Price units: Slip_price = S * (VWAP_exec - P_ref)
   - Basis points: Slip_bps = S * ((VWAP_exec - P_ref) / P_ref) * 10,000
   - Monetary value: Slip_money = S * (VWAP_exec - P_ref) * Q_filled * Multiplier
   Where S = +1 for BUY, -1 for SELL.
4. Additive attribution decomposition:
   Total Deviation = Market Movement + Execution Concession vs Midpoint
   Execution Concession vs Midpoint = Spread Crossing + Residual Execution Concession
   Exact additive reconciliation: Total Price Deviation == Market Movement + Spread Crossing + Residual Execution.
5. Opportunity cost and Implementation Shortfall for unexecuted quantities.
6. Calibration metrics: ME, MAE, RMSE, prediction interval coverage, t-stat.
"""

from decimal import Decimal, ROUND_HALF_UP
import math
from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel, Field


class FillExecutionData(BaseModel):
    fill_id: str
    fill_timestamp: str
    price: Decimal
    quantity: Decimal
    venue: Optional[str] = "DEFAULT"
    bid_at_fill: Optional[Decimal] = None
    ask_at_fill: Optional[Decimal] = None
    midpoint_at_fill: Optional[Decimal] = None
    fees: Decimal = Decimal("0.0")


class FillAttributionResult(BaseModel):
    fill_id: str
    quantity: Decimal
    fill_price: Decimal
    multiplier: Decimal
    side: str  # BUY or SELL
    reference_price: Decimal
    fill_slippage_price: Decimal
    fill_slippage_bps: Decimal
    fill_slippage_money: Decimal
    
    # Attribution
    market_movement_price: Decimal
    market_movement_bps: Decimal
    market_movement_money: Decimal
    
    spread_crossing_price: Decimal
    spread_crossing_bps: Decimal
    spread_crossing_money: Decimal
    
    residual_execution_price: Decimal
    residual_execution_bps: Decimal
    residual_execution_money: Decimal
    
    total_reconciled: bool
    reconciliation_discrepancy: Decimal


class SlippageExecutionSummaryResult(BaseModel):
    side: str
    multiplier: Decimal
    total_requested_quantity: Decimal
    total_filled_quantity: Decimal
    unfilled_quantity: Decimal
    fill_rate_pct: Decimal
    
    benchmark_price: Decimal
    benchmark_type: str
    
    vwap_execution_price: Decimal
    gross_executed_notional: Decimal
    
    # Realized Slippage
    slippage_price_units: Decimal
    slippage_bps: Decimal
    slippage_monetary_amount: Decimal
    is_favorable: bool  # True if slippage is negative (price improvement)
    
    # Additive Attribution Totals
    total_market_movement_price: Decimal
    total_market_movement_bps: Decimal
    total_market_movement_money: Decimal
    
    total_spread_crossing_price: Decimal
    total_spread_crossing_bps: Decimal
    total_spread_crossing_money: Decimal
    
    total_residual_execution_price: Decimal
    total_residual_execution_bps: Decimal
    total_residual_execution_money: Decimal
    
    attribution_reconciled: bool
    
    # Fees and All-in Cost
    total_explicit_fees: Decimal
    total_all_in_cost: Decimal
    
    # Opportunity Cost & Implementation Shortfall (if terminal price provided)
    terminal_price: Optional[Decimal] = None
    opportunity_cost_price_units: Optional[Decimal] = None
    opportunity_cost_bps: Optional[Decimal] = None
    opportunity_cost_monetary_amount: Optional[Decimal] = None
    implementation_shortfall_monetary_amount: Optional[Decimal] = None


class CalibrationMetricsResult(BaseModel):
    observation_count: int
    mean_error: Decimal
    mean_absolute_error: Decimal
    root_mean_squared_error: Decimal
    t_statistic: Optional[Decimal] = None
    p_value_approx: Optional[Decimal] = None
    is_bias_significant: bool = False
    in_interval_count: int
    interval_coverage_pct: Decimal


class SlippageMath:
    """Mathematical engine for execution slippage calculations."""

    @staticmethod
    def get_side_sign(side: str) -> Decimal:
        """
        Return +1 for BUY (higher price is adverse), -1 for SELL (lower price is adverse).
        """
        s = side.strip().upper()
        if s in ("BUY", "B", "BID"):
            return Decimal("1.0")
        elif s in ("SELL", "S", "ASK"):
            return Decimal("-1.0")
        else:
            raise ValueError(f"Invalid side '{side}'. Must be BUY or SELL.")

    @staticmethod
    def calculate_vwap(fills: List[FillExecutionData]) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Calculates execution VWAP:
        VWAP = sum(P_j * Q_j) / sum(Q_j)
        Returns (vwap, total_filled_qty, gross_notional).
        """
        if not fills:
            return Decimal("0.0"), Decimal("0.0"), Decimal("0.0")

        total_value = Decimal("0.0")
        total_qty = Decimal("0.0")

        for f in fills:
            if f.quantity < Decimal("0.0"):
                raise ValueError("Fill quantity cannot be negative.")
            total_value += f.price * f.quantity
            total_qty += f.quantity

        if total_qty == Decimal("0.0"):
            return Decimal("0.0"), Decimal("0.0"), Decimal("0.0")

        vwap = total_value / total_qty
        return vwap, total_qty, total_value

    @staticmethod
    def calculate_realized_slippage(
        side: str,
        benchmark_price: Decimal,
        vwap_exec: Decimal,
        filled_qty: Decimal,
        multiplier: Decimal = Decimal("1.0"),
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Calculates realized slippage:
        Slip_price = S * (VWAP_exec - P_ref)
        Slip_bps = S * ((VWAP_exec - P_ref) / P_ref) * 10,000
        Slip_money = S * (VWAP_exec - P_ref) * Q_filled * Multiplier
        """
        if benchmark_price <= Decimal("0.0"):
            raise ValueError("Benchmark price must be positive.")

        s = SlippageMath.get_side_sign(side)
        price_diff = vwap_exec - benchmark_price
        slip_price = s * price_diff
        slip_bps = s * (price_diff / benchmark_price) * Decimal("10000.0")
        slip_money = s * price_diff * filled_qty * multiplier

        return slip_price, slip_bps, slip_money

    @staticmethod
    def decompose_fill_attribution(
        side: str,
        benchmark_price: Decimal,
        fill: FillExecutionData,
        multiplier: Decimal = Decimal("1.0"),
    ) -> FillAttributionResult:
        """
        Performs exact additive attribution decomposition for a single fill:
        Total Price Deviation = S * (P_j - P_ref)
        Market Movement = S * (M_j - P_ref)
        Spread Crossing = (A_j - M_j) if BUY else (M_j - B_j)
        Residual Execution = S * (P_j - M_j) - Spread Crossing
        
        Total Deviation == Market Movement + Spread Crossing + Residual Execution
        """
        if benchmark_price <= Decimal("0.0"):
            raise ValueError("Benchmark price must be positive.")

        s = SlippageMath.get_side_sign(side)
        p_j = fill.price
        q_j = fill.quantity

        # Midpoint resolution: if provided, use it; otherwise fallback to (bid+ask)/2 if available, else P_j
        if fill.midpoint_at_fill is not None:
            m_j = fill.midpoint_at_fill
        elif fill.bid_at_fill is not None and fill.ask_at_fill is not None:
            m_j = (fill.bid_at_fill + fill.ask_at_fill) / Decimal("2.0")
        else:
            m_j = p_j

        # Best quote fallback
        b_j = fill.bid_at_fill if fill.bid_at_fill is not None else m_j
        a_j = fill.ask_at_fill if fill.ask_at_fill is not None else m_j

        # 1. Total Price Slippage for this fill
        slip_price = s * (p_j - benchmark_price)
        slip_bps = s * ((p_j - benchmark_price) / benchmark_price) * Decimal("10000.0")
        slip_money = slip_price * q_j * multiplier

        # 2. Market Movement: deviation of midpoint from benchmark
        mkt_price = s * (m_j - benchmark_price)
        mkt_bps = s * ((m_j - benchmark_price) / benchmark_price) * Decimal("10000.0")
        mkt_money = mkt_price * q_j * multiplier

        # 3. Spread Crossing: half-spread component at fill time
        if s > 0:  # BUY
            spread_price = a_j - m_j
        else:  # SELL
            spread_price = m_j - b_j
        spread_bps = (spread_price / benchmark_price) * Decimal("10000.0")
        spread_money = spread_price * q_j * multiplier

        # 4. Residual Execution Concession: execution vs midpoint minus spread crossing
        # S * (P_j - M_j) - Spread Crossing
        res_price = (s * (p_j - m_j)) - spread_price
        res_bps = (res_price / benchmark_price) * Decimal("10000.0")
        res_money = res_price * q_j * multiplier

        # Exact additive check:
        reconciled_sum = mkt_price + spread_price + res_price
        discrepancy = abs(slip_price - reconciled_sum)
        total_reconciled = discrepancy < Decimal("1e-7")

        return FillAttributionResult(
            fill_id=fill.fill_id,
            quantity=q_j,
            fill_price=p_j,
            multiplier=multiplier,
            side=side.upper(),
            reference_price=benchmark_price,
            fill_slippage_price=slip_price,
            fill_slippage_bps=slip_bps,
            fill_slippage_money=slip_money,
            market_movement_price=mkt_price,
            market_movement_bps=mkt_bps,
            market_movement_money=mkt_money,
            spread_crossing_price=spread_price,
            spread_crossing_bps=spread_bps,
            spread_crossing_money=spread_money,
            residual_execution_price=res_price,
            residual_execution_bps=res_bps,
            residual_execution_money=res_money,
            total_reconciled=total_reconciled,
            reconciliation_discrepancy=discrepancy,
        )

    @staticmethod
    def calculate_opportunity_cost(
        side: str,
        benchmark_price: Decimal,
        terminal_price: Decimal,
        unfilled_quantity: Decimal,
        multiplier: Decimal = Decimal("1.0"),
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Calculates opportunity cost for unfilled/cancelled quantity:
        OppCost_price = S * (P_terminal - P_ref)
        OppCost_bps = S * ((P_terminal - P_ref) / P_ref) * 10,000
        OppCost_money = S * (P_terminal - P_ref) * Q_unfilled * Multiplier
        """
        if benchmark_price <= Decimal("0.0"):
            raise ValueError("Benchmark price must be positive.")
        if unfilled_quantity < Decimal("0.0"):
            raise ValueError("Unfilled quantity cannot be negative.")

        s = SlippageMath.get_side_sign(side)
        price_diff = terminal_price - benchmark_price
        opp_price = s * price_diff
        opp_bps = s * (price_diff / benchmark_price) * Decimal("10000.0")
        opp_money = s * price_diff * unfilled_quantity * multiplier

        return opp_price, opp_bps, opp_money

    @staticmethod
    def calculate_execution_summary(
        side: str,
        requested_quantity: Decimal,
        benchmark_price: Decimal,
        benchmark_type: str,
        fills: List[FillExecutionData],
        terminal_price: Optional[Decimal] = None,
        multiplier: Decimal = Decimal("1.0"),
    ) -> Tuple[SlippageExecutionSummaryResult, List[FillAttributionResult]]:
        """
        Aggregates fills, runs realized slippage, executes attribution decomposition across
        all fills, computes opportunity cost, and verifies portfolio-level additive reconciliation.
        """
        s = SlippageMath.get_side_sign(side)
        vwap, total_filled_qty, gross_notional = SlippageMath.calculate_vwap(fills)
        unfilled_qty = max(Decimal("0.0"), requested_quantity - total_filled_qty)
        fill_rate_pct = (
            (total_filled_qty / requested_quantity) * Decimal("100.0")
            if requested_quantity > Decimal("0.0")
            else Decimal("0.0")
        )

        # Realized Slippage
        if total_filled_qty > Decimal("0.0"):
            slip_price, slip_bps, slip_money = SlippageMath.calculate_realized_slippage(
                side=side,
                benchmark_price=benchmark_price,
                vwap_exec=vwap,
                filled_qty=total_filled_qty,
                multiplier=multiplier,
            )
        else:
            slip_price, slip_bps, slip_money = Decimal("0.0"), Decimal("0.0"), Decimal("0.0")

        # Fills attribution
        fill_attributions: List[FillAttributionResult] = []
        tot_mkt_money = Decimal("0.0")
        tot_spread_money = Decimal("0.0")
        tot_res_money = Decimal("0.0")
        total_fees = Decimal("0.0")

        for f in fills:
            attr = SlippageMath.decompose_fill_attribution(
                side=side,
                benchmark_price=benchmark_price,
                fill=f,
                multiplier=multiplier,
            )
            fill_attributions.append(attr)
            tot_mkt_money += attr.market_movement_money
            tot_spread_money += attr.spread_crossing_money
            tot_res_money += attr.residual_execution_money
            total_fees += f.fees

        # Calculate weighted price and bps components across executed quantity
        if total_filled_qty > Decimal("0.0"):
            denom = total_filled_qty * multiplier
            tot_mkt_price = tot_mkt_money / denom
            tot_spread_price = tot_spread_money / denom
            tot_res_price = tot_res_money / denom

            tot_mkt_bps = (tot_mkt_price / benchmark_price) * Decimal("10000.0")
            tot_spread_bps = (tot_spread_price / benchmark_price) * Decimal("10000.0")
            tot_res_bps = (tot_res_price / benchmark_price) * Decimal("10000.0")
        else:
            tot_mkt_price = Decimal("0.0")
            tot_spread_price = Decimal("0.0")
            tot_res_price = Decimal("0.0")
            tot_mkt_bps = Decimal("0.0")
            tot_spread_bps = Decimal("0.0")
            tot_res_bps = Decimal("0.0")

        # Attribution check: tot_mkt_money + tot_spread_money + tot_res_money == slip_money
        attr_sum = tot_mkt_money + tot_spread_money + tot_res_money
        attr_reconciled = abs(slip_money - attr_sum) < Decimal("0.01")

        # Opportunity cost
        opp_price: Optional[Decimal] = None
        opp_bps: Optional[Decimal] = None
        opp_money: Optional[Decimal] = None
        is_money: Optional[Decimal] = None

        if terminal_price is not None and unfilled_qty > Decimal("0.0"):
            opp_price, opp_bps, opp_money = SlippageMath.calculate_opportunity_cost(
                side=side,
                benchmark_price=benchmark_price,
                terminal_price=terminal_price,
                unfilled_quantity=unfilled_qty,
                multiplier=multiplier,
            )
            # Implementation Shortfall = Executed Monetary Slippage + Opportunity Cost + Fees
            is_money = slip_money + opp_money + total_fees
        elif terminal_price is not None and unfilled_qty == Decimal("0.0"):
            opp_price = Decimal("0.0")
            opp_bps = Decimal("0.0")
            opp_money = Decimal("0.0")
            is_money = slip_money + total_fees

        total_all_in = slip_money + total_fees

        summary = SlippageExecutionSummaryResult(
            side=side.upper(),
            multiplier=multiplier,
            total_requested_quantity=requested_quantity,
            total_filled_quantity=total_filled_qty,
            unfilled_quantity=unfilled_qty,
            fill_rate_pct=fill_rate_pct,
            benchmark_price=benchmark_price,
            benchmark_type=benchmark_type,
            vwap_execution_price=vwap,
            gross_executed_notional=gross_notional,
            slippage_price_units=slip_price,
            slippage_bps=slip_bps,
            slippage_monetary_amount=slip_money,
            is_favorable=(slip_money < Decimal("0.0")),
            total_market_movement_price=tot_mkt_price,
            total_market_movement_bps=tot_mkt_bps,
            total_market_movement_money=tot_mkt_money,
            total_spread_crossing_price=tot_spread_price,
            total_spread_crossing_bps=tot_spread_bps,
            total_spread_crossing_money=tot_spread_money,
            total_residual_execution_price=tot_res_price,
            total_residual_execution_bps=tot_res_bps,
            total_residual_execution_money=tot_res_money,
            attribution_reconciled=attr_reconciled,
            total_explicit_fees=total_fees,
            total_all_in_cost=total_all_in,
            terminal_price=terminal_price,
            opportunity_cost_price_units=opp_price,
            opportunity_cost_bps=opp_bps,
            opportunity_cost_monetary_amount=opp_money,
            implementation_shortfall_monetary_amount=is_money,
        )

        return summary, fill_attributions

    @staticmethod
    def calculate_calibration_metrics(
        observations: List[Tuple[Decimal, Decimal, Optional[Decimal], Optional[Decimal]]]
    ) -> CalibrationMetricsResult:
        """
        Computes calibration tracking metrics between estimated and realized slippage:
        observations: List of (estimated_bps, realized_bps, lower_bound_bps, upper_bound_bps)
        
        Metrics:
        - Mean Error (ME / Bias): sum(estimated - realized) / N
        - Mean Absolute Error (MAE): sum(|estimated - realized|) / N
        - Root Mean Squared Error (RMSE): sqrt(sum((estimated - realized)^2) / N)
        - t-statistic: ME / (s / sqrt(N))
        - Prediction Interval Coverage: fraction of realized slippage falling within [lower, upper]
        """
        n = len(observations)
        if n == 0:
            return CalibrationMetricsResult(
                observation_count=0,
                mean_error=Decimal("0.0"),
                mean_absolute_error=Decimal("0.0"),
                root_mean_squared_error=Decimal("0.0"),
                t_statistic=None,
                p_value_approx=None,
                is_bias_significant=False,
                in_interval_count=0,
                interval_coverage_pct=Decimal("0.0"),
            )

        errors = []
        abs_errors = []
        sq_errors = []
        in_interval_cnt = 0
        interval_eval_cnt = 0

        for est, real, low, upp in observations:
            err = est - real
            errors.append(err)
            abs_errors.append(abs(err))
            sq_errors.append(err * err)

            if low is not None and upp is not None:
                interval_eval_cnt += 1
                if low <= real <= upp:
                    in_interval_cnt += 1

        me = sum(errors) / Decimal(str(n))
        mae = sum(abs_errors) / Decimal(str(n))
        rmse = Decimal(str(math.sqrt(float(sum(sq_errors) / Decimal(str(n))))))

        # t-statistic for bias
        t_stat: Optional[Decimal] = None
        p_val: Optional[Decimal] = None
        is_sig = False

        if n > 1:
            var_err = sum((e - me) ** 2 for e in errors) / Decimal(str(n - 1))
            std_err = Decimal(str(math.sqrt(float(var_err))))
            if std_err > Decimal("0.0"):
                se_mean = std_err / Decimal(str(math.sqrt(n)))
                t_val = me / se_mean
                t_stat = t_val
                # Approximation of 2-tailed p-value for large N or standard normal
                # abs(t) >= 1.96 => p <= 0.05
                is_sig = abs(t_val) >= Decimal("1.96")
                # rough p-value approximation via erf
                p_val = Decimal(str(math.erfc(float(abs(t_val)) / math.sqrt(2))))

        cov_pct = (
            (Decimal(str(in_interval_cnt)) / Decimal(str(interval_eval_cnt))) * Decimal("100.0")
            if interval_eval_cnt > 0
            else Decimal("0.0")
        )

        return CalibrationMetricsResult(
            observation_count=n,
            mean_error=me,
            mean_absolute_error=mae,
            root_mean_squared_error=rmse,
            t_statistic=t_stat,
            p_value_approx=p_val,
            is_bias_significant=is_sig,
            in_interval_count=in_interval_cnt,
            interval_coverage_pct=cov_pct,
        )

