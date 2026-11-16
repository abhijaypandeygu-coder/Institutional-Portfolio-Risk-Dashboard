"""
Mathematical and analytical calculation engine for M10.09 Stress Loss Attribution.
Implements:
1. Position-level stressed P&L and positive loss contribution with price & FX decomposition.
2. Sector and industry aggregation with unclassified handling.
3. Systematic factor shock attribution (View B: Economic / Factor Attribution).
4. Controlled combined-shock interaction effect estimation: I_AB = Y(A,B) - Y(A,0) - Y(0,B) + Y(0,0).
5. Concentration metrics: HHI, effective contributor count (N_effective), Top-N gross loss drivers.
6. Reconciliation residual tracking: epsilon = Delta V - sum(C_i).
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Tuple, Optional
import numpy as np


def compute_position_pnl_and_decomposition(
    signed_quantity: Decimal,
    baseline_price: Decimal,
    stressed_price: Decimal,
    baseline_fx: Decimal = Decimal("1.0"),
    stressed_fx: Decimal = Decimal("1.0"),
    liquidity_cost: Decimal = Decimal("0.0"),
    fees_and_adjustments: Decimal = Decimal("0.0")
) -> Dict[str, Decimal]:
    """
    Computes position market values and exact arithmetic decomposition:
    MV_0 = q * P_0 * FX_0
    MV_s = q * P_s * FX_s
    Delta MV = q * (P_s - P_0) * FX_0 + q * P_s * (FX_s - FX_0)
    Total PnL = Delta MV - liquidity_cost - fees_and_adjustments
    Loss Contribution = -Total PnL (positive loss convention)
    """
    mv_0 = signed_quantity * baseline_price * baseline_fx
    mv_s = signed_quantity * stressed_price * stressed_fx

    price_effect = signed_quantity * (stressed_price - baseline_price) * baseline_fx
    fx_effect = signed_quantity * stressed_price * (stressed_fx - baseline_fx)
    delta_mv = price_effect + fx_effect

    total_pnl = delta_mv - liquidity_cost - fees_and_adjustments
    loss_contribution = -total_pnl

    return {
        "baseline_market_value": mv_0.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        "stressed_market_value": mv_s.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        "price_pnl": price_effect.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        "fx_pnl": fx_effect.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        "liquidity_cost": liquidity_cost.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        "other_adjustments": fees_and_adjustments.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        "total_pnl": total_pnl.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        "loss_contribution": loss_contribution.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    }


def aggregate_by_dimension(
    positions_data: List[Dict[str, Any]],
    dimension_key: str = "sector",
    total_portfolio_pnl: Optional[Decimal] = None
) -> List[Dict[str, Any]]:
    """
    Aggregates position-level stressed P&L into sectors, industries, or asset groups.
    Handles 'UNCLASSIFIED' for missing classification keys.
    """
    grouped: Dict[str, Dict[str, Any]] = {}

    for pos in positions_data:
        dim_val = str(pos.get(dimension_key) or "UNCLASSIFIED")
        if dim_val not in grouped:
            grouped[dim_val] = {
                "dimension_name": dim_val,
                "holding_count": 0,
                "baseline_market_value": Decimal("0"),
                "stressed_market_value": Decimal("0"),
                "total_pnl": Decimal("0"),
                "loss_contribution": Decimal("0"),
            }

        grouped[dim_val]["holding_count"] += 1
        grouped[dim_val]["baseline_market_value"] += pos.get("baseline_market_value", Decimal("0"))
        grouped[dim_val]["stressed_market_value"] += pos.get("stressed_market_value", Decimal("0"))
        grouped[dim_val]["total_pnl"] += pos.get("total_pnl", Decimal("0"))
        grouped[dim_val]["loss_contribution"] += pos.get("loss_contribution", Decimal("0"))

    results = []
    tot_pnl = total_portfolio_pnl if (total_portfolio_pnl and abs(total_portfolio_pnl) > 0) else None

    for dim_val, data in sorted(grouped.items(), key=lambda x: x[1]["loss_contribution"], reverse=True):
        pnl = data["total_pnl"]
        contrib_pct = (pnl / tot_pnl * Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) if tot_pnl else Decimal("0")
        results.append({
            "dimension_name": dim_val,
            "holding_count": data["holding_count"],
            "baseline_market_value": data["baseline_market_value"].quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
            "stressed_market_value": data["stressed_market_value"].quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
            "total_pnl": pnl.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
            "loss_contribution": data["loss_contribution"].quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
            "contribution_percentage": contrib_pct
        })

    return results


def compute_factor_shock_attribution(
    factor_exposures: Dict[str, float],   # beta_p,k
    factor_shocks: Dict[str, float],      # f_k
    portfolio_baseline_nav: Decimal
) -> Tuple[List[Dict[str, Any]], Decimal]:
    """
    Computes economic factor attribution (View B):
    Monetary factor effect = MV_0 * beta_k * f_k.
    Model residual = Total Stressed Return - sum(beta_k * f_k).
    """
    nav_float = float(portfolio_baseline_nav)
    factor_results = []
    total_explained_factor_pnl = Decimal("0")

    all_factors = sorted(set(factor_exposures.keys()) & set(factor_shocks.keys()))
    for f in all_factors:
        beta = factor_exposures[f]
        shock = factor_shocks[f]
        factor_ret = beta * shock
        monetary_pnl = Decimal(str(round(nav_float * factor_ret, 4)))
        total_explained_factor_pnl += monetary_pnl

        factor_results.append({
            "factor_name": f,
            "factor_shock": float(round(shock, 6)),
            "factor_exposure": float(round(beta, 6)),
            "contribution_value": monetary_pnl,
            "loss_contribution": -monetary_pnl
        })

    return factor_results, total_explained_factor_pnl


def compute_interaction_effect(
    y_both: Decimal,   # Y(A, B)
    y_only_a: Decimal, # Y(A, 0)
    y_only_b: Decimal, # Y(0, B)
    y_baseline: Decimal# Y(0, 0)
) -> Decimal:
    """
    Computes controlled combined-shock interaction effect:
    I_AB = Y(A, B) - Y(A, 0) - Y(0, B) + Y(0, 0)
    """
    return y_both - y_only_a - y_only_b + y_baseline


def compute_loss_concentration_metrics(
    loss_contributions: List[Decimal]
) -> Dict[str, float]:
    """
    Computes concentration metrics across positive loss contributors:
    w_i = L_i / sum(L_j) for L_i > 0.
    HHI = sum(w_i^2).
    N_effective = 1 / HHI.
    """
    positive_losses = [float(l) for l in loss_contributions if l > Decimal("0")]
    tot_loss = sum(positive_losses)

    if tot_loss <= 1e-12 or len(positive_losses) == 0:
        return {"hhi": 0.0, "effective_contributor_count": 0.0, "positive_contributor_count": 0}

    weights = np.array(positive_losses) / tot_loss
    hhi = float(np.sum(weights ** 2))
    n_eff = float(1.0 / hhi) if hhi > 1e-12 else 0.0

    return {
        "hhi": float(round(hhi, 4)),
        "effective_contributor_count": float(round(n_eff, 2)),
        "positive_contributor_count": len(positive_losses)
    }


def compute_reconciliation_residual(
    authoritative_pnl: Decimal,
    sum_explained_pnl: Decimal,
    abs_tolerance: Decimal = Decimal("0.01"),
    rel_tolerance: Decimal = Decimal("0.0001")
) -> Dict[str, Any]:
    """
    Reconciles attribution to authoritative stressed P&L:
    Residual = Authoritative_PnL - Sum_Explained_PnL
    Is Reconciled = |Residual| <= max(abs_tolerance, rel_tolerance * |Authoritative_PnL|)
    """
    residual = authoritative_pnl - sum_explained_pnl
    threshold = max(abs_tolerance, rel_tolerance * abs(authoritative_pnl))
    is_reconciled = abs(residual) <= threshold

    return {
        "authoritative_total_pnl": authoritative_pnl,
        "explained_pnl": sum_explained_pnl,
        "residual_amount": residual.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        "is_reconciled": bool(is_reconciled),
        "reconciliation_status": "RECONCILED" if is_reconciled else "UNRECONCILED"
    }

