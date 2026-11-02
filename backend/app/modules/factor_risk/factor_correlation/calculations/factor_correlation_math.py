"""
M08.07 Factor Correlation & Covariance Mathematical & Econometric Engine.
Provides pure, mathematically correct, auditable routines for:
1. Inter-Factor Correlation Matrix Estimation (Pearson, Spearman, Kendall)
2. Zero-variance and undefined correlation validation
3. Factor Covariance Matrix Estimation (Sample, Exponentially Weighted, Ledoit-Wolf Shrinkage)
4. Mathematical Consistency: Sigma_F == D * P_F * D within float64 numerical tolerance
5. Matrix Diagnostics & PSD Spectral Validation:
   - Symmetry verification
   - Rank and condition number
   - Eigenvalue analysis and nearest-PSD (Higham) projection
6. Rolling & Expanding Factor Relationships:
   - Rolling Pearson / Covariance series
   - Signed correlation changes and absolute strength changes
   - Correlation range, historical percentile rank, and stability categorization
7. Correlation Regime & Break Detection:
   - Threshold monitoring (Positive/Negative/Absolute)
   - Rapid delta alerts
   - Sign reversal detection
   - Baseline statistical divergence & Fisher's z transformation
   - CUSUM cumulative monitoring & candidate change-point detection
   - Persistence & hysteresis recovery logic
"""

from datetime import date
from decimal import Decimal
import math
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import scipy.stats as stats


# ============================================================================
# 1. PAIRWISE & INTER-FACTOR CORRELATION ESTIMATION
# ============================================================================

