# M09.04 — Market Impact Architecture & Mathematical Formulation

## 1. Executive Summary

**M09.04 — Market Impact** is an institutional-grade pre-trade analytics module within the **Institutional Portfolio Risk Dashboard**. The module estimates how hypothetical buy or sell orders of arbitrary size affect execution price and monetary implementation costs under varying market conditions, liquidity horizons, and participation constraints.

The engine delivers:
1. **Static Displayed-Book Depth Walk:** Level-by-level consumption of visible limit order book depth (asks for buys, bids for sells), VWAP average execution price, marginal execution price, visible fill percentage, and residual unfilled quantity.
2. **Cost & Shortfall Decomposition:** Separates spread crossing (half-spread), additional depth-walk concession, and explicit transaction costs without double counting.
3. **Order-Size Sensitivity & Marginal Cost:** Evaluates costs across size increments and calculates marginal unit execution costs:
   $$\text{MarginalCost}(Q_1, Q_2) = \frac{\text{Cost}(Q_2) - \text{Cost}(Q_1)}{Q_2 - Q_1}$$
4. **Participation Constraints & Horizon Slicing:** Enforces maximum volume participation rates ($Q_{\text{fillable}} = \min(Q, PR_{\text{max}} \cdot V_H)$) and computes uniform or volume-proportional execution schedules.
5. **Empirical Impact Models:**
   - **Square-Root Law:** $I_{\text{bps}} = Y \cdot \sigma_H \cdot \sqrt{\frac{Q}{V_H}} \times 10,000$.
   - **Log-Linear Empirical Regression:** Models impact with participation, spread, inverse depth, volatility, and regime multipliers.
   - **Kyle-Style OFI Response:** $\Delta P = \lambda \cdot \text{OFI}$.
6. **Uncertainty & Backtest Diagnostics:** Provides prediction standard errors, confidence intervals, and model validation metrics (MAE, RMSE, Mean Bias, Interval Coverage).

---

## 2. Mathematical Formulations

### 2.1 Static Displayed-Book Depth Walk
For a proposed buy quantity $Q$ against ask levels $\{(P_{a, i}, Q_{a, i})\}_{i=1}^M$:
$$q_i = \min(Q_{\text{remaining}, i}, Q_{a, i})$$
$$V_{\text{gross}} = \sum_{i=1}^K P_{a, i} \cdot q_i \cdot M$$
$$P_{\text{avg}} = \frac{V_{\text{gross}}}{Q_{\text{filled}} \cdot M}$$
$$\text{Cost}_{\text{monetary}} = V_{\text{gross}} - (Q_{\text{filled}} \cdot P_{\text{ref}} \cdot M)$$
$$\text{Cost}_{\text{bps}} = \frac{\text{Cost}_{\text{monetary}}}{Q_{\text{filled}} \cdot P_{\text{ref}} \cdot M} \times 10,000$$

Where $P_{\text{ref}}$ is the arrival midpoint benchmark.

### 2.2 Cost Decomposition
$$\text{SpreadCrossing}_{\text{bps}} = \frac{P_{1} - P_{\text{ref}}}{P_{\text{ref}}} \times 10,000$$
$$\text{AdditionalDepth}_{\text{bps}} = \frac{P_{\text{avg}} - P_{1}}{P_{\text{ref}}} \times 10,000$$
$$\text{TotalExecutionCost}_{\text{bps}} = \text{SpreadCrossing}_{\text{bps}} + \text{AdditionalDepth}_{\text{bps}}$$

### 2.3 Square-Root Impact Law
$$I_{\text{bps}} = Y \cdot \sigma_H \cdot \sqrt{\frac{Q}{V_H}} \times 10,000$$
Where $Y \approx 0.50$ is a calibrated dimensionless parameter, $\sigma_H$ is return volatility over horizon $H$, and $V_H$ is expected market volume.

### 2.4 Empirical Regression Impact
$$I_{\text{bps}} = \Big(\beta_0 + \beta_1 \ln(1 + PR) + \beta_2 \text{Spread}_{\text{bps}} + \beta_3 \text{Depth}^{-1} + \beta_4 \sigma\Big) \times \text{RegimeMultiplier}$$
Standard temporary (70%) and permanent (30%) heuristic splits are generated alongside prediction standard error bands ($I \pm 1.96 \cdot SE$).

---

## 3. Database Schema

The module implements 7 relational tables:
1. `m09_04_market_impact_configs`: Versioned calculation policies, benchmark definitions, and default participation caps.
2. `m09_04_market_impact_scenarios`: Order scenario specifications (side, size, reference price, horizon, regime).
3. `m09_04_market_impact_depth_walks`: Static displayed-book depth walk results (average price, marginal price, fill %, cost in monetary and bps).
4. `m09_04_market_impact_depth_walk_levels`: Granular level-by-level consumption audit records.
5. `m09_04_market_impact_estimates`: Horizon-based modeled impact estimates (Square-Root, Regression, Kyle OFI).
6. `m09_04_market_impact_model_configs`: Versioned empirical model specifications and calibrated parameters.
7. `m09_04_market_impact_model_validation_runs`: Out-of-sample backtest diagnostics (MAE, RMSE, MBE, coverage %).

