# M10.01 Historical Scenarios Architecture

## 1. Overview & Objective

**M10.01 — Historical Scenarios** is an institutional-grade portfolio shock and stress testing module within the **Institutional Portfolio Risk Dashboard**.

It replays market conditions from selected historical episodes (e.g. 2008 Global Financial Crisis, 2020 COVID-19 Crash, 2022 Global Rate Shock) against either:
1. **A current portfolio:** Applying historical shocks to current positions and valuation.
2. **A historical portfolio:** Replaying against point-in-time holdings from M05.07 portfolio history.

The module preserves data provenance, prevents look-ahead bias, enforces strict reconciliation, and distinguishes directly observed asset returns from modeled factor or proxy shocks.

---

## 2. Quantitative Methodology

### 2.1 Return Compounding & Currency Adjustment
- **Simple Return:**
  $$R_t = \frac{P_t}{P_{t-1}} - 1$$
- **Compounded Cumulative Event Return:**
  $$R_{\text{event}} = \prod_{t=1}^{T} (1 + R_t) - 1$$
  *(Never calculated using arithmetic summation).*
- **Currency Adjustment:**
  $$(1 + R_{\text{base}}) = (1 + R_{\text{local}}) \times (1 + R_{\text{FX}})$$
  $$R_{\text{base}} = (1 + R_{\text{local}}) \times (1 + R_{\text{FX}}) - 1$$

### 2.2 Factor Shock Model
Where direct asset returns are unavailable, the M08 factor model estimates asset returns:
$$R_i^{\text{estimated}} = \sum_{k=1}^K \beta_{i,k} F_k + \epsilon_i$$
Where $\beta_{i,k}$ is the instrument sensitivity to factor $k$, and $F_k$ is the observed cumulative historical return of factor $k$.

### 2.3 Position Revaluation & Portfolio Aggregation
- **Signed Quantity:** Long positions $q_i > 0$, short positions $q_i < 0$.
- **Baseline Market Value:** $MV_{i,0} = q_i \times P_{i,0}$
- **Scenario Market Value:** $MV_{i,\text{scenario}} = q_i \times P_{i,0} \times (1 + R_i)$
- **Position PnL:** $\text{PnL}_i = MV_{i,\text{scenario}} - MV_{i,0} = q_i \times P_{i,0} \times R_i$
- **Portfolio PnL:** $\text{PnL}_{\text{portfolio}} = \sum_i \text{PnL}_i$
- **Scenario NAV:** $\text{NAV}_{\text{scenario}} = \text{NAV}_0 + \text{PnL}_{\text{portfolio}}$
- **Return Contribution:** $C_i = w_i \times R_i = \frac{\text{PnL}_i}{\text{NAV}_0}$
- **Reconciliation Constraint:** $\sum_i C_i = R_{\text{portfolio}}$

### 2.4 Coverage Diagnostics
Based on absolute market values so long and short exposures do not offset:
$$\text{Coverage}_{\text{direct}} = \frac{\sum_{i \in \text{Direct}} |MV_i|}{\sum_{i \in \text{Included}} |MV_i|}$$

---

## 3. Database Schema

M10.01 defines 9 core relational tables in PostgreSQL:
1. `historical_scenario_events`: Master catalog of historical episodes.
2. `historical_scenario_event_versions`: Immutable version definitions.
3. `historical_scenario_observations`: Normalized asset and factor historical returns.
4. `historical_shock_mapping_rules`: Mapping hierarchy and priority rules.
5. `historical_scenario_replay_runs`: Replay execution summaries and reconciliation.
6. `historical_shock_mapping_results`: Per-position mapping lineage and rationale.
7. `historical_scenario_replay_positions`: Position-level revaluation and contributions.
8. `historical_scenario_replay_warnings`: Audit warnings and limitations.
9. `historical_scenario_replay_paths`: Daily valuation path points across the event.
