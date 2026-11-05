"""
Historical Scenarios Mathematical Calculations (M10.01).

Implements:
1. Return calculations:
   - Simple return: R_t = (P_t / P_{t-1}) - 1
   - Log return: r_t = ln(P_t / P_{t-1})
   - Compounded cumulative event return: R_{event} = prod(1 + R_t) - 1
2. Currency shock conversion:
   - (1 + R_{base}) = (1 + R_{local}) * (1 + R_{FX})
   - R_{base} = (1 + R_{local}) * (1 + R_{FX}) - 1
3. Factor-based shock estimation:
   - R_i^{estimated} = sum_k (beta_{i,k} * F_k) + epsilon_i
4. Position-level revaluation:
   - Signed quantity convention: long > 0, short < 0
   - MV_{i,0} = q_i * P_{i,0}
   - P_{i,scenario} = P_{i,0} * (1 + R_i)
   - MV_{i,scenario} = q_i * P_{i,scenario}
   - PnL_i = MV_{i,scenario} - MV_{i,0} = q_i * P_{i,0} * R_i
5. Portfolio aggregation & reconciliation:
   - PnL_{portfolio} = sum_i PnL_i
   - NAV_{scenario} = NAV_0 + PnL_{portfolio}
   - R_{portfolio} = PnL_{portfolio} / NAV_0
   - Weight w_i = MV_{i,0} / NAV_0
   - Contribution C_i = w_i * R_i
   - Reconciliation check: sum_i C_i == R_{portfolio}
6. Coverage diagnostics:
   - Absolute exposure coverage:
     Coverage_{direct} = sum_{i in Direct} |MV_i| / sum_{i in Included} |MV_i|
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Optional, Tuple, Any
import math
import numpy as np


def to_decimal(val: Any) -> Decimal:
    """Safely converts input to Decimal without silent floating-point distortion."""
    if val is None:
        return Decimal("0")
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def compute_simple_return(current_price: Decimal, previous_price: Decimal) -> Decimal:
    """Computes R_t = (P_t / P_{t-1}) - 1."""
    if previous_price <= Decimal("0"):
        raise ValueError("Previous price must be strictly positive for return calculation")
    return ((current_price - previous_price) / previous_price).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def compute_cumulative_compounded_return(periodic_returns: List[Decimal]) -> Decimal:
    """
    Computes compounded cumulative return:
    R_{cumulative} = prod_{t=1}^T (1 + R_t) - 1
    Never uses arithmetic sum as cumulative return.
    """
    if not periodic_returns:
        return Decimal("0")

    compounded = Decimal("1.0")
    for r in periodic_returns:
        compounded *= (Decimal("1.0") + r)

    return (compounded - Decimal("1.0")).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def compute_currency_adjusted_return(local_return: Decimal, fx_return: Decimal) -> Decimal:
    """
    Applies currency adjustment:
    (1 + R_{base}) = (1 + R_{local}) * (1 + R_{FX})
    R_{base} = (1 + R_{local}) * (1 + R_{FX}) - 1
    """
    one = Decimal("1.0")
    base_ret = (one + local_return) * (one + fx_return) - one
    return base_ret.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def estimate_factor_shock(
    factor_sensitivities: Dict[str, Decimal],
    factor_shocks: Dict[str, Decimal],
    residual_shock: Decimal = Decimal("0")
) -> Decimal:
    """
    Computes factor-based estimated return:
    R_i^{estimated} = sum_k (beta_{i,k} * F_k) + epsilon_i
    """
    modeled_return = Decimal("0")
    for factor_name, beta in factor_sensitivities.items():
        if factor_name in factor_shocks:
            modeled_return += beta * factor_shocks[factor_name]
    modeled_return += residual_shock
    return modeled_return.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def revalue_position(
    signed_quantity: Decimal,
    baseline_price: Decimal,
    scenario_return: Decimal,
    baseline_nav: Decimal
) -> Dict[str, Decimal]:
    """
    Revalues position under scenario shock:
    MV_{i,0} = q_i * P_{i,0}
    P_{i,scenario} = P_{i,0} * (1 + R_i)
    MV_{i,scenario} = q_i * P_{i,scenario}
    PnL_i = MV_{i,scenario} - MV_{i,0} = q_i * P_{i,0} * R_i
    Weight w_i = MV_{i,0} / NAV_0
    Contribution C_i = w_i * R_i = PnL_i / NAV_0
    """
    baseline_mv = (signed_quantity * baseline_price).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    scenario_price = (baseline_price * (Decimal("1.0") + scenario_return)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
    scenario_mv = (signed_quantity * scenario_price).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    scenario_pnl = (scenario_mv - baseline_mv).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    weight = Decimal("0")
    contribution = Decimal("0")
    if baseline_nav > Decimal("0"):
        weight = (baseline_mv / baseline_nav).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
        contribution = (scenario_pnl / baseline_nav).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    return {
        "baseline_market_value": baseline_mv,
        "scenario_price": scenario_price,
        "scenario_market_value": scenario_mv,
        "scenario_pnl": scenario_pnl,
        "portfolio_weight": weight,
        "portfolio_contribution": contribution
    }


def aggregate_portfolio_replay(
    baseline_nav: Decimal,
    position_results: List[Dict[str, Any]],
    excluded_positions: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Aggregates position-level results into portfolio-level results and computes coverage diagnostics.
    """
    total_pnl = Decimal("0")
    sum_contributions = Decimal("0")
    
    direct_exposure = Decimal("0")
    proxy_exposure = Decimal("0")
    factor_exposure = Decimal("0")
    unmapped_exposure = Decimal("0")
    total_included_exposure = Decimal("0")

    for pos in position_results:
        pnl = pos["scenario_pnl"]
        contrib = pos["portfolio_contribution"]
        mv_abs = abs(pos["baseline_market_value"])
        method = pos.get("mapping_method", "UNMAPPED")

        total_pnl += pnl
        sum_contributions += contrib
        total_included_exposure += mv_abs

        if method == "EXACT_DIRECT":
            direct_exposure += mv_abs
        elif method in ["ALTERNATE_LISTING", "APPROVED_PROXY", "SECTOR_PROXY", "MARKET_INDEX_PROXY"]:
            proxy_exposure += mv_abs
        elif method == "FACTOR_MODEL":
            factor_exposure += mv_abs
        else:
            unmapped_exposure += mv_abs

    if excluded_positions:
        for ex in excluded_positions:
            unmapped_exposure += abs(ex.get("baseline_market_value", Decimal("0")))

    scenario_nav = (baseline_nav + total_pnl).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    portfolio_return = Decimal("0")
    if baseline_nav > Decimal("0"):
        portfolio_return = (total_pnl / baseline_nav).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    # Coverage ratios (based on absolute market values so long/short don't offset)
    direct_cov = Decimal("0")
    proxy_cov = Decimal("0")
    factor_cov = Decimal("0")
    unmapped_cov = Decimal("0")

    denom = total_included_exposure + (sum(abs(ex.get("baseline_market_value", Decimal("0"))) for ex in (excluded_positions or [])))
    if denom > Decimal("0"):
        direct_cov = (direct_exposure / denom).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        proxy_cov = (proxy_exposure / denom).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        factor_cov = (factor_exposure / denom).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        unmapped_cov = (unmapped_exposure / denom).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    reconciliation_discrepancy = abs(portfolio_return - sum_contributions).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    return {
        "baseline_nav": baseline_nav,
        "scenario_nav": scenario_nav,
        "scenario_pnl": total_pnl,
        "scenario_return": portfolio_return,
        "direct_coverage": direct_cov,
        "proxy_coverage": proxy_cov,
        "factor_coverage": factor_cov,
        "unmapped_coverage": unmapped_cov,
        "reconciliation_discrepancy": reconciliation_discrepancy,
        "total_included_exposure": total_included_exposure,
        "included_count": len(position_results),
        "excluded_count": len(excluded_positions or [])
    }
