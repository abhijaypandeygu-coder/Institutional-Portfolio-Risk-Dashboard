"""
Monte Carlo Mathematics and Stochastic Path Simulation Engine.
Implements:
1. Matrix validation, PSD checking, and repair (Eigenvalue clipping / Higham / Shrinkage).
2. Cholesky factorization of correlation and covariance matrices.
3. Vectorized sampling from Multivariate Normal, Multivariate Student-t (with shared chi-square scale mixture),
   and Aligned Historical Bootstrap.
4. Multi-period Geometric Brownian Motion (GBM) path updates preserving positive prices.
5. Signed portfolio valuation across paths and steps: V_p(t) = sum_i(Q_i * S_i(t)) + Cash.
6. Descriptive moments (mean, std, skewness, excess kurtosis), quantiles, and loss probabilities.
7. Loss-positive Monte Carlo Value-at-Risk (VaR) and Expected Shortfall (CVaR).
"""

from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from scipy import stats
from decimal import Decimal, ROUND_HALF_UP


def validate_and_repair_correlation_matrix(
    corr_matrix: np.ndarray,
    min_eigenvalue: float = 1e-7,
    repair_method: str = "EIGENVALUE_CLIPPING"
) -> Tuple[np.ndarray, bool]:
    """
    Validates symmetry, unit diagonal, bounds [-1, 1], and positive semi-definiteness (PSD).
    If not PSD or invalid, applies eigenvalue clipping, shrinkage, or spectral projection.
    Returns (repaired_matrix, was_repaired).
    """
    R = np.copy(corr_matrix).astype(np.float64)
    n = R.shape[0]
    was_repaired = False

    # 1. Check symmetry
    if not np.allclose(R, R.T, atol=1e-8):
        R = 0.5 * (R + R.T)
        was_repaired = True

    # 2. Check diagonal
    if not np.allclose(np.diag(R), 1.0, atol=1e-6):
        np.fill_diagonal(R, 1.0)
        was_repaired = True

    # 3. Check bounds [-1, 1]
    if np.any(R < -1.0) or np.any(R > 1.0):
        R = np.clip(R, -1.0, 1.0)
        np.fill_diagonal(R, 1.0)
        was_repaired = True

    # 4. Check eigenvalues
    eigvals, eigvecs = np.linalg.eigh(R)
    if np.min(eigvals) < min_eigenvalue:
        was_repaired = True
        if repair_method == "SHRINKAGE":
            # Shrink towards identity matrix: R_shrunk = (1 - alpha) * R + alpha * I
            alpha = 0.1
            while np.min(np.linalg.eigvalsh(R)) < min_eigenvalue and alpha <= 1.0:
                R = (1.0 - alpha) * R + alpha * np.eye(n)
                alpha += 0.05
        else:
            # Default: EIGENVALUE_CLIPPING / Spectral reconstruction
            eigvals_clipped = np.maximum(eigvals, min_eigenvalue)
            # Reconstruct: V * diag(eigvals) * V^T
            R_rebuilt = eigvecs @ np.diag(eigvals_clipped) @ eigvecs.T
            # Rescale to ensure unit diagonal
            inv_sqrt_diag = 1.0 / np.sqrt(np.diag(R_rebuilt))
            R = R_rebuilt * np.outer(inv_sqrt_diag, inv_sqrt_diag)
            np.fill_diagonal(R, 1.0)

    # Final symmetry & unit diag enforcement
    R = 0.5 * (R + R.T)
    np.fill_diagonal(R, 1.0)
    return R, was_repaired


def compute_cholesky_factor(matrix: np.ndarray) -> np.ndarray:
    """
    Computes lower triangular Cholesky factor L such that L @ L.T = matrix.
    If matrix is near singular, attempts jitter before raising.
    """
    try:
        return np.linalg.cholesky(matrix)
    except np.linalg.LinAlgError:
        # Add jitter
        jittered = matrix + np.eye(matrix.shape[0]) * 1e-6
        return np.linalg.cholesky(jittered)


