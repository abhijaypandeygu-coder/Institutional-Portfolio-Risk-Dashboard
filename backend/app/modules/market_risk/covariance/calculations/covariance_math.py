"""
M07.06 Covariance Analysis Mathematical Engine.
Implements:
- Sample Covariance (n-1) & Population Covariance (n)
- EWMA & Ledoit-Wolf Shrinkage
- N x N Matrix Generation & Symmetry Enforcement
- Eigenvalue PSD Diagnostics & Spectral/Higham PSD Regularization
- Portfolio Variance w^T Sigma w & Component/Marginal Risk Contributions
- Two-Portfolio Cross Covariance w_A^T Sigma w_B
- Rolling Covariance and Window Deltas
"""
from datetime import date
from decimal import Decimal
import math
from typing import List, Tuple, Dict, Any, Optional
import numpy as np

from backend.app.modules.market_risk.covariance.models import (
    CovarianceEstimator,
    DenominatorPolicy,
    MatrixPSDStatus,
)


def calculate_sample_covariance(
    x: np.ndarray,
    y: np.ndarray,
    denominator_policy: DenominatorPolicy = DenominatorPolicy.UNBIASED_SAMPLE,
    min_observations: int = 5,
) -> Dict[str, Any]:
    """
    Compute pairwise covariance and standard deviations between two 1D return series.
    Returns:
      {
        "covariance": float,
        "variance_a": float,
        "variance_b": float,
        "std_dev_a": float,
        "std_dev_b": float,
        "correlation": float,
        "sample_size": int,
        "is_valid": bool
      }
    """
    n = len(x)
    if n < min_observations or len(y) != n:
        return {
            "covariance": 0.0,
            "variance_a": 0.0,
            "variance_b": 0.0,
            "std_dev_a": 0.0,
            "std_dev_b": 0.0,
            "correlation": 0.0,
            "sample_size": n,
            "is_valid": False,
        }

    ddof = 1 if denominator_policy == DenominatorPolicy.UNBIASED_SAMPLE else 0

    x_mean = float(np.mean(x))
    y_mean = float(np.mean(y))

    # Variance and Covariance
    var_x = float(np.var(x, ddof=ddof))
    var_y = float(np.var(y, ddof=ddof))
    std_x = math.sqrt(max(0.0, var_x))
    std_y = math.sqrt(max(0.0, var_y))

    # Covariance numerator
    cov = float(np.sum((x - x_mean) * (y - y_mean)) / max(1, n - ddof))

    # Correlation
    if std_x > 1e-12 and std_y > 1e-12:
        corr = cov / (std_x * std_y)
        corr = max(-1.0, min(1.0, corr))
    else:
        corr = 0.0

    return {
        "covariance": cov,
        "variance_a": var_x,
        "variance_b": var_y,
        "std_dev_a": std_x,
        "std_dev_b": std_y,
        "correlation": corr,
        "sample_size": n,
        "is_valid": True,
    }


def compute_ewma_covariance(
    x: np.ndarray,
    y: np.ndarray,
    decay_factor: float = 0.94,
) -> float:
    """
    Exponentially weighted moving average covariance.
    """
    n = len(x)
    if n < 2:
        return 0.0
    weights = np.array([(1.0 - decay_factor) * (decay_factor ** (n - 1 - t)) for t in range(n)])
    weights /= np.sum(weights)  # Normalize weights

    x_mean = np.sum(weights * x)
    y_mean = np.sum(weights * y)

    cov = np.sum(weights * (x - x_mean) * (y - y_mean))
    return float(cov)


