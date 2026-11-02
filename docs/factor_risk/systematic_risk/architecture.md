# M08.05 — Systematic Risk Architecture Documentation

## 1. Executive Summary & Purpose

**M08.05 — Systematic Risk** provides the quantitative foundation for calculating how much security and portfolio return variability is explained by systematic factor movements within the Institutional Portfolio Risk Dashboard.

The module implements five primary risk management capabilities:
1. **Common-Factor Covariance Engine:** Resolves aligned historical factor returns from M08.02, estimates the factor covariance matrix ($\boldsymbol{\Sigma}_F$) using Sample, Exponentially Weighted (EWMA), and Ledoit-Wolf Shrinkage methods, and performs spectral PSD and condition number validation.
2. **Instrument Common-Factor Variance & Volatility:** Calculates $\sigma_{sys,i}^2 = \boldsymbol{\beta}_i^T \boldsymbol{\Sigma}_F \boldsymbol{\beta}_i$ and distinguishes systematic volatility from residual/idiosyncratic risk.
3. **Portfolio Systematic Risk & Cross-Security Covariance:** Aggregates portfolio signed exposures ($w_i > 0$ for long, $w_i < 0$ for short) and verifies the dual mathematical equivalence:
   $$\sigma_{sys,p}^2 = \boldsymbol{\beta}_p^T \boldsymbol{\Sigma}_F \boldsymbol{\beta}_p = \sum_{i=1}^N \sum_{j=1}^N w_i w_j (\boldsymbol{\beta}_i^T \boldsymbol{\Sigma}_F \boldsymbol{\beta}_j)$$
4. **Factor Scenario Sensitivity Shocks:** Simulates single-factor, multi-factor, standardized ($z \cdot \sigma$), and conditional covariance stress regimes, reporting both percentage return impacts ($\Delta R_p^{sys} = \boldsymbol{\beta}_p^T \Delta \mathbf{F}$) and monetary dollar impacts ($\Delta V_p^{sys} = NAV_p \cdot \Delta R_p^{sys}$).
5. **Model Coverage Engine:** Evaluates holding-level and portfolio-level factor coverage using absolute weights ($\sum |w_i|$), ensuring missing loadings are never silently treated as zero or allowed to inflate coverage via short-position netting.

---

## 2. Mathematical Foundation

### 2.1 Common-Factor Variance
For an asset or portfolio with factor loadings $\boldsymbol{\beta} \in \mathbb{R}^K$ and factor return covariance matrix $\boldsymbol{\Sigma}_F \in \mathbb{R}^{K \times K}$:

$$\sigma_{sys}^2 = \boldsymbol{\beta}^T \boldsymbol{\Sigma}_F \boldsymbol{\beta}$$
$$\sigma_{sys} = \sqrt{\sigma_{sys}^2}$$

### 2.2 Dual Cross-Security Equivalence Identity
For a portfolio with signed weights $\mathbf{w} \in \mathbb{R}^N$ and security loadings matrix $\mathbf{B} \in \mathbb{R}^{N \times K}$ where $\boldsymbol{\beta}_p = \mathbf{B}^T \mathbf{w}$:

$$\sigma_{sys,p}^2 = (\mathbf{B}^T \mathbf{w})^T \boldsymbol{\Sigma}_F (\mathbf{B}^T \mathbf{w}) = \mathbf{w}^T (\mathbf{B} \boldsymbol{\Sigma}_F \mathbf{B}^T) \mathbf{w} = \sum_{i=1}^N \sum_{j=1}^N w_i w_j (\boldsymbol{\beta}_i^T \boldsymbol{\Sigma}_F \boldsymbol{\beta}_j)$$

The term $\mathbf{B} \boldsymbol{\Sigma}_F \mathbf{B}^T$ represents the $N \times N$ cross-security systematic covariance matrix.

### 2.3 Linear Factor Shock Simulation
Given an explicit factor shock vector $\Delta \mathbf{F} = [\Delta F_1, \dots, \Delta F_K]^T$:
$$\Delta R_p^{sys} = \sum_{k=1}^K \beta_{p,k} \Delta F_k$$
$$\Delta V_p^{sys} = NAV_p \cdot \Delta R_p^{sys}$$

### 2.4 Model Coverage Formulation
$$W_{total} = \sum_{i=1}^N |w_i|, \quad W_{covered} = \sum_{i \in \text{Covered}} |w_i|$$
$$\text{Coverage Percentage} = \frac{W_{covered}}{W_{total}} \times 100$$

---

## 3. Database Architecture

The module introduces 10 SQLAlchemy 2.x declarative tables:
- `m08_05_risk_configs`: Versioned systematic risk settings and SHA-256 configuration hashes.
- `m08_05_factor_covariance_snapshots`: Pinned factor covariance matrices with eigenvalue spectra and condition numbers.
- `m08_05_systematic_risk_runs`: Audit header for executed risk calculations.
- `m08_05_instrument_systematic_risk`: Security-level systematic variance, volatility, and residual stats.
- `m08_05_portfolio_systematic_risk`: Portfolio-level systematic risk and cross-security reconciliation metrics.
- `m08_05_factor_scenario_configs`: Scenario shock definitions.
- `m08_05_factor_scenario_shocks`: Factor-by-factor shock values.
- `m08_05_factor_scenario_runs`: Simulation results.
- `m08_05_factor_scenario_components`: Factor-level dollar and return contributions.
- `m08_05_model_coverage_records`: Point-in-time holding coverage diagnostics.
