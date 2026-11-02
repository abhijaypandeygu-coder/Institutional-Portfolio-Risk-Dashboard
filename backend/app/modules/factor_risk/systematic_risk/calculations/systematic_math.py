"""
M08.05 Systematic Risk Calculations Engine.
Provides pure, mathematically rigorous, auditable functions for:
1. Factor Covariance Matrix Estimation (Sample, Exponentially Weighted, Ledoit-Wolf Shrinkage)
2. Matrix Diagnostics (Symmetry, Eigenvalues, Condition Number, Positive Semidefiniteness)
3. Instrument-Level Common-Factor Variance and Volatility
4. Portfolio-Level Common-Factor Variance & Cross-Security Systematic Covariance
5. Residual and Total Modeled Risk Decomposition
6. Single-Factor and Multi-Factor Scenario Sensitivity Shocks
7. Holding-Level, Factor-Specific, and Portfolio-Level Model Coverage
"""
from datetime import date
from decimal import Decimal
import math
from typing import List, Dict, Any, Optional, Tuple, Set
import numpy as np


# ============================================================================
# 1. FACTOR COVARIANCE ESTIMATION & DIAGNOSTICS
# ============================================================================

def estimate_factor_covariance_matrix(
    returns_matrix: np.ndarray,
    method: str = "SAMPLE",
    decay_factor: float = 0.94,
    annualization_factor: float = 252.0,
) -> Dict[str, Any]:
    """
    Estimates K x K factor covariance matrix from T x K factor return observations.
    
    Methods:
    - SAMPLE: Unbiased sample covariance 1/(T-1) * (F - mean(F))^T * (F - mean(F))
    - EXPONENTIALLY_WEIGHTED: EWMA covariance with lambda=decay_factor
    - SHRINKAGE: Ledoit-Wolf constant correlation target shrinkage
    """
    T, K = returns_matrix.shape
    if T < 2:
        raise ValueError(f"At least 2 observations required for covariance estimation, got T={T}")
    if K < 1:
        raise ValueError(f"At least 1 factor required, got K={K}")

    mean_vec = np.mean(returns_matrix, axis=0)
    demeaned = returns_matrix - mean_vec

    if method == "SAMPLE":
        cov_raw = (demeaned.T @ demeaned) / (T - 1)
        effective_sample_size = float(T)

    elif method == "EXPONENTIALLY_WEIGHTED":
        # Weights: w_t = (1 - lambda) * lambda^(T - 1 - t)
        lam = float(decay_factor)
        powers = np.arange(T - 1, -1, -1)
        weights = (1.0 - lam) * (lam ** powers)
        weights /= np.sum(weights)

        # Weighted covariance
        weighted_demeaned = demeaned * np.sqrt(weights[:, np.newaxis])
        cov_raw = weighted_demeaned.T @ weighted_demeaned
        # Effective sample size: 1 / sum(w^2)
        effective_sample_size = float(1.0 / np.sum(weights ** 2))

    elif method == "SHRINKAGE":
        # Sample covariance baseline
        S = (demeaned.T @ demeaned) / (T - 1)
        variances = np.diag(S)
        stds = np.sqrt(np.maximum(variances, 1e-12))
        corr = S / np.outer(stds, stds)
        
        # Target: Constant correlation matrix
        r_bar = (np.sum(corr) - K) / (K * (K - 1)) if K > 1 else 1.0
        F_target = r_bar * np.outer(stds, stds)
        np.fill_diagonal(F_target, variances)
        
        # Shrinkage intensity heuristic (Ledoit-Wolf approximation)
        shrinkage_intensity = min(1.0, max(0.0, 1.0 / math.sqrt(T)))
        cov_raw = (1.0 - shrinkage_intensity) * S + shrinkage_intensity * F_target
        effective_sample_size = float(T)

    else:
        raise ValueError(f"Unsupported covariance method: {method}")

    # Enforce exact symmetry: (Sigma + Sigma^T) / 2
    cov_sym = 0.5 * (cov_raw + cov_raw.T)

    # Diagnostics
    diag = validate_covariance_matrix(cov_sym)

    # Annualized matrix
    cov_annualized = cov_sym * annualization_factor

    return {
        "covariance_matrix_period": cov_sym,
        "covariance_matrix_annualized": cov_annualized,
        "effective_sample_size": effective_sample_size,
        "observation_count": T,
        "factor_count": K,
        "diagnostics": diag,
    }


