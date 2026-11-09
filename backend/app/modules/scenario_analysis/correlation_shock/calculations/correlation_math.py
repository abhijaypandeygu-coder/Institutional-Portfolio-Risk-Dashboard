"""
M10.05 Correlation Shock Mathematical & Quantitative Risk Engine.
Implements:
1. Pairwise Correlation Transformations:
   - Increase / custom target: rho_stress = (1 - lambda) * rho + lambda * rho_target
   - Convergence toward target: rho_stress = (1 - lambda) * rho + lambda * rho_stress
   - Convergence toward one: rho_stress = (1 - lambda) * rho + lambda
   - Convergence toward zero: rho_stress = (1 - lambda) * rho
2. Matrix Transformations (Full Universe, Pairwise, Group-level)
3. Matrix Mathematical Properties & PSD Validation:
   - Symmetry: |R - R^T| <= tol
   - Unit diagonal: R_ii == 1.0
   - Value bounds: -1.0 <= R_ij <= 1.0
   - Positive Semi-Definiteness (PSD): min(eigenvalues) >= -tol
   - Rank, condition number, eigenvalue distribution
4. Matrix Repair Algorithms:
   - Eigenvalue Clipping (Spectral truncation with diagonal renormalization)
   - Shrinkage toward Identity: R_shrunk = (1 - alpha) * R + alpha * I
   - Higham (2002) Alternating Projections Nearest Correlation Matrix
5. Stressed Covariance Construction:
   - Sigma_stress = D_sigma * R_stress * D_sigma
6. Portfolio Risk Recalculation under Stressed Covariance:
   - Volatility sigma_p = sqrt(w^T Sigma w)
   - Variance Var_p = w^T Sigma w
   - Absolute and percentage changes
7. Euler Risk Contribution Analysis:
   - Marginal Risk Contribution MRC_i = (Sigma w)_i / sigma_p
   - Component Risk Contribution CRC_i = w_i * MRC_i
   - Variance Contribution CCV_i = w_i * (Sigma w)_i
   - Full Euler additivity: sum(CRC_i) == sigma_p, sum(CCV_i) == Var_p
   - Handling of negative contributions and long-short weights
8. Diversification Diagnostics:
   - Gross standalone volatility comparison measure: DB = sum(|w_i| * sigma_i) - sigma_p
   - Diversification Ratio: DR = sum(w_i * sigma_i) / sigma_p (for nonnegative weights)
   - Average, median, min, max pairwise correlations and threshold concentrations
"""
from datetime import datetime, timezone
from decimal import Decimal
import enum
import math
from typing import Dict, List, Optional, Tuple, Any, Union
import numpy as np


class MatrixValidationStatus(str, enum.Enum):
    VALID = "VALID"
    VALID_WITH_WARNINGS = "VALID_WITH_WARNINGS"
    INVALID_NON_SYMMETRIC = "INVALID_NON_SYMMETRIC"
    INVALID_DIAGONAL = "INVALID_DIAGONAL"
    INVALID_BOUNDS = "INVALID_BOUNDS"
    INVALID_NON_PSD = "INVALID_NON_PSD"
    SINGULAR = "SINGULAR"
    ILL_CONDITIONED = "ILL_CONDITIONED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NOT_SUPPORTED = "NOT_SUPPORTED"


class MatrixRepairMethod(str, enum.Enum):
    NO_REPAIR = "NO_REPAIR"
    EIGENVALUE_CLIPPING = "EIGENVALUE_CLIPPING"
    SHRINKAGE_IDENTITY = "SHRINKAGE_IDENTITY"
    HIGHAM_NEAREST = "HIGHAM_NEAREST"


class CorrelationTransformationMethod(str, enum.Enum):
    INCREASE = "INCREASE"
    CONVERGENCE = "CONVERGENCE"
    CONVERGENCE_TO_ONE = "CONVERGENCE_TO_ONE"
    CONVERGENCE_TO_ZERO = "CONVERGENCE_TO_ZERO"
    CUSTOM_PAIRWISE = "CUSTOM_PAIRWISE"
    CUSTOM_TARGET = "CUSTOM_TARGET"


# ---------------------------------------------------------
# 1. Pairwise Correlation Transformation Functions
# ---------------------------------------------------------

