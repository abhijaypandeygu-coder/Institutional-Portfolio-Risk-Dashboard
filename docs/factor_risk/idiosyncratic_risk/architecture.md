# M08.06 Idiosyncratic Risk Architecture & Quantitative Specifications

## 1. Overview & Objective

**M08.06 — Idiosyncratic Risk** provides production-grade quantitative risk analytics measuring security-specific return variability not explained by systematic factors in the Institutional Portfolio Risk Dashboard.

Given the standard factor model specification:
$$R_{i,t} = \alpha_i + \boldsymbol{\beta}_i^T \mathbf{F}_t + \epsilon_{i,t}$$
$$\text{with } \mathbb{E}[\epsilon_{i,t}] = 0, \quad \text{Cov}(\mathbf{F}_t, \epsilon_{i,t}) = \mathbf{0}$$

This module delivers:
1. **Residual Volatility Estimation:** Unbiased sample, population, exponentially weighted (EWMA), and robust normal-consistent MAD scale ($1.4826 \times \text{median}(|\epsilon - \text{median}(\epsilon)|)$).
2. **Residual Covariance Matrix:** Spectral decomposition, condition numbers, positive semi-definite (PSD) enforcement, and diagonal baseline comparison.
3. **Euler Risk Attribution:** Exact holding-level marginal and component variance and volatility allocations, strictly preserving negative contributions for residual risk diversifiers.
4. **Diversification Decomposition:** Contrast against diagonal-only benchmarks, cross-security covariance effect, and absolute contribution Herfindahl-Hirschman Index (HHI).
5. **Issuer Consolidation:** Matrix consolidation $M_{norm} \boldsymbol{\Sigma}_\epsilon M_{norm}^T$ across authoritative parent issuers to avoid misrepresenting concentrated legal-entity risk as diversified holdings.
6. **Econometric Diagnostics:** Jarque-Bera normality tests, outlier identification ($|Z| > 3.0$), lag-1 autocorrelation, Ljung-Box test, ARCH-LM heteroskedasticity, and CUSUM structural break evaluation.

---

## 2. Core Mathematical Formulations

### 2.1 Residual Volatility & Scale
- **Sample Variance:**
  $$\sigma_{\epsilon,i}^2 = \frac{1}{T - 1} \sum_{t=1}^T (\epsilon_{i,t} - \bar{\epsilon}_i)^2$$
- **Annualized Volatility:**
  $$\sigma_{\epsilon,i}^{ann} = \sqrt{\sigma_{\epsilon,i}^2 \times A}$$
- **Robust Scale (MAD):**
  $$\sigma_{MAD} = 1.4826 \times \text{median}(|\epsilon_t - \text{median}(\epsilon)|)$$

### 2.2 Portfolio Idiosyncratic Risk & Euler Allocation
For portfolio weights $\mathbf{w}$ and residual covariance matrix $\boldsymbol{\Sigma}_\epsilon$:
- **Portfolio Residual Variance:**
  $$\sigma_{\epsilon,p}^2 = \mathbf{w}^T \boldsymbol{\Sigma}_\epsilon \mathbf{w}$$
- **Euler Variance Allocation:**
  $$RC_i^{var} = w_i (\boldsymbol{\Sigma}_\epsilon \mathbf{w})_i, \quad \sum_{i=1}^N RC_i^{var} = \sigma_{\epsilon,p}^2$$
- **Euler Volatility Allocation:**
  $$RC_i^{vol} = \frac{w_i (\boldsymbol{\Sigma}_\epsilon \mathbf{w})_i}{\sigma_{\epsilon,p}}, \quad \sum_{i=1}^N RC_i^{vol} = \sigma_{\epsilon,p}$$

### 2.3 Diversification View & Concentration
- **Diagonal Baseline Variance:**
  $$\sigma_{\epsilon,diag}^2 = \sum_{i=1}^N w_i^2 \sigma_{\epsilon,i}^2$$
- **Cross-Security Covariance Effect:**
  $$\Delta \sigma_{cov}^2 = \sigma_{\epsilon,p}^2 - \sigma_{\epsilon,diag}^2$$
- **Absolute Contribution HHI:**
  $$p_i = \frac{|RC_i^{var}|}{\sum_j |RC_j^{var}|}, \quad \text{HHI} = \sum_{i=1}^N p_i^2, \quad N_{eff} = \frac{1}{\text{HHI}}$$

---

## 3. Database Schema Overview

The engine persists all calculations across 8 dedicated tables:
1. `m08_06_residual_configs`: Immutable configuration parameters and hash integrity check.
2. `m08_06_residual_volatility_runs`: Instrument-level residual variance and robust scale estimates.
3. `m08_06_residual_covariance_snapshots`: Cached residual covariance and correlation matrices.
4. `m08_06_portfolio_idiosyncratic_runs`: Portfolio execution run records with diversification metrics.
5. `m08_06_security_risk_contributions`: Holding-level Euler contributions and diversifier flags.
6. `m08_06_issuer_risk_contributions`: Consolidated issuer-level risk allocations.
7. `m08_06_residual_diagnostic_runs`: Econometric misspecification checks, skewness, kurtosis, tests.
8. `m08_06_residual_outliers`: Granular records of point-in-time residual outliers.
