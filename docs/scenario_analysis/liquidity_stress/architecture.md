# M10.06 — Liquidity Stress Testing Architecture

## 1. Executive Summary

**Module ID:** M10.06  
**Module Name:** Liquidity Stress Testing & Stressed Liquidation  
**Parent Module:** M10 — Scenario Analysis & Stress Testing  
**Component Type:** Quantitative Risk & Stressed Microstructure Engine  

The **Liquidity Stress Testing** module models the adverse consequences of severe market illiquidity occurring simultaneously with market-wide price declines. Rather than merely applying arbitrary percentage haircuts, the engine calculates the practical cost, execution capacity, time-to-liquidate, and residual portfolio exposure required to exit positions across configurable multi-session trading horizons.

---

## 2. Quantitative & Mathematical Framework

### 2.1 Spread Stress Engine
For a baseline quote $(B_0, A_0)$ with spread $S_0 = A_0 - B_0$ and midpoint $M_0 = \frac{A_0 + B_0}{2}$:
1. **Proportional Spread Widening:**
   $$S_{\text{stress}} = S_0 (1 + g_s)$$
2. **Multiplier Spread Widening:**
   $$S_{\text{stress}} = S_0 \cdot k_s$$
3. **Simultaneous Market-Price Crash:**
   $$M_{\text{stress}} = M_0 (1 + g_{\text{price}})$$
4. **Stressed Quotes & Tick-Size Rounding:**
   $$B_{\text{stress}} = M_{\text{stress}} - \frac{S_{\text{stress}}}{2}, \quad A_{\text{stress}} = B_{\text{stress}} + S_{\text{stress}}$$

### 2.2 Depth Deterioration & Order Book Walk
Simulates order-book depth depletion across L2 levels:
1. **Uniform & Level Deterioration:**
   $$Q_{i,\text{stress}} = Q_{i,0} \cdot k_i$$
2. **Book-Walk VWAP:**
   $$\text{VWAP}_{\text{stress}} = \frac{\sum_i q_i P_i}{\sum_i q_i}$$
3. **Adverse Concession Beyond Midpoint:**
   $$C_{\text{depth}} = Q (M_{\text{stress}} - \text{VWAP}_{\text{stress}}) \quad \text{for Long Liquidation (selling into bids)}$$

### 2.3 Volume Contraction & Executable Capacity
Given baseline interval volume $V_{0,t}$ and baseline participation cap $p_0$:
$$V_{\text{stress},t} = V_{0,t} (1 - g_v), \quad p_{\text{stress}} = p_0 (1 - g_p)$$
$$\text{Executable Capacity } C_t = V_{\text{stress},t} \cdot p_{\text{stress}}$$

### 2.4 Progressive Horizon Schedules & Residual Risk
Evaluates liquidation progress across standardized horizons (15m, 30m, 1h, 2h, 1d, 3d, 5d, 10d):
$$\text{Liquidation Ratio } (T) = \frac{Q_{\text{liquidated}}(T)}{Q_{\text{position}}}$$
$$\text{Residual Exposure } (T) = (Q_{\text{position}} - Q_{\text{liquidated}}(T)) \cdot M_{\text{stress}}$$

### 2.5 Stressed Execution Cost Breakdown (Without Double Counting)
$$C_{\text{total}} = C_{\text{spread}} + C_{\text{depth}} + C_{\text{impact}} + C_{\text{slippage}} + C_{\text{fees}}$$
- **Spread Crossing:** $Q \cdot \frac{S_{\text{stress}}}{2}$
- **Depth-Walk Concession:** Additional penalty beyond half-spread.
- **Square-Root Market Impact:** $I = Y \cdot \sigma_H \cdot \sqrt{\frac{Q}{V_H}} \cdot \text{Notional}$
- **Calibrated Stressed Slippage & Brokerage/Exchange Fees.**

---

## 3. Database Schema Overview

The module introduces 10 normalized tables:
- `m10_liquidity_stress_scenarios`: Master scenario definitions and versions.
- `m10_liquidity_stress_configurations`: Immutable versioned stress parameters (spread, depth, volume, participation, impact, horizon).
- `m10_liquidity_stress_instrument_overrides`: Instrument-specific overrides.
- `m10_liquidity_stress_runs`: Execution runs with aggregate portfolio notional, costs, duration, and residual exposure.
- `m10_liquidity_stress_market_snapshots`: Baseline vs. stressed quotes and volume.
- `m10_liquidity_stress_depth_levels`: L2 order book levels under stress.
- `m10_liquidity_stress_position_results`: Position-level capacities, costs, durations, and residual risk.
- `m10_liquidity_stress_horizon_results`: Time-bucketed progressive liquidation and completion status.
- `m10_liquidity_stress_cost_attributions`: Factorial cost component breakdown.
- `m10_liquidity_stress_audit_events`: Full reproducibility audit trails.
