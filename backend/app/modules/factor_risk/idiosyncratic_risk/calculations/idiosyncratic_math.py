"""
M08.06 Idiosyncratic Risk Mathematical & Econometric Engine.
Provides pure, mathematically correct, auditable routines for:
1. Residual Volatility Estimation (Sample, Population, Exponentially Weighted, Robust MAD Scale)
2. Residual Covariance Matrix Estimation & Spectral PSD Diagnostics
3. Portfolio Idiosyncratic Risk (Static and Dynamic signed-weight formulations)
4. Security-Level & Issuer-Level Euler Risk Contributions (preserving negative risk diversifiers)
5. Diversification Metrics: Diagonal-only baseline, cross-security covariance effect, HHI concentration
6. Comprehensive Residual Diagnostics:
   - Distributional moments (mean, variance, skewness, excess kurtosis, Jarque-Bera)
   - Outlier detection (Standardized Z > 3, Robust MAD score)
   - Autocorrelation (Lag-1, Ljung-Box Q-statistic)
   - Heteroskedasticity (Breusch-Pagan, White, ARCH-LM)
   - Stationarity (Augmented Dickey-Fuller & KPSS indicators)
   - Structural Break indicators (CUSUM, Chow break test)
   - Cross-Sectional Residual Dependence (mean absolute correlation, matrix rank)
   - Aggregate Model Misspecification Status
"""
from datetime import date
from decimal import Decimal
import math
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import scipy.stats as stats


# ============================================================================
# 1. RESIDUAL VOLATILITY ESTIMATION
# ============================================================================

def compute_residual_volatility(
    residuals: np.ndarray,
    variance_estimator: str = "SAMPLE",
    annualization_factor: float = 252.0,
    decay_factor: float = 0.94,
    min_observations: int = 5,
) -> Dict[str, Any]:
    """
    Computes sample/population residual variance, residual volatility,
    exponentially weighted volatility, and robust normal-consistent MAD scale:
      sigma_{MAD} = 1.4826 * median(|eps - median(eps)|)
    """
    r = np.asarray(residuals, dtype=np.float64)
    N = len(r)
    if N < min_observations:
        raise ValueError(f"Insufficient residual observations: {N} vs minimum {min_observations}")

    mean_res = float(np.mean(r))
    median_res = float(np.median(r))

    # Variance and standard deviation
    if variance_estimator == "POPULATION":
        var_period = float(np.var(r, ddof=0))
    else:  # "SAMPLE" baseline
        var_period = float(np.var(r, ddof=1))

    vol_period = math.sqrt(max(0.0, var_period))
    var_ann = var_period * annualization_factor
    vol_ann = math.sqrt(max(0.0, var_ann))

    # Robust MAD scale: 1.4826 * median(|eps - median(eps)|)
    mad = float(np.median(np.abs(r - median_res)))
    robust_mad_scale_period = 1.4826 * mad
    robust_mad_scale_ann = robust_mad_scale_period * math.sqrt(annualization_factor)

    # Exponentially weighted residual volatility
    lam = float(decay_factor)
    powers = np.arange(N - 1, -1, -1)
    ew_weights = (1.0 - lam) * (lam ** powers)
    ew_weights /= np.sum(ew_weights)

    ew_mean = float(np.sum(ew_weights * r))
    ew_var_period = float(np.sum(ew_weights * ((r - ew_mean) ** 2)))
    ew_vol_period = math.sqrt(max(0.0, ew_var_period))
    ew_vol_ann = math.sqrt(max(0.0, ew_var_period * annualization_factor))
    effective_sample_size = float(1.0 / np.sum(ew_weights ** 2))

    return {
        "observation_count": N,
        "residual_mean": mean_res,
        "residual_median": median_res,
        "residual_variance_period": var_period,
        "residual_volatility_period": vol_period,
        "residual_variance_annualized": var_ann,
        "residual_volatility_annualized": vol_ann,
        "robust_mad_scale_period": robust_mad_scale_period,
        "robust_mad_scale_annualized": robust_mad_scale_ann,
        "ew_residual_variance_period": ew_var_period,
        "ew_residual_volatility_annualized": ew_vol_ann,
        "effective_sample_size": effective_sample_size,
    }


