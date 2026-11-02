"""
M07.05 Correlation Analysis Mathematical & Statistical Engine.
High-precision statistical computations for Pearson, Spearman, Kendall tau-b,
pairwise session alignment, matrix PSD diagnostics, nearest correlation repair,
and rolling correlation analytics.
"""
from datetime import date, datetime
from decimal import Decimal
import math
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
from scipy import stats

from backend.app.modules.market_risk.correlation.models import (
    CorrelationEstimator,
    CorrelationAlignmentPolicy,
    CorrelationMissingDataPolicy,
    PSDStatus,
)


def align_two_series(
    series_a: List[Tuple[date, Decimal]],
    series_b: List[Tuple[date, Decimal]],
    alignment_policy: CorrelationAlignmentPolicy = CorrelationAlignmentPolicy.COMMON_SESSION_DATE,
    missing_data_policy: CorrelationMissingDataPolicy = CorrelationMissingDataPolicy.STRICT_PAIRWISE_COMPLETE,
) -> Tuple[List[date], np.ndarray, np.ndarray]:
    """
    Align two historical return series by date according to policy.
    Returns:
        (aligned_dates, returns_a_np, returns_b_np)
    """
    dict_a = {d: float(val) for d, val in series_a}
    dict_b = {d: float(val) for d, val in series_b}

    if alignment_policy in (
        CorrelationAlignmentPolicy.COMMON_SESSION_DATE,
        CorrelationAlignmentPolicy.COMMON_TIMESTAMP,
    ):
        common_dates = sorted(set(dict_a.keys()).intersection(set(dict_b.keys())))
    elif alignment_policy == CorrelationAlignmentPolicy.CROSS_MARKET_CALENDAR_UNION:
        # Union with forward fill or omission
        all_dates = sorted(set(dict_a.keys()).union(set(dict_b.keys())))
        aligned_dates = []
        ret_a_list = []
        ret_b_list = []
        last_a = None
        last_b = None
        for d in all_dates:
            val_a = dict_a.get(d)
            val_b = dict_b.get(d)
            if val_a is not None:
                last_a = val_a
            if val_b is not None:
                last_b = val_b

            if missing_data_policy == CorrelationMissingDataPolicy.FORWARD_FILL_LAST_PRICE:
                if last_a is not None and last_b is not None:
                    aligned_dates.append(d)
                    ret_a_list.append(last_a)
                    ret_b_list.append(last_b)
            else:
                if val_a is not None and val_b is not None:
                    aligned_dates.append(d)
                    ret_a_list.append(val_a)
                    ret_b_list.append(val_b)
        return aligned_dates, np.array(ret_a_list, dtype=np.float64), np.array(ret_b_list, dtype=np.float64)
    else:
        common_dates = sorted(set(dict_a.keys()).intersection(set(dict_b.keys())))

    dates_out = []
    a_vals = []
    b_vals = []
    for d in common_dates:
        va = dict_a[d]
        vb = dict_b[d]
        if np.isfinite(va) and np.isfinite(vb):
            dates_out.append(d)
            a_vals.append(va)
            b_vals.append(vb)

    return dates_out, np.array(a_vals, dtype=np.float64), np.array(b_vals, dtype=np.float64)


