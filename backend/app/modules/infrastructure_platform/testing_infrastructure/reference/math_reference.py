"""
Institutional Mathematical Reference Models for M15.10 Testing Infrastructure.
These calculations are derived independently by hand / analytical formulas to serve
as immutable truth oracles for testing financial and quantitative modules.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Tuple
import math
import numpy as np


class FinancialMathReference:
    """Independent reference implementations for core quantitative risk metrics."""

    @staticmethod
    def calculate_gross_and_net_exposure(positions: List[Dict[str, Any]]) -> Dict[str, Decimal]:
        """
        Gross Exposure = Sum(|market_value|)
        Net Exposure = Sum(market_value)
        Long Exposure = Sum(market_value where market_value > 0)
        Short Exposure = Sum(|market_value| where market_value < 0)
        """
        long_exp = Decimal("0.0")
        short_exp = Decimal("0.0")

        for pos in positions:
            mv = Decimal(str(pos["market_value"]))
            if mv > Decimal("0.0"):
                long_exp += mv
            else:
                short_exp += abs(mv)

        gross_exp = long_exp + short_exp
        net_exp = long_exp - short_exp

        return {
            "long_exposure": long_exp,
            "short_exposure": short_exp,
            "gross_exposure": gross_exp,
            "net_exposure": net_exp,
        }

    @staticmethod
    def calculate_sample_volatility(returns: List[float], annualization_factor: float = 252.0) -> float:
        """
        Independent sample standard deviation with Bessel correction (N - 1), annualized:
        vol = sqrt(annualization_factor * (1 / (N - 1)) * sum((r_i - mean)^2))
        """
        n = len(returns)
        if n < 2:
            return 0.0
        mean = sum(returns) / n
        sum_sq_diff = sum((r - mean) ** 2 for r in returns)
        sample_var = sum_sq_diff / (n - 1)
        return math.sqrt(sample_var * annualization_factor)

    @staticmethod
    def calculate_historical_var(losses: List[float], confidence_level: float = 0.95) -> float:
        """
        Historical VaR:
        Given an array of loss amounts (positive = loss), sort descending.
        VaR_alpha = loss at rank floor(N * (1 - alpha)) or percentile (100 * alpha).
        Formula: numpy percentile with linear interpolation or standard order statistic.
        """
        sorted_losses = sorted(losses)
        n = len(sorted_losses)
        idx = int(math.floor(confidence_level * n))
        idx = min(idx, n - 1)
        return float(sorted_losses[idx])

    @staticmethod
    def calculate_expected_shortfall(losses: List[float], confidence_level: float = 0.95) -> float:
        """
        Expected Shortfall (CVaR):
        Mean of losses exceeding the VaR at alpha.
        """
        var_val = FinancialMathReference.calculate_historical_var(losses, confidence_level)
        tail_losses = [l for l in losses if l >= var_val]
        if not tail_losses:
            return var_val
        return float(sum(tail_losses) / len(tail_losses))

    @staticmethod
    def calculate_max_drawdown(nav_series: List[float]) -> Tuple[float, int, int]:
        """
        Max Drawdown = max_t (Peak_t - NAV_t) / Peak_t
        Returns (max_drawdown_fraction, peak_index, trough_index)
        """
        if not nav_series:
            return 0.0, 0, 0

        peak = nav_series[0]
        peak_idx = 0
        max_dd = 0.0
        m_peak_idx = 0
        m_trough_idx = 0

        for idx, val in enumerate(nav_series):
            if val > peak:
                peak = val
                peak_idx = idx
            dd = (peak - val) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
                m_peak_idx = peak_idx
                m_trough_idx = idx

        return max_dd, m_peak_idx, m_trough_idx

    @staticmethod
    def calculate_portfolio_variance_2asset(w1: float, w2: float, sigma1: float, sigma2: float, rho: float) -> float:
        """
        sigma_p^2 = w1^2*s1^2 + w2^2*s2^2 + 2*w1*w2*s1*s2*rho
        """
        return (w1**2 * sigma1**2) + (w2**2 * sigma2**2) + (2 * w1 * w2 * sigma1 * sigma2 * rho)

    @staticmethod
    def calculate_bid_ask_spread_metrics(best_bid: float, best_ask: float) -> Dict[str, float]:
        """
        absolute_spread = ask - bid
        mid_price = (ask + bid) / 2
        relative_spread_bps = (absolute_spread / mid_price) * 10,000
        """
        if best_ask <= 0 or best_bid <= 0 or best_ask < best_bid:
            raise ValueError("Invalid order book top levels")
        abs_spread = best_ask - best_bid
        mid_price = (best_ask + best_bid) / 2.0
        spread_bps = (abs_spread / mid_price) * 10000.0
        return {
            "absolute_spread": abs_spread,
            "mid_price": mid_price,
            "spread_bps": spread_bps,
        }

    @staticmethod
    def calculate_order_book_imbalance(bid_qty: float, ask_qty: float) -> float:
        """
        imbalance = (bid_qty - ask_qty) / (bid_qty + ask_qty)
        Bound in [-1.0, 1.0]
        """
        total = bid_qty + ask_qty
        if total == 0:
            return 0.0
        return (bid_qty - ask_qty) / total