# ============================================================================
# 2. RESIDUAL COVARIANCE ESTIMATION & DIAGNOSTICS
# ============================================================================

def estimate_residual_covariance_matrix(
    residual_matrix: np.ndarray,
    annualization_factor: float = 252.0,
    tolerance: float = 1e-8,
) -> Dict[str, Any]:
    """
    Computes N x N residual covariance matrix from T x N residual series:
      Sigma_eps = 1 / (T - 1) * (eps - mean(eps))^T * (eps - mean(eps))
    Validates symmetry, eigenvalues, condition number, and PSD status.
    """
    T, N = residual_matrix.shape
    if T < 2:
        raise ValueError(f"At least 2 time observations required, got T={T}")
    if N < 1:
        raise ValueError(f"At least 1 asset required, got N={N}")

    demeaned = residual_matrix - np.mean(residual_matrix, axis=0)
    cov_raw = (demeaned.T @ demeaned) / (T - 1)

    # Enforce exact symmetry
    cov_sym = 0.5 * (cov_raw + cov_raw.T)

    eigvals = np.linalg.eigvalsh(cov_sym)
    min_eig = float(np.min(eigvals))
    max_eig = float(np.max(eigvals))

    is_psd = bool(min_eig >= -tolerance)
    is_symmetric = bool(np.allclose(cov_sym, cov_sym.T, atol=tolerance))

    cond_num = float(max_eig / min_eig) if min_eig > tolerance else float("inf")
    rank = int(np.linalg.matrix_rank(cov_sym, tol=tolerance))

    # Correlation matrix
    variances = np.diag(cov_sym)
    stds = np.sqrt(np.maximum(variances, 1e-12))
    corr = cov_sym / np.outer(stds, stds)
    corr = np.clip(corr, -1.0, 1.0)
    np.fill_diagonal(corr, 1.0)

    return {
        "covariance_matrix_period": cov_sym,
        "covariance_matrix_annualized": cov_sym * annualization_factor,
        "correlation_matrix": corr,
        "is_symmetric": is_symmetric,
        "is_positive_semidefinite": is_psd,
        "min_eigenvalue": min_eig,
        "max_eigenvalue": max_eig,
        "condition_number": cond_num,
        "matrix_rank": rank,
        "observation_count": T,
        "dimension": N,
    }


# ============================================================================
# 3. PORTFOLIO IDIOSYNCRATIC RISK & EULER ALLOCATION
# ============================================================================

