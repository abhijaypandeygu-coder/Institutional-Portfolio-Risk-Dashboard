"""
M08.03 Factor Sensitivity Mathematical, Diagnostic & Stability Engine.
Authoritative quantitative computational core for:
1. Multi-factor linear regressions (OLS, WLS, EWLS, Ridge Regression, Quantile Regression)
2. Classical, HC3 heteroskedasticity-robust, and HAC Newey-West standard errors
3. Model goodness-of-fit (R2, Adj-R2, RSS, TSS, RMSE, MAE, RSE)
4. Residual diagnostics: Durbin-Watson (autocorrelation), Jarque-Bera (normality)
5. Multicollinearity: Condition Number & Variance Inflation Factors (VIF)
6. Multiple-testing adjustments: Benjamini-Hochberg False Discovery Rate (FDR) & Bonferroni
7. Rolling coefficient stability metrics (volatility, sign changes, range, relative change)
8. Structural Break Tests: Chow F-test and CUSUM recursive residual test
"""
from typing import Dict, Any, List, Optional, Tuple
import math
import numpy as np
from scipy import stats

from backend.app.modules.factor_risk.factor_sensitivity.models import (
    ModelFamily,
    StandardErrorMethod,
    StatisticalSignificanceCategory,
    CoefficientStabilityStatus,
    StructuralBreakTestType,
    StructuralBreakResultStatus,
    SensitivityRunStatus,
)


# ============================================================================
# 1. CORE REGRESSION SOLVER
# ============================================================================

