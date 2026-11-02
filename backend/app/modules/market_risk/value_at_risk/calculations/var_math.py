"""
Module M07.02: Value at Risk Mathematical Formulas.
Implements empirical loss quantiles, parametric variance-covariance VaR,
Cholesky-based Monte Carlo correlated simulations, Euler component risk attribution,
and horizon scaling.
"""
from decimal import Decimal, ROUND_HALF_UP
import math
import numpy as np
from typing import List, Tuple, Optional, Dict
from scipy.stats import norm, t as student_t

from backend.app.modules.market_risk.value_at_risk.models import (
    VaRQuantileMethod,
    VaRDistributionAssumption,
)

PRECISION_SIX = Decimal("0.000001")
PRECISION_EIGHT = Decimal("0.00000001")


def calculate_loss_quantile_from_returns(
    returns: List[Decimal],
    confidence_level: Decimal,
    quantile_method: VaRQuantileMethod = VaRQuantileMethod.LINEAR_INTERPOLATION,
) -> Tuple[Decimal, Decimal, int]:
    """
    Given portfolio return observations R, computes loss return L = -R,
    and extracts the empirical quantile Q_c(L).
    Returns: (signed_loss_quantile, non_negative_var_return, tail_observations_count)
    """
    n = len(returns)
    if n == 0:
        return Decimal("0.0"), Decimal("0.0"), 0

    # Losses L_t = -R_t
    losses = [float(-r) for r in returns]
    losses.sort()

    # Probability p = confidence_level (e.g. 0.95 or 0.99)
    # The tail consists of losses > quantile
    p_pct = float(confidence_level) * 100.0

    if quantile_method == VaRQuantileMethod.NEAREST_RANK:
        # Nearest rank: index = ceil(p * n) - 1
        idx = max(0, min(n - 1, int(math.ceil(float(confidence_level) * n)) - 1))
        loss_q = losses[idx]
    else:
        # Linear interpolation (standard numpy percentile)
        loss_q = float(np.percentile(losses, p_pct, method="linear"))

    tail_count = sum(1 for l in losses if l >= loss_q)

    signed_loss = Decimal(str(loss_q)).quantize(PRECISION_EIGHT, rounding=ROUND_HALF_UP)
    non_negative_var = max(Decimal("0.0"), signed_loss)

    return signed_loss, non_negative_var, tail_count


def calculate_parametric_portfolio_var(
    weights: List[Decimal],
    covariance_matrix: List[List[Decimal]],
    confidence_level: Decimal,
    holding_horizon_days: int = 1,
    expected_returns: Optional[List[Decimal]] = None,
    distribution: VaRDistributionAssumption = VaRDistributionAssumption.NORMAL,
    degrees_of_freedom: int = 5,
) -> Tuple[Decimal, Decimal, Decimal, List[Decimal], List[Decimal]]:
    """
    Parametric Variance-Covariance VaR and Euler Component Risk Attribution.
    Portfolio variance: sigma_p^2 = w^T * Sigma * w
    Portfolio expected return: mu_p = w^T * mu
    Loss quantile: VaR = z_c * sigma_p * sqrt(H) - mu_p * H
    Component VaR_i = w_i * (Sigma * w)_i / sigma_p * z_c * sqrt(H)

    Returns:
    (portfolio_volatility, signed_loss_quantile, non_negative_var, marginal_vars, component_vars)
    """
    w_vec = np.array([float(w) for w in weights])
    cov_mat = np.array([[float(c) for c in row] for row in covariance_matrix])

    # Portfolio Variance
    port_var = float(w_vec.T @ cov_mat @ w_vec)
    port_vol = math.sqrt(max(0.0, port_var))

    # Horizon scaling sqrt(H)
    sqrt_h = math.sqrt(float(holding_horizon_days))

    # Mean Return
    if expected_returns:
        mu_vec = np.array([float(m) for m in expected_returns])
        mu_p = float(w_vec.T @ mu_vec) * float(holding_horizon_days)
    else:
        mu_p = 0.0

    # Quantile z_c
    c_val = float(confidence_level)
    if distribution == VaRDistributionAssumption.STUDENT_T:
        # Standardized Student-t quantile: scale by sqrt((df-2)/df)
        df = max(3, degrees_of_freedom)
        scale_factor = math.sqrt((df - 2.0) / df)
        raw_t = student_t.ppf(c_val, df=df)
        z_c = raw_t * scale_factor
    else:
        z_c = norm.ppf(c_val)

    # Parametric Loss Quantile
    loss_quantile = (z_c * port_vol * sqrt_h) - mu_p

    # Euler Component Risk Attribution:
    # Covariance of asset i with portfolio: cov(r_i, r_p) = (Sigma * w)_i
    # Marginal VaR_i = (Sigma * w)_i / port_vol * z_c * sqrt(H)
    # Component VaR_i = w_i * Marginal VaR_i
    if port_vol > 0.0:
        cov_with_port = cov_mat @ w_vec
        marginal_vars_np = (cov_with_port / port_vol) * z_c * sqrt_h
        component_vars_np = w_vec * marginal_vars_np
    else:
        marginal_vars_np = np.zeros_like(w_vec)
        component_vars_np = np.zeros_like(w_vec)

    signed_loss = Decimal(str(loss_quantile)).quantize(PRECISION_EIGHT, rounding=ROUND_HALF_UP)
    non_negative_var = max(Decimal("0.0"), signed_loss)
    port_vol_dec = Decimal(str(port_vol)).quantize(PRECISION_EIGHT, rounding=ROUND_HALF_UP)

    marginal_dec = [Decimal(str(m)).quantize(PRECISION_EIGHT, rounding=ROUND_HALF_UP) for m in marginal_vars_np]
    component_dec = [Decimal(str(c)).quantize(PRECISION_EIGHT, rounding=ROUND_HALF_UP) for c in component_vars_np]

    return port_vol_dec, signed_loss, non_negative_var, marginal_dec, component_dec


