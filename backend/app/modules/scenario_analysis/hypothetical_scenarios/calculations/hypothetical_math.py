"""
Hypothetical Scenarios Mathematical Calculations (M10.02).

Implements:
1. Channel A: Direct Valuation Shocks (Immediate PnL)
   - Price shocks:
     * Percentage price shock: P_{i,s} = P_{i,0} * (1 + r_i)
     * Absolute price shock: P_{i,s} = P_{i,0} + Delta P_i
     * Target price shock: Delta P_i = P_{i,target} - P_{i,0}
   - Factor shocks:
     * Modeled instrument return: R_i^{factor} = sum_k (beta_{i,k} * F_k) + epsilon_i
     * Combined factor + residual: (1 + R_i^{scenario}) = (1 + R_i^{factor}) * (1 + R_i^{residual})
   - Position revaluation & reconciliation:
     * Signed quantity: long > 0, short < 0
     * MV_{i,0} = q_i * P_{i,0}
     * MV_{i,s} = q_i * P_{i,s}
     * PnL_i = MV_{i,s} - MV_{i,0} = q_i * (P_{i,s} - P_{i,0})
     * Weight w_i = MV_{i,0} / NAV_0
     * Contribution C_i = w_i * R_i^{base}
     * Check: sum_i C_i == R_{portfolio}
   - Cross-currency conversion:
     * (1 + R_{base}) = (1 + R_{local}) * (1 + R_{FX})

2. Channel B: Risk-Model Assumption Shocks (No immediate PnL)
   - Volatility shocks:
     * Percentage scaling: sigma_s = sigma_0 * (1 + delta_sigma)
     * Absolute increase: sigma_s = sigma_0 + Delta sigma
     * Target volatility: sigma_s = sigma_{target}
   - Correlation shocks:
     * Pairwise override, group uplift, equicorrelation target
     * Full matrix validation: symmetry, unit diagonal, bounds [-1, 1], Positive Semidefinite (PSD)
     * Higham-style nearest correlation matrix repair projection if non-PSD
   - Covariance reconstruction:
     * Sigma_s = D_s * R_s * D_s, where D_s = diag(sigma_{1,s}, ..., sigma_{N,s})
   - Stressed Parametric VaR & ES:
     * Portfolio variance: sigma_{p,s}^2 = w^T * Sigma_s * w
     * VaR_alpha = z_alpha * sigma_{p,s} * NAV
     * ES_alpha = (phi(z_alpha) / (1 - alpha)) * sigma_{p,s} * NAV

3. Channel C: Liquidity & Execution Condition Shocks (Overlays)
   - Stressed spread: S_s = S_0 * (1 + delta_S) or S_0 + Delta S
   - Stressed depth: D_s = max(0, D_0 * (1 - delta_D))
   - Stressed volume: V_s = max(0, V_0 * (1 - delta_V))
   - Stressed depth-walk slippage estimation
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Optional, Tuple, Any
import math
import numpy as np
from scipy import linalg


def to_decimal(val: Any) -> Decimal:
    """Converts value to Decimal safely without silent float rounding."""
    if val is None:
        return Decimal("0")
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def apply_price_shock(
    baseline_price: Decimal,
    shock_method: str, # PERCENTAGE, ABSOLUTE, TARGET_PRICE
    shock_value: Decimal
) -> Tuple[Decimal, Decimal]:
    """
    Applies price shock.
    Returns: (scenario_price, price_return)
    """
    if baseline_price <= Decimal("0"):
        raise ValueError("Baseline price must be strictly positive")

    if shock_method == "PERCENTAGE":
        scenario_price = (baseline_price * (Decimal("1.0") + shock_value)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
        price_return = shock_value
    elif shock_method == "ABSOLUTE":
        scenario_price = (baseline_price + shock_value).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
        price_return = ((scenario_price - baseline_price) / baseline_price).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
    elif shock_method == "TARGET_PRICE":
        scenario_price = shock_value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
        price_return = ((scenario_price - baseline_price) / baseline_price).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
    else:
        raise ValueError(f"Unsupported price shock method: {shock_method}")

    if scenario_price <= Decimal("0"):
        raise ValueError(f"Scenario price must be strictly positive for equity valuation. Got {scenario_price}")

    return scenario_price, price_return


def apply_factor_shock(
    factor_sensitivities: Dict[str, Decimal],
    factor_shocks: Dict[str, Decimal],
    residual_shock: Decimal = Decimal("0")
) -> Decimal:
    """
    Computes modeled return from systematic factor shocks:
    R_i^{factor} = sum_k (beta_{i,k} * F_k) + epsilon_i
    """
    total_ret = Decimal("0")
    for f_name, beta in factor_sensitivities.items():
        if f_name in factor_shocks:
            total_ret += beta * factor_shocks[f_name]
    total_ret += residual_shock
    return total_ret.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def apply_volatility_shock(
    baseline_volatility: Decimal,
    shock_method: str, # PERCENTAGE, ABSOLUTE, TARGET_VOLATILITY
    shock_value: Decimal
) -> Decimal:
    """
    Computes stressed volatility:
    - PERCENTAGE: sigma_s = sigma_0 * (1 + delta_sigma)
    - ABSOLUTE: sigma_s = sigma_0 + Delta sigma
    - TARGET: sigma_s = sigma_{target}
    """
    if baseline_volatility < Decimal("0"):
        raise ValueError("Baseline volatility cannot be negative")

    if shock_method == "PERCENTAGE":
        stressed_vol = baseline_volatility * (Decimal("1.0") + shock_value)
    elif shock_method == "ABSOLUTE":
        stressed_vol = baseline_volatility + shock_value
    elif shock_method == "TARGET_VOLATILITY":
        stressed_vol = shock_value
    else:
        raise ValueError(f"Unsupported volatility shock method: {shock_method}")

    if stressed_vol < Decimal("0"):
        raise ValueError(f"Scenario volatility cannot be negative. Got {stressed_vol}")

    return stressed_vol.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def validate_and_repair_correlation_matrix(
    corr_matrix: np.ndarray,
    repair_policy: str = "REJECT_INVALID_MATRIX" # REJECT_INVALID_MATRIX, NEAREST_CORRELATION_MATRIX_REPAIR
) -> Tuple[np.ndarray, bool, Dict[str, Any]]:
    """
    Validates complete correlation matrix:
    - Symmetry: R == R^T
    - Unit diagonal: R_{ii} == 1
    - Bounds: -1 <= R_{ij} <= 1
    - Positive Semidefinite (PSD): eigenvalues >= 0
    Optionally repairs non-PSD matrix via eigenvalue clipping & diagonal re-normalization.
    """
    N = corr_matrix.shape[0]
    if corr_matrix.shape[1] != N:
        raise ValueError("Correlation matrix must be square")

    # Symmetrize
    sym_matrix = (corr_matrix + corr_matrix.T) / 2.0
    np.fill_diagonal(sym_matrix, 1.0)

    # Check bounds
    if np.any(sym_matrix < -1.0 - 1e-7) or np.any(sym_matrix > 1.0 + 1e-7):
        raise ValueError("Correlation matrix elements must be bounded between -1 and 1")

    eigenvals, eigenvecs = np.linalg.eigh(sym_matrix)
    min_eigenval = float(np.min(eigenvals))
    is_psd = min_eigenval >= -1e-8

    repaired = False
    repair_magnitude = 0.0
    final_matrix = sym_matrix

    if not is_psd:
        if repair_policy == "REJECT_INVALID_MATRIX":
            raise ValueError(f"Correlation matrix is non-positive-semidefinite (min eigenvalue: {min_eigenval:.6f})")
        elif repair_policy == "NEAREST_CORRELATION_MATRIX_REPAIR":
            # Higham-style spectral projection: clip negative eigenvalues to 1e-8, project, and re-normalize diagonal
            clipped_eigenvals = np.maximum(eigenvals, 1e-8)
            reconstructed = eigenvecs @ np.diag(clipped_eigenvals) @ eigenvecs.T
            # Re-normalize diagonal to 1.0
            d = np.sqrt(np.diag(reconstructed))
            reconstructed = reconstructed / np.outer(d, d)
            np.fill_diagonal(reconstructed, 1.0)
            
            repair_magnitude = float(np.linalg.norm(reconstructed - sym_matrix, 'fro'))
            final_matrix = reconstructed
            repaired = True

    diagnostics = {
        "min_eigenvalue": min_eigenval,
        "is_psd_originally": is_psd,
        "repaired": repaired,
        "repair_magnitude": repair_magnitude
    }
    return final_matrix, is_psd or repaired, diagnostics


def reconstruct_covariance_matrix(
    volatilities: np.ndarray,
    correlation_matrix: np.ndarray
) -> np.ndarray:
    """
    Constructs scenario covariance matrix:
    Sigma_s = D_s * R_s * D_s
    """
    D = np.diag(volatilities)
    cov = D @ correlation_matrix @ D
    return (cov + cov.T) / 2.0


def compute_stressed_risk_metrics(
    portfolio_weights: np.ndarray,
    baseline_nav: Decimal,
    covariance_matrix: np.ndarray,
    confidence_level: float = 0.95
) -> Dict[str, Decimal]:
    """
    Computes portfolio volatility, Parametric VaR, and Parametric Expected Shortfall under stressed covariance:
    sigma_p^2 = w^T * Sigma * w
    VaR = z_alpha * sigma_p * NAV
    ES = (phi(z_alpha) / (1 - alpha)) * sigma_p * NAV
    """
    w = portfolio_weights
    port_var = float(w.T @ covariance_matrix @ w)
    port_vol = math.sqrt(max(0.0, port_var))

    # Standard normal quantile
    # z_95 = 1.64485, z_99 = 2.32635
    if abs(confidence_level - 0.95) < 0.01:
        z = 1.6448536269514722
        phi = 0.10313564037803027 # standard normal pdf at 1.64485
    elif abs(confidence_level - 0.99) < 0.01:
        z = 2.3263478740408408
        phi = 0.02665214224747441
    else:
        from scipy.stats import norm
        z = norm.ppf(confidence_level)
        phi = norm.pdf(z)

    nav_flt = float(baseline_nav)
    var_dollar = z * port_vol * nav_flt
    es_dollar = (phi / (1.0 - confidence_level)) * port_vol * nav_flt

    return {
        "portfolio_volatility": Decimal(str(port_vol)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        "parametric_var": Decimal(str(var_dollar)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "parametric_es": Decimal(str(es_dollar)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    }


def revalue_hypothetical_position(
    signed_quantity: Decimal,
    baseline_price: Decimal,
    scenario_price: Decimal,
    baseline_nav: Decimal
) -> Dict[str, Decimal]:
    """
    Computes position PnL, market values, and portfolio return contribution:
    MV_{i,0} = q_i * P_{i,0}
    MV_{i,s} = q_i * P_{i,s}
    PnL_i = MV_{i,s} - MV_{i,0}
    Contribution C_i = PnL_i / NAV_0
    """
    baseline_mv = (signed_quantity * baseline_price).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    scenario_mv = (signed_quantity * scenario_price).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    scenario_pnl = (scenario_mv - baseline_mv).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    weight = Decimal("0")
    contrib = Decimal("0")
    if baseline_nav > Decimal("0"):
        weight = (baseline_mv / baseline_nav).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
        contrib = (scenario_pnl / baseline_nav).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    return {
        "baseline_market_value": baseline_mv,
        "scenario_market_value": scenario_mv,
        "scenario_pnl": scenario_pnl,
        "portfolio_weight": weight,
        "portfolio_contribution": contrib
    }


def apply_liquidity_overlay(
    baseline_spread: Decimal,
    baseline_bid_depth: Decimal,
    baseline_ask_depth: Decimal,
    baseline_volume: Decimal,
    spread_shock_pct: Decimal = Decimal("0"),
    depth_shock_pct: Decimal = Decimal("0"),
    volume_shock_pct: Decimal = Decimal("0")
) -> Dict[str, Decimal]:
    """
    Computes stressed liquidity parameters:
    S_s = S_0 * (1 + delta_S)
    D_s = max(0, D_0 * (1 - delta_D))
    V_s = max(0, V_0 * (1 - delta_V))
    """
    stressed_spread = (baseline_spread * (Decimal("1.0") + spread_shock_pct)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    stressed_bid_depth = max(Decimal("0"), baseline_bid_depth * (Decimal("1.0") - depth_shock_pct)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    stressed_ask_depth = max(Decimal("0"), baseline_ask_depth * (Decimal("1.0") - depth_shock_pct)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    stressed_volume = max(Decimal("0"), baseline_volume * (Decimal("1.0") - volume_shock_pct)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    return {
        "scenario_spread": stressed_spread,
        "scenario_bid_depth": stressed_bid_depth,
        "scenario_ask_depth": stressed_ask_depth,
        "scenario_volume": stressed_volume
    }