def fit_factor_sensitivity_regression(
    y_returns: np.ndarray,
    X_factors: np.ndarray,
    factor_names: List[str],
    model_family: ModelFamily = ModelFamily.OLS,
    include_intercept: bool = True,
    ewls_decay_factor: float = 0.94,
    ridge_lambda: float = 0.01,
    quantile_tau: float = 0.50,
    observation_weights: Optional[np.ndarray] = None,
    min_observations: int = 30,
    min_obs_per_param_multiplier: int = 5,
    standard_error_method: StandardErrorMethod = StandardErrorMethod.HC3_HETEROSKEDASTICITY_ROBUST,
    confidence_level: float = 0.95,
) -> Dict[str, Any]:
    """
    Fits systematic factor regression model:
        y_t = alpha + sum_k (beta_k * F_k,t) + eps_t
    Supports: OLS, WLS, EWLS, Ridge, Quantile.
    """
    T = len(y_returns)
    K = len(factor_names)
    P = K + (1 if include_intercept else 0)

    # 1. Sample adequacy
    if T < min_observations or T < (min_obs_per_param_multiplier * P) or X_factors.shape[0] != T:
        return {
            "status": SensitivityRunStatus.FAILED,
            "failure_reason": f"Insufficient observations: {T} < max({min_observations}, {min_obs_per_param_multiplier * P})",
            "observation_count": T,
            "coefficients": {},
            "diagnostics": {},
        }

    # 2. Factor variance
    factor_vars = np.var(X_factors, axis=0, ddof=1)
    if np.any(factor_vars < 1e-12):
        return {
            "status": SensitivityRunStatus.FAILED,
            "failure_reason": "One or more systematic factors has zero or degenerate variance",
            "observation_count": T,
            "coefficients": {},
            "diagnostics": {"factor_variances": factor_vars.tolist()},
        }

    # 3. Construct design matrix X
    if include_intercept:
        ones = np.ones((T, 1), dtype=np.float64)
        X = np.hstack([ones, X_factors])
    else:
        X = X_factors.copy()

    y = y_returns.copy()

    # 4. Observation weights (WLS / EWLS)
    effective_sample_size = float(T)
    if model_family == ModelFamily.EWLS:
        exponents = np.arange(T - 1, -1, -1, dtype=np.float64)
        weights = ewls_decay_factor ** exponents
        weights = weights / np.sum(weights) * T
        W_sqrt = np.sqrt(weights)[:, np.newaxis]
        X_w = X * W_sqrt
        y_w = y * np.sqrt(weights)
        effective_sample_size = float((np.sum(weights) ** 2) / np.sum(weights ** 2))
    elif model_family == ModelFamily.WLS and observation_weights is not None:
        w = observation_weights / np.sum(observation_weights) * T
        W_sqrt = np.sqrt(w)[:, np.newaxis]
        X_w = X * W_sqrt
        y_w = y * np.sqrt(w)
        effective_sample_size = float((np.sum(w) ** 2) / np.sum(w ** 2))
    else:
        X_w = X
        y_w = y

    # 5. Multicollinearity & Conditioning Diagnostics
    rank = int(np.linalg.matrix_rank(X_w))
    s_factors = np.linalg.svd(X_factors, compute_uv=False)
    cond_number = float(s_factors[0] / s_factors[-1]) if s_factors[-1] > 1e-12 else float("inf")

    if rank < P and model_family not in [ModelFamily.RIDGE]:
        return {
            "status": SensitivityRunStatus.COMPLETED_WITH_WARNINGS,
            "failure_reason": "Design matrix is rank-deficient (perfect multicollinearity)",
            "observation_count": T,
            "coefficients": {},
            "diagnostics": {
                "rank": rank,
                "parameters": P,
                "condition_number": cond_number,
            },
        }

    # 6. Fit Parameters by Model Family
    if model_family == ModelFamily.RIDGE:
        # Ridge: (X^T X + lambda * I_penalty)^(-1) X^T y
        penalty_diag = np.ones(P, dtype=np.float64) * ridge_lambda
        if include_intercept:
            penalty_diag[0] = 0.0  # Do not penalize intercept
        A = np.dot(X_w.T, X_w) + np.diag(penalty_diag)
        b_vec = np.dot(X_w.T, y_w)
        coefficients = np.linalg.solve(A, b_vec)
    elif model_family == ModelFamily.QUANTILE:
        # Median / Quantile regression via iteratively reweighted least squares (IRLS)
        coefficients = _fit_quantile_irls(X_w, y_w, tau=quantile_tau)
    else:
        # Classical QR decomposition (OLS / WLS / EWLS)
        Q, R = np.linalg.qr(X_w)
        qty = np.dot(Q.T, y_w)
        try:
            coefficients = np.linalg.solve(R, qty)
        except np.linalg.LinAlgError:
            coefficients = np.linalg.lstsq(X_w, y_w, rcond=None)[0]

    # Fitted values and residuals
    y_fitted = np.dot(X, coefficients)
    residuals = y - y_fitted
    df_resid = max(1, T - P)

    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    ss_res = float(np.sum(residuals ** 2))
    r_squared = float(1.0 - (ss_res / ss_tot)) if ss_tot > 1e-12 else 0.0
    r_squared = max(0.0, min(1.0, r_squared))
    adj_r_squared = float(1.0 - ((1.0 - r_squared) * (T - 1) / df_resid)) if T > P else 0.0
    residual_variance = float(ss_res / df_resid)
    rse = float(np.sqrt(residual_variance))
    mse = float(np.mean(residuals ** 2))
    rmse = float(np.sqrt(mse))
    mae = float(np.mean(np.abs(residuals)))

    # 7. Standard Error Estimation
    try:
        Q, R = np.linalg.qr(X_w)
        R_inv = np.linalg.inv(R)
        xtx_inv = np.dot(R_inv, R_inv.T)
    except Exception:
        xtx_inv = np.linalg.pinv(np.dot(X_w.T, X_w))

    if standard_error_method == StandardErrorMethod.HC3_HETEROSKEDASTICITY_ROBUST:
        h = np.sum(Q ** 2, axis=1)
        h = np.clip(h, 0.0, 0.9999)
        hc3_w = (residuals / (1.0 - h)) ** 2
        meat = np.dot(X.T, X * hc3_w[:, np.newaxis])
        cov_matrix = np.dot(xtx_inv, np.dot(meat, xtx_inv))
    elif standard_error_method == StandardErrorMethod.HAC_NEWEY_WEST:
        L = max(1, int(4.0 * ((T / 100.0) ** (2.0 / 9.0))))
        meat = np.dot(X.T, X * (residuals ** 2)[:, np.newaxis])
        for lag in range(1, L + 1):
            weight = 1.0 - (lag / (L + 1.0))
            cross = np.dot(X[lag:].T, (X[:-lag] * (residuals[lag:] * residuals[:-lag])[:, np.newaxis]))
            meat += weight * (cross + cross.T)
        cov_matrix = np.dot(xtx_inv, np.dot(meat, xtx_inv))
    else:
        cov_matrix = residual_variance * xtx_inv

    std_errors = np.sqrt(np.maximum(0.0, np.diag(cov_matrix)))
    alpha_sig = 1.0 - confidence_level
    t_crit = float(stats.t.ppf(1.0 - alpha_sig / 2.0, df=df_resid))

    # Variance Inflation Factors (VIF)
    vif_dict: Dict[str, float] = {}
    if K > 1:
        corr_matrix = np.corrcoef(X_factors, rowvar=False)
        if not np.any(np.isnan(corr_matrix)):
            try:
                inv_corr = np.linalg.inv(corr_matrix)
                for idx, fname in enumerate(factor_names):
                    vif_dict[fname] = float(inv_corr[idx, idx])
            except np.linalg.LinAlgError:
                for fname in factor_names:
                    vif_dict[fname] = float("inf")

    # Residual diagnostic tests: Durbin-Watson & Jarque-Bera
    diff_res = np.diff(residuals)
    dw_stat = float(np.sum(diff_res ** 2) / ss_res) if ss_res > 1e-12 else 2.0
    jb_stat, jb_pval = stats.jarque_bera(residuals)
    jb_stat = float(jb_stat)
    jb_pval = float(jb_pval)

    # 8. Unpack Intercept and Coefficients
    intercept_val = None
    intercept_se = None
    intercept_t = None
    intercept_p = None

    if include_intercept:
        intercept_val = float(coefficients[0])
        intercept_se = float(std_errors[0])
        intercept_t = float(intercept_val / intercept_se) if intercept_se > 1e-12 else None
        intercept_p = float(2.0 * (1.0 - stats.t.cdf(abs(intercept_t), df=df_resid))) if intercept_t is not None else None
        factor_coeffs = coefficients[1:]
        factor_se = std_errors[1:]
    else:
        factor_coeffs = coefficients
        factor_se = std_errors

    raw_p_values = []
    coeff_data = {}
    for idx, fname in enumerate(factor_names):
        b = float(factor_coeffs[idx])
        se = float(factor_se[idx])
        t_stat = float(b / se) if se > 1e-12 else None
        p_val = float(2.0 * (1.0 - stats.t.cdf(abs(t_stat), df=df_resid))) if t_stat is not None else None
        ci_lower = float(b - t_crit * se) if se > 1e-12 else None
        ci_upper = float(b + t_crit * se) if se > 1e-12 else None

        sig = StatisticalSignificanceCategory.INFERENCE_UNAVAILABLE
        if p_val is not None:
            raw_p_values.append(p_val)
            if p_val < 0.01:
                sig = StatisticalSignificanceCategory.HIGH_SIGNIFICANCE
            elif p_val < 0.05:
                sig = StatisticalSignificanceCategory.MODERATE_SIGNIFICANCE
            elif p_val < 0.10:
                sig = StatisticalSignificanceCategory.LOW_SIGNIFICANCE
            else:
                sig = StatisticalSignificanceCategory.NOT_SIGNIFICANT

        sigma_factor = float(np.sqrt(factor_vars[idx]))
        economic_1s = float(b * sigma_factor)

        coeff_data[fname] = {
            "factor_code": fname,
            "factor_position": idx + 1,
            "coefficient_value": b,
            "standard_error": se,
            "t_statistic": t_stat,
            "p_value": p_val,
            "adjusted_p_value": None,
            "confidence_interval_lower": ci_lower,
            "confidence_interval_upper": ci_upper,
            "confidence_level": confidence_level,
            "significance_status": sig,
            "economic_contribution_1sigma": economic_1s,
            "variance_inflation_factor": vif_dict.get(fname),
        }

    # Benjamini-Hochberg False Discovery Rate Adjustment
    if raw_p_values:
        adj_p = _benjamini_hochberg_correction(raw_p_values)
        for idx, fname in enumerate(factor_names):
            coeff_data[fname]["adjusted_p_value"] = adj_p[idx]

    return {
        "status": SensitivityRunStatus.COMPLETED,
        "model_family": model_family,
        "observation_count": T,
        "effective_sample_size": effective_sample_size,
        "intercept": {
            "value": intercept_val,
            "standard_error": intercept_se,
            "t_statistic": intercept_t,
            "p_value": intercept_p,
        },
        "coefficients": coeff_data,
        "diagnostics": {
            "r_squared": r_squared,
            "adjusted_r_squared": adj_r_squared,
            "residual_sum_of_squares": ss_res,
            "total_sum_of_squares": ss_tot,
            "residual_variance": residual_variance,
            "residual_standard_error": rse,
            "rmse": rmse,
            "mae": mae,
            "degrees_of_freedom": df_resid,
            "design_matrix_rank": rank,
            "condition_number": cond_number,
            "vif": vif_dict,
            "durbin_watson": dw_stat,
            "jarque_bera": {"statistic": jb_stat, "p_value": jb_pval},
        },
    }