def transform_correlation_pair(
    rho: float,
    method: CorrelationTransformationMethod,
    stress_intensity: float,
    target_correlation: Optional[float] = None,
    clamp: bool = True,
) -> float:
    """
    Transforms a single pairwise correlation coefficient rho according to stress method and intensity.
    Formula: rho_stress = (1 - lambda) * rho + lambda * target
    """
    lam = float(np.clip(stress_intensity, 0.0, 1.0))
    rho_val = float(rho)

    if method == CorrelationTransformationMethod.INCREASE:
        target = 1.0 if target_correlation is None else float(target_correlation)
        res = (1.0 - lam) * rho_val + lam * target
    elif method == CorrelationTransformationMethod.CONVERGENCE:
        target = 0.80 if target_correlation is None else float(target_correlation)
        res = (1.0 - lam) * rho_val + lam * target
    elif method == CorrelationTransformationMethod.CONVERGENCE_TO_ONE:
        res = (1.0 - lam) * rho_val + lam * 1.0
    elif method == CorrelationTransformationMethod.CONVERGENCE_TO_ZERO:
        res = (1.0 - lam) * rho_val + lam * 0.0
    elif method in (CorrelationTransformationMethod.CUSTOM_PAIRWISE, CorrelationTransformationMethod.CUSTOM_TARGET):
        target = rho_val if target_correlation is None else float(target_correlation)
        res = (1.0 - lam) * rho_val + lam * target
    else:
        res = rho_val

    if clamp:
        res = float(np.clip(res, -1.0, 1.0))
    return res


# ---------------------------------------------------------
# 2. Matrix Validation & Properties
# ---------------------------------------------------------

def validate_correlation_matrix(
    matrix: np.ndarray,
    symmetry_tol: float = 1e-6,
    diagonal_tol: float = 1e-6,
    psd_tol: float = 1e-7,
    condition_warn_thresh: float = 1e4,
) -> Dict[str, Any]:
    """
    Dedicated matrix validation engine.
    Separates mathematical PSD validity from downstream model condition usability.
    """
    mat = np.asarray(matrix, dtype=np.float64)
    if mat.ndim != 2 or mat.shape[0] != mat.shape[1]:
        return {
            "status": MatrixValidationStatus.NOT_SUPPORTED,
            "is_symmetric": False,
            "diagonal_valid": False,
            "bounds_valid": False,
            "is_psd": False,
            "minimum_eigenvalue": -999.0,
            "maximum_eigenvalue": -999.0,
            "matrix_rank": 0,
            "condition_number": None,
            "negative_eigenvalue_count": 0,
            "warnings": ["Matrix must be 2D square array."],
        }

    n = mat.shape[0]
    if n == 0:
        return {
            "status": MatrixValidationStatus.INSUFFICIENT_DATA,
            "is_symmetric": True,
            "diagonal_valid": True,
            "bounds_valid": True,
            "is_psd": True,
            "minimum_eigenvalue": 0.0,
            "maximum_eigenvalue": 0.0,
            "matrix_rank": 0,
            "condition_number": 1.0,
            "negative_eigenvalue_count": 0,
            "warnings": ["Empty matrix."],
        }

    # 1. Symmetry
    sym_diff = np.max(np.abs(mat - mat.T))
    is_symmetric = bool(sym_diff <= symmetry_tol)

    # 2. Diagonal == 1.0
    diag = np.diag(mat)
    diag_diff = np.max(np.abs(diag - 1.0))
    diagonal_valid = bool(diag_diff <= diagonal_tol)

    # 3. Bounds [-1, 1]
    bounds_valid = bool(np.all(mat >= -1.0 - 1e-6) and np.all(mat <= 1.0 + 1e-6))

    # Eigenvalues (use eigh on symmetrized matrix to be numerically robust)
    sym_mat = 0.5 * (mat + mat.T)
    eigenvalues = np.linalg.eigvalsh(sym_mat)
    min_eig = float(np.min(eigenvalues))
    max_eig = float(np.max(eigenvalues))
    neg_eigs = int(np.sum(eigenvalues < -psd_tol))
    is_psd = bool(neg_eigs == 0 and min_eig >= -psd_tol)

    # Rank & Condition Number
    rank = int(np.linalg.matrix_rank(sym_mat, tol=psd_tol))
    is_singular = rank < n

    cond_number: Optional[float] = None
    if min_eig > 1e-12:
        cond_number = float(max_eig / min_eig)
    elif min_eig >= 0.0:
        cond_number = float(1e15)

    is_ill_conditioned = bool(cond_number is not None and cond_number > condition_warn_thresh)

    warnings: List[str] = []
    if not is_symmetric:
        warnings.append(f"Matrix is not symmetric (max asymmetry: {sym_diff:.8f}).")
    if not diagonal_valid:
        warnings.append(f"Diagonal entries deviate from 1.0 (max deviation: {diag_diff:.8f}).")
    if not bounds_valid:
        warnings.append("Some correlation coefficients are outside [-1, 1].")
    if not is_psd:
        warnings.append(f"Matrix has {neg_eigs} negative eigenvalues (min eigenvalue: {min_eig:.8f}).")
    if is_singular:
        warnings.append(f"Matrix is singular (numerical rank: {rank}/{n}).")
    if is_ill_conditioned:
        warnings.append(f"Matrix is ill-conditioned (condition number: {cond_number:.2f}).")

    # Determine state
    if not is_symmetric:
        status = MatrixValidationStatus.INVALID_NON_SYMMETRIC
    elif not diagonal_valid:
        status = MatrixValidationStatus.INVALID_DIAGONAL
    elif not bounds_valid:
        status = MatrixValidationStatus.INVALID_BOUNDS
    elif not is_psd:
        status = MatrixValidationStatus.INVALID_NON_PSD
    elif is_singular:
        status = MatrixValidationStatus.SINGULAR
    elif is_ill_conditioned:
        status = MatrixValidationStatus.ILL_CONDITIONED
    elif len(warnings) > 0:
        status = MatrixValidationStatus.VALID_WITH_WARNINGS
    else:
        status = MatrixValidationStatus.VALID

    return {
        "status": status,
        "is_symmetric": is_symmetric,
        "diagonal_valid": diagonal_valid,
        "bounds_valid": bounds_valid,
        "is_psd": is_psd,
        "minimum_eigenvalue": min_eig,
        "maximum_eigenvalue": max_eig,
        "matrix_rank": rank,
        "condition_number": cond_number,
        "negative_eigenvalue_count": neg_eigs,
        "warnings": warnings,
    }