def calculate_pairwise_correlation(
    x: np.ndarray,
    y: np.ndarray,
    estimator: CorrelationEstimator = CorrelationEstimator.PEARSON,
    min_observations: int = 5,
) -> Dict[str, Any]:
    """
    Compute pairwise correlation between two aligned 1D numpy arrays of returns.
    Includes p-value, t-statistic, std_error, 95% confidence intervals, and covariance.
    """
    n = len(x)
    if n < min_observations or len(y) != n:
        return {
            "correlation": 0.0,
            "sample_size": n,
            "p_value": None,
            "t_statistic": None,
            "std_error": None,
            "ci_lower_95": None,
            "ci_upper_95": None,
            "covariance": None,
            "volatility_a": None,
            "volatility_b": None,
            "is_valid": False,
        }

    std_x = float(np.std(x, ddof=1)) if n > 1 else 0.0
    std_y = float(np.std(y, ddof=1)) if n > 1 else 0.0

    # If either series has zero variance, correlation is undefined / zero
    if std_x < 1e-12 or std_y < 1e-12:
        return {
            "correlation": 0.0,
            "sample_size": n,
            "p_value": 1.0,
            "t_statistic": 0.0,
            "std_error": None,
            "ci_lower_95": 0.0,
            "ci_upper_95": 0.0,
            "covariance": 0.0,
            "volatility_a": std_x,
            "volatility_b": std_y,
            "is_valid": True,
        }

    # Covariance
    cov = float(np.cov(x, y, ddof=1)[0, 1])

    if estimator == CorrelationEstimator.PEARSON:
        r, p_val = stats.pearsonr(x, y)
    elif estimator == CorrelationEstimator.SPEARMAN:
        res = stats.spearmanr(x, y)
        r, p_val = float(res.statistic), float(res.pvalue)
    elif estimator == CorrelationEstimator.KENDALL_TAU_B:
        res = stats.kendalltau(x, y, variant='b')
        r, p_val = float(res.statistic), float(res.pvalue)
    else:
        r, p_val = stats.pearsonr(x, y)

    # Clamp r to [-1.0, 1.0] due to floating precision
    r = max(-1.0, min(1.0, float(r)))

    # t-statistic and std error for Pearson
    t_stat = None
    std_err = None
    ci_lower = None
    ci_upper = None

    if n > 2 and abs(r) < 1.0:
        t_stat = float(r * math.sqrt((n - 2) / max(1e-12, (1.0 - r * r))))
        std_err = float(math.sqrt((1.0 - r * r) / (n - 2)))
        # Fisher z-transformation for 95% CI
        try:
            z = np.arctanh(r)
            se_z = 1.0 / math.sqrt(n - 3) if n > 3 else 0.0
            z_low = z - 1.95996 * se_z
            z_high = z + 1.95996 * se_z
            ci_lower = float(np.tanh(z_low))
            ci_upper = float(np.tanh(z_high))
        except Exception:
            ci_lower = None
            ci_upper = None
    elif abs(r) >= 1.0:
        ci_lower = r
        ci_upper = r

    return {
        "correlation": r,
        "sample_size": n,
        "p_value": float(p_val) if np.isfinite(p_val) else None,
        "t_statistic": t_stat,
        "std_error": std_err,
        "ci_lower_95": ci_lower,
        "ci_upper_95": ci_upper,
        "covariance": cov,
        "volatility_a": std_x,
        "volatility_b": std_y,
        "is_valid": True,
    }