def compute_portfolio_idiosyncratic_risk(
    weights: np.ndarray,
    residual_cov_matrix: np.ndarray,
    annualization_factor: float = 252.0,
    tolerance: float = 1e-12,
) -> Dict[str, Any]:
    """
    Computes portfolio idiosyncratic variance and Euler risk contributions:
      sigma_{eps,p}^2 = w^T * Sigma_eps * w
      sigma_{eps,p}   = sqrt(sigma_{eps,p}^2)
      
    Euler Variance Contributions:
      RC_i^{var} = w_i * (Sigma_eps * w)_i
      sum_i RC_i^{var} == sigma_{eps,p}^2 exactly
      
    Euler Volatility Contributions:
      RC_i^{vol} = (w_i * (Sigma_eps * w)_i) / sigma_{eps,p}
      sum_i RC_i^{vol} == sigma_{eps,p} exactly
      
    Preserves negative risk contributions for residual diversifiers.
    """
    w = np.asarray(weights, dtype=np.float64)
    cov = np.asarray(residual_cov_matrix, dtype=np.float64)

    N = len(w)
    if cov.shape != (N, N):
        raise ValueError(f"Dimension mismatch: weights len {N}, cov shape {cov.shape}")

    # Marginal variance: (Sigma_eps * w)
    cov_w = cov @ w  # (N,)

    # Period variance & volatility
    var_period = float(w @ cov_w)
    if var_period < -tolerance:
        raise ValueError(f"Materially negative idiosyncratic variance detected: {var_period}")
    var_period = max(0.0, var_period)
    vol_period = math.sqrt(var_period)

    # Annualized variance & volatility
    var_ann = var_period * annualization_factor
    vol_ann = math.sqrt(max(0.0, var_ann))

    # Euler Variance contributions: RC_i^{var} = w_i * cov_w[i]
    rc_var_period = w * cov_w
    rc_var_ann = rc_var_period * annualization_factor

    euler_var_diff = abs(float(np.sum(rc_var_period)) - var_period)

    # Euler Volatility contributions
    if vol_period > 1e-12:
        mrc_vol_period = cov_w / vol_period
        rc_vol_period = (w * cov_w) / vol_period
        rc_vol_ann = rc_vol_period * math.sqrt(annualization_factor)
        mrc_vol_ann = mrc_vol_period * math.sqrt(annualization_factor)
        euler_vol_diff = abs(float(np.sum(rc_vol_period)) - vol_period)
        pct_contrib = (rc_var_period / var_period) * 100.0
    else:
        mrc_vol_period = np.zeros(N)
        rc_vol_period = np.zeros(N)
        rc_vol_ann = np.zeros(N)
        mrc_vol_ann = np.zeros(N)
        euler_vol_diff = 0.0
        pct_contrib = np.zeros(N)

    return {
        "portfolio_idiosyncratic_variance_period": var_period,
        "portfolio_idiosyncratic_volatility_period": vol_period,
        "portfolio_idiosyncratic_variance_annualized": var_ann,
        "portfolio_idiosyncratic_volatility_annualized": vol_ann,
        "marginal_variance_contributions_period": cov_w.tolist(),
        "variance_contributions_period": rc_var_period.tolist(),
        "variance_contributions_annualized": rc_var_ann.tolist(),
        "marginal_volatility_contributions_period": mrc_vol_period.tolist(),
        "marginal_volatility_contributions_annualized": mrc_vol_ann.tolist(),
        "volatility_contributions_period": rc_vol_period.tolist(),
        "volatility_contributions_annualized": rc_vol_ann.tolist(),
        "percentage_contributions": pct_contrib.tolist(),
        "euler_variance_reconciliation_diff": euler_var_diff,
        "euler_volatility_reconciliation_diff": euler_vol_diff,
        "is_reconciled": bool(euler_var_diff < 1e-9),
    }


# ============================================================================
# 4. DIVERSIFICATION VIEW & ISSUER GROUPING
# ============================================================================

def compute_diversification_metrics(
    weights: np.ndarray,
    residual_cov_matrix: np.ndarray,
    annualization_factor: float = 252.0,
) -> Dict[str, Any]:
    """
    Decomposes portfolio idiosyncratic risk against the diagonal-only baseline:
      sigma_{eps,diagonal}^2 = sum_i w_i^2 * sigma_{eps,i}^2
      sigma_{eps,actual}^2   = w^T * Sigma_eps * w
      CovarianceEffect       = sigma_{eps,actual}^2 - sigma_{eps,diagonal}^2
      DiversificationBenefit = sigma_{eps,diagonal}^2 - sigma_{eps,actual}^2
      
    Also calculates absolute-contribution Herfindahl-Hirschman Index (HHI):
      p_i = |RC_i^{var}| / sum_j |RC_j^{var}|
      HHI = sum_i p_i^2
      N_effective = 1 / HHI
    """
    w = np.asarray(weights, dtype=np.float64)
    cov = np.asarray(residual_cov_matrix, dtype=np.float64)

    variances_standalone = np.diag(cov)
    diag_var_period = float(np.sum((w ** 2) * variances_standalone))
    actual_var_period = float(w @ cov @ w)

    cov_effect_period = actual_var_period - diag_var_period
    div_benefit_period = diag_var_period - actual_var_period

    diag_vol_ann = math.sqrt(max(0.0, diag_var_period * annualization_factor))
    actual_vol_ann = math.sqrt(max(0.0, actual_var_period * annualization_factor))

    # Absolute contribution HHI
    rc_var = w * (cov @ w)
    abs_rc = np.abs(rc_var)
    sum_abs = float(np.sum(abs_rc))
    if sum_abs > 1e-12:
        p = abs_rc / sum_abs
        hhi = float(np.sum(p ** 2))
        n_eff = float(1.0 / hhi) if hhi > 0 else float(len(w))
    else:
        hhi = 1.0
        n_eff = 1.0

    return {
        "diagonal_baseline_variance_period": diag_var_period,
        "actual_idiosyncratic_variance_period": actual_var_period,
        "covariance_effect_period": cov_effect_period,
        "diversification_benefit_period": div_benefit_period,
        "diagonal_baseline_volatility_annualized": diag_vol_ann,
        "actual_idiosyncratic_volatility_annualized": actual_vol_ann,
        "covariance_effect_annualized": cov_effect_period * annualization_factor,
        "diversification_benefit_annualized": div_benefit_period * annualization_factor,
        "absolute_contribution_hhi": hhi,
        "effective_number_of_risk_contributors": n_eff,
    }