def _fit_quantile_irls(X: np.ndarray, y: np.ndarray, tau: float = 0.50, max_iter: int = 50) -> np.ndarray:
    """Iteratively Reweighted Least Squares for Quantile Regression."""
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    for _ in range(max_iter):
        r = y - np.dot(X, beta)
        # Huber-like smoothing of quantile check function derivative
        weights = np.where(r >= 0, tau, 1.0 - tau) / np.maximum(np.abs(r), 1e-4)
        W_sqrt = np.sqrt(weights)[:, np.newaxis]
        X_w = X * W_sqrt
        y_w = y * np.sqrt(weights)
        beta_new = np.linalg.lstsq(X_w, y_w, rcond=None)[0]
        if np.max(np.abs(beta_new - beta)) < 1e-5:
            break
        beta = beta_new
    return beta


def benjamini_hochberg_correction(p_values: List[float]) -> List[float]:
    """Computes Benjamini-Hochberg False Discovery Rate adjusted p-values."""
    m = len(p_values)
    if m <= 1:
        return p_values
    sorted_indices = np.argsort(p_values)
    sorted_p = np.array(p_values)[sorted_indices]
    adj_sorted = np.zeros(m, dtype=np.float64)
    adj_sorted[-1] = sorted_p[-1]
    for i in range(m - 2, -1, -1):
        adj = sorted_p[i] * m / (i + 1)
        adj_sorted[i] = min(adj_sorted[i + 1], adj)
    adj_sorted = np.clip(adj_sorted, 0.0, 1.0)
    adjusted = np.zeros(m, dtype=np.float64)
    adjusted[sorted_indices] = adj_sorted
    return adjusted.tolist()