# ---------------------------------------------------------
# 3. Matrix Repair Engine
# ---------------------------------------------------------

def repair_correlation_matrix(
    raw_matrix: np.ndarray,
    method: MatrixRepairMethod = MatrixRepairMethod.EIGENVALUE_CLIPPING,
    eigenvalue_floor: float = 1e-7,
    shrinkage_alpha: float = 0.1,
    higham_max_iter: int = 100,
    higham_tol: float = 1e-7,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Controlled correlation matrix repair engine.
    Preserves audit metadata: Frobenius norm distance, maximum absolute adjustment,
    eigenvalue changes, and convergence status.
    """
    mat = np.asarray(raw_matrix, dtype=np.float64)
    n = mat.shape[0]

    # Pre-validation
    pre_diag = validate_correlation_matrix(mat)
    pre_status = pre_diag["status"]

    if method == MatrixRepairMethod.NO_REPAIR or n <= 1:
        return mat.copy(), {
            "method": method.value,
            "parameters": {},
            "pre_repair_status": pre_status.value,
            "post_repair_status": pre_status.value,
            "maximum_adjustment": 0.0,
            "frobenius_adjustment": 0.0,
            "convergence_status": "SKIPPED",
            "iterations": 0,
        }

    # Symmetrize initial input
    sym_mat = 0.5 * (mat + mat.T)
    np.fill_diagonal(sym_mat, 1.0)

    converged = True
    iterations = 1

    if method == MatrixRepairMethod.SHRINKAGE_IDENTITY:
        alpha = float(np.clip(shrinkage_alpha, 0.0, 1.0))
        identity = np.eye(n, dtype=np.float64)
        repaired = (1.0 - alpha) * sym_mat + alpha * identity
        params = {"alpha": alpha}

    elif method == MatrixRepairMethod.HIGHAM_NEAREST:
        # Alternating projections algorithm (Higham, 2002)
        y = sym_mat.copy()
        gamma = np.zeros_like(y)
        converged = False

        for k in range(1, higham_max_iter + 1):
            iterations = k
            r = y - gamma
            # Projection onto PSD cone: spectral decomposition
            w, v = np.linalg.eigh(r)
            w_clipped = np.maximum(w, eigenvalue_floor)
            x = v @ np.diag(w_clipped) @ v.T
            gamma = x - r

            # Projection onto unit diagonal symmetric space
            y_next = x.copy()
            np.fill_diagonal(y_next, 1.0)
            y_next = 0.5 * (y_next + y_next.T)

            # Check convergence
            diff = np.max(np.abs(y_next - y))
            if diff < higham_tol:
                converged = True
                y = y_next
                break
            y = y_next

        repaired = y
        params = {
            "max_iterations": higham_max_iter,
            "tolerance": higham_tol,
            "eigenvalue_floor": eigenvalue_floor,
        }

    else:
        # Default: EIGENVALUE_CLIPPING (Spectral clipping + diagonal renormalization)
        w, v = np.linalg.eigh(sym_mat)
        w_clipped = np.maximum(w, eigenvalue_floor)
        repaired_cov = v @ np.diag(w_clipped) @ v.T
        # Renormalize diagonal to exactly 1.0
        d = np.sqrt(np.diag(repaired_cov))
        d_inv = 1.0 / np.maximum(d, 1e-12)
        repaired = repaired_cov * np.outer(d_inv, d_inv)
        np.fill_diagonal(repaired, 1.0)
        repaired = 0.5 * (repaired + repaired.T)
        params = {"eigenvalue_floor": eigenvalue_floor}

    # Ensure clean bounds [-1, 1] and unit diagonal
    repaired = np.clip(repaired, -1.0, 1.0)
    np.fill_diagonal(repaired, 1.0)
    repaired = 0.5 * (repaired + repaired.T)

    post_diag = validate_correlation_matrix(repaired)
    post_status = post_diag["status"]

    max_adj = float(np.max(np.abs(repaired - mat)))
    frob_adj = float(np.linalg.norm(repaired - mat, "fro"))

    audit_meta = {
        "method": method.value,
        "parameters": params,
        "pre_repair_status": pre_status.value,
        "post_repair_status": post_status.value,
        "maximum_adjustment": max_adj,
        "frobenius_adjustment": frob_adj,
        "convergence_status": "CONVERGED" if converged else "MAX_ITERATIONS_REACHED",
        "iterations": iterations,
    }

    return repaired, audit_meta


# ---------------------------------------------------------
# 4. Stressed Covariance Construction
# ---------------------------------------------------------

def construct_stressed_covariance(
    correlation_matrix: np.ndarray,
    volatilities: np.ndarray,
) -> np.ndarray:
    """
    Constructs covariance matrix:
    Sigma = D_sigma * R * D_sigma
    Element-wise: Sigma_ij = sigma_i * sigma_j * R_ij
    """
    r = np.asarray(correlation_matrix, dtype=np.float64)
    vols = np.asarray(volatilities, dtype=np.float64).flatten()
    n = len(vols)
    if r.shape != (n, n):
        raise ValueError(f"Correlation shape {r.shape} does not match volatility vector length {n}")

    # Outer product of volatilities
    vol_outer = np.outer(vols, vols)
    cov = r * vol_outer
    # Ensure exact symmetry
    cov = 0.5 * (cov + cov.T)
    return cov


# ---------------------------------------------------------
# 5. Stressed Portfolio Risk & Euler Risk Contributions
# ---------------------------------------------------------

def calculate_portfolio_risk_and_contributions(
    weights: np.ndarray,
    cov_matrix: np.ndarray,
    asset_ids: List[str],
    asset_symbols: Optional[List[str]] = None,
    volatilities: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """
    Calculates portfolio volatility, variance, and exact Euler risk contributions.
    Supports long/short portfolios with signed weights.
    Reconciles:
      sum(CRC_i) == sigma_p
      sum(CCV_i) == Var_p
    """
    w = np.asarray(weights, dtype=np.float64).reshape(-1, 1)
    sigma = np.asarray(cov_matrix, dtype=np.float64)
    n = len(w)

    if n == 0 or sigma.shape != (n, n):
        raise ValueError(f"Weights length ({n}) must match covariance matrix shape {sigma.shape}")

    # Gradient: Sigma * w
    v = sigma @ w
    port_var = float((w.T @ v).item())

    # Protect against slight numerical negative due to floating precision
    if port_var <= 1e-15:
        port_var = 0.0
        port_vol = 0.0
    else:
        port_vol = math.sqrt(port_var)

    w_flat = w.flatten()
    v_flat = v.flatten()

    # Marginal and Component contributions to variance
    # CCV_i = w_i * (Sigma w)_i
    ccv = w_flat * v_flat

    # Marginal and Component contributions to volatility
    if port_vol > 1e-12:
        mrc = v_flat / port_vol
        crc = w_flat * mrc
        pct_crc = (crc / port_vol) * 100.0
        pct_ccv = (ccv / port_var) * 100.0 if port_var > 1e-15 else np.zeros(n)
    else:
        mrc = np.zeros(n, dtype=np.float64)
        crc = np.zeros(n, dtype=np.float64)
        pct_crc = np.zeros(n, dtype=np.float64)
        pct_ccv = np.zeros(n, dtype=np.float64)

    # Standalone asset volatilities from covariance diagonal
    standalone_vols = np.sqrt(np.maximum(np.diag(sigma), 0.0))
    if volatilities is not None and len(volatilities) == n:
        standalone_vols = np.asarray(volatilities, dtype=np.float64)

    contributions: List[Dict[str, Any]] = []
    for i in range(n):
        aid = asset_ids[i]
        sym = asset_symbols[i] if asset_symbols and i < len(asset_symbols) else aid
        contributions.append({
            "asset_id": aid,
            "symbol": sym,
            "weight": float(w_flat[i]),
            "standalone_volatility": float(standalone_vols[i]),
            "marginal_risk_contribution": float(mrc[i]),
            "component_risk_contribution": float(crc[i]),
            "component_variance_contribution": float(ccv[i]),
            "percentage_risk_contribution": float(pct_crc[i]),
            "percentage_variance_contribution": float(pct_ccv[i]),
        })

    # Euler reconciliation checks
    sum_crc = float(np.sum(crc))
    vol_residual = float(abs(sum_crc - port_vol))
    sum_ccv = float(np.sum(ccv))
    var_residual = float(abs(sum_ccv - port_var))

    reconciled = (vol_residual <= 1e-5) and (var_residual <= 1e-5)

    return {
        "portfolio_variance": port_var,
        "portfolio_volatility": port_vol,
        "contributions": contributions,
        "sum_component_volatility": sum_crc,
        "volatility_residual": vol_residual,
        "sum_component_variance": sum_ccv,
        "variance_residual": var_residual,
        "is_euler_reconciled": reconciled,
    }


# ---------------------------------------------------------
# 6. Diversification & Concentration Metrics
# ---------------------------------------------------------

def calculate_diversification_metrics(
    weights: np.ndarray,
    volatilities: np.ndarray,
    portfolio_volatility: float,
    correlation_matrix: np.ndarray,
) -> Dict[str, Any]:
    """
    Computes institutional diversification diagnostics:
    - Diversification Benefit DB = sum(|w_i| * sigma_i) - sigma_p
    - Diversification Ratio DR = (sum(w_i * sigma_i)) / sigma_p (for nonnegative weights)
    - Average, median, min, max pairwise correlations (off-diagonal)
    - Correlation concentration: % of pairs > 0.50, > 0.70, > 0.85
    """
    w = np.asarray(weights, dtype=np.float64).flatten()
    vols = np.asarray(volatilities, dtype=np.float64).flatten()
    r = np.asarray(correlation_matrix, dtype=np.float64)
    n = len(w)

    port_vol = float(portfolio_volatility)

    # Standalone weighted sum (gross weights)
    gross_standalone_sum = float(np.sum(np.abs(w) * vols))
    diversification_benefit = float(gross_standalone_sum - port_vol)

    # Diversification Ratio (meaningful when weights are long-only nonnegative)
    all_nonnegative = bool(np.all(w >= -1e-6))
    diversification_ratio: Optional[float] = None
    if all_nonnegative and port_vol > 1e-12:
        weighted_sum = float(np.sum(w * vols))
        diversification_ratio = float(weighted_sum / port_vol)

    # Off-diagonal correlation statistics
    if n > 1:
        triu_indices = np.triu_indices(n, k=1)
        pairs_corr = r[triu_indices]
        avg_corr = float(np.mean(pairs_corr))
        med_corr = float(np.median(pairs_corr))
        min_corr = float(np.min(pairs_corr))
        max_corr = float(np.max(pairs_corr))

        pct_above_50 = float(np.mean(pairs_corr > 0.50) * 100.0)
        pct_above_70 = float(np.mean(pairs_corr > 0.70) * 100.0)
        pct_above_85 = float(np.mean(pairs_corr > 0.85) * 100.0)
    else:
        avg_corr = 1.0
        med_corr = 1.0
        min_corr = 1.0
        max_corr = 1.0
        pct_above_50 = 100.0
        pct_above_70 = 100.0
        pct_above_85 = 100.0

    return {
        "diversification_benefit": diversification_benefit,
        "diversification_ratio": diversification_ratio,
        "gross_standalone_sum": gross_standalone_sum,
        "is_long_only": all_nonnegative,
        "average_pairwise_correlation": avg_corr,
        "median_pairwise_correlation": med_corr,
        "min_pairwise_correlation": min_corr,
        "max_pairwise_correlation": max_corr,
        "pct_pairs_above_50": pct_above_50,
        "pct_pairs_above_70": pct_above_70,
        "pct_pairs_above_85": pct_above_85,
    }


# ---------------------------------------------------------
# 7. Baseline vs Stressed Comparison Engine
# ---------------------------------------------------------

def compare_baseline_vs_stressed(
    base_risk: Dict[str, Any],
    stress_risk: Dict[str, Any],
    base_div: Dict[str, Any],
    stress_div: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compares baseline and stressed risk results and generates concise, data-grounded explanations.
    """
    base_vol = base_risk["portfolio_volatility"]
    stress_vol = stress_risk["portfolio_volatility"]
    delta_vol = stress_vol - base_vol
    pct_delta_vol = (delta_vol / base_vol * 100.0) if base_vol > 1e-12 else 0.0

    base_var = base_risk["portfolio_variance"]
    stress_var = stress_risk["portfolio_variance"]
    delta_var = stress_var - base_var
    pct_delta_var = (delta_var / base_var * 100.0) if base_var > 1e-15 else 0.0

    delta_avg_corr = stress_div["average_pairwise_correlation"] - base_div["average_pairwise_correlation"]
    delta_div_benefit = stress_div["diversification_benefit"] - base_div["diversification_benefit"]

    # Identify top contributor in stressed portfolio
    stress_contribs = stress_risk.get("contributions", [])
    top_contributor = None
    if stress_contribs:
        sorted_contribs = sorted(stress_contribs, key=lambda x: abs(x["component_risk_contribution"]), reverse=True)
        top_contributor = sorted_contribs[0]["symbol"]

    # Formulate data-grounded quantitative narrative
    narrative_points = []
    if abs(pct_delta_vol) < 0.01:
        narrative_points.append("Portfolio volatility remained virtually unchanged under the applied correlation scenario.")
    elif pct_delta_vol > 0:
        narrative_points.append(
            f"Portfolio volatility increased by {delta_vol:.4f} ({pct_delta_vol:.2f}%), rising from {base_vol:.4f} to {stress_vol:.4f}."
        )
    else:
        narrative_points.append(
            f"Portfolio volatility decreased by {abs(delta_vol):.4f} ({abs(pct_delta_vol):.2f}%), indicating hedging effects or net short exposures benefited from correlation shifts."
        )

    if delta_avg_corr > 0.001:
        narrative_points.append(
            f"Average pairwise correlation increased by {delta_avg_corr:+.4f} (from {base_div['average_pairwise_correlation']:.4f} to {stress_div['average_pairwise_correlation']:.4f})."
        )
    elif delta_avg_corr < -0.001:
        narrative_points.append(
            f"Average pairwise correlation decreased by {delta_avg_corr:.4f}."
        )

    if delta_div_benefit < -0.0001:
        narrative_points.append(
            f"Gross diversification benefit deteriorated by {abs(delta_div_benefit):.4f}, as cross-asset co-movements strengthened."
        )
    elif delta_div_benefit > 0.0001:
        narrative_points.append(
            f"Gross diversification benefit improved by {delta_div_benefit:.4f}."
        )

    if top_contributor:
        narrative_points.append(f"Top risk contributor under stressed correlations is {top_contributor}.")

    return {
        "baseline_volatility": base_vol,
        "stressed_volatility": stress_vol,
        "absolute_volatility_change": delta_vol,
        "percentage_volatility_change": pct_delta_vol,
        "baseline_variance": base_var,
        "stressed_variance": stress_var,
        "absolute_variance_change": delta_var,
        "percentage_variance_change": pct_delta_var,
        "baseline_average_correlation": base_div["average_pairwise_correlation"],
        "stressed_average_correlation": stress_div["average_pairwise_correlation"],
        "average_correlation_change": delta_avg_corr,
        "baseline_diversification_benefit": base_div["diversification_benefit"],
        "stressed_diversification_benefit": stress_div["diversification_benefit"],
        "diversification_benefit_change": delta_div_benefit,
        "baseline_diversification_ratio": base_div["diversification_ratio"],
        "stressed_diversification_ratio": stress_div["diversification_ratio"],
        "top_contributor": top_contributor,
        "narrative": " ".join(narrative_points),
    }