def validate_covariance_matrix(cov: np.ndarray, tolerance: float = 1e-8) -> Dict[str, Any]:
    """
    Validates symmetry, eigenvalues, condition number, and positive semidefiniteness (PSD).
    """
    if cov.ndim != 2 or cov.shape[0] != cov.shape[1]:
        raise ValueError("Covariance matrix must be a 2D square matrix")

    is_symmetric = bool(np.allclose(cov, cov.T, atol=tolerance))
    eigvals = np.linalg.eigvalsh(cov)
    min_eig = float(np.min(eigvals))
    max_eig = float(np.max(eigvals))

    is_psd = bool(min_eig >= -tolerance)

    if min_eig > tolerance:
        cond_num = float(max_eig / min_eig)
    elif min_eig >= -tolerance:
        cond_num = float("inf")
    else:
        cond_num = float("nan")

    rank = int(np.linalg.matrix_rank(cov, tol=tolerance))

    # Correlation matrix
    variances = np.diag(cov)
    stds = np.sqrt(np.maximum(variances, 1e-12))
    corr = cov / np.outer(stds, stds)
    corr = np.clip(corr, -1.0, 1.0)
    np.fill_diagonal(corr, 1.0)

    return {
        "is_symmetric": is_symmetric,
        "is_positive_semidefinite": is_psd,
        "min_eigenvalue": min_eig,
        "max_eigenvalue": max_eig,
        "condition_number": cond_num,
        "matrix_rank": rank,
        "eigenvalues": eigvals.tolist(),
        "correlation_matrix": corr.tolist(),
    }


# ============================================================================
# 2. INSTRUMENT-LEVEL SYSTEMATIC RISK
# ============================================================================

def compute_instrument_systematic_risk(
    beta_vector: np.ndarray,
    cov_matrix: np.ndarray,
    residual_variance: Optional[float] = None,
    factor_residual_cov: float = 0.0,
    annualization_factor: float = 252.0,
) -> Dict[str, Any]:
    """
    Computes instrument common-factor variance and volatility:
      sigma_{sys,i}^2 = beta_i^T * Sigma_F * beta_i
      sigma_{sys,i}   = sqrt(sigma_{sys,i}^2)
    
    Also calculates total modeled risk if residual variance is provided:
      sigma_{total}^2 = sigma_{sys}^2 + sigma_{eps}^2 + 2 * Cov(beta^T F, eps)
    """
    beta = np.asarray(beta_vector, dtype=np.float64)
    cov = np.asarray(cov_matrix, dtype=np.float64)

    if beta.ndim != 1 or cov.ndim != 2 or len(beta) != cov.shape[0]:
        raise ValueError(f"Incompatible dimensions: beta shape {beta.shape}, cov shape {cov.shape}")

    # Period variance
    sys_var_period = float(beta @ cov @ beta)
    if sys_var_period < -1e-12:
        raise ValueError(f"Materially negative systematic variance detected: {sys_var_period}")
    sys_var_period = max(0.0, sys_var_period)
    sys_vol_period = math.sqrt(sys_var_period)

    # Annualized variance and volatility
    sys_var_ann = sys_var_period * annualization_factor
    sys_vol_ann = math.sqrt(sys_var_ann)

    # Standalone factor variances: beta_k^2 * sigma_{F_k}^2
    standalone_vars_period = (beta ** 2) * np.diag(cov)
    standalone_vars_ann = standalone_vars_period * annualization_factor

    # Total modeled risk
    total_var_period = None
    total_vol_period = None
    total_var_ann = None
    total_vol_ann = None
    sys_risk_ratio = None
    idiosyncratic_ratio = None

    if residual_variance is not None and residual_variance >= 0.0:
        res_var_p = float(residual_variance)
        cross_cov_p = float(factor_residual_cov)
        tot_var_p = sys_var_period + res_var_p + 2.0 * cross_cov_p
        tot_var_p = max(0.0, tot_var_p)

        total_var_period = tot_var_p
        total_vol_period = math.sqrt(tot_var_p)
        total_var_ann = tot_var_p * annualization_factor
        total_vol_ann = math.sqrt(total_var_ann)

        if tot_var_p > 1e-12:
            sys_risk_ratio = sys_var_period / tot_var_p
            idiosyncratic_ratio = res_var_p / tot_var_p

    return {
        "systematic_variance_period": sys_var_period,
        "systematic_volatility_period": sys_vol_period,
        "systematic_variance_annualized": sys_var_ann,
        "systematic_volatility_annualized": sys_vol_ann,
        "standalone_factor_variances_period": standalone_vars_period.tolist(),
        "standalone_factor_variances_annualized": standalone_vars_ann.tolist(),
        "residual_variance_period": residual_variance,
        "residual_variance_annualized": residual_variance * annualization_factor if residual_variance is not None else None,
        "total_modeled_variance_period": total_var_period,
        "total_modeled_volatility_period": total_vol_period,
        "total_modeled_variance_annualized": total_var_ann,
        "total_modeled_volatility_annualized": total_vol_ann,
        "systematic_risk_ratio": sys_risk_ratio,
        "idiosyncratic_risk_ratio": idiosyncratic_ratio,
    }