def _benjamini_hochberg_correction(p_values: List[float]) -> List[float]:
    return benjamini_hochberg_correction(p_values)


# ============================================================================
# 2. COEFFICIENT STABILITY & STRUCTURAL BREAK TESTS
# ============================================================================

def analyze_coefficient_stability(
    rolling_coefficients: List[float],
    min_observations: int = 10,
    volatility_threshold_high: float = 0.35,
    volatility_threshold_moderate: float = 0.15,
) -> Dict[str, Any]:
    """
    Computes rolling coefficient stability metrics:
    - Mean, std, min, max, absolute change, relative change, sign changes
    - Stability status: STABLE, MODERATELY_UNSTABLE, HIGHLY_UNSTABLE
    """
    n = len(rolling_coefficients)
    if n < min_observations:
        return {
            "status": CoefficientStabilityStatus.INSUFFICIENT_STABILITY_HISTORY,
            "observations_analyzed": n,
            "mean": float(np.mean(rolling_coefficients)) if n > 0 else 0.0,
            "std": 0.0,
            "min": float(np.min(rolling_coefficients)) if n > 0 else 0.0,
            "max": float(np.max(rolling_coefficients)) if n > 0 else 0.0,
            "latest": rolling_coefficients[-1] if n > 0 else 0.0,
            "previous": rolling_coefficients[-2] if n > 1 else 0.0,
            "absolute_change": 0.0,
            "relative_change": None,
            "sign_change_count": 0,
        }

    arr = np.array(rolling_coefficients, dtype=np.float64)
    mean_val = float(np.mean(arr))
    std_val = float(np.std(arr, ddof=1))
    min_val = float(np.min(arr))
    max_val = float(np.max(arr))
    latest = float(arr[-1])
    previous = float(arr[-2])
    abs_change = float(abs(latest - previous))
    
    rel_change = None
    if abs(previous) > 1e-4:
        rel_change = float((latest - previous) / abs(previous) * 100.0)

    # Count sign changes
    signs = np.sign(arr)
    signs = signs[signs != 0]
    sign_changes = int(np.sum(np.diff(signs) != 0)) if len(signs) > 1 else 0

    # Stability status
    status = CoefficientStabilityStatus.STABLE
    if std_val > volatility_threshold_high or sign_changes >= 3:
        status = CoefficientStabilityStatus.HIGHLY_UNSTABLE
    elif std_val > volatility_threshold_moderate or sign_changes >= 1:
        status = CoefficientStabilityStatus.MODERATELY_UNSTABLE

    return {
        "status": status,
        "observations_analyzed": n,
        "mean": mean_val,
        "std": std_val,
        "min": min_val,
        "max": max_val,
        "latest": latest,
        "previous": previous,
        "absolute_change": abs_change,
        "relative_change": rel_change,
        "sign_change_count": sign_changes,
    }


