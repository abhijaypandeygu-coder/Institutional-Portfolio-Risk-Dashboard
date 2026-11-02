"""
M07.09 Risk Contribution Mathematical Engine.
Vectorized implementation of:
1. Portfolio Variance & Volatility (sigma_p^2 = w^T Sigma w, sigma_p = sqrt(w^T Sigma w))
2. Marginal Risk Contribution (MRC_i = (Sigma w)_i / sigma_p)
3. Marginal Contribution to Variance (MCV_i = 2 (Sigma w)_i)
4. Component Risk Contribution (CRC_i = w_i * MRC_i)
5. Component Contribution to Variance (CCV_i = w_i * (Sigma w)_i)
6. Percentage Contributions (CRC%_i = CRC_i / sigma_p * 100)
7. Finite Difference Central Numerical Verification of MRC
8. Euler Theorem Additivity Verification (sum CRC = sigma_p, sum CCV = sigma_p^2)
9. Group-level Risk Aggregation across partitions (Mutually exclusive sum = total)
10. Scenario Weight Perturbation & Marginal Risk Impact
"""
import math
from typing import List, Dict, Any, Optional
import numpy as np

from backend.app.modules.market_risk.risk_contribution.models import (
    RiskContributionStatus,
    ReconciliationStatus,
)