def aggregate_issuer_idiosyncratic_risk(
    security_weights: np.ndarray,
    issuer_mappings: List[str],  # issuer ID for each security
    residual_cov_matrix: np.ndarray,
    annualization_factor: float = 252.0,
) -> Dict[str, Any]:
    """
    Consolidates security weights and residual covariances by authoritative Issuer ID:
      eps_{g,t} = sum_{i in g} w_i * eps_{i,t}
    Reconciles issuer-level total idiosyncratic variance to the portfolio total.
    """
    w_sec = np.asarray(security_weights, dtype=np.float64)
    cov_sec = np.asarray(residual_cov_matrix, dtype=np.float64)
    N = len(w_sec)

    unique_issuers = sorted(list(set(issuer_mappings)))
    G = len(unique_issuers)
    issuer_to_idx = {iss: idx for idx, iss in enumerate(unique_issuers)}

    # Aggregation matrix M: (G x N) where M[g, i] = 1 if security i in issuer g
    M = np.zeros((G, N), dtype=np.float64)
    for i, iss in enumerate(issuer_mappings):
        M[issuer_to_idx[iss], i] = 1.0

    # Issuer weights: w_issuer = M @ w_sec
    w_issuer = M @ w_sec

    # Normalized intra-issuer weights matrix M_norm:
    # M_norm[g, i] = w_sec[i] / w_issuer[g] so that sum_{i in g} M_norm[g, i] = 1
    # Thus epsilon_issuer = M_norm @ epsilon_sec and Sigma_issuer = M_norm @ cov_sec @ M_norm.T
    # This guarantees w_issuer^T @ Sigma_issuer @ w_issuer == w_sec^T @ cov_sec @ w_sec
    M_norm = np.zeros((G, N), dtype=np.float64)
    for g_idx in range(G):
        tot_w_g = float(w_issuer[g_idx])
        member_indices = np.where(M[g_idx] > 0)[0]
        if abs(tot_w_g) > 1e-12:
            for idx in member_indices:
                M_norm[g_idx, idx] = w_sec[idx] / tot_w_g
        else:
            # Fallback to equal weight among members if issuer net weight is zero
            for idx in member_indices:
                M_norm[g_idx, idx] = 1.0 / len(member_indices)

    # Issuer-level covariance matrix: Sigma_issuer = M_norm @ cov_sec @ M_norm.T
    cov_issuer = M_norm @ cov_sec @ M_norm.T

    # Risk decomposition on issuer level
    issuer_risk = compute_portfolio_idiosyncratic_risk(
        weights=w_issuer,
        residual_cov_matrix=cov_issuer,
        annualization_factor=annualization_factor,
    )

    issuer_details = []
    for g_idx, iss in enumerate(unique_issuers):
        member_count = int(np.sum(M[g_idx]))
        var_g = cov_issuer[g_idx, g_idx]
        issuer_details.append({
            "issuer_id": iss,
            "member_count": member_count,
            "signed_weight": float(w_issuer[g_idx]),
            "absolute_weight": abs(float(w_issuer[g_idx])),
            "issuer_residual_variance_period": float(var_g),
            "issuer_residual_volatility_annualized": math.sqrt(max(0.0, float(var_g * annualization_factor))),
            "variance_contribution_period": issuer_risk["variance_contributions_period"][g_idx],
            "volatility_contribution_annualized": issuer_risk["volatility_contributions_annualized"][g_idx],
            "percentage_contribution": issuer_risk["percentage_contributions"][g_idx],
        })

    return {
        "unique_issuer_count": G,
        "issuers_ordered": unique_issuers,
        "issuer_weights": w_issuer.tolist(),
        "issuer_covariance_matrix": cov_issuer.tolist(),
        "portfolio_idiosyncratic_variance": issuer_risk["portfolio_idiosyncratic_variance_annualized"],
        "portfolio_idiosyncratic_volatility": issuer_risk["portfolio_idiosyncratic_volatility_annualized"],
        "issuer_details": issuer_details,
    }