def compute_pairwise_correlation(
    x: np.ndarray,
    y: np.ndarray,
    method: str = "PEARSON",
    confidence_level: float = 0.95,
) -> Dict[str, Any]:
    """
    Computes pairwise correlation between two factor return series.
    Detects zero-variance and returns undefined (None) rather than zero.
    Calculates Fisher's z transformation confidence interval and p-value.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)

    if len(x) != len(y):
        raise ValueError(f"Length mismatch: x={len(x)}, y={len(y)}")

    valid_mask = np.isfinite(x) & np.isfinite(y)
    x_clean = x[valid_mask]
    y_clean = y[valid_mask]
    N = len(x_clean)

    if N < 3:
        return {
            "observation_count": N,
            "correlation": None,
            "covariance": None,
            "std_x": None,
            "std_y": None,
            "p_value": None,
            "ci_lower": None,
            "ci_upper": None,
            "is_defined": False,
            "reason": f"Insufficient observations: {N} < 3",
        }

    std_x = float(np.std(x_clean, ddof=1))
    std_y = float(np.std(y_clean, ddof=1))

    if std_x < 1e-12 or std_y < 1e-12:
        return {
            "observation_count": N,
            "correlation": None,
            "covariance": 0.0,
            "std_x": std_x,
            "std_y": std_y,
            "p_value": None,
            "ci_lower": None,
            "ci_upper": None,
            "is_defined": False,
            "reason": "Zero variance detected in one or both factor series",
        }

    # Covariance
    mean_x = float(np.mean(x_clean))
    mean_y = float(np.mean(y_clean))
    cov_val = float(np.sum((x_clean - mean_x) * (y_clean - mean_y)) / (N - 1))

    method_upper = method.upper()
    if method_upper == "SPEARMAN":
        corr_val, p_val = stats.spearmanr(x_clean, y_clean)
        corr_val, p_val = float(corr_val), float(p_val)
    elif method_upper == "KENDALL":
        corr_val, p_val = stats.kendalltau(x_clean, y_clean)
        corr_val, p_val = float(corr_val), float(p_val)
    else:  # PEARSON baseline
        corr_val = cov_val / (std_x * std_y)
        corr_val = max(-1.0, min(1.0, corr_val))
        # Two-tailed t-test p-value
        if abs(corr_val) >= 1.0:
            p_val = 0.0
        else:
            t_stat = corr_val * math.sqrt((N - 2) / (1.0 - corr_val ** 2))
            p_val = float(2.0 * (1.0 - stats.t.cdf(abs(t_stat), df=N - 2)))

    # Fisher's z confidence interval (for Pearson)
    ci_lower, ci_upper = None, None
    if method_upper == "PEARSON" and abs(corr_val) < 0.999999 and N > 3:
        z = np.arctanh(corr_val)
        se_z = 1.0 / math.sqrt(N - 3)
        z_crit = stats.norm.ppf(0.5 + confidence_level / 2.0)
        ci_lower = float(np.tanh(z - z_crit * se_z))
        ci_upper = float(np.tanh(z + z_crit * se_z))

    return {
        "observation_count": N,
        "correlation": corr_val,
        "covariance": cov_val,
        "std_x": std_x,
        "std_y": std_y,
        "p_value": p_val,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "is_defined": True,
        "reason": None,
    }


def compute_inter_factor_correlation_matrix(
    returns_matrix: np.ndarray,
    method: str = "PEARSON",
    tolerance: float = 1e-8,
) -> Dict[str, Any]:
    """
    Computes complete K x K inter-factor correlation matrix from T x K returns.
    Enforces exact unit diagonal and validates spectral properties.
    """
    T, K = returns_matrix.shape
    if T < 3:
        raise ValueError(f"At least 3 observations required, got T={T}")
    if K < 1:
        raise ValueError(f"At least 1 factor required, got K={K}")

    corr_matrix = np.eye(K, dtype=np.float64)
    cov_matrix = np.zeros((K, K), dtype=np.float64)
    stds = np.zeros(K, dtype=np.float64)
    is_valid = True
    undefined_pairs = []

    for k in range(K):
        col = returns_matrix[:, k]
        s = float(np.std(col, ddof=1))
        stds[k] = s
        cov_matrix[k, k] = s ** 2
        if s < 1e-12:
            is_valid = False
            undefined_pairs.append((k, k, "Zero variance factor"))

    for i in range(K):
        for j in range(i + 1, K):
            res = compute_pairwise_correlation(
                returns_matrix[:, i], returns_matrix[:, j], method=method
            )
            if res["is_defined"]:
                r = res["correlation"]
                c = res["covariance"]
                corr_matrix[i, j] = r
                corr_matrix[j, i] = r
                cov_matrix[i, j] = c
                cov_matrix[j, i] = c
            else:
                is_valid = False
                undefined_pairs.append((i, j, res["reason"]))
                corr_matrix[i, j] = np.nan
                corr_matrix[j, i] = np.nan
                cov_matrix[i, j] = np.nan
                cov_matrix[j, i] = np.nan

    # Symmetry and eigenvalue analysis if fully defined
    if is_valid and not np.isnan(corr_matrix).any():
        eigvals = np.linalg.eigvalsh(corr_matrix)
        min_eig = float(np.min(eigvals))
        max_eig = float(np.max(eigvals))
        is_psd = bool(min_eig >= -tolerance)
        cond_num = float(max_eig / min_eig) if min_eig > tolerance else float("inf")
        rank = int(np.linalg.matrix_rank(corr_matrix, tol=tolerance))
    else:
        min_eig, max_eig, cond_num, rank, is_psd = None, None, None, None, False

    return {
        "correlation_matrix": corr_matrix,
        "covariance_matrix": cov_matrix,
        "factor_stds": stds,
        "is_valid": is_valid,
        "is_positive_semidefinite": is_psd,
        "min_eigenvalue": min_eig,
        "max_eigenvalue": max_eig,
        "condition_number": cond_num,
        "matrix_rank": rank,
        "undefined_pairs": undefined_pairs,
        "dimension": K,
        "observation_count": T,
    }


# ============================================================================
# 2. FACTOR COVARIANCE ESTIMATION & CONSISTENCY
# ============================================================================

def estimate_factor_covariance(
    returns_matrix: np.ndarray,
    method: str = "SAMPLE",
    annualization_factor: float = 252.0,
    decay_factor: float = 0.94,
    shrinkage_target: str = "IDENTITY",
    shrinkage_intensity: Optional[float] = None,
    tolerance: float = 1e-8,
) -> Dict[str, Any]:
    """
    Estimates K x K factor covariance matrix via:
    1. SAMPLE: Sample covariance (unbiased N-1 denominator)
    2. EXPONENTIALLY_WEIGHTED: EWMA covariance with lambda decay
    3. LEDOIT_WOLF: Analytical shrinkage toward structured target
    
    Verifies mutual consistency: Sigma_F == D * P_F * D within float64 precision.
    """
    T, K = returns_matrix.shape
    if T < 2:
        raise ValueError(f"At least 2 observations required, got T={T}")

    method_upper = method.upper()

    if method_upper == "EXPONENTIALLY_WEIGHTED":
        lam = float(decay_factor)
        powers = np.arange(T - 1, -1, -1)
        w = (1.0 - lam) * (lam ** powers)
        w /= np.sum(w)
        mean_vec = np.sum(returns_matrix * w[:, np.newaxis], axis=0)
        demeaned = returns_matrix - mean_vec
        cov_period = (demeaned * w[:, np.newaxis]).T @ demeaned
        # Scale for unbiasedness
        denom = 1.0 - np.sum(w ** 2)
        if denom > 0:
            cov_period = cov_period / denom
        eff_n = float(1.0 / np.sum(w ** 2))
    elif method_upper == "LEDOIT_WOLF":
        # Sample baseline
        mean_vec = np.mean(returns_matrix, axis=0)
        demeaned = returns_matrix - mean_vec
        sample_cov = (demeaned.T @ demeaned) / (T - 1)

        # Target matrix
        var_diag = np.diag(sample_cov)
        mean_var = float(np.mean(var_diag))
        if shrinkage_target == "IDENTITY":
            target = mean_var * np.eye(K)
        else:
            # Equicorrelation target
            stds = np.sqrt(np.maximum(var_diag, 1e-12))
            corr = sample_cov / np.outer(stds, stds)
            np.fill_diagonal(corr, 0.0)
            avg_corr = float(np.sum(corr) / (K * (K - 1))) if K > 1 else 0.0
            target = avg_corr * np.outer(stds, stds)
            np.fill_diagonal(target, var_diag)

        if shrinkage_intensity is not None:
            sh_intensity = max(0.0, min(1.0, float(shrinkage_intensity)))
        else:
            # Analytical Ledoit-Wolf intensity formula approximation
            diff = sample_cov - target
            delta2 = np.sum(diff ** 2)
            y = demeaned ** 2
            phi = np.sum((y.T @ y) / (T - 1) - sample_cov ** 2)
            sh_intensity = float(max(0.0, min(1.0, phi / (delta2 * T)))) if delta2 > 1e-12 else 0.0

        cov_period = (1.0 - sh_intensity) * sample_cov + sh_intensity * target
        eff_n = float(T)
    else:  # SAMPLE baseline
        mean_vec = np.mean(returns_matrix, axis=0)
        demeaned = returns_matrix - mean_vec
        cov_period = (demeaned.T @ demeaned) / (T - 1)
        eff_n = float(T)

    # Force exact symmetry
    cov_period = 0.5 * (cov_period + cov_period.T)
    cov_ann = cov_period * annualization_factor

    # Derive corresponding correlation matrix P_F and factor stds
    variances = np.diag(cov_period)
    stds = np.sqrt(np.maximum(variances, 1e-12))
    corr_matrix = cov_period / np.outer(stds, stds)
    corr_matrix = np.clip(corr_matrix, -1.0, 1.0)
    np.fill_diagonal(corr_matrix, 1.0)

    # Validate Sigma_F == D * P_F * D consistency
    recon_cov = np.outer(stds, stds) * corr_matrix
    max_consistency_diff = float(np.max(np.abs(cov_period - recon_cov)))

    # Spectral analysis
    eigvals = np.linalg.eigvalsh(cov_period)
    min_eig = float(np.min(eigvals))
    max_eig = float(np.max(eigvals))
    is_psd = bool(min_eig >= -tolerance)
    cond_num = float(max_eig / min_eig) if min_eig > tolerance else float("inf")
    rank = int(np.linalg.matrix_rank(cov_period, tol=tolerance))

    return {
        "covariance_matrix_period": cov_period,
        "covariance_matrix_annualized": cov_ann,
        "correlation_matrix": corr_matrix,
        "factor_stds_period": stds,
        "factor_stds_annualized": stds * math.sqrt(annualization_factor),
        "is_positive_semidefinite": is_psd,
        "min_eigenvalue": min_eig,
        "max_eigenvalue": max_eig,
        "condition_number": cond_num,
        "matrix_rank": rank,
        "effective_sample_size": eff_n,
        "consistency_diff": max_consistency_diff,
        "is_consistent": bool(max_consistency_diff < 1e-6),
        "dimension": K,
        "observation_count": T,
    }


def project_to_nearest_psd(
    matrix: np.ndarray,
    epsilon: float = 1e-7,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Higham (2002) spectral projection onto the nearest positive semi-definite cone.
    Clips negative eigenvalues to epsilon and reconstructs matrix.
    Preserves original matrix audit trail and logs eigenvalue adjustments.
    """
    sym = 0.5 * (matrix + matrix.T)
    eigvals, eigvecs = np.linalg.eigh(sym)

    adjusted_eigvals = np.maximum(eigvals, epsilon)
    reconstructed = eigvecs @ np.diag(adjusted_eigvals) @ eigvecs.T
    reconstructed = 0.5 * (reconstructed + reconstructed.T)

    max_shift = float(np.max(np.abs(reconstructed - sym)))
    neg_count = int(np.sum(eigvals < 0))

    meta = {
        "original_min_eigenvalue": float(np.min(eigvals)),
        "adjusted_min_eigenvalue": float(np.min(adjusted_eigvals)),
        "negative_eigenvalues_clipped": neg_count,
        "maximum_absolute_matrix_shift": max_shift,
    }
    return reconstructed, meta


