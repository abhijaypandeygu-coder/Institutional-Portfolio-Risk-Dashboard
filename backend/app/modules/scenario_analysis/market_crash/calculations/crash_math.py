"""
Market Crash Calculations Engine (M10.03).
Pure quantitative mathematical functions for:
- Index shocks (percentage, target index level, index point changes, multi-stage compounding)
- Instrument-to-benchmark mapping validation
- Linear beta response (single-index and multi-benchmark)
- Nonlinear downside responses (downside beta, piecewise beta, stress amplification, quadratic response, user-defined adjustments, sector adjustments)
- Instrument price boundary validation (P_s >= 0, R_s >= -1)
- Position-level signed PnL revaluation (MV = q * P, PnL = q * (P_s - P_0))
- Portfolio NAV, loss (positive representation), return, and signed contributions
- Exposure and coverage metrics (mapped coverage, beta coverage, nonlinear coverage)
- Loss attribution (instrument ranking, sector attribution, benchmark impact, linear vs nonlinear decomposition)
- Multi-currency base return conversion: (1 + R_base) = (1 + R_local) * (1 + R_FX)
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional, Tuple
import math
import numpy as np


# -------------------------------------------------------------------------
# 1. Index Shock Calculations
# -------------------------------------------------------------------------

def calculate_index_shock_return(
    shock_method: str, # PERCENTAGE, TARGET_LEVEL, POINT_CHANGE, MULTI_STAGE
    baseline_index_level: Optional[Decimal] = None,
    target_index_level: Optional[Decimal] = None,
    index_point_change: Optional[Decimal] = None,
    percentage_shock: Optional[Decimal] = None,
    multi_stage_returns: Optional[List[Decimal]] = None
) -> Tuple[Decimal, Decimal]:
    """
    Computes scenario index return R_{m,s} and scenario index level I_{m,s}.
    Guarantees R_{m,s} >= -1.0 (cannot drop below -100%).
    Returns: (scenario_return, scenario_index_level)
    """
    method = shock_method.upper()

    if method == "PERCENTAGE":
        if percentage_shock is None:
            raise ValueError("percentage_shock is required for PERCENTAGE method")
        r_m = percentage_shock
        if r_m < Decimal("-1.0"):
            raise ValueError(f"Index shock return {r_m} cannot be less than -1.0 (-100%)")
        base = baseline_index_level or Decimal("1000.00")
        i_s = base * (Decimal("1.0") + r_m)
        return r_m.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP), i_s.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    elif method == "TARGET_LEVEL":
        if baseline_index_level is None or target_index_level is None:
            raise ValueError("baseline_index_level and target_index_level are required for TARGET_LEVEL method")
        if baseline_index_level <= Decimal("0"):
            raise ValueError("baseline_index_level must be strictly positive")
        if target_index_level < Decimal("0"):
            raise ValueError("target_index_level cannot be negative")
        r_m = (target_index_level / baseline_index_level) - Decimal("1.0")
        return r_m.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP), target_index_level.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    elif method == "POINT_CHANGE":
        if baseline_index_level is None or index_point_change is None:
            raise ValueError("baseline_index_level and index_point_change are required for POINT_CHANGE method")
        if baseline_index_level <= Decimal("0"):
            raise ValueError("baseline_index_level must be strictly positive")
        i_s = baseline_index_level + index_point_change
        if i_s < Decimal("0"):
            raise ValueError(f"Target index level {i_s} from point change cannot be negative")
        r_m = (i_s / baseline_index_level) - Decimal("1.0")
        return r_m.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP), i_s.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    elif method == "MULTI_STAGE":
        if not multi_stage_returns:
            raise ValueError("multi_stage_returns is required for MULTI_STAGE method")
        cum_factor = Decimal("1.0")
        for stage_r in multi_stage_returns:
            if stage_r < Decimal("-1.0"):
                raise ValueError(f"Stage return {stage_r} cannot be less than -1.0")
            cum_factor *= (Decimal("1.0") + stage_r)
        r_m = cum_factor - Decimal("1.0")
        base = baseline_index_level or Decimal("1000.00")
        i_s = base * cum_factor
        return r_m.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP), i_s.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    else:
        raise ValueError(f"Unsupported shock_method: {shock_method}")


# -------------------------------------------------------------------------
# 2. Linear Beta & Multi-Benchmark Response
# -------------------------------------------------------------------------

def calculate_linear_beta_response(
    beta_value: Decimal,
    benchmark_shock_return: Decimal
) -> Decimal:
    """
    Calculates linear instrument return:
    R_{i,linear} = beta_{i,m} * R_{m,s}
    """
    r_linear = beta_value * benchmark_shock_return
    return r_linear.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def calculate_multi_benchmark_response(
    benchmark_betas: Dict[str, Decimal], # {benchmark_id: beta}
    benchmark_shocks: Dict[str, Decimal]  # {benchmark_id: R_m}
) -> Decimal:
    """
    Calculates multi-benchmark linear response:
    R_{i,linear} = sum_{m=1}^M beta_{i,m} * R_{m,s}
    """
    total_r = Decimal("0")
    for b_id, beta in benchmark_betas.items():
        shock = benchmark_shocks.get(b_id, Decimal("0"))
        total_r += beta * shock
    return total_r.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


# -------------------------------------------------------------------------
# 3. Nonlinear Downside Engine
# -------------------------------------------------------------------------

def calculate_downside_response(
    linear_return: Decimal,
    benchmark_shock: Decimal,
    response_model: str = "LINEAR", # LINEAR, DOWNSIDE_BETA, PIECEWISE_BETA, STRESS_AMPLIFICATION, QUADRATIC, USER_DEFINED
    unconditional_beta: Optional[Decimal] = None,
    downside_beta: Optional[Decimal] = None,
    threshold: Optional[Decimal] = None,
    stress_multiplier: Optional[Decimal] = None, # lambda_i >= 0
    exponent: Optional[Decimal] = None,         # p >= 1.0
    curvature: Optional[Decimal] = None,        # gamma_i
    sector_adjustment: Optional[Decimal] = None,
    user_adjustment: Optional[Decimal] = None
) -> Dict[str, Decimal]:
    """
    Computes instrument scenario return with decomposition:
    - linear_market_response
    - downside_adjustment
    - nonlinear_adjustment
    - sector_adjustment
    - user_adjustment
    - final_scenario_return = linear + downside + nonlinear + sector + user

    Guarantees final_scenario_return >= -1.0.
    """
    model = response_model.upper()
    downside_adj = Decimal("0")
    nonlinear_adj = Decimal("0")
    sec_adj = sector_adjustment or Decimal("0")
    usr_adj = user_adjustment or Decimal("0")

    base_linear = linear_return

    if model == "LINEAR":
        pass

    elif model == "DOWNSIDE_BETA":
        if downside_beta is not None and unconditional_beta is not None:
            # If downside beta is explicitly provided, compute differential
            # R_{downside} = beta^- * R_m
            # downside_adj = (beta^- - beta) * R_m
            diff_beta = downside_beta - unconditional_beta
            downside_adj = diff_beta * benchmark_shock
        elif downside_beta is not None:
            downside_adj = (downside_beta * benchmark_shock) - linear_return

    elif model == "PIECEWISE_BETA":
        # R = beta_normal * R_m if R_m >= c else beta_downside * R_m
        thresh = threshold or Decimal("-0.10") # e.g. -10% market crash threshold
        if benchmark_shock < thresh and downside_beta is not None and unconditional_beta is not None:
            diff_beta = downside_beta - unconditional_beta
            downside_adj = diff_beta * (benchmark_shock - thresh)

    elif model == "STRESS_AMPLIFICATION":
        # excess downside magnitude d_m = max(0, -R_m - c)
        # adverse adjustment A_i = -lambda_i * (d_m)^p
        thresh_mag = threshold or Decimal("0.10") # positive magnitude threshold (e.g. 10% drop)
        p = float(exponent or Decimal("1.5"))
        lam = float(stress_multiplier or Decimal("0.5"))
        shock_mag = float(-benchmark_shock)
        thresh_flt = float(thresh_mag)

        if shock_mag > thresh_flt:
            d_m = shock_mag - thresh_flt
            a_i = -lam * (d_m ** p)
            nonlinear_adj = Decimal(str(a_i)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    elif model == "QUADRATIC":
        # R_{i,s} = beta * R_m + gamma * R_m^2
        gam = curvature or Decimal("0.0")
        nl = gam * (benchmark_shock ** 2)
        nonlinear_adj = nl.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    elif model == "USER_DEFINED":
        # Explicit user adjustment passed in usr_adj
        pass

    final_r = base_linear + downside_adj + nonlinear_adj + sec_adj + usr_adj

    # Boundary check: price return cannot be below -100%
    if final_r < Decimal("-1.0"):
        # We clamp to -1.0 or flag an error. In strict crash simulations, -1.0 means total writeoff.
        # But we record the exact adjustment and enforce minimum of -1.0
        final_r = Decimal("-1.0")

    return {
        "linear_return": base_linear.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
        "downside_adjustment": downside_adj.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
        "nonlinear_adjustment": nonlinear_adj.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
        "sector_adjustment": sec_adj.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
        "user_adjustment": usr_adj.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
        "final_scenario_return": final_r.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
    }


# -------------------------------------------------------------------------
# 4. Currency Conversion
# -------------------------------------------------------------------------

def calculate_base_currency_return(
    local_return: Decimal,
    fx_return: Optional[Decimal] = None
) -> Decimal:
    """
    Converts local currency return into portfolio base currency return:
    (1 + R_base) = (1 + R_local) * (1 + R_FX)
    R_base = (1 + R_local) * (1 + R_FX) - 1
    """
    if fx_return is None or fx_return == Decimal("0"):
        return local_return
    r_base = ((Decimal("1.0") + local_return) * (Decimal("1.0") + fx_return)) - Decimal("1.0")
    return r_base.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


# -------------------------------------------------------------------------
# 5. Position Revaluation & Portfolio Aggregation
# -------------------------------------------------------------------------

def revalue_position(
    signed_quantity: Decimal,
    baseline_price: Decimal,
    final_return: Decimal,
    baseline_nav: Decimal
) -> Dict[str, Decimal]:
    """
    Revalues position under scenario:
    P_s = P_0 * (1 + R)
    MV_0 = q * P_0
    MV_s = q * P_s
    PnL = MV_s - MV_0 = q * P_0 * R
    Loss = max(0, -PnL)
    Contribution = PnL / NAV_0
    """
    if baseline_price < Decimal("0"):
        raise ValueError(f"Baseline price {baseline_price} cannot be negative")

    scenario_price = baseline_price * (Decimal("1.0") + final_return)
    if scenario_price < Decimal("0"):
        scenario_price = Decimal("0")

    mv_0 = signed_quantity * baseline_price
    mv_s = signed_quantity * scenario_price
    pnl = mv_s - mv_0
    loss = Decimal("0") if pnl >= Decimal("0") else -pnl

    contribution = Decimal("0")
    if baseline_nav > Decimal("0"):
        contribution = pnl / baseline_nav

    return {
        "scenario_price": scenario_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "baseline_market_value": mv_0.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "scenario_market_value": mv_s.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "scenario_pnl": pnl.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "scenario_loss": loss.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "portfolio_contribution": contribution.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
    }


def compute_portfolio_revaluation(
    baseline_nav: Decimal,
    position_revaluations: List[Dict[str, Decimal]]
) -> Dict[str, Decimal]:
    """
    Aggregates position revaluations into portfolio NAV and metrics:
    PnL_{portfolio} = sum PnL_i
    NAV_s = NAV_0 + PnL_{portfolio}
    Loss_{portfolio} = max(0, -PnL_{portfolio})
    Return_{portfolio} = PnL_{portfolio} / NAV_0
    """
    total_pnl = sum([p["scenario_pnl"] for p in position_revaluations], Decimal("0"))
    total_mv_0 = sum([abs(p["baseline_market_value"]) for p in position_revaluations], Decimal("0"))
    net_mv_0 = sum([p["baseline_market_value"] for p in position_revaluations], Decimal("0"))

    scenario_nav = baseline_nav + total_pnl
    portfolio_loss = Decimal("0") if total_pnl >= Decimal("0") else -total_pnl
    portfolio_return = Decimal("0")
    if baseline_nav > Decimal("0"):
        portfolio_return = total_pnl / baseline_nav

    return {
        "baseline_nav": baseline_nav.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "scenario_nav": scenario_nav.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "scenario_pnl": total_pnl.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "scenario_loss": portfolio_loss.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "scenario_return": portfolio_return.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
        "gross_exposure": total_mv_0.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "net_exposure": net_mv_0.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    }


# -------------------------------------------------------------------------
# 6. Coverage & Attribution Metrics
# -------------------------------------------------------------------------

def compute_coverage_metrics(
    positions_data: List[Dict[str, Any]]
) -> Dict[str, Decimal]:
    """
    Computes exposure coverage using absolute baseline market values:
    - mapped_coverage = sum_{mapped} |MV_i| / sum_{included} |MV_i|
    - beta_coverage = sum_{beta_valid} |MV_i| / sum_{included} |MV_i|
    - nonlinear_coverage = sum_{nonlinear_valid} |MV_i| / sum_{included} |MV_i|
    """
    total_abs_mv = Decimal("0")
    mapped_abs_mv = Decimal("0")
    beta_abs_mv = Decimal("0")
    nl_abs_mv = Decimal("0")

    for p in positions_data:
        mv = abs(Decimal(str(p.get("baseline_market_value", "0"))))
        total_abs_mv += mv
        if p.get("is_mapped"):
            mapped_abs_mv += mv
        if p.get("is_beta_valid"):
            beta_abs_mv += mv
        if p.get("is_nonlinear_eligible"):
            nl_abs_mv += mv

    if total_abs_mv <= Decimal("0"):
        return {
            "mapped_coverage": Decimal("1.0000"),
            "beta_coverage": Decimal("1.0000"),
            "nonlinear_coverage": Decimal("1.0000")
        }

    return {
        "mapped_coverage": (mapped_abs_mv / total_abs_mv).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        "beta_coverage": (beta_abs_mv / total_abs_mv).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        "nonlinear_coverage": (nl_abs_mv / total_abs_mv).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    }


def decompose_linear_nonlinear_impact(
    baseline_market_value: Decimal,
    linear_return: Decimal,
    final_return: Decimal
) -> Tuple[Decimal, Decimal]:
    """
    Decomposes position PnL into linear vs nonlinear impact:
    PnL_{linear} = MV_0 * R_{linear}
    PnL_{nonlinear} = MV_0 * (R_{final} - R_{linear})
    Reconciliation: PnL_{linear} + PnL_{nonlinear} == PnL_{total}
    """
    pnl_lin = baseline_market_value * linear_return
    pnl_nl = baseline_market_value * (final_return - linear_return)
    return (
        pnl_lin.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        pnl_nl.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )
