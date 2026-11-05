"""
Sector Shock Math Engine (M10.04).
Pure quantitative logic for:
1. Direct sector/industry shock application (uniform return or sensitivity-adjusted: R_direct = beta_s * R_s).
2. Spillover transmission matrix: r_spillover = W * r_direct.
3. Factor-mediated transmission: F_{k,spillover} = sum_j a_{kj} * R_{j,direct}, R_{i,factor} = sum_k beta_{i,k} * F_{k,spillover}.
4. Additive & compound composition with conflict resolution and no double-counting.
5. Base currency return conversion: (1 + R_base) = (1 + R_local) * (1 + R_FX).
6. Signed position revaluation: MV_0 = q * P_0, MV_s = q * P_s, PnL = q * P_0 * R, Loss = max(0, -PnL).
7. Portfolio aggregation, NAV reconciliation (NAV_s = NAV_0 + PnL), and signed return contribution: C_i = PnL_i / NAV_0.
8. Attribution decomposition: PnL_{direct}, PnL_{spillover}, PnL_{factor}, PnL_{manual}.
9. Absolute exposure coverage metrics: classification coverage, direct shock coverage, spillover coverage, sensitivity coverage.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple, Any
import numpy as np


# -------------------------------------------------------------------------
# 1. Direct Sector & Industry Return
# -------------------------------------------------------------------------

def calculate_direct_sector_response(
    sector_shock: Decimal,
    sensitivity: Optional[Decimal] = None # beta_{i,s}
) -> Decimal:
    """
    Computes direct sector response:
    - Uniform group return: R_direct = R_s
    - Sensitivity-adjusted: R_direct = beta_s * R_s
    """
    if sensitivity is not None:
        r = sensitivity * sector_shock
    else:
        r = sector_shock
    return r.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


# -------------------------------------------------------------------------
# 2. Spillover Transmission Engine
# -------------------------------------------------------------------------

def calculate_spillover_effects(
    direct_shocks: Dict[str, Decimal], # {source_group: shock}
    spillover_matrix: Dict[str, Dict[str, Decimal]] # {target_group: {source_group: coeff}}
) -> Dict[str, Decimal]:
    """
    Calculates indirect spillover shocks to target groups:
    S_target = sum_{source} w_{target, source} * R_{source, direct}
    """
    spillovers: Dict[str, Decimal] = {}
    for target_group, sources in spillover_matrix.items():
        total_indirect = Decimal("0")
        for src_group, coeff in sources.items():
            if src_group in direct_shocks:
                src_shock = direct_shocks[src_group]
                total_indirect += coeff * src_shock
        spillovers[target_group] = total_indirect.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
    return spillovers


def calculate_factor_mediated_spillover(
    direct_shocks: Dict[str, Decimal], # {source_sector: shock}
    sector_to_factor_matrix: Dict[str, Dict[str, Decimal]], # {factor_id: {source_sector: coeff}}
    instrument_factor_betas: Dict[str, Decimal] # {factor_id: beta_{i,k}}
) -> Tuple[Dict[str, Decimal], Decimal]:
    """
    Computes:
    1. Induced factor shocks: F_{k,spillover} = sum_j a_{kj} * R_{j,direct}
    2. Factor-mediated return for instrument: R_{i,factor} = sum_k beta_{i,k} * F_{k,spillover}
    Returns: (factor_shocks, instrument_factor_return)
    """
    factor_shocks: Dict[str, Decimal] = {}
    for factor_id, sources in sector_to_factor_matrix.items():
        f_shock = Decimal("0")
        for src_sec, coeff in sources.items():
            if src_sec in direct_shocks:
                f_shock += coeff * direct_shocks[src_sec]
        factor_shocks[factor_id] = f_shock.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    inst_factor_r = Decimal("0")
    for factor_id, f_shock in factor_shocks.items():
        beta_k = instrument_factor_betas.get(factor_id, Decimal("0"))
        inst_factor_r += beta_k * f_shock

    return factor_shocks, inst_factor_r.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


# -------------------------------------------------------------------------
# 3. Sector Shock Composition & Boundary Validation
# -------------------------------------------------------------------------

def compose_sector_returns(
    direct_return: Decimal = Decimal("0"),
    spillover_return: Decimal = Decimal("0"),
    factor_return: Decimal = Decimal("0"),
    manual_adjustment: Decimal = Decimal("0"),
    composition_policy: str = "ADDITIVE" # ADDITIVE, COMPOUND
) -> Dict[str, Decimal]:
    """
    Combines direct, spillover, factor, and manual adjustments.
    Enforces scenario price return boundary R >= -1.0 (-100%).
    """
    if composition_policy.upper() == "COMPOUND":
        # (1 + R_total) = (1 + R_dir) * (1 + R_spill) * (1 + R_fac) * (1 + R_man)
        factor = (
            (Decimal("1.0") + direct_return) *
            (Decimal("1.0") + spillover_return) *
            (Decimal("1.0") + factor_return) *
            (Decimal("1.0") + manual_adjustment)
        )
        total_r = factor - Decimal("1.0")
    else:
        # Default additive composition
        total_r = direct_return + spillover_return + factor_return + manual_adjustment

    if total_r < Decimal("-1.0"):
        total_r = Decimal("-1.0")

    return {
        "direct_return": direct_return.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
        "spillover_return": spillover_return.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
        "factor_return": factor_return.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
        "manual_adjustment": manual_adjustment.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
        "final_scenario_return": total_r.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
    }


# -------------------------------------------------------------------------
# 4. Multi-Currency Conversion
# -------------------------------------------------------------------------

def convert_to_base_currency(
    local_return: Decimal,
    fx_return: Optional[Decimal] = None
) -> Decimal:
    """
    Converts local instrument return into portfolio base currency return:
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

