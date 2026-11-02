"""
M07.07 Portfolio Beta Mathematical & Econometric Engine.
Implements:
- OLS regression with intercept: R_i = alpha + beta * R_b + eps
- Beta coefficient: Cov(R_i, R_b) / Var(R_b)
- Regression alpha/intercept: mean(R_i) - beta * mean(R_b)
- R-squared & Adjusted R-squared
- Residual standard error & Beta standard error
- Student's t-statistic, two-tailed p-value, and 95% confidence intervals
- Portfolio direct regression & static weight implied beta: beta_p = sum(w_i * beta_i)
- Risk contributions by security
"""
from typing import Dict, Any, List, Optional
import math
import numpy as np
from scipy import stats

from backend.app.modules.market_risk.beta.models import (
    BetaModelType,
    BetaRegressionStatus,
)


def calculate_ols_beta(
    returns_asset: np.ndarray,
    returns_benchmark: np.ndarray,
    model_type: BetaModelType = BetaModelType.OLS_WITH_INTERCEPT,
    include_intercept: bool = True,
    min_observations: int = 5,
    confidence_level: float = 0.95,
) -> Dict[str, Any]:
    """
    Perform OLS regression of asset returns on benchmark returns.
    """
    if not include_intercept:
        model_type = BetaModelType.OLS_WITHOUT_INTERCEPT

    n = len(returns_asset)
    if n < min_observations or len(returns_benchmark) != n:
        return {
            "beta": None,
            "alpha": None,
            "r_squared": None,
            "adjusted_r_squared": None,
            "beta_std_error": None,
            "beta_t_stat": None,
            "p_value": None,
            "ci_lower": None,
            "ci_upper": None,
            "residual_std_error": None,
            "sample_size": n,
            "status": BetaRegressionStatus.INSUFFICIENT_OBSERVATIONS,
            "regression_status": BetaRegressionStatus.INSUFFICIENT_OBSERVATIONS,
        }

    y = returns_asset
    x = returns_benchmark

    var_x = float(np.var(x, ddof=1))
    var_y = float(np.var(y, ddof=1))

    if var_x < 1e-12:
        return {
            "beta": None,
            "alpha": float(np.mean(y)),
            "r_squared": None,
            "adjusted_r_squared": None,
            "beta_std_error": None,
            "beta_t_stat": None,
            "p_value": None,
            "ci_lower": None,
            "ci_upper": None,
            "residual_std_error": None,
            "sample_size": n,
            "status": BetaRegressionStatus.ZERO_BENCHMARK_VARIANCE,
            "regression_status": BetaRegressionStatus.ZERO_BENCHMARK_VARIANCE,
        }

    mean_x = float(np.mean(x))
    mean_y = float(np.mean(y))

    if model_type == BetaModelType.OLS_WITH_INTERCEPT:
        ss_xx = float(np.sum((x - mean_x) ** 2))
        ss_xy = float(np.sum((x - mean_x) * (y - mean_y)))
        ss_yy = float(np.sum((y - mean_y) ** 2))

        beta = ss_xy / ss_xx if ss_xx > 1e-12 else 0.0
        alpha = mean_y - beta * mean_x

        fitted = alpha + beta * x
        residuals = y - fitted
        sse = float(np.sum(residuals ** 2))

        df_resid = max(1, n - 2)
        r_squared = 1.0 - (sse / ss_yy) if ss_yy > 1e-12 else 0.0
        r_squared = max(0.0, min(1.0, r_squared))

        adj_r2 = 1.0 - (1.0 - r_squared) * (float(n - 1) / float(df_resid)) if n > 2 else r_squared

        s_err = math.sqrt(sse / df_resid) if df_resid > 0 else 0.0
        se_beta = s_err / math.sqrt(ss_xx) if ss_xx > 1e-12 else 0.0

        if se_beta > 1e-12:
            t_stat = beta / se_beta
            p_val = float(2.0 * (1.0 - stats.t.cdf(abs(t_stat), df=df_resid)))
        else:
            t_stat = 0.0
            p_val = 1.0

        # Confidence Interval
        crit_t = float(stats.t.ppf(0.5 + confidence_level / 2.0, df=df_resid)) if df_resid > 0 else 1.96
        ci_low = beta - crit_t * se_beta
        ci_high = beta + crit_t * se_beta

    else:
        # No intercept regression
        ss_xx = float(np.sum(x ** 2))
        ss_xy = float(np.sum(x * y))
        ss_yy = float(np.sum(y ** 2))

        beta = ss_xy / ss_xx if ss_xx > 1e-12 else 0.0
        alpha = 0.0

        fitted = beta * x
        residuals = y - fitted
        sse = float(np.sum(residuals ** 2))

        df_resid = max(1, n - 1)
        r_squared = 1.0 - (sse / ss_yy) if ss_yy > 1e-12 else 0.0
        r_squared = max(0.0, min(1.0, r_squared))
        adj_r2 = r_squared

        s_err = math.sqrt(sse / df_resid)
        se_beta = s_err / math.sqrt(ss_xx) if ss_xx > 1e-12 else 0.0
        t_stat = beta / se_beta if se_beta > 1e-12 else 0.0
        p_val = float(2.0 * (1.0 - stats.t.cdf(abs(t_stat), df=df_resid))) if se_beta > 1e-12 else 1.0
        crit_t = float(stats.t.ppf(0.5 + confidence_level / 2.0, df=df_resid))
        ci_low = beta - crit_t * se_beta
        ci_high = beta + crit_t * se_beta

    return {
        "beta": beta,
        "alpha": alpha,
        "r_squared": r_squared,
        "adjusted_r_squared": adj_r2,
        "beta_std_error": se_beta,
        "beta_t_stat": t_stat,
        "p_value": p_val,
        "ci_lower": ci_low,
        "ci_upper": ci_high,
        "residual_std_error": s_err,
        "sample_size": n,
        "status": BetaRegressionStatus.VALID,
        "regression_status": BetaRegressionStatus.VALID,
    }


def calculate_portfolio_weighted_beta(
    weights: np.ndarray,
    betas: np.ndarray,
    symbols: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Compute portfolio beta via weighted aggregation of security betas:
    beta_p = sum(w_i * beta_i).
    Computes component beta contributions w_i * beta_i and contribution percentages.
    """
    contributions = weights * betas
    p_beta = float(np.sum(contributions))

    reconciliation_sum = float(np.sum(contributions))
    discrepancy = float(abs(reconciliation_sum - p_beta))

    contrib_details = []
    sym_list = symbols if symbols is not None else [f"ASSET_{i}" for i in range(len(weights))]
    for i in range(len(weights)):
        contrib_details.append({
            "symbol": sym_list[i],
            "weight": float(weights[i]),
            "beta": float(betas[i]),
            "weighted_beta": float(contributions[i]),
            "percentage_of_total_beta": float(contributions[i] / p_beta) if abs(p_beta) > 1e-12 else 0.0,
        })

    return {
        "portfolio_beta": p_beta,
        "contributions": contrib_details,
        "reconciliation_sum": reconciliation_sum,
        "discrepancy": discrepancy,
    }