# ============================================================================
# 3. ROLLING RELATIONSHIPS & HISTORICAL COMPARISON
# ============================================================================

def compute_rolling_factor_relationships(
    returns_x: np.ndarray,
    returns_y: np.ndarray,
    dates: List[date],
    window_length: int = 60,
    min_observations: int = 20,
    baseline_window: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Computes rolling correlation and covariance time series:
    - Current vs previous observation change
    - Signed correlation delta vs Absolute strength delta
    - Historical baseline comparison and percentile rank
    - Sign reversal identification
    """
    x = np.asarray(returns_x, dtype=np.float64)
    y = np.asarray(returns_y, dtype=np.float64)
    T = len(x)

    if T < min_observations:
        raise ValueError(f"Total observations {T} is less than minimum {min_observations}")

    rolling_dates = []
    rolling_corr = []
    rolling_cov = []
    rolling_std_x = []
    rolling_std_y = []
    obs_counts = []

    for t in range(window_length - 1, T):
        w_x = x[t - window_length + 1 : t + 1]
        w_y = y[t - window_length + 1 : t + 1]
        res = compute_pairwise_correlation(w_x, w_y, method="PEARSON")
        if res["is_defined"]:
            rolling_dates.append(dates[t])
            rolling_corr.append(res["correlation"])
            rolling_cov.append(res["covariance"])
            rolling_std_x.append(res["std_x"])
            rolling_std_y.append(res["std_y"])
            obs_counts.append(res["observation_count"])

    if not rolling_corr:
        raise ValueError("No valid rolling correlations could be computed")

    corr_arr = np.array(rolling_corr, dtype=np.float64)
    current_corr = float(corr_arr[-1])
    prev_corr = float(corr_arr[-2]) if len(corr_arr) > 1 else current_corr

    signed_change = current_corr - prev_corr
    abs_strength_change = abs(current_corr) - abs(prev_corr)
    is_sign_reversal = bool((current_corr * prev_corr) < 0 and abs(current_corr) > 0.05)

    # Baseline calculation
    b_window = baseline_window if baseline_window and baseline_window <= len(corr_arr) else len(corr_arr)
    baseline_sample = corr_arr[-b_window:]
    baseline_mean = float(np.mean(baseline_sample))
    baseline_std = float(np.std(baseline_sample, ddof=1)) if len(baseline_sample) > 1 else 0.0
    percentile_rank = float(stats.percentileofscore(corr_arr, current_corr))

    # Relationship stability classification
    if abs(current_corr) < 0.20:
        stability = "WEAK_RELATIONSHIP"
    elif is_sign_reversal:
        stability = "SIGN_REVERSAL"
    elif baseline_std > 0.35:
        stability = "HIGH_VOLATILITY_RELATIONSHIP"
    elif signed_change > 0.15:
        stability = "INCREASING_POSITIVE"
    elif signed_change < -0.15:
        stability = "INCREASING_NEGATIVE"
    elif current_corr >= 0.20:
        stability = "STABLE_POSITIVE"
    else:
        stability = "STABLE_NEGATIVE"

    return {
        "dates": rolling_dates,
        "rolling_correlations": rolling_corr,
        "rolling_covariances": rolling_cov,
        "rolling_std_x": rolling_std_x,
        "rolling_std_y": rolling_std_y,
        "observation_counts": obs_counts,
        "current_correlation": current_corr,
        "previous_correlation": prev_corr,
        "signed_correlation_change": signed_change,
        "absolute_strength_change": abs_strength_change,
        "is_sign_reversal": is_sign_reversal,
        "rolling_min": float(np.min(corr_arr)),
        "rolling_max": float(np.max(corr_arr)),
        "rolling_mean": float(np.mean(corr_arr)),
        "rolling_std": float(np.std(corr_arr, ddof=1)) if len(corr_arr) > 1 else 0.0,
        "baseline_correlation": baseline_mean,
        "percentile_rank": percentile_rank,
        "relationship_stability": stability,
    }


# ============================================================================
# 4. REGIME & STRUCTURAL BREAK DETECTION
# ============================================================================

def evaluate_correlation_regimes(
    current_correlation: float,
    previous_correlation: float,
    baseline_correlation: float,
    consecutive_above_threshold_count: int = 1,
    high_positive_threshold: float = 0.70,
    high_negative_threshold: float = -0.70,
    rapid_change_threshold: float = 0.25,
    confirmation_required: int = 2,
    recovery_threshold: float = 0.60,
    rolling_correlation_series: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """
    Evaluates correlation regime states, alert triggers, and structural break signals.
    Distinguishes:
    - High positive vs high negative coherence
    - Rapid shock changes vs persistent regimes
    - Sign reversals
    - CUSUM-style structural shift indicators
    """
    r_curr = current_correlation
    r_prev = previous_correlation
    r_base = baseline_correlation
    delta = r_curr - r_prev
    delta_base = r_curr - r_base

    alerts = []
    is_high_pos = bool(r_curr >= high_positive_threshold)
    is_high_neg = bool(r_curr <= high_negative_threshold)
    is_rapid_change = bool(abs(delta) >= rapid_change_threshold)
    is_sign_rev = bool((r_curr * r_prev) < 0 and abs(r_curr - r_prev) >= 0.20)

    # Persistence check
    is_persistent = bool(consecutive_above_threshold_count >= confirmation_required and (is_high_pos or is_high_neg))

    if is_high_pos:
        severity = "HIGH" if r_curr > 0.85 else "WARNING"
        alerts.append({
            "alert_type": "HIGH_POSITIVE_CORRELATION",
            "severity": severity,
            "threshold": high_positive_threshold,
            "current_value": r_curr,
            "message": f"High positive factor correlation {r_curr:.4f} exceeds {high_positive_threshold}",
        })

    if is_high_neg:
        severity = "HIGH" if r_curr < -0.85 else "WARNING"
        alerts.append({
            "alert_type": "HIGH_NEGATIVE_CORRELATION",
            "severity": severity,
            "threshold": high_negative_threshold,
            "current_value": r_curr,
            "message": f"High negative factor correlation {r_curr:.4f} is below {high_negative_threshold}",
        })

    if is_rapid_change:
        alerts.append({
            "alert_type": "RAPID_CORRELATION_CHANGE",
            "severity": "WARNING",
            "threshold": rapid_change_threshold,
            "current_value": delta,
            "message": f"Rapid correlation shift of {delta:.4f} exceeds threshold {rapid_change_threshold}",
        })

    if is_sign_rev:
        alerts.append({
            "alert_type": "SIGN_REVERSAL",
            "severity": "WARNING",
            "threshold": 0.0,
            "current_value": r_curr,
            "message": f"Factor correlation sign reversal from {r_prev:.4f} to {r_curr:.4f}",
        })

    # CUSUM structural break indicator on rolling series
    has_structural_break = False
    max_cusum_stat = 0.0
    if rolling_correlation_series is not None and len(rolling_correlation_series) >= 20:
        c_series = np.asarray(rolling_correlation_series, dtype=np.float64)
        c_mean = np.mean(c_series)
        c_std = np.std(c_series, ddof=1)
        if c_std > 1e-12:
            cusum_path = np.cumsum(c_series - c_mean)
            max_cusum_stat = float(np.max(np.abs(cusum_path)) / (c_std * math.sqrt(len(c_series))))
            if max_cusum_stat > 1.36 or abs(delta_base) > 0.50:
                has_structural_break = True
                alerts.append({
                    "alert_type": "POTENTIAL_STRUCTURAL_BREAK",
                    "severity": "CRITICAL" if max_cusum_stat > 1.63 else "HIGH",
                    "threshold": 1.36,
                    "current_value": max_cusum_stat,
                    "message": f"Potential structural break in factor correlation relationship (CUSUM stat={max_cusum_stat:.2f})",
                })

    # Regime status classification
    if has_structural_break:
        regime_status = "POTENTIAL_STRUCTURAL_BREAK"
    elif is_persistent:
        regime_status = "PERSISTENT_HIGH_CORRELATION" if is_high_pos else "PERSISTENT_LOW_CORRELATION"
    elif is_high_pos:
        regime_status = "HIGH_POSITIVE_COHERENCE"
    elif is_high_neg:
        regime_status = "HIGH_NEGATIVE_COHERENCE"
    elif is_sign_rev:
        regime_status = "SIGN_REVERSAL"
    elif abs(delta_base) >= 0.30:
        regime_status = "CORRELATION_SHIFT"
    else:
        regime_status = "NORMAL"

    is_recovered = bool(abs(r_curr) < recovery_threshold and abs(r_prev) >= recovery_threshold)

    return {
        "regime_status": regime_status,
        "alerts": alerts,
        "is_persistent": is_persistent,
        "is_recovered": is_recovered,
        "has_structural_break": has_structural_break,
        "cusum_statistic": max_cusum_stat,
        "signed_delta": delta,
        "baseline_delta": delta_base,
    }

