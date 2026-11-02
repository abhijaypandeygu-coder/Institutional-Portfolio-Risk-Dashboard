"""
M08.04 Factor Attribution Mathematical & Econometric Calculation Engine.
Provides authoritative quantitative implementations for:
1. Single-period Factor Return Attribution (ex-ante lagged & ex-post explanatory)
2. Bottom-up vs. Direct Return Attribution with long/short signed weighting
3. Multi-period Carino Linking Engine (continuous limits for near-zero returns)
4. Factor Covariance Matrix construction, conditioning & positive-semidefinite (PSD) verification
5. Systematic Euler Risk Decomposition: Variance Contributions, Volatility Contributions, Marginal Risk
6. Total Modeled Risk with Factor-Residual Covariance interaction
7. Formal Attribution Reconciliation Bridge (Return & Risk reconciliation residuals)
"""
from typing import Dict, Any, List, Optional, Tuple
import math
import numpy as np
from scipy import stats

from backend.app.modules.factor_risk.factor_sensitivity.models import (
    StandardErrorMethod,
)


# ============================================================================
# 1. FACTOR RETURN ATTRIBUTION (SINGLE-PERIOD)
# ============================================================================

def compute_single_period_return_attribution(
    factor_sensitivities: Dict[str, float],
    factor_returns: Dict[str, float],
    realized_portfolio_return: float,
    risk_free_rate: float = 0.0,
    intercept: float = 0.0,
    is_excess_return_model: bool = True,
) -> Dict[str, Any]:
    """
    Computes single-period factor return attribution:
    Excess Return Model:
        R_{p,t} = R_{f,t} + alpha_p + sum_k (beta_{p,k} * F_{k,t}) + eps_{p,t}
    Total Return Model:
        R_{p,t} = alpha_p + sum_k (beta_{p,k} * F_{k,t}) + eps_{p,t}
    
    Args:
        factor_sensitivities: Dict mapping factor_code -> portfolio sensitivity beta
        factor_returns: Dict mapping factor_code -> realized factor return F_k
        realized_portfolio_return: Observed portfolio total return R_p
        risk_free_rate: Risk-free rate R_f for the period
        intercept: Model regression constant alpha
        is_excess_return_model: If True, decomposes excess return over R_f
    
    Returns:
        Dict containing component contributions, model residual, and total explained return.
    """
    factor_contributions = {}
    total_factor_contribution = 0.0

    for factor_code, beta in factor_sensitivities.items():
        f_ret = factor_returns.get(factor_code, 0.0)
        c_k = float(beta * f_ret)
        factor_contributions[factor_code] = {
            "factor_code": factor_code,
            "sensitivity": beta,
            "factor_return": f_ret,
            "contribution": c_k,
        }
        total_factor_contribution += c_k

    rf_contrib = risk_free_rate if is_excess_return_model else 0.0
    alpha_contrib = intercept

    # Model residual: eps = R_p - (R_f + alpha + sum(beta * F))
    explained_model_return = rf_contrib + alpha_contrib + total_factor_contribution
    model_residual = float(realized_portfolio_return - explained_model_return)

    # Attribution sum exactly reproduces realized return within machine epsilon
    total_reconciled = explained_model_return + model_residual
    reconciliation_residual = float(realized_portfolio_return - total_reconciled)

    return {
        "realized_portfolio_return": realized_portfolio_return,
        "risk_free_contribution": rf_contrib,
        "intercept_contribution": alpha_contrib,
        "factor_contributions": factor_contributions,
        "total_factor_contribution": total_factor_contribution,
        "model_residual": model_residual,
        "reconciliation_residual": reconciliation_residual,
        "total_attributed_return": total_reconciled,
        "is_excess_return_model": is_excess_return_model,
    }