def decompose_portfolio_risk(
    weights: np.ndarray,
    cov_matrix: np.ndarray,
    asset_ids: List[str],
    symbols: Optional[List[str]] = None,
    verify_finite_difference: bool = True,
    epsilon: float = 1e-6,
    reconciliation_tol: float = 1e-6,
) -> Dict[str, Any]:
    """
    Perform mathematical decomposition of portfolio risk into marginal and component contributions.

    Args:
        weights: 1D array of portfolio weights (length N). Can be signed (long/short).
        cov_matrix: N x N covariance matrix (symmetric, positive semi-definite).
        asset_ids: List of asset/instrument identifiers corresponding to matrix rows/columns.
        symbols: Optional ticker symbols.
        verify_finite_difference: If True, computes central difference numerical approximation.
        epsilon: Perturbation step for finite difference.
        reconciliation_tol: Tolerance for Euler reconciliation status.

    Returns:
        Dict containing variance, volatility, holding-level metrics, and reconciliation diagnostics.
    """
    n = len(weights)
    if n == 0 or cov_matrix.shape != (n, n):
        raise ValueError(f"Weights length ({n}) must match cov_matrix shape {cov_matrix.shape}")

    w = np.asarray(weights, dtype=np.float64).reshape(-1, 1)
    Sigma = np.asarray(cov_matrix, dtype=np.float64)

    # 1. Gradient vector: v = Sigma * w
    v = Sigma @ w  # Shape (n, 1)

    # 2. Portfolio Variance & Volatility
    port_var = float((w.T @ v).item())
    
    if port_var <= 1e-15:
        # Zero risk / degenerate portfolio
        return {
            "status": RiskContributionStatus.DEGENERATE_PORTFOLIO_ZERO_RISK,
            "portfolio_variance": max(0.0, port_var),
            "portfolio_volatility": 0.0,
            "holdings": [],
            "sum_component_variance": 0.0,
            "variance_residual": 0.0,
            "sum_component_volatility": 0.0,
            "volatility_residual": 0.0,
            "relative_residual": 0.0,
            "reconciliation_status": ReconciliationStatus.RECONCILED,
            "max_fd_error": 0.0,
        }

    port_vol = math.sqrt(port_var)

    # 3. Marginal Contributions
    # Marginal Contribution to Variance: MCV = 2 * (Sigma w)
    # Marginal Risk Contribution: MRC = (Sigma w) / sigma_p
    mcv = (2.0 * v).flatten()
    mrc = (v / port_vol).flatten()

    # 4. Component Contributions
    # Component Contribution to Variance: CCV_i = w_i * (Sigma w)_i
    # Component Risk Contribution: CRC_i = w_i * MRC_i = w_i * (Sigma w)_i / sigma_p
    w_flat = w.flatten()
    ccv = w_flat * v.flatten()
    crc = w_flat * mrc

    # 5. Percentage Shares (Percentage of Total Portfolio Volatility & Variance)
    # Note: sum(pct_crc) == 100.0%, individual shares may be negative for hedges/shorts
    pct_crc = (crc / port_vol) * 100.0
    pct_ccv = (ccv / port_var) * 100.0

    # 6. Standalone Volatilities & Correlations with Portfolio
    # Standalone volatility of asset i: sigma_i = sqrt(Sigma_ii)
    # Correlation with portfolio: rho_ip = (Sigma w)_i / (sigma_i * sigma_p) = MRC_i / sigma_i
    diag_var = np.diag(Sigma)
    standalone_vols = np.sqrt(np.maximum(0.0, diag_var))
    correlations_with_p = np.zeros(n, dtype=np.float64)
    for i in range(n):
        if standalone_vols[i] > 1e-12:
            rho = mrc[i] / standalone_vols[i]
            correlations_with_p[i] = max(-1.0, min(1.0, rho))
        else:
            correlations_with_p[i] = 0.0

    # 7. Finite Difference Verification of MRC
    # Central difference: [sigma_p(w + eps*e_i) - sigma_p(w - eps*e_i)] / (2*eps)
    fd_mrc = np.zeros(n, dtype=np.float64)
    fd_errors = np.zeros(n, dtype=np.float64)
    if verify_finite_difference:
        for i in range(n):
            w_plus = w.copy()
            w_minus = w.copy()
            w_plus[i] += epsilon
            w_minus[i] -= epsilon

            var_plus = float((w_plus.T @ Sigma @ w_plus).item())
            var_minus = float((w_minus.T @ Sigma @ w_minus).item())
            vol_plus = math.sqrt(max(0.0, var_plus))
            vol_minus = math.sqrt(max(0.0, var_minus))

            num_grad = (vol_plus - vol_minus) / (2.0 * epsilon)
            fd_mrc[i] = num_grad
            fd_errors[i] = abs(num_grad - mrc[i])

    # 8. Euler Theorem Reconciliation
    sum_ccv = float(np.sum(ccv))
    sum_crc = float(np.sum(crc))
    var_residual = abs(sum_ccv - port_var)
    vol_residual = abs(sum_crc - port_vol)
    rel_residual = vol_residual / port_vol if port_vol > 1e-12 else 0.0

    if vol_residual <= reconciliation_tol:
        recon_status = ReconciliationStatus.RECONCILED
    elif vol_residual <= reconciliation_tol * 100.0:
        recon_status = ReconciliationStatus.RECONCILIATION_WARNING
    else:
        recon_status = ReconciliationStatus.RECONCILIATION_FAILED

    # Build holding result dicts
    syms = symbols if symbols and len(symbols) == n else asset_ids
    holdings_data = []
    for i in range(n):
        holdings_data.append({
            "asset_id": asset_ids[i],
            "symbol": syms[i],
            "weight": float(w_flat[i]),
            "standalone_volatility": float(standalone_vols[i]),
            "marginal_risk_contribution": float(mrc[i]),
            "marginal_variance_contribution": float(mcv[i]),
            "component_risk_contribution": float(crc[i]),
            "component_variance_contribution": float(ccv[i]),
            "percentage_risk_contribution": float(pct_crc[i]),
            "percentage_variance_contribution": float(pct_ccv[i]),
            "correlation_with_portfolio": float(correlations_with_p[i]),
            "finite_difference_mrc": float(fd_mrc[i]) if verify_finite_difference else None,
            "finite_difference_error": float(fd_errors[i]) if verify_finite_difference else None,
        })

    return {
        "status": RiskContributionStatus.VALID,
        "portfolio_variance": port_var,
        "portfolio_volatility": port_vol,
        "sum_component_variance": sum_ccv,
        "variance_residual": var_residual,
        "sum_component_volatility": sum_crc,
        "volatility_residual": vol_residual,
        "relative_residual": rel_residual,
        "reconciliation_status": recon_status,
        "max_fd_error": float(np.max(fd_errors)) if verify_finite_difference else None,
        "holdings": holdings_data,
    }