# ============================================================================
# 3. PORTFOLIO-LEVEL SYSTEMATIC RISK & CROSS-SECURITY COVARIANCE
# ============================================================================

def compute_portfolio_systematic_risk(
    portfolio_beta_vector: np.ndarray,
    cov_matrix: np.ndarray,
    residual_variance: Optional[float] = None,
    factor_residual_cov: float = 0.0,
    annualization_factor: float = 252.0,
) -> Dict[str, Any]:
    """
    Computes portfolio common-factor variance:
      sigma_{sys,p}^2 = beta_p^T * Sigma_F * beta_p
    """
    return compute_instrument_systematic_risk(
        beta_vector=portfolio_beta_vector,
        cov_matrix=cov_matrix,
        residual_variance=residual_variance,
        factor_residual_cov=factor_residual_cov,
        annualization_factor=annualization_factor,
    )


def compute_cross_security_systematic_variance(
    weights: np.ndarray,
    betas_matrix: np.ndarray,
    cov_matrix: np.ndarray,
    annualization_factor: float = 252.0,
) -> Dict[str, Any]:
    """
    Verifies the dual portfolio variance identity:
      sigma_{sys,p}^2 = (sum_i w_i beta_i)^T * Sigma_F * (sum_i w_i beta_i)
                      = sum_i sum_j w_i w_j (beta_i^T * Sigma_F * beta_j)
    
    Preserves exact cross-security systematic covariance terms w_i w_j (beta_i^T Sigma_F beta_j).
    """
    w = np.asarray(weights, dtype=np.float64)       # (N,)
    B = np.asarray(betas_matrix, dtype=np.float64)  # (N, K)
    cov = np.asarray(cov_matrix, dtype=np.float64)  # (K, K)

    N, K = B.shape
    if len(w) != N or cov.shape != (K, K):
        raise ValueError(f"Dimension mismatch: weights ({len(w)}), Betas ({B.shape}), Cov ({cov.shape})")

    # Method 1: Aggregated portfolio beta
    beta_p = w @ B  # (K,)
    var_aggregated = float(beta_p @ cov @ beta_p)

    # Method 2: Double summation of cross-security systematic covariances
    # Security systematic covariance matrix: S_sec = B @ cov @ B.T  (N x N)
    S_sec = B @ cov @ B.T
    var_double_sum = float(w @ S_sec @ w)

    discrepancy = abs(var_aggregated - var_double_sum)

    return {
        "portfolio_beta": beta_p.tolist(),
        "variance_from_aggregated_beta": var_aggregated,
        "variance_from_cross_securities": var_double_sum,
        "reconciliation_discrepancy": discrepancy,
        "is_reconciled": bool(discrepancy < 1e-12),
        "security_systematic_cov_matrix": S_sec.tolist(),
        "annualized_variance": var_aggregated * annualization_factor,
        "annualized_volatility": math.sqrt(max(0.0, var_aggregated * annualization_factor)),
    }


# ============================================================================
# 4. SCENARIO SENSITIVITY SHOCKS
# ============================================================================

