# M07.02 — Value at Risk (VaR) Engine Architecture

## 1. Executive Summary

Module `M07.02 — Value at Risk (VaR)` delivers an institutional market-risk measurement engine for the Institutional Portfolio Risk Dashboard. The system models potential downside loss thresholds over configurable holding horizons and confidence intervals, implementing three distinct methodologies:
1. **Historical VaR**: Empirical quantile analysis of portfolio returns and historical simulation.
2. **Parametric VaR**: Variance-covariance analytical model under normal and Student's t distributions, featuring exact Euler component risk attribution.
3. **Monte Carlo VaR**: Correlated stochastic simulation utilizing Cholesky decomposition of covariance matrices, fixed random seeds for reproducibility, and full empirical loss quantiles.

---

## 2. Core Mathematical Specifications

### 2.1 Sign Convention and Loss Definition
All VaR metrics strictly adhere to the non-negative loss threshold convention:
$$L = -R$$
Where $R$ is portfolio return and $L$ is portfolio loss.
$$\text{VaR}_c(L) = Q_c(L) = \inf \{ l \in \mathbb{R} : P(L \le l) \ge c \}$$
For confidence level $c \in [0.90, 0.999]$:
- Percentage VaR ($\text{VaR}\%$): Expressed as a non-negative percentage of valuation base: $\text{VaR}\% = \max(0, -Q_{1-c}(R)) \times 100\%$.
- Monetary VaR ($\text{VaR}_{\$}$): Expressed in reporting currency: $\text{VaR}_{\$} = V_0 \times \text{VaR}_{\text{return}}$, where $V_0$ is the authoritative valuation base (e.g. Portfolio NAV).

### 2.2 Time Horizon Scaling
For $H$-day holding horizons under the square-root-of-time rule (assuming i.i.d. zero-mean returns):
$$\sigma_H = \sigma_1 \times \sqrt{H}$$
$$\text{VaR}_H = \text{VaR}_1 \times \sqrt{H}$$

### 2.3 Parametric Euler Component Risk Attribution
Given portfolio return variance $\sigma_p^2 = w^T \Sigma w$, marginal contribution to volatility is:
$$\frac{\partial \sigma_p}{\partial w_i} = \frac{(\Sigma w)_i}{\sigma_p}$$
Marginal VaR:
$$\text{MarginalVaR}_i = \frac{(\Sigma w)_i}{\sigma_p} z_c \sqrt{H}$$
Component VaR:
$$\text{ComponentVaR}_i = w_i \times \text{MarginalVaR}_i$$
Under Euler's theorem for homogeneous functions of degree 1:
$$\sum_{i=1}^k \text{ComponentVaR}_i = \text{VaR}_p$$
This ensures exact additivity across long, short, and cash holdings.

### 2.4 Monte Carlo Cholesky Simulation
For constituent instruments with covariance matrix $\Sigma$:
1. Perform Cholesky factorisation: $\Sigma = L L^T$.
2. Generate independent standard normal random draws: $Z \sim \mathcal{N}(0, I_k)$.
3. Compute correlated return vectors: $R = L Z$.
4. Calculate simulated portfolio returns: $R_p = w^T R$.
5. Empirical quantile extraction at $(1-c)$ over $N$ simulations.

---

## 3. Database Schema

Tables deployed under `backend/app/modules/market_risk/value_at_risk/models/`:
- `m07_var_configs`: Model configurations specifying methodology, confidence level, horizon, lookback period, simulation count, random seed, and valuation base type.
- `m07_var_results`: Authoritative VaR execution results recording signed loss quantiles, percentage VaR, monetary VaR, status, and observation counts.
- `m07_var_risk_contributions`: Granular constituent risk contributions storing instrument weight, marginal VaR, component VaR amount, and percentage of total VaR.
- `m07_var_historical_scenarios`: Historical simulation scenario dates, simulated portfolio returns, and simulated P&L impact.
- `m07_var_diagnostics`: Execution audit logs recording covariance condition numbers, Cholesky convergence, degrees of freedom, and data coverage.

---

## 4. API Endpoints

Mounted under `/api/v1/portfolios/{portfolio_id}/risk/var` and `/api/v1/risk/var`:
- `POST /calculate`: Run ad-hoc or configured VaR calculation across Historical, Parametric, or Monte Carlo methods.
- `GET /latest`: Retrieve latest authoritative VaR metrics for a portfolio.
- `GET /model-comparison`: Execute and compare Historical, Parametric, and Monte Carlo models side-by-side with discrepancy analysis.
- `GET /risk-contributions`: Retrieve Euler component risk contributions and marginal risk metrics.
- `GET /historical-trend`: Retrieve time series of historical VaR results.
- `POST /configs`: Create or register reusable model configurations.