def generate_correlated_innovations(
    n_paths: int,
    n_instruments: int,
    cholesky_L: np.ndarray,
    distribution_type: str = "MULTIVARIATE_NORMAL",
    degrees_of_freedom: float = 5.0,
    rng: Optional[np.random.Generator] = None,
    empirical_returns: Optional[np.ndarray] = None
) -> np.ndarray:
    """
    Generates standardized correlated innovations Z with shape (n_paths, n_instruments).
    E[Z] = 0, Cov(Z) ~ Correlation Matrix.
    
    Distributions:
    - MULTIVARIATE_NORMAL: Z = U @ L.T, U ~ N(0, I)
    - STUDENT_T: Z = sqrt((nu - 2) / W) * (U @ L.T) where W ~ Chi2(nu), inducing true tail dependence
    - EMPIRICAL_BOOTSTRAP: Aligned resampling across historical cross-sectional observations
    """
    if rng is None:
        rng = np.random.default_rng()

    if distribution_type == "MULTIVARIATE_NORMAL":
        # Standard normal random matrix: (n_paths, n_instruments)
        U = rng.standard_normal(size=(n_paths, n_instruments))
        # Correlated innovations: U @ L^T
        Z = U @ cholesky_L.T
        return Z

    elif distribution_type == "STUDENT_T":
        nu = max(2.01, float(degrees_of_freedom))
        # Independent standard normals
        U = rng.standard_normal(size=(n_paths, n_instruments))
        Z_norm = U @ cholesky_L.T
        # Shared chi-squared random variable per path: W ~ Chi-squared(nu)
        # Shape: (n_paths, 1) to induce joint tail dependence
        W = rng.chisquare(df=nu, size=(n_paths, 1))
        # Variance of Student-t is nu / (nu - 2). To scale to unit variance:
        # scale = sqrt((nu - 2) / W)
        scale = np.sqrt((nu - 2.0) / W)
        Z_t = scale * Z_norm
        return Z_t

    elif distribution_type == "EMPIRICAL_BOOTSTRAP":
        if empirical_returns is None or len(empirical_returns) < 5:
            # Fallback to normal if empirical series is insufficient
            U = rng.standard_normal(size=(n_paths, n_instruments))
            return U @ cholesky_L.T
        
        # Cross-sectionally aligned bootstrap
        n_obs = empirical_returns.shape[0]
        # Resample time indices with replacement
        sample_indices = rng.integers(0, n_obs, size=n_paths)
        sampled = empirical_returns[sample_indices, :]  # (n_paths, n_instruments)
        
        # Center and standardize
        means = np.mean(sampled, axis=0)
        stds = np.std(sampled, axis=0, ddof=1)
        stds = np.where(stds < 1e-8, 1.0, stds)
        standardized = (sampled - means) / stds
        return standardized

    else:
        # Default normal fallback
        U = rng.standard_normal(size=(n_paths, n_instruments))
        return U @ cholesky_L.T


def simulate_geometric_brownian_paths(
    initial_prices: np.ndarray,      # (n_instruments,)
    drifts: np.ndarray,              # annual expected returns mu (n_instruments,)
    volatilities: np.ndarray,        # annual volatilities sigma (n_instruments,)
    cholesky_L: np.ndarray,          # Cholesky factor of correlation matrix (n_inst, n_inst)
    n_paths: int,
    n_steps: int,
    dt: float,                       # time step in years (e.g., 1/252 for daily)
    distribution_type: str = "MULTIVARIATE_NORMAL",
    degrees_of_freedom: float = 5.0,
    rng: Optional[np.random.Generator] = None,
    empirical_returns: Optional[np.ndarray] = None,
    store_full_paths: bool = False
) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    """
    Simulates price paths using Geometric Brownian Motion:
    S_{t+dt} = S_t * exp( (mu - 0.5 * sigma^2)*dt + sigma * sqrt(dt) * Z_t )
    
    Guarantees strictly positive prices.
    Returns:
    - terminal_prices: shape (n_paths, n_instruments)
    - full_paths: shape (n_paths, n_steps + 1, n_instruments) if store_full_paths else None
    """
    n_inst = len(initial_prices)
    if rng is None:
        rng = np.random.default_rng()

    # Precalculate drift per step: (mu - 0.5 * sigma^2) * dt
    drift_step = (drifts - 0.5 * (volatilities ** 2)) * dt  # shape (n_instruments,)
    vol_step = volatilities * np.sqrt(dt)                  # shape (n_instruments,)

    # Initialize current prices: (n_paths, n_instruments)
    current_prices = np.tile(initial_prices, (n_paths, 1)).astype(np.float64)

    full_paths = None
    if store_full_paths:
        full_paths = np.empty((n_paths, n_steps + 1, n_inst), dtype=np.float64)
        full_paths[:, 0, :] = current_prices

    for step in range(1, n_steps + 1):
        Z = generate_correlated_innovations(
            n_paths=n_paths,
            n_instruments=n_inst,
            cholesky_L=cholesky_L,
            distribution_type=distribution_type,
            degrees_of_freedom=degrees_of_freedom,
            rng=rng,
            empirical_returns=empirical_returns
        )
        # Log-returns: drift_step + vol_step * Z
        log_ret = drift_step + vol_step * Z
        current_prices = current_prices * np.exp(log_ret)

        if store_full_paths and full_paths is not None:
            full_paths[:, step, :] = current_prices

    return current_prices, full_paths


