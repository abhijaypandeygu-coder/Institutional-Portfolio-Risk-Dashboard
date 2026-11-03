# M09.06 — Liquidity Stress Testing & Stressed Execution Cost Estimation Architecture

## 1. Executive Summary

**M09.06 Liquidity Stress Testing & Stressed Execution Cost Estimation** provides institutional scenario-analysis and stress capabilities within the **Institutional Portfolio Risk Dashboard**.

It simulates deterioration in market liquidity through configurable transformations of:
1. Bid-ask spreads (widening multipliers, percentage shocks, additive basis-point shocks).
2. Displayed and modeled order-book depth (uniform, side-specific, level-specific reductions).
3. Traded market volume (session and time-of-day interval contraction).
4. Execution participation capacity (fixed, capped, or schedule-based).

It recalculates:
- Synthetic stressed quote levels around preserved midpoints with exchange tick-size enforcement.
- Static depth-walk execution concession over synthetic depth ladders.
- Liquidation duration across discrete interval volume profiles and session transitions.
- Residual unliquidated quantities and incomplete liquidation statuses.
- Stressed total execution costs (Spread Crossing + Depth Walk Concession + Market Impact + Explicit Fees + Opportunity Cost) without double counting.
- Reverse stress testing search to identify critical shock thresholds that breach cost or duration constraints.
- Portfolio-level concurrent liquidation scheduling and critical-path duration.

---

## 2. Core Mathematical Formulations

### 2.1 Spread Widening & Synthetic Quotes
$$S_{\text{stress}} = m_s \cdot S_0 \quad \text{or} \quad S_0 \cdot (1 + r_s) \quad \text{or} \quad S_0 + \frac{\Delta_{\text{bps}}}{10,000} \cdot M_0$$

Synthetic quotes around preserved midpoint $M_0 = \frac{\text{Bid}_0 + \text{Ask}_0}{2}$:
$$\text{Bid}_{\text{stress}} = \text{RoundDown}_{\text{tick}}\left(M_0 - \frac{S_{\text{stress}}}{2}\right)$$
$$\text{Ask}_{\text{stress}} = \text{RoundUp}_{\text{tick}}\left(M_0 + \frac{S_{\text{stress}}}{2}\right)$$

### 2.2 Depth Reduction
$$Q_{i, \text{stress}} = Q_{i, 0} \cdot (1 - r_d), \quad 0 \le r_d \le 1$$

### 2.3 Volume Contraction & Participation Capacity
$$V_{i, \text{stress}} = V_{i, 0} \cdot (1 - r_v)$$
$$\text{Capacity}_i = p \cdot V_{i, \text{stress}}$$
$$\text{Capacity}_{1:N} = \sum_{i=1}^N p \cdot V_{i, \text{stress}}$$
$$\text{Fillable}_N = \min(Q, \text{Capacity}_{1:N}), \quad Q_{\text{residual}} = Q - \text{Fillable}_N$$

### 2.4 Liquidation Duration
Estimated completion interval $n$ is the first interval where:
$$\text{Capacity}_{1:n} \ge Q_{\text{target}}$$
If $\text{Capacity}_{1:N} < Q_{\text{target}}$ at horizon $N$, status is `LIQUIDATION_NOT_COMPLETED`.

### 2.5 Reconciled Stressed Execution Cost
$$\text{Total Cost} \equiv \text{SpreadCost} + \text{DepthConcession} + \text{MarketImpact} + \text{Fees} + \text{OpportunityCost}$$
- Spread Cost: $Q_{\text{filled}} \cdot \frac{S_{\text{stress}}}{2} \cdot M$
- Depth Concession: $\sum_{j=1}^k Q_j \cdot |P_j - P_{\text{touch}}|$
- Cost Escalation: $\text{Cost}_{\text{stress}} - \text{Cost}_{\text{baseline}}$
- Cost Escalation (%): $\frac{\text{Cost}_{\text{stress}} - \text{Cost}_{\text{baseline}}}{\text{Cost}_{\text{baseline}}} \times 100$

### 2.6 Reverse Stress Testing
Searches for parameter limits:
- Critical Volume Contraction:
  $$r_{v, \text{crit}} = 1 - \frac{Q}{N_{\max} \cdot p \cdot V_0}$$
- Critical Spread Multiplier:
  $$m_{s, \text{crit}} = \frac{2 \cdot \text{Cost}_{\max}}{Q \cdot S_0}$$

---

## 3. Component Architecture

- `calculations/stress_math.py`: Pure high-precision mathematical engine using `Decimal` arithmetic.
- `models/stress_models.py`: SQLAlchemy 2.x declarative models (`LiquidityStressConfig`, `LiquidityStressScenarioRun`, `LiquidityStressMonitoringSnapshot`).
- `schemas/stress_schemas.py`: Pydantic v2 schemas.
- `repositories/stress_repository.py`: Async database access patterns.
- `services/stress_service.py`: Service orchestrating baseline retrieval, synthetic book generation, liquidation schedules, and reverse stress search.
- `router.py`: REST endpoints mounted under `/api/v1/market-microstructure/liquidity-stress`.