def compute_covariance_matrix(
    returns_dict: Dict[str, List[Tuple[date, Decimal]]],
    asset_order: List[str],
    estimator: CovarianceEstimator = CovarianceEstimator.SAMPLE,
    denominator_policy: DenominatorPolicy = DenominatorPolicy.UNBIASED_SAMPLE,
    min_observations: int = 5,
    ewma_decay: float = 0.94,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Construct N x N covariance matrix with diagnostics:
    - Guaranteed symmetry
    - Non-negative diagonal variances
    - Eigenvalue decomposition & PSD diagnostics
    """
    from backend.app.modules.market_risk.correlation.calculations.correlation_math import align_two_series

    n = len(asset_order)
    matrix = np.zeros((n, n), dtype=np.float64)
    total_pairs = (n * (n - 1)) // 2
    valid_pairs = 0
    variances = []

    # First compute diagonal variances
    for i in range(n):
        aid = asset_order[i]
        rets_i = [float(val) for _, val in returns_dict.get(aid, [])]
        arr_i = np.array(rets_i, dtype=np.float64)
        if len(arr_i) >= min_observations:
            ddof = 1 if denominator_policy == DenominatorPolicy.UNBIASED_SAMPLE else 0
            v = float(np.var(arr_i, ddof=ddof))
            matrix[i, i] = max(0.0, v)
        else:
            matrix[i, i] = 0.0
        variances.append(matrix[i, i])

    # Then off-diagonal covariances
    for i in range(n):
        for j in range(i + 1, n):
            aid_i = asset_order[i]
            aid_j = asset_order[j]
            s_i = returns_dict.get(aid_i, [])
            s_j = returns_dict.get(aid_j, [])

            _, x, y = align_two_series(s_i, s_j)
            if len(x) >= min_observations:
                if estimator == CovarianceEstimator.EWMA:
                    cov_val = compute_ewma_covariance(x, y, decay_factor=ewma_decay)
                else:
                    pair_res = calculate_sample_covariance(x, y, denominator_policy=denominator_policy, min_observations=min_observations)
                    cov_val = pair_res["covariance"]
                valid_pairs += 1
            else:
                cov_val = 0.0

            matrix[i, j] = cov_val
            matrix[j, i] = cov_val

    # Symmetry validation
    sym_discrepancy = float(np.max(np.abs(matrix - matrix.T)))
    is_symmetric = sym_discrepancy < 1e-8

    # PSD & Eigenvalue diagnostics
    # Use eigvalsh for symmetric real matrix
    eigenvalues = np.linalg.eigvalsh(matrix)
    min_eig = float(np.min(eigenvalues))
    max_eig = float(np.max(eigenvalues))
    neg_eigs = int(np.sum(eigenvalues < -1e-8))

    cond_number = None
    if min_eig > 1e-12:
        cond_number = float(max_eig / min_eig)

    is_psd = neg_eigs == 0 and min_eig >= -1e-8
    psd_status = MatrixPSDStatus.VALID_PSD if is_psd else MatrixPSDStatus.NON_PSD

    completeness = (valid_pairs / total_pairs) if total_pairs > 0 else 1.0

    diag = {
        "psd_status": psd_status,
        "min_eigenvalue": min_eig,
        "max_eigenvalue": max_eig,
        "condition_number": cond_number,
        "negative_eigenvalues_count": neg_eigs,
        "is_symmetric": is_symmetric,
        "max_symmetry_discrepancy": sym_discrepancy,
        "completeness_ratio": completeness,
        "average_variance": float(np.mean(variances)) if variances else 0.0,
    }

    return matrix, diag


def repair_covariance_psd(
    raw_matrix: np.ndarray,
    method: str = "SPECTRAL_CLIPPING",
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Repair a non-PSD covariance matrix while preserving asset variances where possible.
    Converts to correlation, repairs correlation, and reconstructs Sigma* = D R* D.
    """
    from backend.app.modules.market_risk.correlation.calculations.correlation_math import repair_psd_matrix

    n = raw_matrix.shape[0]
    std_devs = np.sqrt(np.maximum(np.diag(raw_matrix), 1e-12))
    d_inv = 1.0 / std_devs
    
    # Raw correlation matrix
    raw_corr = raw_matrix * np.outer(d_inv, d_inv)
    np.fill_diagonal(raw_corr, 1.0)
    raw_corr = 0.5 * (raw_corr + raw_corr.T)

    # Repair correlation
    repaired_corr, t_info = repair_psd_matrix(raw_corr, method="EIGENVALUE_CLIPPING")

    # Reconstruct covariance: Sigma* = D R* D
    repaired_cov = repaired_corr * np.outer(std_devs, std_devs)
    np.fill_diagonal(repaired_cov, np.diag(raw_matrix))
    repaired_cov = 0.5 * (repaired_cov + repaired_cov.T)

    new_eigs = np.linalg.eigvalsh(repaired_cov)
    min_eig_after = float(np.min(new_eigs))
    frob_dist = float(np.linalg.norm(repaired_cov - raw_matrix, 'fro'))
    max_adj = float(np.max(np.abs(repaired_cov - raw_matrix)))

    transform_diag = {
        "method": method,
        "min_eigenvalue_after": min_eig_after,
        "frobenius_distance": frob_dist,
        "max_absolute_cell_adjustment": max_adj,
    }

    return repaired_cov, transform_diag


def calculate_portfolio_variance_and_risk_contributions(
    weights: np.ndarray,
    cov_matrix: np.ndarray,
    symbols: List[str],
    annualization_factor: float = 252.0,
) -> Dict[str, Any]:
    """
    Calculate portfolio variance, volatility, and component/marginal risk contributions.
    Supports long-short signed weights.
    Formulas:
      - Portfolio Variance: sigma_p^2 = w^T Sigma w
      - Portfolio Volatility: sigma_p = sqrt(sigma_p^2)
      - Marginal Contribution to Variance (MCV): (Sigma w)_i
      - Component Contribution to Variance (CV): w_i * (Sigma w)_i  [sum(CV) = sigma_p^2]
      - Marginal Contribution to Volatility (MCR): (Sigma w)_i / sigma_p
      - Component Contribution to Volatility (CR): w_i * (Sigma w)_i / sigma_p [sum(CR) = sigma_p]
    """
    w = weights.reshape(-1, 1)
    sigma_w = cov_matrix @ w  # (N, 1)

    # Portfolio period variance
    port_var = float((w.T @ sigma_w).item())
    # Numerical guard: if port_var is very tiny negative due to precision, clamp to 0
    if -1e-12 < port_var < 0.0:
        port_var = 0.0
    elif port_var < -1e-12:
        raise ValueError(f"Materially negative portfolio variance encountered: {port_var}")

    port_vol = math.sqrt(port_var)

    ann_var = port_var * annualization_factor
    ann_vol = port_vol * math.sqrt(annualization_factor)

    mcv = sigma_w.flatten()  # Marginal contribution to variance
    cv = (weights * mcv).flatten()  # Component contribution to variance

    if port_vol > 1e-12:
        mcr = mcv / port_vol  # Marginal contribution to volatility
        cr = cv / port_vol    # Component contribution to volatility
    else:
        mcr = np.zeros_like(mcv)
        cr = np.zeros_like(cv)

    # Reconciliations
    sum_cv = float(np.sum(cv))
    sum_cr = float(np.sum(cr))
    var_discrepancy = float(abs(sum_cv - port_var))
    vol_discrepancy = float(abs(sum_cr - port_vol))

    return {
        "period_portfolio_variance": port_var,
        "period_portfolio_volatility": port_vol,
        "annualized_portfolio_variance": ann_var,
        "annualized_portfolio_volatility": ann_vol,
        "marginal_contributions_variance": mcv.tolist(),
        "component_contributions_variance": cv.tolist(),
        "marginal_contributions_volatility": mcr.tolist(),
        "component_contributions_volatility": cr.tolist(),
        "reconciliation_variance_sum": sum_cv,
        "reconciliation_volatility_sum": sum_cr,
        "variance_discrepancy": var_discrepancy,
        "volatility_discrepancy": vol_discrepancy,
    }


def calculate_portfolio_pair_covariance(
    weights_a: np.ndarray,
    weights_b: np.ndarray,
    cov_matrix: np.ndarray,
) -> Dict[str, Any]:
    """
    Calculate covariance between two portfolios: Cov(R_A, R_B) = w_A^T Sigma w_B.
    Also calculates individual variances and derived correlation.
    """
    w_a = weights_a.reshape(-1, 1)
    w_b = weights_b.reshape(-1, 1)

    cov_ab = float((w_a.T @ cov_matrix @ w_b).item())
    var_a = float((w_a.T @ cov_matrix @ w_a).item())
    var_b = float((w_b.T @ cov_matrix @ w_b).item())

    vol_a = math.sqrt(max(0.0, var_a))
    vol_b = math.sqrt(max(0.0, var_b))

    if vol_a > 1e-12 and vol_b > 1e-12:
        corr_ab = cov_ab / (vol_a * vol_b)
        corr_ab = max(-1.0, min(1.0, corr_ab))
    else:
        corr_ab = 0.0

    return {
        "period_covariance": cov_ab,
        "portfolio_a_variance": var_a,
        "portfolio_b_variance": var_b,
        "portfolio_a_volatility": vol_a,
        "portfolio_b_volatility": vol_b,
        "derived_correlation": corr_ab,
    }


def calculate_rolling_covariance(
    aligned_dates: List[date],
    returns_a: np.ndarray,
    returns_b: np.ndarray,
    window_days: int = 30,
    denominator_policy: DenominatorPolicy = DenominatorPolicy.UNBIASED_SAMPLE,
) -> List[Dict[str, Any]]:
    """
    Calculate rolling covariance time series over moving observation windows.
    Tracks covariance value and delta vs prior step.
    """
    n = len(aligned_dates)
    results = []
    if n < window_days:
        return results

    prior_cov = None

    for i in range(window_days, n + 1):
        win_dates = aligned_dates[i - window_days : i]
        win_a = returns_a[i - window_days : i]
        win_b = returns_b[i - window_days : i]

        calc = calculate_sample_covariance(
            win_a,
            win_b,
            denominator_policy=denominator_policy,
            min_observations=min(5, window_days // 2),
        )
        curr_cov = calc["covariance"]
        delta_cov = (curr_cov - prior_cov) if prior_cov is not None else None

        results.append({
            "observation_date": win_dates[-1],
            "covariance": curr_cov,
            "delta_covariance": delta_cov,
            "sample_size": len(win_a),
        })

        prior_cov = curr_cov

    return results
