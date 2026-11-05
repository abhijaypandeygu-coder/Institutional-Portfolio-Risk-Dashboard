# M10.03 — Market Crash Simulation Architecture

## 1. Executive Summary

The **M10.03 Market Crash Simulation** module implements an institutional-grade stress testing framework inside the **Institutional Portfolio Risk Dashboard**. It translates broad equity-market index shocks (across Indian and US markets) into instrument-level stress responses and reconciled portfolio P&L.

Rather than assuming all instruments decline uniformly by a single percentage, the engine maps securities to appropriate benchmarks, accounts for linear market sensitivity (beta), incorporates nonlinear downside behavior (downside beta, piecewise thresholds, stress amplification, quadratic response, and sector overlays), supports multi-currency FX conversion, and reconciles position-level profit/loss to total portfolio NAV.

---

## 2. Core Methodologies & Mathematical Foundations

### 2.1 Index Shock Engine
Supports 4 distinct market shock specifications:
1. **Percentage Shock:** $R_{m,s} = \delta_m, \quad I_{m,s} = I_{m,0} \cdot (1 + \delta_m)$
2. **Target Index Level:** $R_{m,s} = (I_{m,\text{target}} / I_{m,0}) - 1$
3. **Absolute Point Change:** $I_{m,s} = I_{m,0} + \Delta I_m, \quad R_{m,s} = (I_{m,s} / I_{m,0}) - 1$
4. **Multi-Stage Compounding:** $R_{m,\text{cumulative}} = \prod_{t=1}^T (1 + R_{m,t}) - 1$

All index shocks enforce $R_{m,s} \ge -1.0$ (cannot decline below -100%).

---

### 2.2 Linear Beta & Multi-Benchmark Response
- **Single-Index Beta:** $R_{i,\text{linear}} = \beta_{i,m} \cdot R_{m,s}$
- **Multi-Benchmark Sensitivity:** $R_{i,\text{linear}} = \sum_{m=1}^M \beta_{i,m} \cdot R_{m,s}$

---

### 2.3 Nonlinear Downside Engine
Captures structural breakdown and asymmetric sensitivity during crises:
- **Downside Beta:** Uses $\beta_i^-$ (estimated conditional on $R_m < c$):
  $$R_{i,s} = \beta_i^- \cdot R_{m,s} = \beta_i \cdot R_{m,s} + (\beta_i^- - \beta_i) \cdot R_{m,s}$$
- **Piecewise Beta:** Normal beta above threshold $c$, downside beta below $c$:
  $$R_{i,s} = \beta_{i,\text{normal}} R_{m,s} + (\beta_{i,\text{downside}} - \beta_{i,\text{normal}})(R_{m,s} - c) \quad \text{for } R_{m,s} < c$$
- **Stress Amplification:** Adverse penalty beyond decline threshold $c$:
  $$d_m = \max(0, -R_{m,s} - c), \quad A_i = -\lambda_i \cdot (d_m)^p, \quad R_{i,s} = \beta_i R_{m,s} + A_i$$
- **Quadratic Response:** $R_{i,s} = \beta_i R_{m,s} + \gamma_i R_{m,s}^2$
- **User-Defined & Sector Adjustments:** Additive overlays $A_{i,\text{sector}} + A_{i,\text{user}}$.

Boundary condition: $R_{i,s} \ge -1.0$ enforced before repricing.

---

### 2.4 Multi-Currency FX Conversion
Converts local equity returns into portfolio base currency without double counting:
$$(1 + R_{\text{base}}) = (1 + R_{\text{local}}) \cdot (1 + R_{\text{FX}})$$
$$R_{\text{base}} = (1 + R_{\text{local}})(1 + R_{\text{FX}}) - 1$$

---

### 2.5 Position Revaluation & Portfolio Aggregation
- **Baseline Market Value:** $\text{MV}_{i,0} = q_i \cdot P_{i,0}$
- **Scenario Price:** $P_{i,s} = P_{i,0} \cdot (1 + R_{i,\text{base}})$
- **Scenario Market Value:** $\text{MV}_{i,s} = q_i \cdot P_{i,s}$
- **Signed Position PnL:** $\text{PnL}_i = \text{MV}_{i,s} - \text{MV}_{i,0} = q_i \cdot P_{i,0} \cdot R_{i,\text{base}}$
  - For long positions ($q_i > 0$): negative return produces a loss.
  - For short positions ($q_i < 0$): negative return produces a gain.
- **Positive Loss Representation:** $\text{Loss}_i = \max(0, -\text{PnL}_i)$
- **Portfolio NAV & Return:**
  $$\text{PnL}_{\text{portfolio}} = \sum_{i=1}^N \text{PnL}_i, \quad \text{NAV}_s = \text{NAV}_0 + \text{PnL}_{\text{portfolio}}, \quad R_{\text{portfolio}} = \frac{\text{PnL}_{\text{portfolio}}}{\text{NAV}_0}$$
  $$\text{Loss}_{\text{portfolio}} = \max(0, -\text{PnL}_{\text{portfolio}})$$
- **Return Contribution Reconciliation:**
  $$C_i = \frac{\text{PnL}_i}{\text{NAV}_0}, \quad \sum_{i=1}^N C_i \equiv R_{\text{portfolio}}$$

---

### 2.6 Exposure Coverage & Attribution Decomposition
- **Exposure Coverage:**
  $$\text{Coverage}_{\text{mapped}} = \frac{\sum_{i \in \text{Mapped}} |\text{MV}_{i,0}|}{\sum_{i \in \text{Included}} |\text{MV}_{i,0}|}, \quad \text{Coverage}_{\beta} = \frac{\sum_{i \in \text{BetaValid}} |\text{MV}_{i,0}|}{\sum_{i \in \text{Included}} |\text{MV}_{i,0}|}$$
- **Linear vs Nonlinear Decomposition:**
  $$\text{PnL}_{i,\text{linear}} = \text{MV}_{i,0} \cdot R_{i,\text{linear}}, \quad \text{PnL}_{i,\text{nonlinear}} = \text{MV}_{i,0} \cdot (R_{i,\text{final}} - R_{i,\text{linear}})$$
  $$\text{PnL}_{i,\text{linear}} + \text{PnL}_{i,\text{nonlinear}} \equiv \text{PnL}_i$$

---

## 3. Database Architecture

12 normalized relational models under SQLAlchemy 2.x:
1. `MarketCrashScenario`: Scenario metadata, author, ownership, and current version.
2. `MarketCrashScenarioVersion`: Immutable snapshot of configuration with SHA-256 fingerprint.
3. `MarketCrashBenchmarkShock`: Shock definitions (NIFTY 50, SPX, NASDAQ, Russell).
4. `MarketCrashMappingRule`: Benchmark assignment rules by market, sector, or override.
5. `MarketCrashMappingResult`: Per-run resolved instrument mappings.
6. `MarketCrashSensitivitySnapshot`: Applied betas, downside betas, and observation metadata.
7. `MarketCrashNonlinearParameter`: Piecewise thresholds, stress multipliers, and exponents.
8. `MarketCrashSimulationRun`: Execution master record with NAV, PnL, loss, and coverage metrics.
9. `MarketCrashPositionResult`: Detailed position revaluation outputs.
10. `MarketCrashSummaryResult`: Aggregated portfolio exposure and position statistics.
11. `MarketCrashAttributionResult`: Loss attribution by Sector, Benchmark, and Linear/Nonlinear impact.
12. `MarketCrashWarning` & `MarketCrashAuditLog`: Diagnostic auditing and lifecycle history.
