"""
Return calculation mathematical services for M14.02 — Portfolio Performance Reports.

Implements:
1. Time-Weighted Return (TWR) with boundary valuations.
2. Modified Dietz approximation with day-count weighting.
3. Money-Weighted Return (MWR / XIRR) with Newton-Raphson / bisection solver.
4. Cumulative compounding and annualization.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Tuple, Optional, Dict, Any
import math


def calculate_subperiod_twr(
    v_start: Decimal,
    v_end: Decimal,
    net_external_flow: Decimal = Decimal("0.0"),
    cash_flow_timing: str = "VALUATION_AT_FLOW_BOUNDARY",
) -> Optional[Decimal]:
    """
    Computes exact subperiod return neutralizing external flows.
    If flow is valued at boundary:
    r_i = (v_end - net_external_flow) / v_start - 1 (for end-of-subperiod flow)
    or when valuations immediately precede flow: v_end / v_start - 1.
    """
    if v_start <= Decimal("0.0"):
        return None

    # Under standard end-of-day cash flow convention:
    # Ending value includes the flow, so net investment gain is (v_end - v_start - net_flow)
    # Return = (v_end - net_flow) / v_start - 1.0
    adjusted_end = v_end - net_external_flow
    if adjusted_end < Decimal("0.0"):
        return None

    return (adjusted_end / v_start) - Decimal("1.0")


def calculate_modified_dietz(
    v_start: Decimal,
    v_end: Decimal,
    cash_flows: List[Tuple[date, Decimal]],  # (flow_date, flow_amount)
    start_date: date,
    end_date: date,
) -> Optional[Decimal]:
    """
    Calculates Modified Dietz return:
    R_MD = (V_E - V_B - Sum(CF_j)) / (V_B + Sum(w_j * CF_j))
    Where w_j = (end_date - flow_date) / (end_date - start_date)
    """
    total_days = (end_date - start_date).days
    if total_days <= 0:
        return Decimal("0.0")

    sum_cf = sum((cf for _, cf in cash_flows), Decimal("0.0"))
    weighted_cf = Decimal("0.0")

    for cf_date, cf_amt in cash_flows:
        # Clamped remaining days
        remaining_days = max(0, (end_date - cf_date).days)
        w_j = Decimal(remaining_days) / Decimal(total_days)
        weighted_cf += w_j * cf_amt

    denominator = v_start + weighted_cf
    if denominator <= Decimal("0.0"):
        return None

    numerator = v_end - v_start - sum_cf
    return numerator / denominator


def compound_returns(periodic_returns: List[Decimal]) -> Decimal:
    """
    Compounds periodic returns:
    R_cum = Product(1 + r_t) - 1
    """
    wealth = Decimal("1.0")
    for r in periodic_returns:
        wealth *= (Decimal("1.0") + r)
    return wealth - Decimal("1.0")


def annualize_return(
    cumulative_return: Decimal,
    elapsed_days: int,
    basis_days: int = 365,
    min_days_for_annualization: int = 180,
) -> Optional[Decimal]:
    """
    Annualizes cumulative return:
    R_ann = (1 + R_cum) ^ (basis / elapsed) - 1
    Only valid when elapsed >= min_days_for_annualization.
    """
    if elapsed_days < min_days_for_annualization or elapsed_days <= 0:
        return None

    # Check bounds
    if cumulative_return <= Decimal("-1.0"):
        return Decimal("-1.0")

    cum_float = float(cumulative_return)
    exponent = float(basis_days) / float(elapsed_days)
    try:
        ann_float = math.pow(1.0 + cum_float, exponent) - 1.0
        return Decimal(str(round(ann_float, 8)))
    except (ValueError, OverflowError):
        return None


def calculate_xirr(
    dated_cash_flows: List[Tuple[date, Decimal]],  # (date, amount) negative for outflow/inv, positive for inflow/term
    guess: float = 0.1,
    max_iter: int = 100,
    tol: float = 1e-7,
) -> Optional[Decimal]:
    """
    Calculates Money-Weighted Return (MWR / XIRR) via Newton-Raphson.
    Cash flows from investor perspective:
    - Initial value: negative (outflow / investment)
    - Contributions: negative (outflows)
    - Withdrawals: positive (inflows)
    - Terminal value: positive (inflow / liquidation)
    """
    if len(dated_cash_flows) < 2:
        return None

    # Check that there is at least one positive and one negative cash flow
    has_pos = any(cf[1] > Decimal("0.0") for cf in dated_cash_flows)
    has_neg = any(cf[1] < Decimal("0.0") for cf in dated_cash_flows)
    if not (has_pos and has_neg):
        return None

    base_date = min(cf[0] for cf in dated_cash_flows)
    flows = [(float((d - base_date).days) / 365.0, float(amt)) for d, amt in dated_cash_flows]

    rate = guess
    for _ in range(max_iter):
        f_val = 0.0
        df_val = 0.0
        for t, amt in flows:
            denom = math.pow(1.0 + rate, t) if (1.0 + rate) > 0.0 else 1e-12
            f_val += amt / denom
            if (1.0 + rate) > 0.0:
                df_val += -t * amt / (denom * (1.0 + rate))

        if abs(f_val) < tol:
            return Decimal(str(round(rate, 8)))

        if abs(df_val) < 1e-12:
            break

        new_rate = rate - (f_val / df_val)
        if new_rate <= -0.999:  # Keep in reasonable domain
            new_rate = (rate - 0.999) / 2.0

        if abs(new_rate - rate) < tol:
            return Decimal(str(round(new_rate, 8)))

        rate = new_rate

    return None
