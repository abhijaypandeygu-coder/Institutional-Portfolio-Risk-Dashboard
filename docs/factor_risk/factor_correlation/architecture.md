# M08.07 Factor Correlation Architecture Documentation

## 1. Executive Summary & Module Scope

**M08.07 — Factor Correlation** is the authoritative quantitative analytics module within the **Institutional Portfolio Risk Dashboard** responsible for measuring, monitoring, and regularizing co-movements among systematic factor returns.

Factor returns are rarely orthogonal in practice. Macroeconomic shocks, monetary policy shifts, and liquidity cascades routinely induce dynamic inter-factor correlations (e.g., Value and Momentum correlation breakdown or Market and Quality flight-to-safety dynamics).

M08.07 fulfills four foundational responsibilities in the risk modeling architecture:
1. **Inter-Factor Correlation Analysis:** Complete $K \times K$ pairwise correlation matrices across Pearson baseline, Spearman rank, and Kendall's $\tau$, with two-tailed significance testing, Fisher's $z$ confidence intervals, and rigorous zero-variance detection.
2. **Authoritative Factor Covariance Ownership:** Serves as the single source of truth for factor covariance estimation ($\boldsymbol{\Sigma}_F$) consumed by M08.05 Systematic Risk and M08.04 Factor Attribution. Guarantees mutual mathematical consistency $\boldsymbol{\Sigma}_F = \mathbf{D} \mathbf{P}_F \mathbf{D}$, supports Sample, RiskMetrics EWMA ($\lambda = 0.94$), and Ledoit-Wolf analytical shrinkage, with Higham (2002) spectral projection onto the nearest positive semi-definite cone.
3. **Rolling Factor Dynamics:** Tracks moving relationships across multiple horizons (20, 60, 120, 252 days), separating **signed changes** ($\Delta \rho$) from **absolute strength changes** ($\Delta |\rho|$), scoring percentile ranks against historical baselines, and categorizing stability states (`STABLE_POSITIVE`, `SIGN_REVERSAL`, `HIGH_VOLATILITY_RELATIONSHIP`).
4. **Correlation Regime & Structural Break Monitoring:** Automatically detects extreme positive/negative coherence, rapid correlation shifts, sign flips, and CUSUM structural breaks with persistence and hysteresis recovery rules.

---

## 2. Mathematical Architecture

### 2.1 Pairwise Correlation & Fisher's $z$ Transformation

For two factor return series $\mathbf{f}_i$ and $\mathbf{f}_j$ over $T$ observations:
$$\rho_{ij} = \frac{\sum_{t=1}^T (f_{it} - \bar{f}_i)(f_{jt} - \bar{f}_j)}{\sqrt{\sum_{t=1}^T (f_{it} - \bar{f}_i)^2 \sum_{t=1}^T (f_{jt} - \bar{f}_j)^2}}$$

**Zero Variance Rule:** If $\text{Var}(\mathbf{f}_i) < 10^{-12}$ or $\text{Var}(\mathbf{f}_j) < 10^{-12}$, the correlation is mathematically undefined ($\frac{0}{0}$). The engine flags `is_defined = False` with `undefined_reason` and explicitly rejects substituting 0.0.

**Fisher's $z$ Confidence Intervals:**
For Pearson correlation, Fisher's $z$-transformation linearizes the sampling distribution:
$$z = \frac{1}{2} \ln \left( \frac{1 + \rho}{1 - \rho} \right) = \text{arctanh}(\rho)$$
$$\text{SE}(z) = \frac{1}{\sqrt{T - 3}}$$
Given standard normal quantile $z_{\alpha/2}$, the confidence interval in $z$-space is $[z - z_{\alpha/2}\text{SE}, z + z_{\alpha/2}\text{SE}]$. Transforming back yields:
$$\text{CI} = \left[ \tanh(z - z_{\alpha/2}\text{SE}), \tanh(z + z_{\alpha/2}\text{SE}) \right]$$

---

### 2.2 Factor Covariance Estimation & Mathematical Consistency

The relationship between factor covariance $\boldsymbol{\Sigma}_F$, factor correlation $\mathbf{P}_F$, and factor standard deviations $\mathbf{D} = \text{diag}(\sigma_1, \dots, \sigma_K)$ must strictly satisfy:
$$\boldsymbol{\Sigma}_F = \mathbf{D} \mathbf{P}_F \mathbf{D}$$

The engine computes both matrices simultaneously and validates:
$$\max_{i, j} \left| \boldsymbol{\Sigma}_{F, ij} - \sigma_i \rho_{ij} \sigma_j \right| < 10^{-6}$$