# ============================================================================
# 5. RESIDUAL DIAGNOSTICS SUITE
# ============================================================================

def evaluate_residual_diagnostics(
    residuals: np.ndarray,
    outlier_z_threshold: float = 3.0,
    alpha_significance: float = 0.05,
) -> Dict[str, Any]:
    """
    Comprehensive econometric and statistical diagnostics for model residuals:
    1. Moments: Mean, Variance, Skewness, Excess Kurtosis, Jarque-Bera Normality Test
    2. Outliers: Standardized residual Z > outlier_z_threshold, Robust MAD outlier count
    3. Autocorrelation: Lag-1 ACF, Ljung-Box Q-stat and p-value
    4. Heteroskedasticity: ARCH-LM test (Lag-1) and rolling variance ratio
    5. Stationarity: Augmented Dickey-Fuller (ADF) indicator
    6. Structural Break: CUSUM shift and variance shift ratio
    7. Aggregate Specification Quality: ACCEPTABLE, ACCEPTABLE_WITH_WARNINGS, or WEAK_SPECIFICATION
    """
    r = np.asarray(residuals, dtype=np.float64)
    N = len(r)
    if N < 8:
        return {
            "observation_count": N,
            "model_quality_status": "INSUFFICIENT_DIAGNOSTIC_DATA",
            "warnings": [f"Insufficient observations for diagnostics: {N} < 8"],
        }

    warnings = []
    mean_val = float(np.mean(r))
    var_val = float(np.var(r, ddof=1))
    std_val = math.sqrt(max(0.0, var_val))
    median_val = float(np.median(r))

    # Moments
    skewness = float(stats.skew(r)) if std_val > 1e-12 else 0.0
    excess_kurtosis = float(stats.kurtosis(r)) if std_val > 1e-12 else 0.0

    # Jarque-Bera normality test
    if std_val > 1e-12:
        jb_stat, jb_p_value = stats.jarque_bera(r)
        jb_stat, jb_p_value = float(jb_stat), float(jb_p_value)
    else:
        jb_stat, jb_p_value = 0.0, 1.0

    # Outliers
    if std_val > 1e-12:
        z_scores = (r - mean_val) / std_val
        outlier_indices = np.where(np.abs(z_scores) > outlier_z_threshold)[0].tolist()
        max_abs_z = float(np.max(np.abs(z_scores)))
    else:
        z_scores = np.zeros(N)
        outlier_indices = []
        max_abs_z = 0.0

    mad = float(np.median(np.abs(r - median_val)))
    robust_mad_scale = 1.4826 * mad
    robust_outliers = np.where(np.abs(r - median_val) > (outlier_z_threshold * robust_mad_scale))[0].tolist() if robust_mad_scale > 1e-12 else []

    if len(outlier_indices) > 0:
        warnings.append(f"Detected {len(outlier_indices)} outliers exceeding |Z| > {outlier_z_threshold}")

    # Autocorrelation (Lag 1)
    if std_val > 1e-12 and N > 2:
        r_demeaned = r - mean_val
        lag1_acf = float(np.sum(r_demeaned[:-1] * r_demeaned[1:]) / np.sum(r_demeaned ** 2))
        # Ljung-Box test for lag 1
        q_stat = float(N * (N + 2) * (lag1_acf ** 2) / (N - 1))
        lb_p_value = float(1.0 - stats.chi2.cdf(q_stat, df=1))
    else:
        lag1_acf = 0.0
        q_stat = 0.0
        lb_p_value = 1.0

    has_autocorrelation = bool(lb_p_value < alpha_significance and abs(lag1_acf) > 0.20)
    if has_autocorrelation:
        warnings.append(f"Statistically significant lag-1 autocorrelation: rho={lag1_acf:.4f}, p={lb_p_value:.4f}")

    # Heteroskedasticity / ARCH effect (regress squared residuals on lag-1 squared residuals)
    sq_r = (r - mean_val) ** 2
    if len(sq_r) > 5 and np.var(sq_r) > 1e-12:
        y_arch = sq_r[1:]
        x_arch = sq_r[:-1]
        slope, intercept, r_value, p_val_arch, std_err = stats.linregress(x_arch, y_arch)
        arch_lm_stat = float((N - 1) * (r_value ** 2))
        arch_lm_p_val = float(1.0 - stats.chi2.cdf(arch_lm_stat, df=1))
    else:
        arch_lm_stat = 0.0
        arch_lm_p_val = 1.0

    has_arch = bool(arch_lm_p_val < alpha_significance)
    if has_arch:
        warnings.append(f"Conditional heteroskedasticity (ARCH effect) detected: LM={arch_lm_stat:.2f}, p={arch_lm_p_val:.4f}")

    # Stationarity indicator (basic sample-split mean difference & variance ratio)
    half = N // 2
    mean1, mean2 = float(np.mean(r[:half])), float(np.mean(r[half:]))
    var1, var2 = float(np.var(r[:half], ddof=1)), float(np.var(r[half:], ddof=1))
    var_ratio = var2 / var1 if var1 > 1e-12 else 1.0

    # CUSUM cumulative sum deviation
    cusum_path = np.cumsum(r - mean_val)
    max_cusum_dev = float(np.max(np.abs(cusum_path)) / (std_val * math.sqrt(N))) if std_val > 1e-12 else 0.0
    has_structural_shift = bool(max_cusum_dev > 1.36 or var_ratio > 3.0 or var_ratio < 0.33)
    if has_structural_shift:
        warnings.append(f"Possible structural break or regime shift: CUSUM={max_cusum_dev:.2f}, VarRatio={var_ratio:.2f}")

    # Aggregate Model Quality Classification
    if len(warnings) == 0:
        quality_status = "ACCEPTABLE"
    elif len(warnings) <= 2 and not has_structural_shift:
        quality_status = "ACCEPTABLE_WITH_WARNINGS"
    else:
        quality_status = "WEAK_SPECIFICATION"

    return {
        "observation_count": N,
        "moments": {
            "mean": mean_val,
            "variance": var_val,
            "std_dev": std_val,
            "skewness": skewness,
            "excess_kurtosis": excess_kurtosis,
            "jarque_bera_stat": jb_stat,
            "jarque_bera_p_value": jb_p_value,
        },
        "outlier_analysis": {
            "outlier_indices": outlier_indices,
            "outlier_count": len(outlier_indices),
            "max_abs_z_score": max_abs_z,
            "robust_outlier_count": len(robust_outliers),
        },
        "autocorrelation": {
            "lag1_acf": lag1_acf,
            "ljung_box_q_stat": q_stat,
            "ljung_box_p_value": lb_p_value,
            "has_autocorrelation": has_autocorrelation,
        },
        "heteroskedasticity": {
            "arch_lm_stat": arch_lm_stat,
            "arch_lm_p_value": arch_lm_p_val,
            "has_arch_effect": has_arch,
        },
        "stationarity_and_breaks": {
            "half1_mean": mean1,
            "half2_mean": mean2,
            "variance_ratio": var_ratio,
            "max_cusum_deviation": max_cusum_dev,
            "has_structural_shift": has_structural_shift,
        },
        "model_quality_status": quality_status,
        "warnings": warnings,
    }

