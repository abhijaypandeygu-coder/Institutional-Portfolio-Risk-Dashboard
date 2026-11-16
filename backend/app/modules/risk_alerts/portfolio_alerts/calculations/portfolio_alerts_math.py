"""
Mathematical and analytical calculation routines for M12.04 Portfolio Alerts.

Includes:
1. Portfolio loss calculations:
   - Absolute monetary P&L: P&L = V_t - V_0
   - Percentage P&L: P&L% = (V_t - V_0) / V_0 * 100
   - Loss magnitude: Loss_t = max(0, -P&L_t)
   - NAV-adjusted loss: Loss%_NAV = max(0, -P&L_t) / NAV_ref * 100
   - Intraday loss velocity: Delta PnL / Delta t (bps / min, currency / hr)
   - Loss attribution residual calculation
2. Concentration change calculations:
   - Percentage-point change: Delta C_pp = 100 * (C_t - C_baseline)
   - Relative change: Delta C_rel = (C_t - C_baseline) / |C_baseline|
   - Herfindahl-Hirschman Index (HHI): sum(w_i^2) for nonnegative normalized weights
3. Position movement calculations:
   - Quantity delta: Delta Q = Q_t - Q_{t-1}
   - Percentage quantity change: Delta Q% = (Q_t - Q_{t-1}) / |Q_{t-1}| * 100
   - Movement type classification: NEW_LONG, NEW_SHORT, INCREASE, REDUCTION, CLOSED, REVERSAL
4. Cash movement calculations:
   - Delta cash: Cash_t - Cash_{t-1}
   - Movement relative to NAV: |Delta Cash| / NAV_ref * 100
5. Reconciliation break calculations:
   - Break magnitude: |Internal - External|
   - Relative break %: |Internal - External| / Reference * 100
   - Quantity break: Q_internal - Q_external
6. Deterministic idempotency fingerprint for portfolio alert deduplication.
"""

from decimal import Decimal, ROUND_HALF_UP
import math
from typing import List, Optional, Tuple, Dict, Any
import hashlib


