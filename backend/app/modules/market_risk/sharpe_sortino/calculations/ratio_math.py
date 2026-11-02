"""
M07.08 Sharpe & Sortino Mathematical Engine.
Implements:
- Annualized rate to effective period rate conversion with day-count & compounding conventions
- Period and annualized Sharpe ratio
- Target shortfall & All-period Downside Deviation (semideviation)
- Period and annualized Sortino ratio
- Zero denominator and degeneracy handling
"""
import math
from typing import Dict, Any, List, Optional
import numpy as np

from backend.app.modules.market_risk.sharpe_sortino.models import (
    SharpeDenominatorPolicy,
    SortinoTargetPolicy,
    SortinoDenominatorPolicy,
    RateConvention,
    DayCountConvention,
    RatioCalculationStatus,
)


def convert_rate_to_period_return(
    annualized_rate: float,
    rate_convention: RateConvention = RateConvention.EFFECTIVE_ANNUAL_RATE,
    day_count: DayCountConvention = DayCountConvention.ACTUAL_365,
    days_in_period: int = 1,
) -> float:
    """
    Converts an annualized interest rate into an effective period return.
    """
    divisor = 360.0 if day_count == DayCountConvention.ACTUAL_360 else 365.0
    tau = float(days_in_period) / divisor

    if rate_convention == RateConvention.EFFECTIVE_ANNUAL_RATE:
        # R_period = (1 + y)^tau - 1
        if 1.0 + annualized_rate <= 0:
            return 0.0
        return float((1.0 + annualized_rate) ** tau - 1.0)

    elif rate_convention == RateConvention.SIMPLE_ANNUAL_RATE:
        # R_period = y * tau
        return float(annualized_rate * tau)

    elif rate_convention == RateConvention.CONTINUOUSLY_COMPOUNDED:
        # R_period = exp(c * tau) - 1
        return float(math.exp(annualized_rate * tau) - 1.0)

    elif rate_convention == RateConvention.NOMINAL_ANNUAL_RATE:
        # Assuming quarterly nominal compounding m=4: (1 + y/4)^(4*tau) - 1
        m = 4.0
        return float((1.0 + annualized_rate / m) ** (m * tau) - 1.0)

    # Default fallback
    return float((1.0 + annualized_rate) ** tau - 1.0)


def calculate_sharpe_ratio(
    returns_portfolio: np.ndarray,
    returns_risk_free: np.ndarray,
    denominator_policy: SharpeDenominatorPolicy = SharpeDenominatorPolicy.PORTFOLIO_RETURN_VOLATILITY,
    annualization_factor: float = 252.0,
    min_observations: int = 5,
) -> Dict[str, Any]:
    """
    Calculates period and annualized Sharpe ratio with statistical diagnostics.
    """
    n = len(returns_portfolio)
    if n < min_observations or len(returns_risk_free) != n:
        return {
            "mean_return": 0.0,
            "mean_risk_free": 0.0,
            "mean_excess_return": 0.0,
            "volatility": 0.0,
            "period_sharpe": None,
            "annualized_sharpe": None,
            "sample_size": n,
            "status": RatioCalculationStatus.INSUFFICIENT_OBSERVATIONS,
        }

    excess_returns = returns_portfolio - returns_risk_free
    mean_rp = float(np.mean(returns_portfolio))
    mean_rf = float(np.mean(returns_risk_free))
    mean_x = float(np.mean(excess_returns))

    if denominator_policy == SharpeDenominatorPolicy.EXCESS_RETURN_VOLATILITY:
        vol = float(np.std(excess_returns, ddof=1))
    else:
        vol = float(np.std(returns_portfolio, ddof=1))

    if vol < 1e-12:
        return {
            "mean_return": mean_rp,
            "mean_risk_free": mean_rf,
            "mean_excess_return": mean_x,
            "volatility": vol,
            "period_sharpe": None,
            "annualized_sharpe": None,
            "sample_size": n,
            "status": RatioCalculationStatus.ZERO_VOLATILITY,
        }

    period_sharpe = mean_x / vol
    ann_factor = math.sqrt(annualization_factor) if annualization_factor > 0 else 1.0
    annualized_sharpe = period_sharpe * ann_factor

    return {
        "mean_return": mean_rp,
        "mean_risk_free": mean_rf,
        "mean_excess_return": mean_x,
        "volatility": vol,
        "period_sharpe": period_sharpe,
        "annualized_sharpe": annualized_sharpe,
        "sample_size": n,
        "status": RatioCalculationStatus.VALID,
    }