def simulate_monte_carlo_portfolio_var(
    weights: List[Decimal],
    covariance_matrix: List[List[Decimal]],
    confidence_level: Decimal,
    simulation_count: int = 10000,
    holding_horizon_days: int = 1,
    random_seed: Optional[int] = 42,
    distribution: VaRDistributionAssumption = VaRDistributionAssumption.NORMAL,
) -> Tuple[Decimal, Decimal, int, List[float]]:
    """
    Monte Carlo Simulation using Cholesky Decomposition of Covariance Matrix.
    Simulates correlated asset returns, computes portfolio return R = w^T * r,
    and evaluates the empirical loss quantile.
    Returns: (signed_loss_quantile, non_negative_var, successful_sims, simulated_losses_sample)
    """
    if random_seed is not None:
        np.random.seed(random_seed)

    w_vec = np.array([float(w) for w in weights])
    cov_mat = np.array([[float(c) for c in row] for row in covariance_matrix])
    k = len(w_vec)

    # Scale covariance matrix for holding horizon H
    cov_mat_h = cov_mat * float(holding_horizon_days)

    # Cholesky Decomposition: Sigma_H = L * L^T
    try:
        chol_l = np.linalg.cholesky(cov_mat_h)
    except np.linalg.LinAlgError:
        # SVD / Eigenvalue regularization for near-singular matrix
        eigvals, eigvecs = np.linalg.eigh(cov_mat_h)
        eigvals = np.maximum(eigvals, 1e-8)
        cov_repaired = eigvecs @ np.diag(eigvals) @ eigvecs.T
        chol_l = np.linalg.cholesky(cov_repaired)

    # Generate standard normal random vectors Z ~ N(0, I)
    z = np.random.standard_normal((simulation_count, k))
    # Correlated asset return shocks: r = z * L^T
    r_sim = z @ chol_l.T

    # Portfolio simulated returns R_p = r_sim * w
    port_returns = r_sim @ w_vec
    simulated_losses = -port_returns
    simulated_losses.sort()

    p_pct = float(confidence_level) * 100.0
    loss_q = float(np.percentile(simulated_losses, p_pct, method="linear"))

    signed_loss = Decimal(str(loss_q)).quantize(PRECISION_EIGHT, rounding=ROUND_HALF_UP)
    non_negative_var = max(Decimal("0.0"), signed_loss)

    # Extract sample of 100 points for distribution chart
    sample_stride = max(1, len(simulated_losses) // 100)
    loss_sample = simulated_losses[::sample_stride].tolist()

    return signed_loss, non_negative_var, simulation_count, loss_sample
