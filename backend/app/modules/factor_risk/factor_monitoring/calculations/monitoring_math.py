"""
M08.08 Factor Monitoring Mathematical & Analytical Engine.
Implements:
1. Exposure Drift Calculations:
   - Signed drift: Delta beta = beta_current - beta_reference
   - Absolute drift magnitude: |beta_current - beta_reference|
   - Percentage drift with near-zero guardrail: (Delta beta / |beta_ref|) * 100
   - Standardized exposure drift: Delta beta^{1sigma} = beta_current * sigma_F - beta_ref * sigma_F
   - Sign reversal identification & orientation analysis
   - Symmetric holding weight vs. loading drift decomposition:
     Delta(w_i * beta_i) = Delta w_i * (beta_t + beta_{t-1})/2 + Delta beta_i * (w_t + w_{t-1})/2
2. Factor Concentration Analytics:
   - Exposure-based concentration: absolute standardized exposure share p_k^{exp} = |e_k| / sum(|e_j|)
   - Exposure HHI = sum((p_k^{exp})^2) and Effective Factor Count N_eff^{exp} = 1 / HHI
   - Risk-contribution-based concentration: p_k^{risk} = |RC_k| / sum(|RC_j|)
   - Risk contribution HHI = sum((p_k^{risk})^2) and Effective Factor Count N_eff^{risk} = 1 / HHI
   - Top-1, Top-2, Top-3 factor dependence shares
3. Threshold Monitoring, Utilization & Headroom:
   - Utilization calculation: (Current / Limit) * 100 with directional and range bounds
   - Headroom calculation: Limit - Current
   - Breach state evaluation: NORMAL, WARNING, BREACH, CRITICAL_BREACH, RECOVERY_PENDING, RECOVERED
   - Hysteresis & persistence verification
4. Trend Analysis & Moving Statistics:
   - Rolling mean, min, max, std, trend direction, consecutive increases/decreases
"""

import math
from typing import Dict, List, Optional, Tuple, Any
import numpy as np


# ==============================================================================
# 1. EXPOSURE DRIFT CALCULATIONS
# ==============================================================================

def compute_factor_exposure_drift(
    current_beta: float,
    reference_beta: float,
    factor_volatility: Optional[float] = None,
    near_zero_tolerance: float = 1e-4,
) -> Dict[str, Any]:
    """
    Computes signed drift, absolute drift, percentage drift, standardized drift,
    and sign transition classifications for an individual factor.
    """
    curr = float(current_beta)
    ref = float(reference_beta)

    signed_drift = curr - ref
    abs_drift = abs(signed_drift)

    # Percentage drift with strict near-zero reference guardrail
    if abs(ref) < near_zero_tolerance:
        pct_drift = None
        pct_defined = False
        pct_reason = "PERCENTAGE_DRIFT_UNDEFINED (Reference exposure near zero)"
    else:
        pct_drift = (signed_drift / abs(ref)) * 100.0
        pct_defined = True
        pct_reason = None

    # Standardized exposure drift if factor volatility is available
    if factor_volatility is not None and factor_volatility > 0:
        std_curr = curr * float(factor_volatility)
        std_ref = ref * float(factor_volatility)
        std_drift = std_curr - std_ref
    else:
        std_curr = None
        std_ref = None
        std_drift = None

    # Sign transition detection
    sign_curr = 1 if curr > near_zero_tolerance else (-1 if curr < -near_zero_tolerance else 0)
    sign_ref = 1 if ref > near_zero_tolerance else (-1 if ref < -near_zero_tolerance else 0)

    is_sign_reversal = False
    sign_change_desc = "UNCHANGED"
    if sign_curr * sign_ref < 0:
        is_sign_reversal = True
        sign_change_desc = "POSITIVE_TO_NEGATIVE" if sign_ref > 0 else "NEGATIVE_TO_POSITIVE"
    elif sign_ref != 0 and sign_curr == 0:
        sign_change_desc = "MOVED_TO_NEUTRAL"
    elif sign_ref == 0 and sign_curr != 0:
        sign_change_desc = "MOVED_FROM_NEUTRAL"

    # Drift magnitude classification
    if abs_drift < 0.05:
        drift_class = "WITHIN_TOLERANCE"
    elif abs_drift < 0.15:
        drift_class = "LOW_DRIFT"
    elif abs_drift < 0.30:
        drift_class = "MODERATE_DRIFT"
    elif abs_drift < 0.50:
        drift_class = "HIGH_DRIFT"
    else:
        drift_class = "CRITICAL_DRIFT"

    if is_sign_reversal:
        drift_class = "SIGN_REVERSAL"

    return {
        "current_exposure": curr,
        "reference_exposure": ref,
        "signed_drift": signed_drift,
        "absolute_drift": abs_drift,
        "percentage_drift": pct_drift,
        "is_percentage_drift_defined": pct_defined,
        "percentage_drift_reason": pct_reason,
        "standardized_current_exposure": std_curr,
        "standardized_reference_exposure": std_ref,
        "standardized_drift": std_drift,
        "is_sign_reversal": is_sign_reversal,
        "sign_change_description": sign_change_desc,
        "drift_classification": drift_class,
    }


