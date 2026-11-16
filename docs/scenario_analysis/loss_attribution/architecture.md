# M10.09 Stress Loss Attribution — Architecture

## 1. Overview
**M10.09 — Stress Loss Attribution** is the analytical attribution engine within the **Scenario Analysis & Stress Testing** pillar of the Institutional Portfolio Risk Dashboard.

Its primary function is to decompose portfolio stressed P&L ($\Delta V = V_s - V_0$) into interpretable structural components:
1. **Position Contribution:** Exact price, FX, and liquidity impact across individual long/short holdings.
2. **Sector & Industry Aggregation:** Hierarchical aggregation into sector/industry exposures with unclassified tracking.
3. **Economic Factor Attribution (View B):** Systematic risk factor shock decomposition ($\sum \beta_k f_k$).
4. **Nonlinear Interaction Effects:** Multi-shock cross-terms ($I_{AB} = Y(A,B) - Y(A,0) - Y(0,B) + Y(0,0)$).
5. **Loss Concentration:** Herfindahl-Hirschman Index (HHI) and Effective Contributor Count ($N_{\text{eff}}$).
6. **Reconciliation Residuals:** Transparent reporting of unexplained variances ($\epsilon = \Delta V - \sum C_i$).

---

## 2. Mathematical Framework

### 2.1 Position Valuation & Exact Decomposition
Let:
- $q_i$ = signed position quantity (positive for long, negative for short).
- $P_{i,0}, P_{i,s}$ = baseline and stressed prices.
- $FX_{i,0}, FX_{i,s}$ = baseline and stressed FX rates into portfolio base currency.

Market values:
$$MV_{i,0} = q_i P_{i,0} FX_{i,0}, \quad MV_{i,s} = q_i P_{i,s} FX_{i,s}$$

Exact price and FX decomposition:
$$\Delta MV_i = q_i (P_{i,s} - P_{i,0}) FX_{i,0} + q_i P_{i,s} (FX_{i,s} - FX_{i,0})$$

Net Position P&L and Positive Loss Convention:
$$PnL_i = \Delta MV_i - \text{LiquidityCost}_i - \text{Fees}_i$$
$$L_i = -PnL_i \quad \text{(Positive Loss Convention)}$$

### 2.2 Sector and Industry Aggregation
For group $G \in \{\text{Sector}_k, \text{Industry}_j\}$:
$$PnL_G = \sum_{i \in G} PnL_i, \quad L_G = \sum_{i \in G} L_i$$
Holdings without classification mapping are assigned to `UNCLASSIFIED` rather than dropped.

### 2.3 Economic Factor Attribution (View B)
Given factor sensitivity exposures $\boldsymbol{\beta}_p$ and stress factor shocks $\mathbf{f}$:
$$PnL_{\text{factor}} = V_0 \sum_{k=1}^K \beta_{p,k} f_k$$
Economic Factor Attribution is presented as an alternative explanatory model view and is never naively summed with position P&L.

### 2.4 Controlled Combined-Shock Interaction Effects
When simultaneous stress assumptions (e.g. broad market crash and volatility expansion) interact nonlinearly:
$$I_{AB} = Y(A,B) - Y(A,0) - Y(0,B) + Y(0,0)$$
where $Y(A,B)$ is the output under combined shocks, and $Y(A,0), Y(0,B)$ are isolated shocks.

### 2.5 Loss Concentration Metrics
For positive loss contributors ($L_i > 0$), normalized weights are:
$$w_i = \frac{L_i}{\sum_{j: L_j > 0} L_j}$$
- **Loss HHI:**
  $$HHI = \sum_{i: L_i > 0} w_i^2$$
- **Effective Contributor Count:**
  $$N_{\text{effective}} = \frac{1}{HHI}$$

### 2.6 Financial Reconciliation Residuals
$$\text{Residual} = \Delta V_{\text{authoritative}} - \sum_{i=1}^N PnL_i$$
Result is reconciled if:
$$|\text{Residual}| \le \max(\epsilon_{\text{abs}}, \epsilon_{\text{rel}} |\Delta V|)$$
where $\epsilon_{\text{abs}} = 0.01, \epsilon_{\text{rel}} = 0.0001$.

---

## 3. Architecture & Data Flow

```
                      +---------------------------------------+
                      |        Attribution API Router         |
                      |   /api/v1/stress-loss-attributions    |
                      +-------------------+-------------------+
                                          |
                                          v
                      +---------------------------------------+
                      |      StressLossAttributionService     |
                      +-------------------+-------------------+
                                          |
                      +-------------------+-------------------+
                      |                                       |
                      v                                       v
    +----------------------------------+   +----------------------------------+
    |      ScenarioEngineAdapter       |   |          AttributionMath         |
    | - Authoritative PnL & Baseline   |   | - Position Price/FX Decomp       |
    | - Upstream Scenario Output       |   | - Sector & Industry Aggregation  |
    +----------------------------------+   | - Factor Attribution (View B)    |
                      |                    | - Nonlinear Interaction Effects  |
                      |                    | - Loss HHI & N_effective         |
                      |                    | - Residual & Reconciliation Check|
                      |                    +----------------------------------+
                      v                                       |
    +---------------------------------------------------------+
    |               StressLossAttributionRepository           |
    | - StressLossAttribution & Run Metadata                  |
    | - StressPositionContribution & Sector/Industry Records  |
    | - StressFactorContribution & Interaction Records        |
    | - Immutable Audit Log                                   |
    +---------------------------------------------------------+
```
