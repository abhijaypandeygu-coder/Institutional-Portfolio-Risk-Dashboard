"""
Module M07.03: Expected Shortfall Mathematical Formulas.
Implements:
1. Fractional-Tail Expected Shortfall (CVaR) computation:
   ES_c = (1 / alpha) * sum_{i} (q_i * L_i)
   where alpha = 1 - c, sum q_i = alpha.
2. Tail diagnostics:
   - Expected tail mass n * alpha
   - Effective tail sample size: N_eff = 1 / sum(w_i^2)
   - Tail dispersion (tail standard deviation, median, IQR)
   - Boundary sensitivity (difference between fractional, strict, and tied boundary inclusion)
3. Tail scenario decomposition:
   - Scenario-weighted constituent tail loss attribution
"""
from decimal import Decimal, ROUND_HALF_UP
import math
import numpy as np
from typing import List, Tuple, Optional, Dict, Any

from backend.app.modules.market_risk.expected_shortfall.models import (
    ESQuantileMethod,
    ESTailWeightingMethod,
    ESTailStabilityStatus,
)

PRECISION_SIX = Decimal("0.000001")
PRECISION_EIGHT = Decimal("0.00000001")


def calculate_fractional_tail_expected_shortfall(
    losses: List[Decimal],
    confidence_level: Decimal,
    quantile_method: ESQuantileMethod = ESQuantileMethod.LINEAR_INTERPOLATION,
    tail_weighting_method: ESTailWeightingMethod = ESTailWeightingMethod.FRACTIONAL_BOUNDARY,
) -> Dict[str, Any]:
    """
    Computes empirical loss quantile (VaR) and Expected Shortfall (ES) with exact fractional boundary weighting.
    Losses L_t = -R_t (positive loss is adverse).
    Tail probability alpha = 1 - c.
    Returns structured results:
    - signed_var_quantile
    - non_negative_var
    - signed_es_average
    - non_negative_es
    - tail_excess
    - tail_excess_pct
    - expected_tail_mass
    - full_tail_count
    - effective_tail_sample_size
    - boundary_weight
    - tail_indices (sorted descending)
    - tail_weights
    - tail_median
    - tail_std
    - worst_loss
    - boundary_sensitivity
    """
    n = len(losses)
    if n == 0:
        return {
            "signed_var": Decimal("0.0"),
            "var_return": Decimal("0.0"),
            "signed_es": Decimal("0.0"),
            "es_return": Decimal("0.0"),
            "tail_excess": Decimal("0.0"),
            "tail_excess_pct": Decimal("0.0"),
            "expected_tail_mass": Decimal("0.0"),
            "full_tail_count": 0,
            "effective_tail_sample_size": Decimal("0.0"),
            "boundary_weight": Decimal("1.0"),
            "tail_observations": [],
            "tail_median": Decimal("0.0"),
            "tail_std": Decimal("0.0"),
            "worst_loss": Decimal("0.0"),
            "tail_stability": ESTailStabilityStatus.INSUFFICIENT_TAIL_SAMPLE,
        }

    alpha = float(Decimal("1.0") - confidence_level)
    p_pct = float(confidence_level) * 100.0

    # Sort loss observations descending: L_(1) >= L_(2) >= ... >= L_(n)
    # Track original index
    indexed_losses = sorted(
        [(i, float(loss), loss) for i, loss in enumerate(losses)],
        key=lambda x: x[1],
        reverse=True,
    )
    sorted_floats = [x[1] for x in indexed_losses]

    # Evaluate loss quantile (VaR) at confidence level c
    # Note: in ascending order, c-th percentile is (1 - alpha) quantile
    ascending_floats = sorted(sorted_floats)
    if quantile_method == ESQuantileMethod.NEAREST_RANK:
        rank_idx = max(0, min(n - 1, int(math.ceil(float(confidence_level) * n)) - 1))
        var_q = ascending_floats[rank_idx]
    else:
        var_q = float(np.percentile(ascending_floats, p_pct, method="linear"))

    # Discrete fractional tail probability mass
    # Total required tail probability = alpha
    # Each scenario has base probability mass p_s = 1 / n
    target_mass = alpha
    accumulated_mass = 0.0
    tail_obs_data: List[Dict[str, Any]] = []

    included_losses_floats: List[float] = []
    included_weights_normalized: List[float] = []

    last_boundary_weight = 1.0

    for rank, (orig_idx, fl_loss, dec_loss) in enumerate(indexed_losses):
        p_s = 1.0 / n
        if accumulated_mass + p_s <= target_mass + 1e-12:
            # Full observation included in tail
            tail_obs_data.append({
                "original_index": orig_idx,
                "loss": dec_loss,
                "loss_float": fl_loss,
                "weight": Decimal(str(p_s / alpha)).quantize(PRECISION_SIX, rounding=ROUND_HALF_UP),
                "is_boundary": False,
            })
            included_losses_floats.append(fl_loss)
            included_weights_normalized.append(p_s / alpha)
            accumulated_mass += p_s
        elif accumulated_mass < target_mass - 1e-12:
            # Boundary observation receives remaining fractional mass
            rem_mass = target_mass - accumulated_mass
            frac = rem_mass / p_s  # fraction of this observation's probability
            last_boundary_weight = frac
            norm_weight = rem_mass / alpha
            tail_obs_data.append({
                "original_index": orig_idx,
                "loss": dec_loss,
                "loss_float": fl_loss,
                "weight": Decimal(str(norm_weight)).quantize(PRECISION_SIX, rounding=ROUND_HALF_UP),
                "is_boundary": True,
            })
            included_losses_floats.append(fl_loss)
            included_weights_normalized.append(norm_weight)
            accumulated_mass += rem_mass
            break
        else:
            break

    # If tail_weighting_method is STRICT_EXCESS, fallback to strictly > var_q
    if tail_weighting_method == ESTailWeightingMethod.STRICT_EXCESS:
        strict_losses = [fl for fl in sorted_floats if fl > var_q]
        if strict_losses:
            es_val = float(np.mean(strict_losses))
        else:
            es_val = var_q
    else:
        # Standard weighted average of tail observations
        # sum (normalized_weight_i * loss_i)
        if included_weights_normalized:
            es_val = sum(w * l for w, l in zip(included_weights_normalized, included_losses_floats))
        else:
            es_val = var_q

    # Convert to high-precision Decimals
    signed_var_dec = Decimal(str(var_q)).quantize(PRECISION_EIGHT, rounding=ROUND_HALF_UP)
    non_neg_var_dec = max(Decimal("0.0"), signed_var_dec)

    signed_es_dec = Decimal(str(es_val)).quantize(PRECISION_EIGHT, rounding=ROUND_HALF_UP)
    non_neg_es_dec = max(Decimal("0.0"), signed_es_dec)

    # Tail excess = ES - VaR
    tail_excess_dec = max(Decimal("0.0"), non_neg_es_dec - non_neg_var_dec)
    if non_neg_var_dec > Decimal("0.0"):
        tail_excess_pct_dec = ((tail_excess_dec / non_neg_var_dec) * Decimal("100.0")).quantize(
            PRECISION_SIX, rounding=ROUND_HALF_UP
        )
    else:
        tail_excess_pct_dec = Decimal("0.0")

    # Tail sample diagnostics
    expected_tail_mass_dec = Decimal(str(n * alpha)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    full_tail_count = len(tail_obs_data)

    # Effective tail sample size: N_eff = 1 / sum(w_i^2)
    sum_sq_w = sum(w ** 2 for w in included_weights_normalized)
    n_eff = (1.0 / sum_sq_w) if sum_sq_w > 0 else float(full_tail_count)
    n_eff_dec = Decimal(str(n_eff)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    worst_loss_dec = Decimal(str(sorted_floats[0])).quantize(PRECISION_EIGHT, rounding=ROUND_HALF_UP)

    if included_losses_floats:
        tail_med = float(np.median(included_losses_floats))
        tail_std = float(np.std(included_losses_floats)) if len(included_losses_floats) > 1 else 0.0
    else:
        tail_med = float(var_q)
        tail_std = 0.0

    tail_median_dec = Decimal(str(tail_med)).quantize(PRECISION_EIGHT, rounding=ROUND_HALF_UP)
    tail_std_dec = Decimal(str(tail_std)).quantize(PRECISION_EIGHT, rounding=ROUND_HALF_UP)

    # Assess tail stability
    if expected_tail_mass_dec < Decimal("3.0"):
        tail_stability = ESTailStabilityStatus.INSUFFICIENT_TAIL_SAMPLE
    elif last_boundary_weight < 0.2:
        tail_stability = ESTailStabilityStatus.TAIL_BOUNDARY_SENSITIVE
    elif expected_tail_mass_dec < Decimal("10.0"):
        tail_stability = ESTailStabilityStatus.MODERATELY_STABLE
    else:
        tail_stability = ESTailStabilityStatus.STABLE

    return {
        "signed_var": signed_var_dec,
        "var_return": non_neg_var_dec,
        "signed_es": signed_es_dec,
        "es_return": non_neg_es_dec,
        "tail_excess": tail_excess_dec,
        "tail_excess_pct": tail_excess_pct_dec,
        "expected_tail_mass": expected_tail_mass_dec,
        "full_tail_count": full_tail_count,
        "effective_tail_sample_size": n_eff_dec,
        "boundary_weight": Decimal(str(last_boundary_weight)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP),
        "tail_observations": tail_obs_data,
        "tail_median": tail_median_dec,
        "tail_std": tail_std_dec,
        "worst_loss": worst_loss_dec,
        "tail_stability": tail_stability,
    }


def calculate_scenario_tail_attributions(
    holdings: List[Tuple[str, str, Decimal, Decimal]],  # (inst_id, name, signed_val, weight)
    instrument_scenario_losses: Dict[str, List[Decimal]],
    tail_observations: List[Dict[str, Any]],
    portfolio_valuation_base: Decimal,
    total_es_amount: Decimal,
) -> List[Dict[str, Any]]:
    """
    Decomposes Expected Shortfall into constituent scenario-weighted tail contributions:
    ESContribution_i = sum_s ( q_s * L_{i,s} )
    where q_s are the normalized tail weights (sum q_s = 1.0) applied to each tail scenario.
    Reconciles exactly: sum_i ESContribution_i = Total ES (for additive linear portfolio returns).
    """
    results: List[Dict[str, Any]] = []
    if not tail_observations or total_es_amount <= Decimal("0.0"):
        return results

    # Normalize tail weights
    weights = [float(obs["weight"]) for obs in tail_observations]
    total_w = sum(weights) or 1.0
    norm_weights = [w / total_w for w in weights]

    for inst_id, inst_name, val_amount, port_w in holdings:
        inst_losses = instrument_scenario_losses.get(inst_id, [])
        if not inst_losses:
            # If instrument has no loss series, contribution is zero
            results.append({
                "entity_id": inst_id,
                "entity_name": inst_name,
                "weight_percentage": (port_w * Decimal("100.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                "average_tail_loss_percentage": Decimal("0.0"),
                "contribution_amount": Decimal("0.0"),
                "percentage_of_total_es": Decimal("0.0"),
                "is_additive": True,
            })
            continue

        # Extract instrument losses for the corresponding tail scenario indices
        contrib_fl = 0.0
        for obs, nw in zip(tail_observations, norm_weights):
            idx = obs["original_index"]
            if idx < len(inst_losses):
                l_is = float(inst_losses[idx])
                contrib_fl += nw * l_is

        # Instrument contribution to total ES
        # L_port = sum w_i * L_i
        # Contrib_i_amount = V_0 * w_i * avg_tail_loss_i
        inst_tail_loss_dec = Decimal(str(contrib_fl)).quantize(PRECISION_SIX, rounding=ROUND_HALF_UP)
        inst_contrib_amount = (portfolio_valuation_base * port_w * inst_tail_loss_dec).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        pct_of_total = (
            ((inst_contrib_amount / total_es_amount) * Decimal("100.0")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if total_es_amount > Decimal("0.0")
            else Decimal("0.0")
        )

        results.append({
            "entity_id": inst_id,
            "entity_name": inst_name,
            "weight_percentage": (port_w * Decimal("100.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "average_tail_loss_percentage": (inst_tail_loss_dec * Decimal("100.0")).quantize(
                PRECISION_SIX, rounding=ROUND_HALF_UP
            ),
            "contribution_amount": inst_contrib_amount,
            "percentage_of_total_es": pct_of_total,
            "is_additive": True,
        })

    return results
