"""
Module M07.01: Statistical Realized Volatility Calculations.
Pure deterministic mathematical formulas using Decimal with stable two-pass variance,
rolling statistics, annualization, and trend regression.
"""
from decimal import Decimal, ROUND_HALF_UP
import math
from typing import List, Tuple, Optional
from backend.app.modules.market_risk.historical_volatility.models import (
    ReturnType,
    StatisticalEstimator,
    VolatilityTrendClassification,
    VolatilityWindowComparisonLabel,
)

PRECISION_EIGHT = Decimal("0.00000001")
PRECISION_SIX = Decimal("0.000001")


def calculate_return(
    start_price: Decimal,
    end_price: Decimal,
    return_type: ReturnType = ReturnType.LOGARITHMIC,
) -> Decimal:
    """
    Calculate simple or logarithmic return between two price points.
    """
    if start_price <= Decimal("0.0") or end_price <= Decimal("0.0"):
        raise ValueError(f"Prices must be strictly positive: start={start_price}, end={end_price}")
    
    if return_type == ReturnType.LOGARITHMIC:
        # ln(P_t / P_{t-1})
        val = math.log(float(end_price) / float(start_price))
        return Decimal(str(val)).quantize(PRECISION_EIGHT, rounding=ROUND_HALF_UP)
    else:
        # (P_t / P_{t-1}) - 1
        val = (end_price / start_price) - Decimal("1.0")
        return val.quantize(PRECISION_EIGHT, rounding=ROUND_HALF_UP)


def calculate_sample_variance_and_std_dev(
    returns: List[Decimal],
    estimator: StatisticalEstimator = StatisticalEstimator.SAMPLE_STD_DEV,
) -> Tuple[Decimal, Decimal, Decimal]:
    """
    Two-pass numerically stable variance and standard deviation algorithm.
    Returns: (mean_return, variance, std_dev)
    """
    n = len(returns)
    if n < 2 and estimator == StatisticalEstimator.SAMPLE_STD_DEV:
        return Decimal("0.0"), Decimal("0.0"), Decimal("0.0")
    if n < 1:
        return Decimal("0.0"), Decimal("0.0"), Decimal("0.0")

    # Pass 1: Mean
    sum_ret = sum(returns)
    mean = sum_ret / Decimal(str(n))

    # Pass 2: Sum of squared differences
    sum_sq_diff = sum((r - mean) ** 2 for r in returns)

    degrees_of_freedom = n - 1 if estimator == StatisticalEstimator.SAMPLE_STD_DEV else n
    if degrees_of_freedom <= 0:
        return mean.quantize(PRECISION_EIGHT, rounding=ROUND_HALF_UP), Decimal("0.0"), Decimal("0.0")

    variance = sum_sq_diff / Decimal(str(degrees_of_freedom))
    std_dev = Decimal(str(math.sqrt(float(variance))))

    return (
        mean.quantize(PRECISION_EIGHT, rounding=ROUND_HALF_UP),
        variance.quantize(PRECISION_EIGHT, rounding=ROUND_HALF_UP),
        std_dev.quantize(PRECISION_EIGHT, rounding=ROUND_HALF_UP),
    )


def annualize_volatility(
    period_std_dev: Decimal,
    periods_per_year: int,
) -> Tuple[Decimal, Decimal]:
    """
    Annualize per-period standard deviation:
    sigma_annual = sigma_period * sqrt(periods_per_year)
    Returns: (annualization_factor, annualized_volatility)
    """
    if periods_per_year <= 0:
        raise ValueError(f"Periods per year must be positive: {periods_per_year}")

    factor = Decimal(str(math.sqrt(float(periods_per_year)))).quantize(
        PRECISION_SIX, rounding=ROUND_HALF_UP
    )
    ann_vol = (period_std_dev * factor).quantize(PRECISION_EIGHT, rounding=ROUND_HALF_UP)
    return factor, ann_vol


def calculate_volatility_trend_slope(
    volatilities: List[Decimal],
) -> Tuple[Decimal, Decimal]:
    """
    Ordinary least squares linear regression on rolling volatility series:
    vol_t = alpha + beta * t
    Returns: (alpha, beta_slope)
    """
    n = len(volatilities)
    if n < 2:
        return Decimal("0.0"), Decimal("0.0")

    # t = 1, 2, ..., n
    t_vals = [Decimal(str(i + 1)) for i in range(n)]
    mean_t = sum(t_vals) / Decimal(str(n))
    mean_v = sum(volatilities) / Decimal(str(n))

    numerator = sum((t_vals[i] - mean_t) * (volatilities[i] - mean_v) for i in range(n))
    denominator = sum((t_vals[i] - mean_t) ** 2 for i in range(n))

    if denominator == Decimal("0.0"):
        return mean_v.quantize(PRECISION_EIGHT, rounding=ROUND_HALF_UP), Decimal("0.0")

    beta = (numerator / denominator).quantize(PRECISION_EIGHT, rounding=ROUND_HALF_UP)
    alpha = (mean_v - (beta * mean_t)).quantize(PRECISION_EIGHT, rounding=ROUND_HALF_UP)

    return alpha, beta


def classify_volatility_trend(
    current_vol: Decimal,
    prior_vol: Optional[Decimal],
    slope: Optional[Decimal] = None,
    threshold_pct: Decimal = Decimal("0.05"),  # 5% relative change
) -> VolatilityTrendClassification:
    """
    Classify volatility trend based on recent changes and slope.
    """
    if prior_vol is None or prior_vol <= Decimal("0.0"):
        return VolatilityTrendClassification.INSUFFICIENT_HISTORY

    pct_change = (current_vol - prior_vol) / prior_vol

    if slope is not None and slope > Decimal("0.0001"):
        return VolatilityTrendClassification.VOLATILITY_INCREASING
    elif slope is not None and slope < Decimal("-0.0001"):
        return VolatilityTrendClassification.VOLATILITY_DECREASING
    elif pct_change > threshold_pct:
        return VolatilityTrendClassification.VOLATILITY_INCREASING
    elif pct_change < -threshold_pct:
        return VolatilityTrendClassification.VOLATILITY_DECREASING
    else:
        return VolatilityTrendClassification.VOLATILITY_STABLE


def compare_volatility_horizons(
    short_vol: Decimal,
    long_vol: Decimal,
    tolerance: Decimal = Decimal("0.01"),  # 1% difference
) -> VolatilityWindowComparisonLabel:
    """
    Compare short-term vs long-term annualized volatility.
    """
    spread = short_vol - long_vol
    if spread > tolerance:
        return VolatilityWindowComparisonLabel.SHORT_TERM_HIGHER
    elif spread < -tolerance:
        return VolatilityWindowComparisonLabel.SHORT_TERM_LOWER
    else:
        return VolatilityWindowComparisonLabel.HORIZONS_SIMILAR
