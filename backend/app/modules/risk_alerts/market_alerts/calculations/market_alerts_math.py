"""
Mathematical calculations and statistical routines for M12.02 Market Alerts.

Includes:
1. Abnormal price movement (absolute, percentage, return, direction classification).
2. Historical price deviation (returns, mean, sample stdev, Z-score, empirical percentile).
3. Market band calculations (analytical percentage bands, volatility-scaled bands, approach/breach state).
4. Short-horizon realized volatility (interval returns, RV_t, annualized RV, baseline comparison, spike ratio).
5. Market-wide index return, advance/decline ratio, and market stress breadth calculation.
6. Portfolio impact directional classification.
7. Event fingerprint / idempotency key generation.
"""

from decimal import Decimal, ROUND_HALF_UP
import math
from typing import List, Optional, Tuple, Dict, Any


def calculate_price_movement(
    current_price: Decimal,
    reference_price: Decimal,
) -> Tuple[Decimal, Decimal, str]:
    """
    Calculate absolute movement Delta P and percentage movement R_t.
    Delta P = P_t - P_{t-h}
    R_t = ((P_t - P_{t-h}) / P_{t-h}) * 100

    Direction: UPWARD, DOWNWARD, NO_DIRECTION, UNAVAILABLE
    """
    if reference_price <= Decimal("0"):
        return Decimal("0"), Decimal("0"), "UNAVAILABLE"
    
    delta_p = current_price - reference_price
    pct_change = (delta_p / reference_price) * Decimal("100")
    
    if delta_p > Decimal("0"):
        direction = "UPWARD"
    elif delta_p < Decimal("0"):
        direction = "DOWNWARD"
    else:
        direction = "NO_DIRECTION"
        
    return delta_p, pct_change, direction


def calculate_historical_deviation(
    observed_return_pct: Decimal,
    historical_returns_pct: List[Decimal],
) -> Tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
    """
    Calculate historical mean return mu_r, sample standard deviation sigma_r,
    and standardized deviation score Z_t = (r_t - mu_r) / sigma_r.
    Also returns the empirical percentile (0.0 to 100.0) of the observed absolute return.
    """
    if not historical_returns_pct or len(historical_returns_pct) < 2:
        return None, None, None

    n = len(historical_returns_pct)
    float_returns = [float(r) for r in historical_returns_pct]
    obs = float(observed_return_pct)

    mean_r = sum(float_returns) / n
    variance = sum((r - mean_r) ** 2 for r in float_returns) / (n - 1)
    
    if variance <= 1e-12:
        stdev_r = 0.0
        z_score = None
    else:
        stdev_r = math.sqrt(variance)
        z_score = Decimal(str(round((obs - mean_r) / stdev_r, 4)))

    # Empirical percentile of absolute return
    abs_obs = abs(obs)
    count_less = sum(1 for r in float_returns if abs(r) <= abs_obs)
    percentile = Decimal(str(round((count_less / n) * 100.0, 2)))

    stdev_dec = Decimal(str(round(stdev_r, 6)))
    return z_score, percentile, stdev_dec


def calculate_analytical_bands(
    reference_price: Decimal,
    band_pct: Optional[Decimal] = None,
    volatility: Optional[Decimal] = None,
    multiplier_k: Decimal = Decimal("2.0"),
) -> Tuple[Decimal, Decimal]:
    """
    Calculates upper and lower analytical bands.
    Fixed percentage:
        P_upper = P_ref * (1 + b)
        P_lower = P_ref * (1 - b)
    Volatility-scaled:
        P_upper = P_ref * exp(k * sigma_h)
        P_lower = P_ref * exp(-k * sigma_h)
    """
    if reference_price <= Decimal("0"):
        return Decimal("0"), Decimal("0")

    if volatility is not None and volatility > Decimal("0"):
        sigma_float = float(volatility)
        k_float = float(multiplier_k)
        ref_float = float(reference_price)
        upper = Decimal(str(round(ref_float * math.exp(k_float * sigma_float), 4)))
        lower = Decimal(str(round(ref_float * math.exp(-k_float * sigma_float), 4)))
        return upper, lower
    elif band_pct is not None and band_pct > Decimal("0"):
        b = band_pct / Decimal("100") if band_pct > Decimal("1") else band_pct
        upper = reference_price * (Decimal("1") + b)
        lower = reference_price * (Decimal("1") - b)
        return upper.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), lower.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    else:
        return reference_price, reference_price