def compute_bottom_up_instrument_attribution(
    instrument_weights: Dict[str, float],
    instrument_sensitivities: Dict[str, Dict[str, float]],
    factor_returns: Dict[str, float],
    instrument_returns: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Computes bottom-up factor return attribution from signed security holdings:
        C_{p,k} = sum_i w_i * beta_{i,k} * F_k
    Preserves signed weights for long and short positions.
    """
    factors = list(factor_returns.keys())
    instrument_contributions = {}
    aggregated_factor_contributions = {f: 0.0 for f in factors}
    total_covered_weight = 0.0
    total_absolute_weight = 0.0

    for inst_id, w in instrument_weights.items():
        total_absolute_weight += abs(w)
        betas = instrument_sensitivities.get(inst_id)
        if betas is None:
            continue
        total_covered_weight += abs(w)

        inst_contribs = {}
        for f in factors:
            b_ik = betas.get(f, 0.0)
            f_ret = factor_returns.get(f, 0.0)
            c_ik = float(w * b_ik * f_ret)
            inst_contribs[f] = c_ik
            aggregated_factor_contributions[f] += c_ik

        instrument_contributions[inst_id] = {
            "weight": w,
            "sensitivities": betas,
            "contributions": inst_contribs,
            "total_factor_contribution": sum(inst_contribs.values()),
        }

    coverage_pct = (total_covered_weight / total_absolute_weight * 100.0) if total_absolute_weight > 0 else 100.0

    return {
        "aggregated_factor_contributions": aggregated_factor_contributions,
        "total_bottom_up_factor_contribution": sum(aggregated_factor_contributions.values()),
        "instrument_contributions": instrument_contributions,
        "coverage_percentage": coverage_pct,
        "covered_weight": total_covered_weight,
        "total_absolute_weight": total_absolute_weight,
    }


# ============================================================================
# 2. MULTI-PERIOD CARINO LINKING ENGINE
# ============================================================================

def compute_carino_multi_period_linking(
    period_portfolio_returns: List[float],
    period_component_contributions: List[Dict[str, float]],
) -> Dict[str, Any]:
    """
    Implements exact Carino multi-period linking:
        R_cum = prod_{t=1}^T (1 + R_t) - 1
        k_t = ln(1 + R_t) / R_t   (with continuous limit k_t -> 1 as R_t -> 0)
        k = ln(1 + R_cum) / R_cum (with continuous limit k -> 1 as R_cum -> 0)
        C_{j,cum} = sum_{t=1}^T (k_t / k) * c_{j,t}
    
    Guarantees: sum_j C_{j,cum} == R_cum exactly within floating point tolerance.
    """
    T = len(period_portfolio_returns)
    if T == 0:
        return {
            "cumulative_portfolio_return": 0.0,
            "linked_component_contributions": {},
            "reconciliation_difference": 0.0,
        }

    # 1. Cumulative Compounded Return
    prod = 1.0
    for r in period_portfolio_returns:
        prod *= (1.0 + r)
    R_cum = prod - 1.0

    # 2. Carino Scaling Factor k for cumulative return
    if abs(R_cum) < 1e-12:
        k_cum = 1.0
    elif (1.0 + R_cum) <= 0:
        raise ValueError(f"Total loss boundary exceeded: 1 + R_cum = {1.0 + R_cum} <= 0")
    else:
        k_cum = math.log(1.0 + R_cum) / R_cum

    # 3. Period-specific scaling factors k_t
    k_t_list = []
    for r in period_portfolio_returns:
        if abs(r) < 1e-12:
            k_t = 1.0
        elif (1.0 + r) <= 0:
            raise ValueError(f"Total loss boundary exceeded in sub-period: 1 + r = {1.0 + r} <= 0")
        else:
            k_t = math.log(1.0 + r) / r
        k_t_list.append(k_t)

    # 4. Link each component across time
    # Collect all component keys across periods
    all_keys = set()
    for comp_dict in period_component_contributions:
        all_keys.update(comp_dict.keys())

    linked_contributions = {k: 0.0 for k in all_keys}
    for t in range(T):
        weight_t = k_t_list[t] / k_cum
        p_comps = period_component_contributions[t]
        for key in all_keys:
            c_jt = p_comps.get(key, 0.0)
            linked_contributions[key] += weight_t * c_jt

    sum_linked = sum(linked_contributions.values())
    diff = float(R_cum - sum_linked)

    return {
        "cumulative_portfolio_return": R_cum,
        "linked_component_contributions": linked_contributions,
        "sum_linked_contributions": sum_linked,
        "reconciliation_difference": diff,
        "periods_linked": T,
    }


# ============================================================================
# 3. FACTOR COVARIANCE & SYSTEMATIC RISK DECOMPOSITION
# ============================================================================

def validate_factor_covariance_matrix(
    cov_matrix: np.ndarray,
    factor_names: List[str],
    tolerance: float = 1e-8,
) -> Dict[str, Any]:
    """
    Validates symmetry, finite values, and positive semidefiniteness (PSD) of factor covariance.
    """
    K = len(factor_names)
    if cov_matrix.shape != (K, K):
        raise ValueError(f"Covariance matrix shape {cov_matrix.shape} does not match factor count {K}")

    if not np.all(np.isfinite(cov_matrix)):
        return {"is_valid": False, "reason": "Non-finite values present in covariance matrix"}

    # Symmetry check
    asym = np.max(np.abs(cov_matrix - cov_matrix.T))
    if asym > tolerance:
        return {"is_valid": False, "reason": f"Covariance matrix is asymmetric (max diff {asym:.2e})"}

    # Eigenvalue PSD check
    eigvals = np.linalg.eigvalsh(cov_matrix)
    min_eig = float(np.min(eigvals))
    is_psd = min_eig >= -tolerance

    # Condition number
    max_eig = float(np.max(eigvals))
    cond_num = float(max_eig / max(min_eig, 1e-12)) if min_eig > 0 else float("inf")

    return {
        "is_valid": is_psd,
        "min_eigenvalue": min_eig,
        "max_eigenvalue": max_eig,
        "condition_number": cond_num,
        "is_positive_semidefinite": is_psd,
    }


def compute_systematic_factor_risk(
    beta_vector: np.ndarray,
    cov_matrix: np.ndarray,
    factor_names: List[str],
    annualization_factor: float = 252.0,
) -> Dict[str, Any]:
    """
    Computes systematic factor variance, volatility, and Euler risk attribution:
        sigma_{sys}^2 = beta^T Sigma_F beta
        sigma_{sys} = sqrt(sigma_{sys}^2)
        RC_k^{var} = beta_k * (Sigma_F beta)_k
        RC_k^{vol} = [beta_k * (Sigma_F beta)_k] / sigma_{sys}
        MRC_k^{vol} = (Sigma_F beta)_k / sigma_{sys}
        MRC_k^{var} = 2 * (Sigma_F beta)_k
    
    Reconciles exactly:
        sum_k RC_k^{var} == sigma_{sys}^2
        sum_k RC_k^{vol} == sigma_{sys}
    """
    K = len(factor_names)
    beta = np.array(beta_vector, dtype=np.float64).reshape(-1)
    Sigma = np.array(cov_matrix, dtype=np.float64)

    # Systematic period variance: beta^T Sigma beta
    sigma_F_beta = np.dot(Sigma, beta)  # (K,)
    sys_var_period = float(np.dot(beta, sigma_F_beta))
    sys_var_period = max(0.0, sys_var_period)

    sys_vol_period = float(math.sqrt(sys_var_period))

    # Annualized variance and volatility
    sys_var_ann = float(sys_var_period * annualization_factor)
    sys_vol_ann = float(sys_vol_period * math.sqrt(annualization_factor))

    variance_contributions = {}
    volatility_contributions = {}
    marginal_risk_vol = {}
    marginal_risk_var = {}
    pct_vol_contributions = {}

    for idx, f_name in enumerate(factor_names):
        b_k = float(beta[idx])
        grad_k = float(sigma_F_beta[idx])

        # Euler Variance Contribution
        rc_var = float(b_k * grad_k)
        rc_var_ann = float(rc_var * annualization_factor)
        variance_contributions[f_name] = rc_var_ann

        # Marginal Risk
        if sys_vol_period > 1e-12:
            mrc_vol = float(grad_k / sys_vol_period)
            mrc_vol_ann = float(mrc_vol * math.sqrt(annualization_factor))
            rc_vol = float((b_k * grad_k) / sys_vol_period)
            rc_vol_ann = float(rc_vol * math.sqrt(annualization_factor))
            pct_vol = float((rc_vol / sys_vol_period) * 100.0)
        else:
            mrc_vol_ann = 0.0
            rc_vol_ann = 0.0
            pct_vol = 0.0

        volatility_contributions[f_name] = rc_vol_ann
        marginal_risk_vol[f_name] = mrc_vol_ann
        marginal_risk_var[f_name] = float(2.0 * grad_k * annualization_factor)
        pct_vol_contributions[f_name] = pct_vol

    # Reconciliation
    sum_rc_var = sum(variance_contributions.values())
    sum_rc_vol = sum(volatility_contributions.values())

    return {
        "systematic_variance_period": sys_var_period,
        "systematic_volatility_period": sys_vol_period,
        "systematic_variance_annualized": sys_var_ann,
        "systematic_volatility_annualized": sys_vol_ann,
        "variance_contributions": variance_contributions,
        "volatility_contributions": volatility_contributions,
        "marginal_volatility_contributions": marginal_risk_vol,
        "marginal_variance_contributions": marginal_risk_var,
        "percentage_volatility_contributions": pct_vol_contributions,
        "euler_variance_reconciliation_difference": float(sys_var_ann - sum_rc_var),
        "euler_volatility_reconciliation_difference": float(sys_vol_ann - sum_rc_vol),
    }


# ============================================================================
# 4. TOTAL MODELED RISK & FACTOR-RESIDUAL COVARIANCE
# ============================================================================

def compute_total_modeled_risk(
    systematic_variance: float,
    residual_variance: float,
    factor_residual_covariance: float = 0.0,
    annualization_factor: float = 252.0,
) -> Dict[str, Any]:
    """
    Decomposes total modeled variance:
        sigma_{total,model}^2 = sigma_{sys}^2 + sigma_{eps}^2 + 2 * Cov(beta^T F, eps)
        sigma_{total,model} = sqrt(sigma_{total,model}^2)
    """
    total_var_period = float(systematic_variance + residual_variance + 2.0 * factor_residual_covariance)
    total_var_period = max(0.0, total_var_period)
    total_vol_period = float(math.sqrt(total_var_period))

    total_var_ann = float(total_var_period * annualization_factor)
    total_vol_ann = float(total_vol_period * math.sqrt(annualization_factor))

    # Volatility contributions
    if total_vol_period > 1e-12:
        sys_vol_contrib = float((systematic_variance + factor_residual_covariance) / total_vol_period * math.sqrt(annualization_factor))
        res_vol_contrib = float((residual_variance + factor_residual_covariance) / total_vol_period * math.sqrt(annualization_factor))
    else:
        sys_vol_contrib = 0.0
        res_vol_contrib = 0.0

    return {
        "systematic_variance": float(systematic_variance * annualization_factor),
        "residual_variance": float(residual_variance * annualization_factor),
        "factor_residual_covariance": float(factor_residual_covariance * annualization_factor),
        "total_modeled_variance": total_var_ann,
        "total_modeled_volatility": total_vol_ann,
        "systematic_volatility_contribution": sys_vol_contrib,
        "residual_volatility_contribution": res_vol_contrib,
    }


# ============================================================================
# 5. FORMAL RECONCILIATION BRIDGE
# ============================================================================

def build_attribution_reconciliation_bridge(
    observed_portfolio_return: float,
    risk_free_rate: float,
    intercept: float,
    factor_contributions: Dict[str, float],
    model_residual: float,
    reconciliation_tolerance: float = 1e-6,
) -> Dict[str, Any]:
    """
    Creates institutional reconciliation bridge:
        R_obs = R_f + alpha + sum_k C_k + eps_model + eps_reconciliation
    Categorizes reconciliation status: FULLY_RECONCILED, RECONCILED_WITHIN_TOLERANCE, UNRECONCILED.
    """
    attributed_sum = float(risk_free_rate + intercept + sum(factor_contributions.values()) + model_residual)
    abs_diff = float(abs(observed_portfolio_return - attributed_sum))

    if abs(observed_portfolio_return) > 1e-6:
        rel_diff = float(abs_diff / abs(observed_portfolio_return) * 100.0)
    else:
        rel_diff = None

    if abs_diff <= 1e-10:
        status = "FULLY_RECONCILED"
    elif abs_diff <= reconciliation_tolerance:
        status = "RECONCILED_WITHIN_TOLERANCE"
    else:
        status = "UNRECONCILED"

    return {
        "observed_portfolio_return": observed_portfolio_return,
        "attributed_portfolio_return": attributed_sum,
        "absolute_reconciliation_difference": abs_diff,
        "relative_reconciliation_difference": rel_diff,
        "reconciliation_status": status,
        "tolerance": reconciliation_tolerance,
    }