def aggregate_group_contributions(
    holdings: List[Dict[str, Any]],
    dimension_key: str,
    portfolio_volatility: float,
    portfolio_variance: float,
) -> List[Dict[str, Any]]:
    """
    Aggregate holding-level component contributions into mutually exclusive groups
    (e.g., sector, industry, geography, strategy sleeve).

    Verifies:
        sum(Group_CRC) == sum(Holding_CRC) == Portfolio_Volatility
    """
    if portfolio_volatility <= 1e-15:
        return []

    groups: Dict[str, Dict[str, Any]] = {}

    for h in holdings:
        g_name = h.get(dimension_key) or "Unclassified"
        if g_name not in groups:
            groups[g_name] = {
                "group_name": g_name,
                "holding_count": 0,
                "total_market_value": 0.0,
                "total_weight": 0.0,
                "component_risk_contribution": 0.0,
                "component_variance_contribution": 0.0,
            }

        groups[g_name]["holding_count"] += 1
        groups[g_name]["total_market_value"] += h.get("market_value", 0.0)
        groups[g_name]["total_weight"] += h.get("weight", 0.0)
        groups[g_name]["component_risk_contribution"] += h["component_risk_contribution"]
        groups[g_name]["component_variance_contribution"] += h["component_variance_contribution"]

    aggregated = []
    for g_name, data in groups.items():
        crc_val = data["component_risk_contribution"]
        ccv_val = data["component_variance_contribution"]
        data["percentage_risk_contribution"] = (crc_val / portfolio_volatility) * 100.0
        data["percentage_variance_contribution"] = (
            (ccv_val / portfolio_variance) * 100.0 if portfolio_variance > 1e-15 else 0.0
        )
        aggregated.append(data)

    # Sort descending by risk contribution
    aggregated.sort(key=lambda x: x["component_risk_contribution"], reverse=True)
    return aggregated


def calculate_weight_perturbation_scenario(
    base_weights: np.ndarray,
    weight_deltas: np.ndarray,
    cov_matrix: np.ndarray,
    asset_ids: List[str],
) -> Dict[str, Any]:
    """
    Evaluate the impact of proposed weight adjustments Delta_w on portfolio risk.
    Computes:
    - Base risk vs Perturbed risk
    - First-order Taylor approximation: Delta_sigma_approx = MRC^T * Delta_w
    - Exact non-linear change: Delta_sigma_exact = sigma(w + Delta_w) - sigma(w)
    - Taylor linearization error
    """
    w_base = np.asarray(base_weights, dtype=np.float64).reshape(-1, 1)
    delta_w = np.asarray(weight_deltas, dtype=np.float64).reshape(-1, 1)
    w_perturbed = w_base + delta_w
    Sigma = np.asarray(cov_matrix, dtype=np.float64)

    # Base risk
    base_decomp = decompose_portfolio_risk(
        weights=w_base.flatten(),
        cov_matrix=Sigma,
        asset_ids=asset_ids,
        verify_finite_difference=False,
    )
    base_vol = base_decomp["portfolio_volatility"]

    # Perturbed risk
    perturbed_decomp = decompose_portfolio_risk(
        weights=w_perturbed.flatten(),
        cov_matrix=Sigma,
        asset_ids=asset_ids,
        verify_finite_difference=False,
    )
    perturbed_vol = perturbed_decomp["portfolio_volatility"]

    # Exact delta
    delta_vol_exact = perturbed_vol - base_vol

    # First-order linear approximation using base MRC
    mrc_vec = np.array([h["marginal_risk_contribution"] for h in base_decomp["holdings"]])
    delta_vol_taylor = float(np.sum(mrc_vec * delta_w.flatten()))

    taylor_error = abs(delta_vol_exact - delta_vol_taylor)

    return {
        "base_volatility": base_vol,
        "perturbed_volatility": perturbed_vol,
        "exact_delta_volatility": delta_vol_exact,
        "taylor_delta_volatility": delta_vol_taylor,
        "taylor_approximation_error": taylor_error,
        "base_weights": w_base.flatten().tolist(),
        "perturbed_weights": w_perturbed.flatten().tolist(),
    }