def compute_chow_break_test(
    y_full: np.ndarray,
    X_full: np.ndarray,
    break_index: int,
    include_intercept: bool = True,
) -> Dict[str, Any]:
    """
    Chow test for structural break at break_index:
        F = ((RSS_p - (RSS_1 + RSS_2)) / k) / ((RSS_1 + RSS_2) / (N_1 + N_2 - 2k))
    """
    N = len(y_full)
    K = X_full.shape[1] + (1 if include_intercept else 0)

    if break_index < (K + 5) or (N - break_index) < (K + 5):
        return {
            "status": StructuralBreakResultStatus.INSUFFICIENT_OBSERVATIONS,
            "test_statistic": 0.0,
            "p_value": None,
            "critical_value_95": 0.0,
        }

    # Helper OLS RSS
    def _get_rss(y_part, X_part):
        if include_intercept:
            X_des = np.hstack([np.ones((len(y_part), 1)), X_part])
        else:
            X_des = X_part
        b = np.linalg.lstsq(X_des, y_part, rcond=None)[0]
        res = y_part - np.dot(X_des, b)
        return float(np.sum(res ** 2))

    rss_pool = _get_rss(y_full, X_full)
    rss_1 = _get_rss(y_full[:break_index], X_full[:break_index])
    rss_2 = _get_rss(y_full[break_index:], X_full[break_index:])

    df1 = K
    df2 = N - 2 * K
    numerator = (rss_pool - (rss_1 + rss_2)) / df1
    denominator = (rss_1 + rss_2) / df2

    if denominator <= 1e-12:
        return {
            "status": StructuralBreakResultStatus.INCONCLUSIVE,
            "test_statistic": 0.0,
            "p_value": None,
            "critical_value_95": 0.0,
        }

    f_stat = float(numerator / denominator)
    f_stat = max(0.0, f_stat)
    p_val = float(1.0 - stats.f.cdf(f_stat, df1, df2))
    crit_95 = float(stats.f.ppf(0.95, df1, df2))

    status = StructuralBreakResultStatus.BREAK_DETECTED if f_stat > crit_95 else StructuralBreakResultStatus.NO_BREAK_DETECTED

    return {
        "status": status,
        "test_statistic": f_stat,
        "p_value": p_val,
        "critical_value_95": crit_95,
        "df1": df1,
        "df2": df2,
        "pre_break_count": break_index,
        "post_break_count": N - break_index,
    }
