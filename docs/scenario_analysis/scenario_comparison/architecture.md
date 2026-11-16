# M10.08 Scenario Comparison — Architecture

## 1. Overview
**M10.08 — Scenario Comparison** is an analytical orchestration layer within the **Scenario Analysis & Stress Testing** pillar of the Institutional Portfolio Risk Dashboard.

It evaluates multiple scenario results across historical shocks (M10.01), hypothetical stresses (M10.02), broad market crashes (M10.03), sector shocks (M10.04), correlation stresses (M10.05), liquidity stress tests (M10.06), and stochastic Monte Carlo distributions (M10.07) against a common baseline portfolio.

---

## 2. Mathematical Framework

### 2.1 Baseline Performance Comparison
Let $V_0$ represent the authoritative baseline portfolio NAV and $V_s$ denote stressed NAV under scenario $s$:
- **Absolute P&L:**
  $$P_s = V_s - V_0$$
- **Percentage Return:**
  $$R_s = \frac{V_s - V_0}{V_0} \times 100$$
- **Loss Amount (Institutional Positive Loss Convention):**
  $$L_s = V_0 - V_s$$
- **Percentage Loss:**
  $$L_{s,\%} = \frac{V_0 - V_s}{V_0} \times 100$$
*(A negative loss indicates a net portfolio gain).*

### 2.2 Metric Normalization Methods
Normalizes metric $X = [x_1, \dots, x_N]$ to scale $Z \in [0, 1]$:
1. **Min-Max Normalization:**
   $$Z_{s} = \frac{x_s - \min(X)}{\max(X) - \min(X)}$$
2. **Z-Score with Logistic Sigmoidal Projection:**
   $$Z_s = \frac{1}{1 + \exp\left(-\frac{x_s - \mu}{\sigma}\right)}$$
3. **Robust Median/MAD Normalization:**
   $$Z_s = \frac{1}{1 + \exp\left(-\frac{x_s - \text{median}(X)}{1.4826 \cdot \text{MAD}(X)}\right)}$$
4. **Percentile / Ordinal Ranking:**
   $$Z_s = \frac{\text{rank}(x_s) - 1}{N - 1}$$

If ranking direction is `ASCENDING` (e.g. lowest stressed NAV or volatility), inverted scores are applied: $Z_s \leftarrow 1 - Z_s$.

### 2.3 Scenario Ranking Engine
- **Single Metric Ranking:** Direct ordering by selected metric ($L_s$, $V_s$, VaR, ES, Max Drawdown, or Liquidity Cost).
- **Weighted Multi-Metric Composite Score:**
  $$\text{Score}_s = \sum_{j=1}^M w_j Z_{s,j} \quad \text{where } \sum_{j=1}^M w_j = 1$$
- **Deterministic Tie-Breaking:** Preserves identical ranks for equivalent metrics and assigns stable display orders.

### 2.4 Assumption Sensitivity Comparison
- **Configuration Differences:** Evaluates absolute $\Delta \theta_k = \theta_{k,B} - \theta_{k,A}$ and relative elasticity $\frac{\Delta \theta_k}{|\theta_{k,A}|}$.
- **Finite Differences:**
  $$\text{Sensitivity}_k = \frac{\Delta Y}{\Delta \theta_k} \approx \frac{Y(\theta_k + \delta) - Y(\theta_k - \delta)}{2\delta}$$

### 2.5 Difference Attribution & Residual Tracking
For scenarios $A$ and $B$, headline difference $\Delta P\&L = P\&L_B - P\&L_A$ decomposes across holdings $i$:
$$\Delta P\&L_i = P\&L_{i,B} - P\&L_{i,A}$$
$$\Delta P\&L = \sum_{i=1}^N \Delta P\&L_i + \epsilon$$
where $\epsilon$ is the tracked reconciliation residual.

---

## 3. Architecture & Data Flow

```
                      +---------------------------------------+
                      |         Comparison API Router         |
                      |      /api/v1/scenario-comparisons     |
                      +-------------------+-------------------+
                                          |
                                          v
                      +---------------------------------------+
                      |       ScenarioComparisonService       |
                      +-------------------+-------------------+
                                          |
                      +-------------------+-------------------+
                      |                                       |
                      v                                       v
    +----------------------------------+   +----------------------------------+
    |      ScenarioEngineAdapter       |   |          ComparisonMath          |
    | - M10.01 Historical              |   | - Baseline Performance           |
    | - M10.02 Hypothetical            |   | - Metric Normalization           |
    | - M10.03 Market Crash            |   | - Scenario Ranking Engine        |
    | - M10.04 Sector Shock            |   | - Configuration Diff             |
    | - M10.05 Correlation Shock       |   | - Pairwise Attribution & Residual|
    | - M10.06 Liquidity Stress        |   +----------------------------------+
    | - M10.07 Monte Carlo             |                      |
    +----------------------------------+                      v
                      |                    +----------------------------------+
                      +------------------->|   ScenarioComparisonRepository   |
                                           | - Immutable Runs & Audit Logs    |
                                           +----------------------------------+
```
