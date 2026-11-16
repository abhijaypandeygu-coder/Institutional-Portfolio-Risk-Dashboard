# M10.07 Monte Carlo Scenarios — Architecture

## 1. Overview
**M10.07 — Monte Carlo Scenarios** is an institutional-grade stochastic simulation engine integrated into the Scenario Analysis & Stress Testing pillar of the Institutional Portfolio Risk Dashboard.

It models the forward joint probability distribution of multi-asset portfolio returns over flexible horizons (1 to 252 trading days) using thousands or millions of correlated stochastic paths.

---

## 2. Mathematical Framework

### 2.1 Geometric Brownian Motion Multi-Period Dynamics
Equity instrument price paths follow the discrete geometric update:
$$S_{i, t+\Delta t} = S_{i,t} \exp\left[ \left(\mu_i - \frac{1}{2}\sigma_i^2\right)\Delta t + \sigma_i \sqrt{\Delta t} Z_{i,t} \right]$$
where:
- $\mu_i$ is annual expected return / drift (supports historical arithmetic mean, geometric drift, or institutional short-horizon zero-drift assumption).
- $\sigma_i$ is annual volatility, scaleable by stress multipliers ($k \cdot \sigma_0$).
- $\Delta t = \frac{\tau}{252}$ where $\tau$ is time step in days.
- $Z_t \in \mathbb{R}^N$ is a correlated standardized innovation vector.

This lognormal specification guarantees strictly positive asset prices for all equity positions ($S_{i,t} > 0, \forall t$).

### 2.2 Correlation Validation, Positive Semi-Definiteness (PSD), and Cholesky Factorization
Given empirical cross-asset correlation matrix $R$:
1. Check symmetry: $R = \frac{1}{2}(R + R^T)$.
2. Unit diagonal: $\text{diag}(R) = 1$.
3. Bounds: $R_{ij} \in [-1, 1]$.
4. Positive Semi-Definiteness (PSD):
   If $\min(\lambda_i) < \epsilon$:
   - **Eigenvalue Clipping / Spectral Projection:**
     $$R_{\text{repaired}} = \sum_{\lambda_i > \epsilon} \lambda_i v_i v_i^T$$
     Rescaled via diagonal normalization $D^{-1/2} R_{\text{repaired}} D^{-1/2}$ to preserve unit diagonal.
   - **Shrinkage:**
     $$R_{\text{shrunk}} = (1 - \alpha) R + \alpha I$$
5. Cholesky Factorization:
   $$R = L L^T$$

### 2.3 Vectorized Stochastic Sampling Engines
Standardized uncorrelated random variates $U \sim \mathcal{N}(0, I_N)$ are correlated via lower triangular matrix $L$:
- **Multivariate Normal:**
  $$Z = U L^T$$
- **Multivariate Student-$t$ with Joint Tail Dependence:**
  $$Z_t = \sqrt{\frac{\nu - 2}{W}} (U L^T) \quad \text{where } W \sim \chi^2(\nu)$$
  Scalar $W$ is drawn per path and shared across all portfolio assets, capturing true systemic tail co-dependence and joint crash probability.
- **Cross-Sectionally Aligned Empirical Bootstrap:**
  Resamples multi-asset vector time-indices with replacement from historical returns, preserving observed empirical copula structure without parametric assumptions.

### 2.4 Portfolio Valuation & Risk Outcome Calculation
Let $Q_i$ denote signed position quantities (positive for long, negative for short), $S_{i,0}$ denote baseline mark prices, and $S_{i,H}^{(p)}$ denote simulated prices on path $p$ at horizon $H$:
$$V_p(0) = \sum_{i=1}^N Q_i S_{i,0} + \text{Cash}$$
$$V_p(H) = \sum_{i=1}^N Q_i S_{i,H}^{(p)} + \text{Cash}$$
$$\text{P\&L}_p = V_p(H) - V_p(0)$$

### 2.5 Loss-Positive VaR and Expected Shortfall Convention
Defining simulated loss $L_p = -\text{P\&L}_p$:
$$\text{VaR}_\alpha = Q_\alpha(L)$$
$$\text{ES}_\alpha = \mathbb{E}\left[ L \mid L \ge \text{VaR}_\alpha \right] = \frac{1}{|K_\alpha|} \sum_{p \in K_\alpha} L_p$$
where $K_\alpha = \{p \mid L_p \ge \text{VaR}_\alpha\}$.

---

## 3. Architecture & Data Flow

```
                      +---------------------------------------+
                      |       FastAPI Scenario Router         |
                      |  /api/v1/risk/scenarios/monte-carlo   |
                      +-------------------+-------------------+
                                          |
                                          v
                      +---------------------------------------+
                      |          MonteCarloService            |
                      | - Resolves Portfolio Holdings         |
                      | - Matrix Validation & Cholesky        |
                      | - Seed PRNG (PCG64)                   |
                      +-------------------+-------------------+
                                          |
                      +-------------------+-------------------+
                      |                                       |
                      v                                       v
    +----------------------------------+   +----------------------------------+
    |         MonteCarloMath           |   |       MonteCarloRepository       |
    | - Correlated Innovation Gen      |   | - MonteCarloScenario             |
    | - Chunked GBM Simulation         |   | - MonteCarloSimulationRun        |
    | - Signed Portfolio Valuation     |   | - MonteCarloSimulationSummary    |
    | - Moments, Quantiles, Loss Prob  |   | - MonteCarloRiskMetric           |
    | - Loss-Positive VaR & CVaR       |   | - MonteCarloInstrumentResult     |
    +----------------------------------+   +----------------------------------+
```

---

## 4. Reproducibility & Governance
- Each simulation run accepts an optional explicit `random_seed` or generates an entropy-seeded value recorded in `m10_monte_carlo_runs.random_seed`.
- Uses NumPy's `PCG64` generator (`np.random.default_rng(seed)`), avoiding mutable global state.
- Computes SHA-256 hash over input parameters (`input_parameters_hash`) for full regulatory and model auditability.
