"""
Mathematical and statistical calculation routines for M12.03 Liquidity Alerts.

Includes:
1. Spread metrics: Absolute spread, Relative spread, Spread in basis points (bps), Widening delta and relative change.
2. Robust spread deviation: Median, MAD (Median Absolute Deviation), robust Z-score, empirical percentile.
3. Order-book depth deterioration: Absolute depth change, decline magnitude %, notional depth calculation.
4. Composite liquidity score deterioration: Absolute change, decline %, tolerance check.
5. Liquidation cost & horizon deterioration: Cost delta, relative change %, horizon delta.
6. Side-specific directional impact: Long -> Bid side liquidity, Short -> Ask side liquidity.
7. Deterministic idempotency fingerprint for liquidity alert deduplication.
"""

from decimal import Decimal, ROUND_HALF_UP
import math
from typing import List, Optional, Tuple, Dict, Any
import hashlib


def calculate_spread_metrics(
    best_bid: Decimal,
    best_ask: Decimal,
    reference_spread_bps: Optional[Decimal] = None,
) -> Tuple[Decimal, Decimal, Decimal, Optional[Decimal], Optional[Decimal]]:
    """
    Calculates:
    - Absolute spread: S_t = Ask - Bid
    - Relative spread: S_rel = (Ask - Bid) / Mid
    - Spread in basis points: S_bps = ((Ask - Bid) / Mid) * 10,000
    - Spread widening delta: Delta S_bps = S_bps - S_ref
    - Relative widening factor: W_t = (S_bps - S_ref) / S_ref
    """
    if best_bid <= Decimal("0") or best_ask <= Decimal("0") or best_ask < best_bid:
        return Decimal("0"), Decimal("0"), Decimal("0"), None, None

    abs_spread = best_ask - best_bid
    mid_price = (best_bid + best_ask) / Decimal("2")
    if mid_price <= Decimal("0"):
        return Decimal("0"), Decimal("0"), Decimal("0"), None, None

    rel_spread = (abs_spread / mid_price).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    spread_bps = (rel_spread * Decimal("10000")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    delta_bps = None
    rel_widening = None
    if reference_spread_bps is not None and reference_spread_bps > Decimal("0"):
        delta_bps = spread_bps - reference_spread_bps
        rel_widening = ((spread_bps - reference_spread_bps) / reference_spread_bps).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    return abs_spread, rel_spread, spread_bps, delta_bps, rel_widening


def calculate_robust_spread_deviation(
    current_spread_bps: Decimal,
    historical_spreads_bps: List[Decimal],
) -> Tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
    """
    Calculates median, MAD, robust Z-score, and empirical percentile:
    MAD = Median( |S_i - Median(S)| )
    Z_robust = (S_t - Median(S)) / (1.4826 * MAD(S))
    Percentile: percentage of historical observations <= current_spread_bps
    """
    if not historical_spreads_bps or len(historical_spreads_bps) < 3:
        return None, None, None, None

    floats = sorted([float(s) for s in historical_spreads_bps])
    n = len(floats)
    
    # Calculate median
    mid_idx = n // 2
    if n % 2 == 1:
        med = floats[mid_idx]
    else:
        med = (floats[mid_idx - 1] + floats[mid_idx]) / 2.0

    # Calculate MAD
    abs_deviations = sorted([abs(x - med) for x in floats])
    if n % 2 == 1:
        mad = abs_deviations[mid_idx]
    else:
        mad = (abs_deviations[mid_idx - 1] + abs_deviations[mid_idx]) / 2.0

    # Robust Z-score
    curr_f = float(current_spread_bps)
    if mad > 1e-8:
        scale = 1.4826 * mad
        z_robust = Decimal(str(round((curr_f - med) / scale, 4)))
    else:
        z_robust = None

    # Empirical percentile
    count_less = sum(1 for x in floats if x <= curr_f)
    pct = Decimal(str(round((count_less / n) * 100.0, 2)))

    med_dec = Decimal(str(round(med, 2)))
    mad_dec = Decimal(str(round(mad, 2)))
    return med_dec, mad_dec, z_robust, pct


def calculate_depth_deterioration(
    current_depth: Decimal,
    reference_depth: Decimal,
) -> Tuple[Decimal, Decimal]:
    """
    Delta D_t = Current - Reference
    Decline % = ((Reference - Current) / Reference) * 100
    """
    if reference_depth <= Decimal("0"):
        return Decimal("0"), Decimal("0")

    delta_depth = current_depth - reference_depth
    decline_pct = ((reference_depth - current_depth) / reference_depth * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return delta_depth, decline_pct


def evaluate_depth_state(
    current_depth: Decimal,
    reference_depth: Decimal,
    decline_threshold_pct: Decimal = Decimal("40.0"),
    severe_threshold_pct: Decimal = Decimal("60.0"),
    recovery_threshold_pct: Decimal = Decimal("25.0"),
) -> str:
    """
    Evaluate depth state:
    - SEVERELY_DETERIORATED (decline >= severe_threshold_pct)
    - DETERIORATING (decline >= decline_threshold_pct)
    - RECOVERING (decline < recovery_threshold_pct from reference)
    - NORMAL
    """
    if reference_depth <= Decimal("0") or current_depth < Decimal("0"):
        return "UNAVAILABLE"

    decline_pct = ((reference_depth - current_depth) / reference_depth) * Decimal("100")
    if decline_pct >= severe_threshold_pct:
        return "SEVERELY_DETERIORATED"
    elif decline_pct >= decline_threshold_pct:
        return "DETERIORATING"
    elif decline_pct <= recovery_threshold_pct:
        return "NORMAL"
    else:
        return "RECOVERING"


def calculate_liquidity_score_decline(
    current_score: Decimal,
    reference_score: Decimal,
) -> Tuple[Decimal, Decimal]:
    """
    Delta L_t = current - reference
    Decline % = ((reference - current) / reference) * 100
    """
    if reference_score <= Decimal("0"):
        return Decimal("0"), Decimal("0")

    delta_score = current_score - reference_score
    decline_pct = ((reference_score - current_score) / reference_score * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return delta_score, decline_pct


def calculate_liquidation_deterioration(
    current_val: Decimal,
    reference_val: Decimal,
) -> Tuple[Decimal, Decimal]:
    """
    Delta = current - reference
    Increase % = ((current - reference) / reference) * 100
    """
    if reference_val <= Decimal("0"):
        return Decimal("0"), Decimal("0")

    delta = current_val - reference_val
    increase_pct = ((current_val - reference_val) / reference_val * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return delta, increase_pct


def map_liquidity_side_for_position(position_direction: str) -> str:
    """
    Long position liquidation requires selling -> BID side.
    Short position liquidation requires buying back -> ASK side.
    """
    if position_direction.upper() == "LONG":
        return "BID"
    elif position_direction.upper() == "SHORT":
        return "ASK"
    return "BOTH"


def generate_liquidity_event_fingerprint(
    alert_category: str,
    metric_type: str,
    market: str,
    exchange: Optional[str],
    instrument_id: str,
    side: Optional[str],
    window_timestamp_str: str,
) -> str:
    raw = f"{alert_category}|{metric_type}|{market}|{exchange or ''}|{instrument_id}|{side or ''}|{window_timestamp_str}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()