def compute_factor_shock_scenario(
    factor_shocks: Dict[str, float],
    factor_names_ordered: List[str],
    portfolio_betas: Dict[str, float],
    instrument_betas: Optional[Dict[str, Dict[str, float]]] = None,
    portfolio_nav: Optional[float] = None,
    instrument_market_values: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Computes linear factor shock scenario impacts:
      Delta R_p^{sys} = sum_k beta_{p,k} * Delta F_k
      Delta V_p^{sys} = NAV_p * Delta R_p^{sys}
      
    For each instrument:
      Delta R_i^{sys} = sum_k beta_{i,k} * Delta F_k
      Delta V_i^{sys} = MV_i^{signed} * Delta R_i^{sys}
    """
    shock_vec = []
    portfolio_beta_vec = []
    factor_contributions_pct = {}

    for f_code in factor_names_ordered:
        shock = float(factor_shocks.get(f_code, 0.0))
        b_p = float(portfolio_betas.get(f_code, 0.0))
        shock_vec.append(shock)
        portfolio_beta_vec.append(b_p)
        contrib = b_p * shock
        factor_contributions_pct[f_code] = contrib

    shock_arr = np.array(shock_vec, dtype=np.float64)
    beta_arr = np.array(portfolio_beta_vec, dtype=np.float64)

    portfolio_pct_impact = float(np.dot(beta_arr, shock_arr))
    portfolio_monetary_impact = None
    if portfolio_nav is not None:
        portfolio_monetary_impact = float(portfolio_nav) * portfolio_pct_impact

    # Instrument-level impacts
    inst_results = {}
    if instrument_betas:
        for inst_id, b_dict in instrument_betas.items():
            b_inst_vec = np.array([float(b_dict.get(fc, 0.0)) for fc in factor_names_ordered], dtype=np.float64)
            inst_pct = float(np.dot(b_inst_vec, shock_arr))
            mv = instrument_market_values.get(inst_id) if instrument_market_values else None
            monetary = float(mv) * inst_pct if mv is not None else None
            
            f_contribs = {fc: float(b_dict.get(fc, 0.0)) * float(factor_shocks.get(fc, 0.0)) for fc in factor_names_ordered}
            inst_results[inst_id] = {
                "percentage_impact": inst_pct,
                "monetary_impact": monetary,
                "factor_contributions": f_contribs,
            }

    return {
        "portfolio_percentage_impact": portfolio_pct_impact,
        "portfolio_monetary_impact": portfolio_monetary_impact,
        "factor_contributions_percentage": factor_contributions_pct,
        "instrument_impacts": inst_results,
        "model_limitation_warning": bool(abs(portfolio_pct_impact) > 0.15 or any(abs(s) > 0.10 for s in shock_vec)),
    }


def compute_standardized_factor_shocks(
    standard_deviation_multiples: Dict[str, float],
    factor_volatilities_period: Dict[str, float],
) -> Dict[str, float]:
    """
    Computes factor shock vector from z-multiples:
      Delta F_k = z_k * sigma_{F_k}
    """
    shocks = {}
    for f_code, z in standard_deviation_multiples.items():
        sigma = factor_volatilities_period.get(f_code, 0.0)
        shocks[f_code] = float(z) * float(sigma)
    return shocks


def compute_conditional_covariance_stress(
    beta_vector: np.ndarray,
    stressed_cov_matrix: np.ndarray,
    baseline_cov_matrix: Optional[np.ndarray] = None,
    annualization_factor: float = 252.0,
) -> Dict[str, Any]:
    """
    Estimates systematic variance under an explicit stressed covariance regime:
      sigma_{sys,stress}^2 = beta^T * Sigma_F^{stress} * beta
    """
    beta = np.asarray(beta_vector, dtype=np.float64)
    cov_stress = np.asarray(stressed_cov_matrix, dtype=np.float64)

    var_stress_p = float(beta @ cov_stress @ beta)
    vol_stress_ann = math.sqrt(max(0.0, var_stress_p * annualization_factor))

    var_baseline_p = None
    vol_baseline_ann = None
    vol_change_pct = None

    if baseline_cov_matrix is not None:
        cov_base = np.asarray(baseline_cov_matrix, dtype=np.float64)
        var_baseline_p = float(beta @ cov_base @ beta)
        vol_baseline_ann = math.sqrt(max(0.0, var_baseline_p * annualization_factor))
        if vol_baseline_ann > 1e-12:
            vol_change_pct = (vol_stress_ann - vol_baseline_ann) / vol_baseline_ann

    return {
        "stressed_systematic_variance_period": var_stress_p,
        "stressed_systematic_volatility_annualized": vol_stress_ann,
        "baseline_systematic_volatility_annualized": vol_baseline_ann,
        "systematic_volatility_stress_change_pct": vol_change_pct,
    }


# ============================================================================
# 5. MODEL COVERAGE ENGINE
# ============================================================================

def evaluate_model_coverage(
    holdings: List[Dict[str, Any]],
    required_factor_codes: List[str],
    minimum_coverage_threshold: float = 80.0,
) -> Dict[str, Any]:
    """
    Calculates holding-level, factor-specific, and portfolio-level model coverage.
    
    Holdings structure:
      {
        "instrument_id": str,
        "signed_market_value": float,
        "factor_loadings": Dict[str, float],   # e.g. {"MKT": 1.2, "SMB": -0.3}
        "is_unsupported": bool,                # e.g. unmodeled derivative/cash
        "is_stale": bool,
        "is_low_quality": bool,
      }
    
    Formula:
      W_total   = sum_i |w_i|
      W_covered = sum_{i in C} |w_i|
      Coverage  = (W_covered / W_total) * 100
      
    Uses absolute weights |w_i| so short positions cannot artificially inflate coverage.
    """
    required_factors = set(required_factor_codes)
    K_req = len(required_factors)

    total_abs_mv = 0.0
    covered_abs_mv = 0.0
    uncovered_abs_mv = 0.0

    covered_holdings_count = 0
    uncovered_holdings_count = 0

    factor_covered_abs_mv = {f: 0.0 for f in required_factor_codes}
    holding_details = []

    for h in holdings:
        inst_id = h["instrument_id"]
        smv = float(h.get("signed_market_value", 0.0))
        amv = abs(smv)
        total_abs_mv += amv

        loadings = h.get("factor_loadings") or {}
        available_factors = set(loadings.keys())
        missing_factors = list(required_factors - available_factors)

        is_unsupported = bool(h.get("is_unsupported", False))
        is_stale = bool(h.get("is_stale", False))
        is_low_quality = bool(h.get("is_low_quality", False))

        if is_unsupported:
            status = "UNSUPPORTED_INSTRUMENT"
            is_cov = False
        elif is_stale:
            status = "STALE_SENSITIVITY"
            is_cov = False
        elif is_low_quality:
            status = "LOW_QUALITY_LOADING"
            is_cov = False
        elif len(missing_factors) == 0:
            status = "COVERED"
            is_cov = True
        elif len(missing_factors) < K_req:
            status = "PARTIALLY_COVERED"
            is_cov = False
        else:
            status = "MISSING_FACTOR_LOADING"
            is_cov = False

        if is_cov:
            covered_abs_mv += amv
            covered_holdings_count += 1
        else:
            uncovered_abs_mv += amv
            uncovered_holdings_count += 1

        # Factor-specific coverage tracking
        for fc in required_factor_codes:
            if fc in loadings and loadings[fc] is not None:
                factor_covered_abs_mv[fc] += amv

        holding_details.append({
            "instrument_id": inst_id,
            "signed_market_value": smv,
            "absolute_market_value": amv,
            "coverage_status": status,
            "is_covered": is_cov,
            "missing_factors": missing_factors,
            "available_factor_count": len(available_factors.intersection(required_factors)),
            "required_factor_count": K_req,
        })

    # Portfolio metrics
    portfolio_coverage_pct = (covered_abs_mv / total_abs_mv * 100.0) if total_abs_mv > 0 else 0.0

    factor_coverage_percentages = {}
    for fc in required_factor_codes:
        f_cov_pct = (factor_covered_abs_mv[fc] / total_abs_mv * 100.0) if total_abs_mv > 0 else 0.0
        factor_coverage_percentages[fc] = f_cov_pct

    # Portfolio coverage tier
    if portfolio_coverage_pct >= 99.0:
        tier = "NEAR_COMPLETE"
    elif portfolio_coverage_pct >= 95.0:
        tier = "HIGH_COVERAGE"
    elif portfolio_coverage_pct >= minimum_coverage_threshold:
        tier = "MODERATE_COVERAGE"
    elif portfolio_coverage_pct > 0.0:
        tier = "LOW_COVERAGE"
    else:
        tier = "NO_COVERAGE"

    return {
        "portfolio_coverage_percentage": portfolio_coverage_pct,
        "coverage_tier": tier,
        "total_absolute_market_value": total_abs_mv,
        "covered_absolute_market_value": covered_abs_mv,
        "uncovered_absolute_market_value": uncovered_abs_mv,
        "total_holding_count": len(holdings),
        "covered_holding_count": covered_holdings_count,
        "uncovered_holding_count": uncovered_holdings_count,
        "factor_coverage_percentages": factor_coverage_percentages,
        "holding_details": holding_details,
    }