def calculate_portfolio_outcomes(
    quantities: np.ndarray,          # signed position quantities (n_instruments,)
    baseline_prices: np.ndarray,     # baseline prices S_0 (n_instruments,)
    simulated_prices: np.ndarray,    # simulated prices S_H (n_paths, n_instruments)
    cash_balance: float = 0.0
) -> Dict[str, np.ndarray]:
    """
    Computes portfolio baseline value, simulated values, terminal P&L, and returns.
    V_p(0) = sum_i(Q_i * S_{i,0}) + Cash
    V_p(H) = sum_i(Q_i * S_{i,H}) + Cash
    P&L = V_p(H) - V_p(0)
    R_p = P&L / V_p(0)
    """
    baseline_positions_value = np.sum(quantities * baseline_prices)
    baseline_portfolio_value = float(baseline_positions_value + cash_balance)

    # Simulated portfolio values: (n_paths,)
    simulated_portfolio_values = np.sum(simulated_prices * quantities, axis=1) + cash_balance
    pnl = simulated_portfolio_values - baseline_portfolio_value

    if abs(baseline_portfolio_value) > 1e-8:
        returns = pnl / abs(baseline_portfolio_value)
    else:
        returns = np.zeros_like(pnl)

    # Instrument-level terminal P&L: (n_paths, n_instruments)
    instrument_pnl = (simulated_prices - baseline_prices) * quantities

    return {
        "baseline_portfolio_value": baseline_portfolio_value,
        "simulated_portfolio_values": simulated_portfolio_values,
        "pnl": pnl,
        "returns": returns,
        "instrument_pnl": instrument_pnl
    }


def compute_distribution_statistics(
    series: np.ndarray,
    loss_threshold: float = 0.0
) -> Dict[str, float]:
    """
    Computes descriptive statistical moments, quantiles, and loss probabilities.
    """
    n = len(series)
    if n == 0:
        return {}

    mean_val = float(np.mean(series))
    std_val = float(np.std(series, ddof=1)) if n > 1 else 0.0
    median_val = float(np.median(series))
    skew_val = float(stats.skew(series)) if (n > 2 and std_val > 1e-9) else 0.0
    kurt_val = float(stats.kurtosis(series)) if (n > 3 and std_val > 1e-9) else 0.0

    percentiles = [1.0, 5.0, 10.0, 25.0, 50.0, 75.0, 90.0, 95.0, 99.0]
    pct_values = np.percentile(series, percentiles)
    pct_dict = {f"p{int(p) if p.is_integer() else str(p).replace('.', '_')}": float(v) for p, v in zip(percentiles, pct_values)}

    # Probability of loss (series < loss_threshold)
    loss_count = int(np.sum(series < loss_threshold))
    loss_prob = float(loss_count / n)

    return {
        "mean": mean_val,
        "std": std_val,
        "median": median_val,
        "skewness": skew_val,
        "excess_kurtosis": kurt_val,
        "min": float(np.min(series)),
        "max": float(np.max(series)),
        "loss_probability": loss_prob,
        **pct_dict
    }


def compute_var_and_cvar(
    pnl_distribution: np.ndarray,
    confidence_levels: List[float] = [0.90, 0.95, 0.99]
) -> Dict[str, Dict[str, float]]:
    """
    Calculates Monte Carlo Value-at-Risk (VaR) and Expected Shortfall (CVaR).
    Strict institutional convention:
    Loss L = -P&L (positive number for losses).
    VaR_alpha = quantile_alpha(L).
    CVaR_alpha = E[ L | L >= VaR_alpha ].
    """
    losses = -pnl_distribution
    n = len(losses)
    results = {}

    for conf in confidence_levels:
        # Quantile at conf (e.g. 95% quantile of losses)
        var_loss = float(np.percentile(losses, conf * 100.0))
        # Tail losses >= VaR
        tail_losses = losses[losses >= var_loss]
        if len(tail_losses) > 0:
            cvar_loss = float(np.mean(tail_losses))
        else:
            cvar_loss = var_loss

        pct_key = f"{int(conf * 100)}%"
        results[pct_key] = {
            "confidence_level": conf,
            "var_loss": var_loss,
            "cvar_loss": cvar_loss,
            "pnl_var_cutoff": -var_loss,   # P&L value at cutoff
            "pnl_tail_mean": -cvar_loss    # Expected tail P&L
        }

    return results


def to_decimal(val: float, places: int = 4) -> Decimal:
    """Helper to convert float to rounded Decimal safely."""
    if np.isnan(val) or np.isinf(val):
        return Decimal("0.0000")
    fmt = f"0.{'0'*places}"
    return Decimal(str(val)).quantize(Decimal(fmt), rounding=ROUND_HALF_UP)

