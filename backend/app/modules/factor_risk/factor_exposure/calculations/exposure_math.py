"""
M08.02 Factor Exposure Mathematical & Econometric Engines.
Provides:
1. Multi-factor Rolling OLS, Expanding OLS, and EWLS Regression Solvers (QR/SVD decomposition)
2. Intercept and Excess-Return/Total-Return handling
3. Classical, HC3 Heteroskedasticity-Robust, and HAC Newey-West Standard Errors
4. Statistical diagnostics: R2, Adj-R2, Condition Number, Variance Inflation Factor (VIF), Rank
5. Normalization: 1-sigma standardized loading (beta * sigma_factor), cross-sectional z-score
6. Portfolio Aggregation: Signed NAV-weighted & Gross-normalized aggregation with coverage tracking
7. Symmetric Exact Decomposition: Delta(w*beta) = Delta(w)*((beta_t + beta_t-1)/2) + Delta(beta)*((w_t + w_t-1)/2)
"""
from typing import Dict, Any, List, Optional, Tuple
import math
import numpy as np
from scipy import stats

from backend.app.modules.factor_risk.factor_exposure.models import (
    EstimationMethod,
    StandardErrorMethod,
    LoadingQualityStatus,
    TiltClassification,
)


def estimate_multifactor_loadings(
    y_returns: np.ndarray,
    X_factors: np.ndarray,
    factor_names: List[str],
    estimation_method: EstimationMethod = EstimationMethod.ROLLING_OLS,
    include_intercept: bool = True,
    ewls_decay_factor: float = 0.94,
    min_observations: int = 30,
    min_obs_per_param_multiplier: int = 5,
    standard_error_method: StandardErrorMethod = StandardErrorMethod.HC3_HETEROSKEDASTICITY_ROBUST,
    confidence_level: float = 0.95,
) -> Dict[str, Any]:
    """
    Multifactor time-series regression solver using stable QR/SVD decomposition.
    Model:
        y_t = alpha + sum_k (beta_k * F_k,t) + eps_t
    Args:
        y_returns: (T,) array of dependent security returns.
        X_factors: (T, K) array of systematic factor returns.
        factor_names: list of K factor codes in pinned model order.
        estimation_method: ROLLING_OLS, EXPANDING_OLS, or EWLS.
        include_intercept: If True, prepends a column of ones.
        ewls_decay_factor: Lambda for exponential weighting (w_j = lambda^(T-1-j)).
        min_observations: Absolute minimum observation count.
        min_obs_per_param_multiplier: Multiplier c such that T >= c * P.
    """
    T = len(y_returns)
    K = len(factor_names)
    P = K + (1 if include_intercept else 0)

    # 1. Sample Size Checks
    if T < min_observations or T < (min_obs_per_param_multiplier * P) or X_factors.shape[0] != T:
        return {
            "status": LoadingQualityStatus.INSUFFICIENT_OBSERVATIONS,
            "observation_count": T,
            "loadings": {},
            "diagnostics": {
                "observation_count": T,
                "required_min": max(min_observations, min_obs_per_param_multiplier * P),
            },
        }

    # 2. Factor Variance Checks
    factor_vars = np.var(X_factors, axis=0, ddof=1)
    if np.any(factor_vars < 1e-12):
        return {
            "status": LoadingQualityStatus.LOW_VARIANCE_FACTOR,
            "observation_count": T,
            "loadings": {},
            "diagnostics": {"factor_variances": factor_vars.tolist()},
        }

    # 3. Construct Design Matrix
    if include_intercept:
        ones = np.ones((T, 1), dtype=np.float64)
        X = np.hstack([ones, X_factors])
    else:
        X = X_factors.copy()

    y = y_returns.copy()

    # 4. Weighting for EWLS
    if estimation_method == EstimationMethod.EWLS:
        # Weights: w_j = lambda^(T - 1 - j), normalized so sum(w) = T
        exponents = np.arange(T - 1, -1, -1, dtype=np.float64)
        weights = ewls_decay_factor ** exponents
        weights = weights / np.sum(weights) * T
        W_sqrt = np.sqrt(weights)[:, np.newaxis]
        X_w = X * W_sqrt
        y_w = y * np.sqrt(weights)
    else:
        X_w = X
        y_w = y

    # 5. Numerical Rank and Condition Number of Factor Matrix
    rank = int(np.linalg.matrix_rank(X_w))
    s_factors = np.linalg.svd(X_factors, compute_uv=False)
    cond_number = float(s_factors[0] / s_factors[-1]) if s_factors[-1] > 1e-12 else float("inf")

    if rank < P:
        return {
            "status": LoadingQualityStatus.MULTICOLLINEARITY_WARNING,
            "observation_count": T,
            "loadings": {},
            "diagnostics": {
                "rank": rank,
                "parameters": P,
                "condition_number": cond_number,
            },
        }

    # 6. Least-Squares Solution using QR Decomposition (Numerically Stable)
    # X_w = Q * R => R * beta = Q^T * y_w
    Q, R = np.linalg.qr(X_w)
    qty = np.dot(Q.T, y_w)
    try:
        coefficients = np.linalg.solve(R, qty)
    except np.linalg.LinAlgError:
        # Fallback to SVD pseudo-inverse if R is singular
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

    # 7. Standard Error and Covariance Matrix Estimation
    # (X^T X)^(-1) via R inverse
    try:
        R_inv = np.linalg.inv(R)
        xtx_inv = np.dot(R_inv, R_inv.T)
    except np.linalg.LinAlgError:
        xtx_inv = np.linalg.pinv(np.dot(X_w.T, X_w))

    if standard_error_method == StandardErrorMethod.HC3_HETEROSKEDASTICITY_ROBUST:
        # HC3: V = (X^T X)^(-1) (sum_t e_t^2 / (1 - h_t)^2 * x_t x_t^T) (X^T X)^(-1)
        # Hat diagonal: h_t = sum_j Q[t, j]^2
        h = np.sum(Q ** 2, axis=1)
        h = np.clip(h, 0.0, 0.9999)  # guard against exact leverage 1
        hc3_weights = (residuals / (1.0 - h)) ** 2
        meat = np.dot(X.T, X * hc3_weights[:, np.newaxis])
        cov_matrix = np.dot(xtx_inv, np.dot(meat, xtx_inv))
    elif standard_error_method == StandardErrorMethod.HAC_NEWEY_WEST:
        # Newey-West with bandwidth L = int(4 * (T/100)^(2/9))
        L = max(1, int(4.0 * ((T / 100.0) ** (2.0 / 9.0))))
        meat = np.dot(X.T, X * (residuals ** 2)[:, np.newaxis])
        for lag in range(1, L + 1):
            weight = 1.0 - (lag / (L + 1.0))
            cross = np.dot(X[lag:].T, (X[:-lag] * (residuals[lag:] * residuals[:-lag])[:, np.newaxis]))
            meat += weight * (cross + cross.T)
        cov_matrix = np.dot(xtx_inv, np.dot(meat, xtx_inv))
    else:
        # Classical OLS standard errors
        cov_matrix = residual_variance * xtx_inv

    std_errors = np.sqrt(np.maximum(0.0, np.diag(cov_matrix)))

    # Student-t critical value for confidence intervals
    alpha_sig = 1.0 - confidence_level
    t_crit = float(stats.t.ppf(1.0 - alpha_sig / 2.0, df=df_resid))

    # Variance Inflation Factor (VIF) for multicollinearity diagnosis
    vif_dict = {}
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

    # 8. Unpack Loadings
    loadings = {}
    intercept_val = None
    if include_intercept:
        intercept_val = float(coefficients[0])
        factor_coeffs = coefficients[1:]
        factor_se = std_errors[1:]
    else:
        factor_coeffs = coefficients
        factor_se = std_errors

    for idx, fname in enumerate(factor_names):
        b = float(factor_coeffs[idx])
        se = float(factor_se[idx])
        t_stat = float(b / se) if se > 1e-12 else None
        p_val = float(2.0 * (1.0 - stats.t.cdf(abs(t_stat), df=df_resid))) if t_stat is not None else None
        ci_lower = float(b - t_crit * se) if se > 1e-12 else None
        ci_upper = float(b + t_crit * se) if se > 1e-12 else None

        loadings[fname] = {
            "factor_code": fname,
            "factor_position": idx + 1,
            "loading_value": b,
            "standard_error": se,
            "t_statistic": t_stat,
            "p_value": p_val,
            "confidence_interval_lower": ci_lower,
            "confidence_interval_upper": ci_upper,
            "r_squared": r_squared,
            "adjusted_r_squared": adj_r_squared,
            "residual_variance": residual_variance,
            "observation_count": T,
            "variance_inflation_factor": vif_dict.get(fname),
            "status": LoadingQualityStatus.ESTIMATED,
        }

    status = LoadingQualityStatus.ESTIMATED
    if cond_number > 100.0 or any(v > 10.0 for v in vif_dict.values()):
        status = LoadingQualityStatus.MULTICOLLINEARITY_WARNING
    elif cond_number > 1000.0:
        status = LoadingQualityStatus.ILL_CONDITIONED

    return {
        "status": status,
        "intercept": intercept_val,
        "observation_count": T,
        "r_squared": r_squared,
        "adjusted_r_squared": adj_r_squared,
        "residual_variance": residual_variance,
        "loadings": loadings,
        "diagnostics": {
            "rank": rank,
            "condition_number": cond_number,
            "degrees_of_freedom": df_resid,
            "vif": vif_dict,
        },
    }