#### Estimators Supported:
1. **Sample Covariance:**
   $$\boldsymbol{\Sigma}_{\text{sample}} = \frac{1}{T - 1} \sum_{t=1}^T (\mathbf{f}_t - \bar{\mathbf{f}})(\mathbf{f}_t - \bar{\mathbf{f}})^T$$
2. **Exponentially Weighted Moving Average (EWMA):**
   $$w_t = (1 - \lambda)\lambda^{T - t}, \quad \boldsymbol{\Sigma}_{\text{ewma}} = \frac{1}{1 - \sum w_t^2} \sum_{t=1}^T w_t (\mathbf{f}_t - \bar{\mathbf{f}}_w)(\mathbf{f}_t - \bar{\mathbf{f}}_w)^T$$
3. **Ledoit-Wolf Analytical Shrinkage:**
   $$\boldsymbol{\Sigma}_{\text{LW}} = (1 - \hat{\delta}) \boldsymbol{\Sigma}_{\text{sample}} + \hat{\delta} \mathbf{F}$$
   where $\mathbf{F}$ is the structured target matrix (e.g., identity or equicorrelation) and $\hat{\delta} \in [0, 1]$ is the asymptotically optimal shrinkage intensity minimizing expected quadratic loss.

---

### 2.3 Spectral Eigenvalue Diagnostics & Higham (2002) Projection

A valid factor covariance or correlation matrix must be positive semi-definite (PSD):
$$\lambda_{\min}(\mathbf{A}) \ge -\epsilon$$

When non-synchronous factor pricing or finite sample noise induces negative eigenvalues, the engine applies Higham's (2002) spectral projection onto the PSD cone:
1. Spectral decomposition: $\mathbf{A} = \mathbf{V} \boldsymbol{\Lambda} \mathbf{V}^T$.
2. Clip eigenvalues: $\boldsymbol{\Lambda}^* = \text{diag}(\max(\lambda_i, \epsilon))$.
3. Reconstruct: $\mathbf{A}^* = \mathbf{V} \boldsymbol{\Lambda}^* \mathbf{V}^T$.
4. Re-symmetrize and scale to preserve trace/correlation diagonals.

---

### 2.4 Signed Delta vs. Absolute Strength Delta

Changes in correlation must never confound direction with strength:
- **Signed Change:** $\Delta \rho = \rho_t - \rho_{t-1}$.
- **Absolute Strength Change:** $\Delta |\rho| = |\rho_t| - |\rho_{t-1}|$.

*Example:* If correlation moves from $-0.80$ to $-0.30$:
- $\Delta \rho = -0.30 - (-0.80) = +0.50$ (positive directional movement).
- $\Delta |\rho| = 0.30 - 0.80 = -0.50$ (weakened linear relationship).

---

### 2.5 CUSUM Structural Break Monitoring

On historical rolling correlations $\rho_1, \dots, \rho_M$, the cumulative sum of recursive demeaned deviations is monitored:
$$S_k = \sum_{i=1}^k (\rho_i - \bar{\rho})$$
$$\text{CUSUM Statistic} = \frac{\max_k |S_k|}{\hat{\sigma}_{\rho} \sqrt{M}}$$
When the CUSUM statistic exceeds the 95% critical threshold ($1.36$) or the current correlation shifts by $> 0.50$ from baseline, a `POTENTIAL_STRUCTURAL_BREAK` alert is raised.

---

## 3. Database Schema Overview

The database models reside in `backend/app/modules/factor_risk/factor_correlation/models/__init__.py`:

1. `m08_07_correlation_configs`: Stores immutable estimation parameters and deterministic SHA-256 configuration hashes.
2. `m08_07_correlation_runs`: Execution logs containing window spans, observation counts, and spectral diagnostics.
3. `m08_07_correlation_pairs`: Pairwise factor statistics ($\rho$, $\text{Cov}$, $\sigma_A$, $\sigma_B$, $p$-value, Fisher $z$ CIs, undefined status).
4. `m08_07_correlation_matrix_snapshots`: Pinned $K \times K$ factor correlation matrices with factor ordering and spectral diagnostics.
5. `m08_07_covariance_configs`: Pinned parameters for factor covariance estimation.
6. `m08_07_covariance_snapshots`: Authoritative factor covariance snapshots ($\boldsymbol{\Sigma}_F$) consumed by M08.05.
7. `m08_07_rolling_factor_correlations`: Rolling time series points and historical summaries.
8. `m08_07_regime_alert_configs`: Configurable alerting thresholds and confirmation rules.
9. `m08_07_regime_alerts`: Detected relationship breaks, sign reversals, and co-movement alarms.