def revalue_sector_position(
    signed_quantity: Decimal,
    baseline_price: Decimal,
    final_return: Decimal,
    baseline_nav: Decimal
) -> Dict[str, Decimal]:
    """
    Position revaluation under sector shock:
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


def compute_portfolio_sector_revaluation(
    baseline_nav: Decimal,
    position_revaluations: List[Dict[str, Decimal]]
) -> Dict[str, Decimal]:
    """
    Aggregates position revaluations:
    PnL_{portfolio} = sum PnL_i
    NAV_s = NAV_0 + PnL_{portfolio}
    Loss_{portfolio} = max(0, -PnL_{portfolio})
    Return_{portfolio} = PnL_{portfolio} / NAV_0
    """
    total_pnl = sum([p["scenario_pnl"] for p in position_revaluations], Decimal("0"))
    total_gross = sum([abs(p["baseline_market_value"]) for p in position_revaluations], Decimal("0"))
    total_net = sum([p["baseline_market_value"] for p in position_revaluations], Decimal("0"))

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
        "gross_exposure": total_gross.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "net_exposure": total_net.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    }


# -------------------------------------------------------------------------
# 6. Exposure Coverage & Attribution Decomposition
# -------------------------------------------------------------------------

def compute_sector_coverage_metrics(
    positions_data: List[Dict[str, Any]]
) -> Dict[str, Decimal]:
    """
    Exposure-weighted coverage using absolute market value:
    - classification_coverage: classified holdings / total
    - direct_coverage: directly shocked holdings / total
    - spillover_coverage: spillover affected holdings / total
    - sensitivity_coverage: valid sensitivity / total
    """
    total_abs_mv = Decimal("0")
    class_abs_mv = Decimal("0")
    direct_abs_mv = Decimal("0")
    spill_abs_mv = Decimal("0")
    sens_abs_mv = Decimal("0")

    for p in positions_data:
        mv = abs(Decimal(str(p.get("baseline_market_value", "0"))))
        total_abs_mv += mv
        if p.get("is_classified"):
            class_abs_mv += mv
        if p.get("is_directly_shocked"):
            direct_abs_mv += mv
        if p.get("is_spillover_affected"):
            spill_abs_mv += mv
        if p.get("is_sensitivity_valid"):
            sens_abs_mv += mv

    if total_abs_mv <= Decimal("0"):
        return {
            "classification_coverage": Decimal("1.0000"),
            "direct_coverage": Decimal("1.0000"),
            "spillover_coverage": Decimal("1.0000"),
            "sensitivity_coverage": Decimal("1.0000")
        }

    return {
        "classification_coverage": (class_abs_mv / total_abs_mv).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        "direct_coverage": (direct_abs_mv / total_abs_mv).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        "spillover_coverage": (spill_abs_mv / total_abs_mv).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        "sensitivity_coverage": (sens_abs_mv / total_abs_mv).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    }


def decompose_sector_impacts(
    baseline_market_value: Decimal,
    direct_return: Decimal,
    spillover_return: Decimal,
    factor_return: Decimal,
    manual_adjustment: Decimal
) -> Dict[str, Decimal]:
    """
    Decomposes PnL into component impacts:
    PnL_direct = MV_0 * R_dir
    PnL_spillover = MV_0 * R_spill
    PnL_factor = MV_0 * R_fac
    PnL_manual = MV_0 * R_man
    """
    pnl_dir = baseline_market_value * direct_return
    pnl_spill = baseline_market_value * spillover_return
    pnl_fac = baseline_market_value * factor_return
    pnl_man = baseline_market_value * manual_adjustment
    total_decomp = pnl_dir + pnl_spill + pnl_fac + pnl_man

    return {
        "direct_impact": pnl_dir.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "spillover_impact": pnl_spill.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "factor_impact": pnl_fac.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "manual_impact": pnl_man.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "total_impact": total_decomp.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    }