def compute_standardized_loading(
    raw_beta: float,
    factor_std_dev: float,
) -> float:
    """
    Computes 1-sigma standardized factor loading:
    beta^{1-sigma}_i,k = beta_i,k * sigma_k
    """
    return float(raw_beta * factor_std_dev)


def compute_cross_sectional_zscores(
    instrument_betas: Dict[str, float],
) -> Dict[str, Optional[float]]:
    """
    Computes cross-sectional z-score for each security relative to point-in-time universe:
    Z_i = (beta_i - mean(beta)) / std(beta)
    """
    values = [b for b in instrument_betas.values() if b is not None]
    if len(values) < 3:
        return {inst_id: None for inst_id in instrument_betas}

    mean_val = float(np.mean(values))
    std_val = float(np.std(values, ddof=1))

    if std_val < 1e-12:
        return {inst_id: 0.0 for inst_id in instrument_betas}

    return {
        inst_id: float((b - mean_val) / std_val) if b is not None else None
        for inst_id, b in instrument_betas.items()
    }


def aggregate_portfolio_factor_exposure(
    holdings: List[Dict[str, Any]],
    factor_code: str,
    portfolio_nav: float,
) -> Dict[str, Any]:
    """
    Aggregates instrument factor loadings into portfolio-level factor exposure.
    NAV-weighted:
        beta_p,k = sum_i (w_i * beta_i,k), where w_i = MV_i / NAV_p (signed)
    Gross-normalized:
        beta^{gross}_p,k = sum_i (w^{gross}_i * beta_i,k), where w^{gross}_i = MV_i / sum(|MV_j|)
    Coverage:
        Coverage = sum_{i in Covered} |w_i| / sum_{all} |w_i|
    """
    if portfolio_nav == 0.0 or math.isnan(portfolio_nav):
        return {
            "exposure_value": 0.0,
            "gross_normalized_exposure": 0.0,
            "coverage_percentage": 0.0,
            "covered_signed_weight": 0.0,
            "covered_absolute_weight": 0.0,
            "missing_signed_weight": 0.0,
            "missing_absolute_weight": 0.0,
            "holding_count": len(holdings),
            "covered_holding_count": 0,
            "uncovered_holding_count": len(holdings),
            "tilt_classification": TiltClassification.UNAVAILABLE,
        }

    total_abs_mv = 0.0
    covered_abs_mv = 0.0
    covered_signed_mv = 0.0
    missing_abs_mv = 0.0
    missing_signed_mv = 0.0

    sum_weighted_beta = 0.0
    sum_gross_weighted_beta = 0.0

    covered_count = 0
    uncovered_count = 0

    for h in holdings:
        signed_mv = float(h.get("signed_market_value", 0.0))
        abs_mv = abs(signed_mv)
        total_abs_mv += abs_mv

        loading = h.get("loadings", {}).get(factor_code)
        if loading is not None and not math.isnan(loading):
            covered_count += 1
            covered_abs_mv += abs_mv
            covered_signed_mv += signed_mv
            
            w_nav = signed_mv / portfolio_nav
            sum_weighted_beta += w_nav * loading
        else:
            uncovered_count += 1
            missing_abs_mv += abs_mv
            missing_signed_mv += signed_mv

    coverage_pct = float((covered_abs_mv / total_abs_mv * 100.0) if total_abs_mv > 0.0 else 0.0)
    covered_signed_w = float(covered_signed_mv / portfolio_nav)
    covered_abs_w = float(covered_abs_mv / portfolio_nav)
    missing_signed_w = float(missing_signed_mv / portfolio_nav)
    missing_abs_w = float(missing_abs_mv / portfolio_nav)

    # Gross-normalized exposure: weights sum to 1.0 over total absolute market value
    if total_abs_mv > 0.0:
        for h in holdings:
            loading = h.get("loadings", {}).get(factor_code)
            if loading is not None and not math.isnan(loading):
                w_gross = float(h.get("signed_market_value", 0.0)) / total_abs_mv
                sum_gross_weighted_beta += w_gross * loading

    # Factor tilt classification
    tilt = TiltClassification.NEUTRAL
    if coverage_pct < 50.0:
        tilt = TiltClassification.LOW_CONFIDENCE
    elif sum_weighted_beta > 0.50:
        tilt = TiltClassification.STRONG_POSITIVE
    elif sum_weighted_beta > 0.15:
        tilt = TiltClassification.MODERATE_POSITIVE
    elif sum_weighted_beta < -0.50:
        tilt = TiltClassification.STRONG_NEGATIVE
    elif sum_weighted_beta < -0.15:
        tilt = TiltClassification.MODERATE_NEGATIVE

    return {
        "exposure_value": float(sum_weighted_beta),
        "gross_normalized_exposure": float(sum_gross_weighted_beta),
        "coverage_percentage": float(coverage_pct),
        "covered_signed_weight": covered_signed_w,
        "covered_absolute_weight": covered_abs_w,
        "missing_signed_weight": missing_signed_w,
        "missing_absolute_weight": missing_abs_w,
        "holding_count": len(holdings),
        "covered_holding_count": covered_count,
        "uncovered_holding_count": uncovered_count,
        "tilt_classification": tilt,
    }


