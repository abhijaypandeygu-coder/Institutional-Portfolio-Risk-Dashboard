# M07.09 Risk Contribution Module Architecture

## 1. Executive Overview

The **M07.09 Risk Contribution** module provides an institutional-grade portfolio risk decomposition and attribution framework. Based on Euler's Homogeneous Function Theorem, the module mathematically attributes total portfolio variance ($\sigma_p^2$) and volatility ($\sigma_p$) down to individual security holdings, sectors, industries, geographies, and asset management sleeves.

Every calculated component risk contribution verifies exact additivity:
$$\sum_{i=1}^N \text{CRC}_i = \sigma_p, \quad \sum_{i=1}^N \text{CCV}_i = \sigma_p^2$$
Long-short and hedging instruments with negative covariance or short positioning naturally carry negative marginal and component risk contributions without artificial clamping.

---

## 2. Core Mathematical Architecture

### 2.1 Portfolio Risk Decomposition
Given portfolio weight vector $\mathbf{w} \in \mathbb{R}^N$ and covariance matrix $\Sigma \in \mathbb{R}^{N \times N}$:
- **Portfolio Variance:**
  $$\sigma_p^2 = \mathbf{w}^T \Sigma \mathbf{w}$$
- **Portfolio Volatility:**
  $$\sigma_p = \sqrt{\mathbf{w}^T \Sigma \mathbf{w}}$$

### 2.2 Marginal Risk Contribution (MRC)
- **Marginal Risk Contribution to Volatility:**
  $$\text{MRC}_i = \frac{\partial \sigma_p}{\partial w_i} = \frac{(\Sigma \mathbf{w})_i}{\sigma_p}$$
- **Marginal Contribution to Variance:**
  $$\text{MCV}_i = \frac{\partial \sigma_p^2}{\partial w_i} = 2 (\Sigma \mathbf{w})_i$$
- **Finite Difference Central Verification:**
  $$\text{MRC}_i^{\text{num}} = \frac{\sigma_p(\mathbf{w} + \epsilon \mathbf{e}_i) - \sigma_p(\mathbf{w} - \epsilon \mathbf{e}_i)}{2\epsilon}$$

### 2.3 Component Risk Contribution (CRC)
- **Component Risk Contribution to Volatility:**
  $$\text{CRC}_i = w_i \cdot \text{MRC}_i = w_i \frac{(\Sigma \mathbf{w})_i}{\sigma_p}$$
- **Component Contribution to Variance (CCV):**
  $$\text{CCV}_i = w_i (\Sigma \mathbf{w})_i$$
- **Percentage Risk Share:**
  $$\text{CRC}\%_i = \frac{\text{CRC}_i}{\sigma_p} \times 100$$

### 2.4 Correlation with Portfolio
$$\rho(R_i, R_p) = \frac{(\Sigma \mathbf{w})_i}{\sigma_i \sigma_p} = \frac{\text{MRC}_i}{\sigma_i}$$

### 2.5 Group Attribution
For mutually exclusive partition $\{G_k\}$:
$$\text{CRC}_{G_k} = \sum_{i \in G_k} \text{CRC}_i, \quad \sum_{k} \text{CRC}_{G_k} = \sigma_p$$

### 2.6 What-if Weight Perturbation
- **Exact Volatility Impact:**
  $$\Delta \sigma_p^{\text{exact}} = \sigma_p(\mathbf{w} + \Delta \mathbf{w}) - \sigma_p(\mathbf{w})$$
- **First-Order Linear Taylor Approximation:**
  $$\Delta \sigma_p^{\text{Taylor}} = \mathbf{MRC}^T \Delta \mathbf{w}$$
- **Linearization Discrepancy Error:**
  $$\text{Error} = |\Delta \sigma_p^{\text{exact}} - \Delta \sigma_p^{\text{Taylor}}|$$

---

## 3. Database Schema

- `m07_09_risk_contribution_runs`: Calculation execution header storing portfolio totals, variance, volatility, annualized metrics, and Euler reconciliation residuals.
- `m07_09_holding_risk_contributions`: Granular asset-level metrics including weights, MRC, MCV, CRC, CCV, percentage risk share, and correlation with the portfolio.
- `m07_09_group_risk_contributions`: Aggregated group attributions across Sector, Industry, Geography, and Strategy Sleeves.