def calculate_downside_deviation(
    returns: np.ndarray,
    target_returns: np.ndarray,
    denominator_policy: SortinoDenominatorPolicy = SortinoDenominatorPolicy.ALL_PERIODS_SEMIDEVIATION,
) -> Dict[str, Any]:
    """
    Computes downside shortfalls and downside deviation.
    Default: ALL_PERIODS_SEMIDEVIATION using full sample N in denominator.
    """
    n = len(returns)
    if n == 0:
        return {
            "downside_deviation": 0.0,
            "downside_count": 0,
            "downside_percentage": 0.0,
        }

    # Shortfall d_t = min(0, R_t - T_t)
    diff = returns - target_returns
    shortfalls = np.minimum(0.0, diff)
    downside_count = int(np.sum(shortfalls < 0.0))
    downside_pct = float(downside_count / n * 100.0)

    if denominator_policy == SortinoDenominatorPolicy.BELOW_TARGET_CONDITIONAL_DOWNSIDE_DISPERSION:
        if downside_count == 0:
            dd = 0.0
        else:
            squared_shortfalls = (shortfalls[shortfalls < 0.0]) ** 2
            dd = float(math.sqrt(np.mean(squared_shortfalls)))
    else:
        # Standard Sortino: sqrt( (1/N) * sum(min(0, R_t - T_t)^2) )
        squared_shortfalls = shortfalls ** 2
        dd = float(math.sqrt(np.mean(squared_shortfalls)))

    return {
        "downside_deviation": dd,
        "downside_count": downside_count,
        "downside_percentage": downside_pct,
    }


def calculate_sortino_ratio(
    returns_portfolio: np.ndarray,
    returns_target: np.ndarray,
    denominator_policy: SortinoDenominatorPolicy = SortinoDenominatorPolicy.ALL_PERIODS_SEMIDEVIATION,
    annualization_factor: float = 252.0,
    min_observations: int = 5,
) -> Dict[str, Any]:
    """
    Calculates period and annualized Sortino ratio.
    """
    n = len(returns_portfolio)
    if n < min_observations or len(returns_target) != n:
        return {
            "mean_return": 0.0,
            "target_return": 0.0,
            "mean_excess_over_target": 0.0,
            "downside_deviation": 0.0,
            "period_sortino": None,
            "annualized_sortino": None,
            "sample_size": n,
            "downside_periods_count": 0,
            "downside_percentage": 0.0,
            "status": RatioCalculationStatus.INSUFFICIENT_OBSERVATIONS,
        }

    mean_rp = float(np.mean(returns_portfolio))
    mean_target = float(np.mean(returns_target))
    mean_excess = mean_rp - mean_target

    dd_stats = calculate_downside_deviation(
        returns=returns_portfolio,
        target_returns=returns_target,
        denominator_policy=denominator_policy,
    )
    dd = dd_stats["downside_deviation"]
    downside_count = dd_stats["downside_count"]
    downside_pct = dd_stats["downside_percentage"]

    if dd < 1e-12:
        return {
            "mean_return": mean_rp,
            "target_return": mean_target,
            "mean_excess_over_target": mean_excess,
            "downside_deviation": dd,
            "period_sortino": None,
            "annualized_sortino": None,
            "sample_size": n,
            "downside_periods_count": downside_count,
            "downside_percentage": downside_pct,
            "status": RatioCalculationStatus.ZERO_DOWNSIDE_DEVIATION,
        }

    period_sortino = mean_excess / dd
    ann_factor = math.sqrt(annualization_factor) if annualization_factor > 0 else 1.0
    annualized_sortino = period_sortino * ann_factor

    return {
        "mean_return": mean_rp,
        "target_return": mean_target,
        "mean_excess_over_target": mean_excess,
        "downside_deviation": dd,
        "period_sortino": period_sortino,
        "annualized_sortino": annualized_sortino,
        "sample_size": n,
        "downside_periods_count": downside_count,
        "downside_percentage": downside_pct,
        "status": RatioCalculationStatus.VALID,
    }