def calculate_portfolio_loss(
    current_val: Decimal,
    reference_val: Decimal,
    reference_nav: Optional[Decimal] = None,
) -> Tuple[Decimal, Decimal, Decimal, Optional[Decimal]]:
    """
    Calculates:
    - Signed P&L: PnL = V_t - V_0
    - Percentage P&L: PnL% = (PnL / V_0) * 100
    - Positive Loss Magnitude: Loss = max(0, -PnL)
    - NAV-adjusted Loss %: (Loss / NAV_ref) * 100
    """
    if reference_val <= Decimal("0"):
        return Decimal("0"), Decimal("0"), Decimal("0"), None

    pnl = current_val - reference_val
    pnl_pct = ((pnl / reference_val) * Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    loss_mag = max(Decimal("0"), -pnl)

    nav_loss_pct = None
    if reference_nav is not None and reference_nav > Decimal("0"):
        nav_loss_pct = ((loss_mag / reference_nav) * Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    return pnl, pnl_pct, loss_mag, nav_loss_pct


def calculate_loss_velocity(
    pnl_t: Decimal,
    pnl_prior: Decimal,
    delta_seconds: int,
    reference_nav: Optional[Decimal] = None,
) -> Tuple[Decimal, Optional[Decimal]]:
    """
    Calculates loss velocity:
    - Currency per hour: (Delta PnL / delta_seconds) * 3600
    - Bps of NAV per minute: ((Delta PnL / NAV) * 10000 / delta_seconds) * 60
    """
    if delta_seconds <= 0:
        return Decimal("0"), None

    delta_pnl = pnl_t - pnl_prior
    sec_dec = Decimal(str(delta_seconds))
    velocity_curr_per_hr = (delta_pnl / sec_dec * Decimal("3600")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    bps_per_min = None
    if reference_nav is not None and reference_nav > Decimal("0"):
        bps_change = (delta_pnl / reference_nav) * Decimal("10000")
        bps_per_min = (bps_change / sec_dec * Decimal("60")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return velocity_curr_per_hr, bps_per_min


def calculate_loss_attribution(
    portfolio_pnl: Decimal,
    instrument_pnls: Dict[str, Decimal],
    reference_nav: Optional[Decimal] = None,
) -> Tuple[Dict[str, Decimal], Dict[str, Decimal], Decimal]:
    """
    Calculates:
    - Instrument contributions
    - Percentage contribution relative to NAV
    - Attribution residual: PortfolioPnL - sum(Contribution_i)
    """
    contrib_pcts = {}
    total_attributed = Decimal("0")

    for inst, pnl_val in instrument_pnls.items():
        total_attributed += pnl_val
        if reference_nav is not None and reference_nav > Decimal("0"):
            contrib_pcts[inst] = ((pnl_val / reference_nav) * Decimal("100")).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )
        else:
            contrib_pcts[inst] = Decimal("0")

    residual = portfolio_pnl - total_attributed
    return instrument_pnls, contrib_pcts, residual


def calculate_concentration_changes(
    current_weight: Decimal,  # e.g. 0.25 for 25%
    baseline_weight: Decimal,
) -> Tuple[Decimal, Optional[Decimal]]:
    """
    Calculates:
    - Percentage-point change: Delta C_pp = 100 * (current - baseline)
    - Relative change: (current - baseline) / |baseline|
    """
    delta_pp = ((current_weight - baseline_weight) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    rel_change = None
    if abs(baseline_weight) > Decimal("0"):
        rel_change = ((current_weight - baseline_weight) / abs(baseline_weight)).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

    return delta_pp, rel_change


def calculate_hhi(weights: List[Decimal]) -> Decimal:
    """
    Herfindahl-Hirschman Index: sum(w_i^2) for normalized weights (0 to 1).
    Returned as standard scale 0 to 10,000.
    """
    if not weights:
        return Decimal("0")
    total_sq = sum((w ** 2) for w in weights)
    return (total_sq * Decimal("10000")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def classify_position_movement(
    prior_quantity: Decimal,
    current_quantity: Decimal,
) -> Tuple[str, Decimal, Optional[Decimal]]:
    """
    Classify position movement:
    - NEW_LONG: 0 -> positive
    - NEW_SHORT: 0 -> negative
    - CLOSED: non-zero -> 0
    - REVERSAL: positive -> negative or negative -> positive
    - INCREASE: same sign, greater absolute magnitude
    - REDUCTION: same sign, smaller absolute magnitude
    - NO_CHANGE
    Returns: movement_type, delta_quantity, pct_change
    """
    delta_q = current_quantity - prior_quantity
    pct_change = None

    if prior_quantity != Decimal("0"):
        pct_change = ((delta_q / abs(prior_quantity)) * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    if prior_quantity == Decimal("0"):
        if current_quantity > Decimal("0"):
            return "NEW_LONG", delta_q, Decimal("100.00")
        elif current_quantity < Decimal("0"):
            return "NEW_SHORT", delta_q, Decimal("100.00")
        else:
            return "NO_CHANGE", Decimal("0"), Decimal("0")

    if current_quantity == Decimal("0"):
        return "CLOSED", delta_q, Decimal("-100.00")

    if (prior_quantity > Decimal("0") and current_quantity < Decimal("0")) or \
       (prior_quantity < Decimal("0") and current_quantity > Decimal("0")):
        return "REVERSAL", delta_q, pct_change

    if abs(current_quantity) > abs(prior_quantity):
        return "INCREASE", delta_q, pct_change
    elif abs(current_quantity) < abs(prior_quantity):
        return "REDUCTION", delta_q, pct_change

    return "NO_CHANGE", Decimal("0"), Decimal("0")


def calculate_cash_movement(
    current_cash: Decimal,
    prior_cash: Decimal,
    reference_nav: Optional[Decimal] = None,
) -> Tuple[Decimal, Optional[Decimal]]:
    """
    Delta cash = current - prior
    Cash movement % of NAV = |Delta Cash| / NAV_ref * 100
    """
    delta_cash = current_cash - prior_cash
    pct_nav = None
    if reference_nav is not None and reference_nav > Decimal("0"):
        pct_nav = ((abs(delta_cash) / reference_nav) * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    return delta_cash, pct_nav


def calculate_reconciliation_break_magnitude(
    internal_val: Decimal,
    external_val: Decimal,
    reference_val: Optional[Decimal] = None,
) -> Tuple[Decimal, Decimal, Optional[Decimal]]:
    """
    Signed break: internal - external
    Break magnitude: |internal - external|
    Relative break %: (|internal - external| / reference) * 100
    """
    signed_break = internal_val - external_val
    break_mag = abs(signed_break)

    rel_break_pct = None
    ref = reference_val or external_val or internal_val
    if ref is not None and abs(ref) > Decimal("0"):
        rel_break_pct = ((break_mag / abs(ref)) * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    return signed_break, break_mag, rel_break_pct


def generate_portfolio_event_fingerprint(
    category: str,
    event_type: str,
    portfolio_id: str,
    entity_key: Optional[str],
    window_timestamp_str: str,
) -> str:
    raw = f"{category}|{event_type}|{portfolio_id}|{entity_key or ''}|{window_timestamp_str}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()