def decompose_exposure_drift_holdings_vs_loadings(
    current_weights: Dict[str, float],
    previous_weights: Dict[str, float],
    current_loadings: Dict[str, float],
    previous_loadings: Dict[str, float],
) -> Dict[str, Any]:
    """
    Decomposes portfolio factor exposure change into:
    1. Weight change effect: Delta w_i * (beta_{i,t} + beta_{i,t-1}) / 2
    2. Sensitivity/Loading change effect: Delta beta_i * (w_{i,t} + w_{i,t-1}) / 2
    3. Entry effects for newly added instruments
    4. Exit effects for removed instruments
    Guarantees exact additive reconciliation to observed exposure drift:
    Delta beta_p = Weight_Effect + Loading_Effect + Entry_Effect + Exit_Effect
    """
    all_instruments = set(current_weights.keys()).union(set(previous_weights.keys()))

    total_weight_effect = 0.0
    total_loading_effect = 0.0
    total_entry_effect = 0.0
    total_exit_effect = 0.0

    component_details = []

    for inst in sorted(list(all_instruments)):
        w_curr = current_weights.get(inst, 0.0)
        w_prev = previous_weights.get(inst, 0.0)
        b_curr = current_loadings.get(inst, 0.0)
        b_prev = previous_loadings.get(inst, 0.0)

        delta_w = w_curr - w_prev
        delta_b = b_curr - b_prev

        if inst in current_weights and inst in previous_weights:
            # Continuing holding: symmetric decomposition
            avg_b = (b_curr + b_prev) / 2.0
            avg_w = (w_curr + w_prev) / 2.0
            w_eff = delta_w * avg_b
            l_eff = delta_b * avg_w
            e_eff = 0.0
            x_eff = 0.0
            total_weight_effect += w_eff
            total_loading_effect += l_eff
        elif inst in current_weights and inst not in previous_weights:
            # New Entry
            w_eff = 0.0
            l_eff = 0.0
            e_eff = w_curr * b_curr
            x_eff = 0.0
            total_entry_effect += e_eff
        else:
            # Exited position
            w_eff = 0.0
            l_eff = 0.0
            e_eff = 0.0
            x_eff = - (w_prev * b_prev)
            total_exit_effect += x_eff

        component_details.append({
            "instrument_id": inst,
            "weight_current": w_curr,
            "weight_previous": w_prev,
            "loading_current": b_curr,
            "loading_previous": b_prev,
            "weight_effect": w_eff,
            "loading_effect": l_eff,
            "entry_effect": e_eff,
            "exit_effect": x_eff,
            "total_instrument_drift": (w_curr * b_curr) - (w_prev * b_prev),
        })

    prev_p_beta = sum(previous_weights[k] * previous_loadings.get(k, 0.0) for k in previous_weights)
    curr_p_beta = sum(current_weights[k] * current_loadings.get(k, 0.0) for k in current_weights)
    observed_drift = curr_p_beta - prev_p_beta
    reconciled_drift = total_weight_effect + total_loading_effect + total_entry_effect + total_exit_effect
    discrepancy = abs(observed_drift - reconciled_drift)

    return {
        "previous_portfolio_exposure": prev_p_beta,
        "current_portfolio_exposure": curr_p_beta,
        "observed_exposure_drift": observed_drift,
        "reconciled_exposure_drift": reconciled_drift,
        "weight_effect": total_weight_effect,
        "loading_effect": total_loading_effect,
        "entry_effect": total_entry_effect,
        "exit_effect": total_exit_effect,
        "reconciliation_discrepancy": discrepancy,
        "is_reconciled": bool(discrepancy < 1e-7),
        "components": component_details,
    }