def compute_correlation_matrix(
    returns_dict: Dict[str, List[Tuple[date, Decimal]]],
    asset_order: List[str],
    estimator: CorrelationEstimator = CorrelationEstimator.PEARSON,
    min_observations: int = 5,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Construct complete N x N correlation matrix across assets.
    Ensures:
      - Unit diagonal (1.0)
      - Exact symmetry
      - Canonical asset ordering
      - Completeness ratio
      - PSD eigenvalue diagnostics
    """
    n = len(asset_order)
    matrix = np.eye(n, dtype=np.float64)
    total_pairs = (n * (n - 1)) // 2
    valid_pairs = 0
    correlations_list = []

    for i in range(n):
        for j in range(i + 1, n):
            asset_i = asset_order[i]
            asset_j = asset_order[j]
            s_i = returns_dict.get(asset_i, [])
            s_j = returns_dict.get(asset_j, [])

            _, x, y = align_two_series(s_i, s_j)
            pair_res = calculate_pairwise_correlation(x, y, estimator=estimator, min_observations=min_observations)
            rho = pair_res["correlation"]
            matrix[i, j] = rho
            matrix[j, i] = rho

            if pair_res["is_valid"]:
                valid_pairs += 1
            correlations_list.append(rho)

    completeness_ratio = (valid_pairs / total_pairs) if total_pairs > 0 else 1.0
    avg_corr = float(np.mean(correlations_list)) if correlations_list else 1.0
    med_corr = float(np.median(correlations_list)) if correlations_list else 1.0

    # PSD & Eigenvalue diagnostics
    # Use eigh for symmetric matrix
    eigenvalues = np.linalg.eigvalsh(matrix)
    min_eig = float(np.min(eigenvalues))
    max_eig = float(np.max(eigenvalues))
    neg_eigs = int(np.sum(eigenvalues < -1e-8))

    cond_number = None
    if min_eig > 1e-12:
        cond_number = float(max_eig / min_eig)

    is_psd = neg_eigs == 0 and min_eig >= -1e-8
    psd_status = PSDStatus.VALID_PSD if is_psd else PSDStatus.NON_PSD

    diagnostics = {
        "psd_status": psd_status,
        "min_eigenvalue": min_eig,
        "max_eigenvalue": max_eig,
        "condition_number": cond_number,
        "negative_eigenvalues_count": neg_eigs,
        "completeness_ratio": completeness_ratio,
        "average_correlation": avg_corr,
        "median_correlation": med_corr,
    }

    return matrix, diagnostics


def repair_psd_matrix(
    raw_matrix: np.ndarray,
    method: str = "EIGENVALUE_CLIPPING",
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Repair a non-PSD correlation matrix to nearest PSD representation.
    Methods:
      - "EIGENVALUE_CLIPPING": Spectral projection (clip negative eigenvalues to epsilon, rescale diagonal to 1.0)
      - "HIGHAM_NEAREST": Alternating projections / Higham (2002) nearest correlation matrix algorithm
    """
    matrix = raw_matrix.copy()
    n = matrix.shape[0]

    if method.upper() == "HIGHAM_NEAREST":
        # Higham's alternating projection algorithm
        # S_0 = matrix, gamma_k = 0
        gamma = np.zeros_like(matrix)
        y = matrix.copy()
        max_iter = 100
        tol = 1e-7

        for k in range(max_iter):
            r = y - gamma
            # Project onto positive semi-definite cone
            w, v = np.linalg.eigh(r)
            w_clipped = np.maximum(w, 1e-8)
            x = v @ np.diag(w_clipped) @ v.T
            gamma = x - r
            # Project onto unit diagonal symmetric space
            y_next = x.copy()
            np.fill_diagonal(y_next, 1.0)
            y_next = 0.5 * (y_next + y_next.T)

            if np.max(np.abs(y_next - y)) < tol:
                y = y_next
                break
            y = y_next

        repaired = y
    else:
        # Spectral clipping & diagonal normalization (standard in risk models)
        w, v = np.linalg.eigh(matrix)
        w_clipped = np.maximum(w, 1e-8)
        repaired_cov = v @ np.diag(w_clipped) @ v.T
        # Rescale diagonal to 1.0
        d = np.sqrt(np.diag(repaired_cov))
        d_inv = 1.0 / np.maximum(d, 1e-12)
        repaired = repaired_cov * np.outer(d_inv, d_inv)
        np.fill_diagonal(repaired, 1.0)
        repaired = 0.5 * (repaired + repaired.T)

    new_eigs = np.linalg.eigvalsh(repaired)
    min_eig_after = float(np.min(new_eigs))
    frob_dist = float(np.linalg.norm(repaired - raw_matrix, 'fro'))
    max_diff = float(np.max(np.abs(repaired - raw_matrix)))

    transform_info = {
        "method": method,
        "min_eigenvalue_after": min_eig_after,
        "frobenius_distance": frob_dist,
        "max_absolute_element_diff": max_diff,
    }

    return repaired, transform_info


def calculate_rolling_correlation(
    aligned_dates: List[date],
    returns_a: np.ndarray,
    returns_b: np.ndarray,
    window_days: int = 30,
    estimator: CorrelationEstimator = CorrelationEstimator.PEARSON,
) -> List[Dict[str, Any]]:
    """
    Calculate rolling correlation series over fixed observation windows.
    Tracks correlation rho, delta_rho (change vs prior window), and sample_size.
    """
    n = len(aligned_dates)
    results = []
    if n < window_days:
        return results

    # Full period baseline correlation
    full_res = calculate_pairwise_correlation(returns_a, returns_b, estimator=estimator)
    baseline_rho = full_res["correlation"]

    prior_rho = None

    for i in range(window_days, n + 1):
        win_dates = aligned_dates[i - window_days : i]
        win_a = returns_a[i - window_days : i]
        win_b = returns_b[i - window_days : i]

        pair_calc = calculate_pairwise_correlation(win_a, win_b, estimator=estimator, min_observations=min(10, window_days // 2))
        curr_rho = pair_calc["correlation"]
        
        delta_rho = (curr_rho - prior_rho) if prior_rho is not None else None
        baseline_dev = (curr_rho - baseline_rho) if baseline_rho is not None else None

        results.append({
            "observation_date": win_dates[-1],
            "correlation": curr_rho,
            "delta_rho": delta_rho,
            "baseline_deviation": baseline_dev,
            "sample_size": len(win_a),
        })

        prior_rho = curr_rho

    return results