def evaluate_band_state(
    current_price: Decimal,
    upper_band: Decimal,
    lower_band: Decimal,
    approach_threshold_pct: Decimal = Decimal("1.0"),
) -> str:
    """
    Evaluate band approach and breach states:
    - BREACHED_UPPER
    - BREACHED_LOWER
    - APPROACHING_UPPER (within approach_threshold_pct of upper_band)
    - APPROACHING_LOWER (within approach_threshold_pct of lower_band)
    - NORMAL
    - UNAVAILABLE
    """
    if current_price <= Decimal("0") or upper_band <= Decimal("0") or lower_band <= Decimal("0"):
        return "UNAVAILABLE"

    if current_price >= upper_band:
        return "BREACHED_UPPER"
    if current_price <= lower_band:
        return "BREACHED_LOWER"

    app_factor = approach_threshold_pct / Decimal("100")
    if current_price >= upper_band * (Decimal("1") - app_factor):
        return "APPROACHING_UPPER"
    if current_price <= lower_band * (Decimal("1") + app_factor):
        return "APPROACHING_LOWER"

    return "NORMAL"


def calculate_realized_volatility(
    interval_returns: List[Decimal],
    annualization_factor: Decimal = Decimal("252.0"),
) -> Tuple[Decimal, Decimal]:
    """
    Calculate Realized Volatility:
    RV_t = sqrt( sum(r_i^2) )
    RV_annualized = RV_t * sqrt(A)
    """
    if not interval_returns:
        return Decimal("0"), Decimal("0")

    sum_sq = sum(float(r) ** 2 for r in interval_returns)
    rv_t = math.sqrt(sum_sq)
    ann_factor = float(annualization_factor)
    rv_ann = rv_t * math.sqrt(ann_factor)

    return (
        Decimal(str(round(rv_t, 6))),
        Decimal(str(round(rv_ann, 6))),
    )


def calculate_volatility_spike(
    short_horizon_rv: Decimal,
    baseline_rv: Decimal,
) -> Tuple[Optional[Decimal], Decimal, str]:
    """
    Calculate volatility spike ratio VR_t = RV_short / RV_baseline
    and volatility change Delta RV_t = RV_short - RV_baseline.
    Regime: NORMAL, ELEVATED, HIGH, EXTREME, UNAVAILABLE
    """
    if baseline_rv <= Decimal("0"):
        return None, Decimal("0"), "UNAVAILABLE"

    spike_ratio = (short_horizon_rv / baseline_rv).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    delta_rv = short_horizon_rv - baseline_rv

    if spike_ratio >= Decimal("3.0"):
        regime = "EXTREME"
    elif spike_ratio >= Decimal("2.0"):
        regime = "HIGH"
    elif spike_ratio >= Decimal("1.4"):
        regime = "ELEVATED"
    else:
        regime = "NORMAL"

    return spike_ratio, delta_rv, regime


def calculate_market_breadth(
    advancing_count: int,
    declining_count: int,
    unchanged_count: int,
    downside_anomalies: int,
    upside_anomalies: int,
    eligible_universe: int,
) -> Dict[str, Any]:
    """
    Calculate advance/decline ratio and downside/upside anomaly breadth percentages.
    Handle zero declining instruments safely.
    """
    if declining_count > 0:
        adr = Decimal(str(round(advancing_count / declining_count, 4)))
    else:
        adr = Decimal("999.0") if advancing_count > 0 else Decimal("1.0")

    if eligible_universe > 0:
        downside_breadth = Decimal(str(round((downside_anomalies / eligible_universe) * 100.0, 2)))
        upside_breadth = Decimal(str(round((upside_anomalies / eligible_universe) * 100.0, 2)))
        pct_declining = Decimal(str(round((declining_count / eligible_universe) * 100.0, 2)))
    else:
        downside_breadth = Decimal("0")
        upside_breadth = Decimal("0")
        pct_declining = Decimal("0")

    return {
        "advance_decline_ratio": adr,
        "downside_breadth_pct": downside_breadth,
        "upside_breadth_pct": upside_breadth,
        "pct_declining": pct_declining,
    }


def classify_directional_impact(
    position_direction: str,  # LONG or SHORT
    movement_direction: str,  # UPWARD or DOWNWARD
) -> str:
    """
    Determine directional context:
    - Long + Downward => ADVERSE
    - Long + Upward => FAVORABLE
    - Short + Upward => ADVERSE
    - Short + Downward => FAVORABLE
    - Otherwise => NEUTRAL
    """
    pos = position_direction.upper()
    mov = movement_direction.upper()

    if pos == "LONG":
        if mov == "DOWNWARD":
            return "ADVERSE"
        elif mov == "UPWARD":
            return "FAVORABLE"
    elif pos == "SHORT":
        if mov == "UPWARD":
            return "ADVERSE"
        elif mov == "DOWNWARD":
            return "FAVORABLE"

    return "NEUTRAL"


def generate_event_fingerprint(
    event_type: str,
    market: str,
    exchange: Optional[str],
    instrument_id: Optional[str],
    direction: Optional[str],
    window_timestamp_str: str,
) -> str:
    """
    Generate deterministic idempotency fingerprint for market event deduplication.
    """
    import hashlib
    raw = f"{event_type}|{market}|{exchange or ''}|{instrument_id or ''}|{direction or ''}|{window_timestamp_str}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()