def decompose_exposure_change(
    earlier_holdings: Dict[str, Dict[str, float]],  # inst_id -> {"weight": w, "loading": beta}
    later_holdings: Dict[str, Dict[str, float]],    # inst_id -> {"weight": w, "loading": beta}
) -> Dict[str, Any]:
    """
    Symmetric exact decomposition of exposure change:
    Delta(w_i * beta_i) = Delta(w_i) * ((beta_t + beta_t-1)/2) + Delta(beta_i) * ((w_t + w_t-1)/2)
    Reconciles exactly: Delta(beta_p) = Weight_Effect + Loading_Effect + Entry_Exit_Effect
    """
    all_instruments = set(earlier_holdings.keys()).union(set(later_holdings.keys()))

    total_weight_effect = 0.0
    total_loading_effect = 0.0
    total_entry_exit_effect = 0.0

    earlier_exp = sum(h["weight"] * h["loading"] for h in earlier_holdings.values())
    later_exp = sum(h["weight"] * h["loading"] for h in later_holdings.values())
    observed_delta = later_exp - earlier_exp

    per_instrument_details = []

    for inst_id in sorted(all_instruments):
        in_earlier = inst_id in earlier_holdings
        in_later = inst_id in later_holdings

        if in_earlier and in_later:
            w_prev = earlier_holdings[inst_id]["weight"]
            b_prev = earlier_holdings[inst_id]["loading"]
            w_curr = later_holdings[inst_id]["weight"]
            b_curr = later_holdings[inst_id]["loading"]

            dw = w_curr - w_prev
            db = b_curr - b_prev
            b_avg = (b_curr + b_prev) / 2.0
            w_avg = (w_curr + w_prev) / 2.0

            w_eff = dw * b_avg
            l_eff = db * w_avg

            total_weight_effect += w_eff
            total_loading_effect += l_eff

            per_instrument_details.append({
                "instrument_id": inst_id,
                "type": "CONTINUOUS",
                "earlier_weight": w_prev,
                "later_weight": w_curr,
                "earlier_loading": b_prev,
                "later_loading": b_curr,
                "weight_effect": w_eff,
                "loading_effect": l_eff,
                "total_effect": w_eff + l_eff,
            })
        elif in_later and not in_earlier:
            # Newly entered holding
            w_curr = later_holdings[inst_id]["weight"]
            b_curr = later_holdings[inst_id]["loading"]
            eff = w_curr * b_curr
            total_entry_exit_effect += eff

            per_instrument_details.append({
                "instrument_id": inst_id,
                "type": "NEW_ENTRY",
                "earlier_weight": 0.0,
                "later_weight": w_curr,
                "earlier_loading": 0.0,
                "later_loading": b_curr,
                "weight_effect": eff,
                "loading_effect": 0.0,
                "total_effect": eff,
            })
        else:
            # Exited holding
            w_prev = earlier_holdings[inst_id]["weight"]
            b_prev = earlier_holdings[inst_id]["loading"]
            eff = -(w_prev * b_prev)
            total_entry_exit_effect += eff

            per_instrument_details.append({
                "instrument_id": inst_id,
                "type": "EXITED",
                "earlier_weight": w_prev,
                "later_weight": 0.0,
                "earlier_loading": b_prev,
                "later_loading": 0.0,
                "weight_effect": eff,
                "loading_effect": 0.0,
                "total_effect": eff,
            })

    total_explained = total_weight_effect + total_loading_effect + total_entry_exit_effect
    residual = observed_delta - total_explained

    pct_change = None
    if abs(earlier_exp) > 1e-4:
        pct_change = float((observed_delta / abs(earlier_exp)) * 100.0)

    return {
        "earlier_exposure": float(earlier_exp),
        "later_exposure": float(later_exp),
        "total_change": float(observed_delta),
        "percentage_change": pct_change,
        "weight_effect": float(total_weight_effect),
        "loading_effect": float(total_loading_effect),
        "entry_exit_effect": float(total_entry_exit_effect),
        "unreconciled_residual": float(residual),
        "instruments": per_instrument_details,
    }