# ==============================================================================
# 2. FACTOR CONCENTRATION ANALYTICS
# ==============================================================================

def compute_exposure_based_concentration(
    factor_loadings: Dict[str, float],
    factor_volatilities: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Computes absolute normalized exposure shares, Exposure HHI, and Effective Factor Count N_eff.
    e_k = beta_k * sigma_{F_k} (or raw |beta_k| if volatilities omitted, clearly flagged).
    p_k^{exposure} = |e_k| / sum_j |e_j|
    HHI_{exposure} = sum( (p_k^{exposure})^2 )
    N_{effective}^{exposure} = 1 / HHI_{exposure}
    """
    if not factor_loadings:
        return {
            "status": "CONCENTRATION_UNAVAILABLE",
            "reason": "No factor loadings provided",
            "hhi": None,
            "effective_factors": None,
            "shares": {},
            "top_1_share": None,
            "top_2_share": None,
            "top_3_share": None,
            "top_factor": None,
        }

    is_standardized = factor_volatilities is not None and all(k in factor_volatilities for k in factor_loadings)

    # Compute absolute exposure values
    abs_exposures = {}
    for k, beta in factor_loadings.items():
        if is_standardized:
            vol = factor_volatilities[k]
            abs_exposures[k] = abs(beta * vol)
        else:
            abs_exposures[k] = abs(beta)

    total_abs_exposure = sum(abs_exposures.values())

    if total_abs_exposure < 1e-12:
        return {
            "status": "CONCENTRATION_UNAVAILABLE",
            "reason": "Total absolute factor exposure is zero or negligible",
            "is_standardized": is_standardized,
            "hhi": None,
            "effective_factors": None,
            "shares": {k: 0.0 for k in factor_loadings},
            "top_1_share": None,
            "top_2_share": None,
            "top_3_share": None,
            "top_factor": None,
        }

    # Normalized exposure distribution shares
    shares = {k: abs_exposures[k] / total_abs_exposure for k in abs_exposures}
    hhi = float(sum(p ** 2 for p in shares.values()))
    n_eff = float(1.0 / hhi) if hhi > 0 else 0.0

    # Top-N shares
    sorted_shares = sorted(shares.items(), key=lambda x: x[1], reverse=True)
    top_1_share = sorted_shares[0][1] if len(sorted_shares) >= 1 else 0.0
    top_2_share = sum(s[1] for s in sorted_shares[:2]) if len(sorted_shares) >= 2 else top_1_share
    top_3_share = sum(s[1] for s in sorted_shares[:3]) if len(sorted_shares) >= 3 else top_2_share
    top_factor = sorted_shares[0][0] if sorted_shares else None

    # Classification
    if top_1_share > 0.70 or n_eff < 1.5:
        status = "SINGLE_FACTOR_DEPENDENCE"
    elif hhi > 0.40 or n_eff < 2.5:
        status = "HIGH_FACTOR_CONCENTRATION"
    elif hhi > 0.25:
        status = "MODERATE_FACTOR_CONCENTRATION"
    else:
        status = "LOW_FACTOR_CONCENTRATION"

    return {
        "status": status,
        "is_standardized": is_standardized,
        "measurement_basis": "STANDARDIZED_EXPOSURE" if is_standardized else "RAW_LOADING",
        "hhi": hhi,
        "effective_factors": n_eff,
        "shares": shares,
        "top_1_share": top_1_share,
        "top_2_share": top_2_share,
        "top_3_share": top_3_share,
        "top_factor": top_factor,
        "factor_count": len(factor_loadings),
    }


def compute_risk_contribution_based_concentration(
    factor_risk_contributions: Dict[str, float],
) -> Dict[str, Any]:
    """
    Computes absolute risk contribution shares, Risk HHI, and Effective Risk Factor Count N_eff.
    Preserves original signed Euler risk contributions.
    p_k^{risk} = |RC_k^{risk}| / sum_j |RC_j^{risk}|
    HHI_{risk} = sum( (p_k^{risk})^2 )
    N_{effective}^{risk} = 1 / HHI_{risk}
    """
    if not factor_risk_contributions:
        return {
            "status": "CONCENTRATION_UNAVAILABLE",
            "reason": "No factor risk contributions provided",
            "hhi": None,
            "effective_factors": None,
            "shares": {},
            "signed_contributions": {},
            "top_1_share": None,
            "top_2_share": None,
            "top_3_share": None,
            "top_risk_driver": None,
        }

    abs_contributions = {k: abs(v) for k, v in factor_risk_contributions.items()}
    total_abs_rc = sum(abs_contributions.values())

    if total_abs_rc < 1e-12:
        return {
            "status": "CONCENTRATION_UNAVAILABLE",
            "reason": "Total absolute risk contribution is zero or negligible",
            "hhi": None,
            "effective_factors": None,
            "shares": {k: 0.0 for k in factor_risk_contributions},
            "signed_contributions": factor_risk_contributions,
            "top_1_share": None,
            "top_2_share": None,
            "top_3_share": None,
            "top_risk_driver": None,
        }

    shares = {k: abs_contributions[k] / total_abs_rc for k in abs_contributions}
    hhi = float(sum(p ** 2 for p in shares.values()))
    n_eff = float(1.0 / hhi) if hhi > 0 else 0.0

    sorted_shares = sorted(shares.items(), key=lambda x: x[1], reverse=True)
    top_1_share = sorted_shares[0][1] if len(sorted_shares) >= 1 else 0.0
    top_2_share = sum(s[1] for s in sorted_shares[:2]) if len(sorted_shares) >= 2 else top_1_share
    top_3_share = sum(s[1] for s in sorted_shares[:3]) if len(sorted_shares) >= 3 else top_2_share
    top_driver = sorted_shares[0][0] if sorted_shares else None

    # Classification
    if top_1_share > 0.70 or n_eff < 1.5:
        status = "SINGLE_FACTOR_DEPENDENCE"
    elif hhi > 0.45 or n_eff < 2.2:
        status = "HIGH_FACTOR_CONCENTRATION"
    elif hhi > 0.28:
        status = "MODERATE_FACTOR_CONCENTRATION"
    else:
        status = "LOW_FACTOR_CONCENTRATION"

    return {
        "status": status,
        "measurement_basis": "EULER_RISK_CONTRIBUTION",
        "hhi": hhi,
        "effective_factors": n_eff,
        "shares": shares,
        "signed_contributions": factor_risk_contributions,
        "top_1_share": top_1_share,
        "top_2_share": top_2_share,
        "top_3_share": top_3_share,
        "top_risk_driver": top_driver,
        "factor_count": len(factor_risk_contributions),
    }


# ==============================================================================
# 3. THRESHOLD UTILIZATION, HEADROOM & EVALUATION
# ==============================================================================

def evaluate_threshold_metric(
    current_value: Optional[float],
    warning_threshold: Optional[float] = None,
    breach_threshold: Optional[float] = None,
    critical_threshold: Optional[float] = None,
    recovery_threshold: Optional[float] = None,
    min_boundary: Optional[float] = None,
    max_boundary: Optional[float] = None,
    consecutive_breach_count: int = 0,
    consecutive_recovery_count: int = 0,
    persistence_required: int = 1,
    recovery_required: int = 2,
    is_active_breach: bool = False,
) -> Dict[str, Any]:
    """
    Evaluates current metric value against boundaries and thresholds.
    Implements deterministic state transition, hysteresis, utilization, and headroom.
    States: NORMAL, WARNING, BREACH, CRITICAL_BREACH, RECOVERY_PENDING, RECOVERED, UNAVAILABLE.
    """
    if current_value is None:
        # Missing or unavailable measurement can NEVER clear an active breach
        return {
            "evaluation_status": "BREACH" if is_active_breach else "UNAVAILABLE",
            "utilization_percentage": None,
            "headroom": None,
            "is_breach": is_active_breach,
            "is_warning": False,
            "consecutive_breach_count": consecutive_breach_count,
            "consecutive_recovery_count": 0,
            "reason": "Measurement value is missing or undefined",
        }

    val = float(current_value)

    # Upper bound determination for utilization calculation
    limit = breach_threshold if breach_threshold is not None else max_boundary
    if limit is not None and abs(limit) > 1e-12:
        utilization = (abs(val) / abs(limit)) * 100.0
        headroom = limit - val
    else:
        utilization = None
        headroom = None

    # Check boundaries / thresholds
    is_crit = False
    is_brk = False
    is_warn = False

    if critical_threshold is not None and abs(val) >= abs(critical_threshold):
        is_crit = True
    elif breach_threshold is not None and abs(val) >= abs(breach_threshold):
        is_brk = True
    elif max_boundary is not None and val > max_boundary:
        is_brk = True
    elif min_boundary is not None and val < min_boundary:
        is_brk = True
    elif warning_threshold is not None and abs(val) >= abs(warning_threshold):
        is_warn = True

    # State transition & hysteresis logic
    new_consec_breach = consecutive_breach_count
    new_consec_recovery = consecutive_recovery_count

    if is_crit or is_brk:
        new_consec_breach += 1
        new_consec_recovery = 0
        if is_crit:
            status = "CRITICAL_BREACH"
        else:
            status = "BREACH" if new_consec_breach >= persistence_required else "PENDING_CONFIRMATION"
        active_breach = True
    elif is_active_breach:
        # Currently in active breach, check if below recovery threshold
        rec_thresh = recovery_threshold if recovery_threshold is not None else (breach_threshold * 0.90 if breach_threshold else None)
        if rec_thresh is not None and abs(val) <= abs(rec_thresh):
            new_consec_recovery += 1
            if new_consec_recovery >= recovery_required:
                status = "RECOVERED"
                active_breach = False
                new_consec_breach = 0
            else:
                status = "RECOVERY_PENDING"
                active_breach = True
        else:
            # Still above recovery threshold, breach persists
            status = "BREACH"
            active_breach = True
            new_consec_recovery = 0
    elif is_warn:
        status = "WARNING"
        active_breach = False
        new_consec_breach = 0
        new_consec_recovery = 0
    else:
        status = "NORMAL"
        active_breach = False
        new_consec_breach = 0
        new_consec_recovery = 0

    return {
        "evaluation_status": status,
        "current_value": val,
        "limit_value": limit,
        "utilization_percentage": utilization,
        "headroom": headroom,
        "is_breach": active_breach,
        "is_warning": (status == "WARNING"),
        "consecutive_breach_count": new_consec_breach,
        "consecutive_recovery_count": new_consec_recovery,
        "reason": None,
    }


# ==============================================================================
# 4. TREND CALCULATIONS & MOVING STATISTICS
# ==============================================================================

def compute_monitoring_trend_statistics(
    history_values: List[float],
) -> Dict[str, Any]:
    """
    Computes rolling mean, min, max, std, absolute delta, percentage delta,
    trend direction, and consecutive increase/decrease streaks.
    """
    if not history_values:
        return {
            "current_value": None,
            "previous_value": None,
            "absolute_change": None,
            "percentage_change": None,
            "rolling_mean": None,
            "rolling_min": None,
            "rolling_max": None,
            "rolling_std": None,
            "trend_direction": "FLAT",
            "consecutive_streak": 0,
        }

    arr = np.asarray(history_values, dtype=np.float64)
    curr = float(arr[-1])
    prev = float(arr[-2]) if len(arr) > 1 else curr

    delta = curr - prev
    pct_delta = (delta / abs(prev) * 100.0) if len(arr) > 1 and abs(prev) > 1e-4 else None

    # Trend direction & streak
    direction = "INCREASING" if delta > 1e-6 else ("DECREASING" if delta < -1e-6 else "FLAT")
    streak = 1
    if len(arr) > 1:
        diffs = np.diff(arr)
        if direction == "INCREASING":
            streak = int(np.sum(diffs[::-1] > 1e-6))
        elif direction == "DECREASING":
            streak = int(np.sum(diffs[::-1] < -1e-6))

    return {
        "current_value": curr,
        "previous_value": prev,
        "absolute_change": delta,
        "percentage_change": pct_delta,
        "rolling_mean": float(np.mean(arr)),
        "rolling_min": float(np.min(arr)),
        "rolling_max": float(np.max(arr)),
        "rolling_std": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
        "trend_direction": direction,
        "consecutive_streak": streak,
        "observation_count": len(arr),
    }

