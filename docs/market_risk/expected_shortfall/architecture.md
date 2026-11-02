# M07.03 — Expected Shortfall (ES) Architecture

## 1. Executive Summary

Module `M07.03 — Expected Shortfall (ES)` delivers an institutional conditional market-risk measurement engine for the Institutional Portfolio Risk Dashboard. Expected Shortfall estimates the average portfolio loss in the adverse tail of the loss distribution beyond a selected confidence quantile ($ES_c = \mathbb{E}[L \mid L \ge \text{VaR}_c]$), answering not merely what the loss threshold is, but how severe losses are when that threshold is breached.

The module supports three distinct calculation methodologies:
1. **Historical Portfolio-Returns ES**: Evaluates tail losses from empirical portfolio NAV returns.
2. **Historical Simulation ES**: Applies empirical historical risk-factor shocks to current portfolio holdings to evaluate hypothetical revaluation losses.
3. **Monte Carlo ES**: Evaluates tail losses from Cholesky-correlated stochastic simulations ($N \ge 10,000$ draws).

---

## 2. Core Mathematical Specifications

### 2.1 Loss Sign Convention & Quantile-Integral ES
All tail calculations adhere to the standard risk sign convention:
$$P\&L_t = V_t - V_0$$
$$L_t = -P\&L_t$$
For confidence level $c \in [0.80, 0.999]$, tail probability is $\alpha = 1 - c$.
The canonical quantile-integral Expected Shortfall is defined as:
$$\text{ES}_c = \frac{1}{1-c} \int_c^1 \text{VaR}_u \, du$$

### 2.2 Discrete Fractional Tail Weighting
In discrete empirical distributions with $n$ observations sorted in descending order of loss ($L_{(1)} \ge L_{(2)} \ge \dots \ge L_{(n)}$):
- Each observation has probability mass $p_s = \frac{1}{n}$.
- Total target tail mass is $\alpha = 1 - c$.
- Observations are included fully until accumulated mass plus $p_s > \alpha$.
- The boundary observation receives the remaining fractional probability mass:
  $$w_{\text{boundary}} = \alpha - \sum_{k=1}^{m} p_s$$
- Normalized weights $q_i = \frac{p_i}{\alpha}$ satisfy $\sum q_i = 1.0$.
$$\text{ES}_c = \sum_{i} q_i L_{(i)}$$

### 2.3 Tail Excess & Severity
$$\text{Tail Excess} = \text{ES}_c - \text{VaR}_c \ge 0$$
$$\text{Tail Excess}\% = \frac{\text{ES}_c - \text{VaR}_c}{\text{VaR}_c} \times 100\%$$

### 2.4 Scenario-Weighted Tail Risk Attribution
Constituent asset contributions are computed directly over the tail scenarios with exact weights $q_s$:
$$\text{ESContribution}_i = V_0 \times w_i \times \sum_{s \in \text{Tail}} q_s L_{i,s}$$
Reconciliation:
$$\sum_{i=1}^k \text{ESContribution}_i = \text{ES}_P$$

---

## 3. Database Schema

- `m07_expected_shortfall_configs`: Stores methodology, confidence level, horizon, lookback, and weighting policies.
- `m07_expected_shortfall_results`: Stores authoritative ES, VaR reference, Tail Excess, and observation counts.
- `m07_es_tail_observations`: Scenario records in the adverse tail with fractional boundary weights.
- `m07_es_diagnostics`: Statistical metrics (expected mass, effective sample size, dispersion, stability).
- `m07_es_contributions`: Constituent risk contributions across instruments and sectors.
- `m07_es_history`: Historical ES time-series for trend tracking.

---

## 4. API Endpoints

Mounted under `/api/v1/portfolios/{portfolio_id}/risk/expected-shortfall` and `/api/v1/risk/expected-shortfall`:
- `POST /calculate`: Run ES across Historical Portfolio Returns, Historical Simulation, or Monte Carlo.
- `GET /summary`: Summary metrics comparing VaR, ES, and Tail Excess.
- `GET /confidence-comparison`: Multi-confidence level sensitivity table (90% to 99.5%).
- `GET /methodology-comparison`: Side-by-side comparison across all 3 ES methodologies.
- `GET /history`: Historical ES trend time-series.
- `GET /{result_id}/tail-scenarios`: Granular scenario drill-down in the adverse tail.
- `GET /{result_id}/contributions`: Scenario-weighted constituent tail attributions.
- `GET /{result_id}/tail-diagnostics`: Tail sample size and stability diagnostics.
