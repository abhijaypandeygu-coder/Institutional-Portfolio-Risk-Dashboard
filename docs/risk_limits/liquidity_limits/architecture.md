# M11.04 — Liquidity Limits Architecture Document

## 1. Executive Overview

**M11.04 — Liquidity Limits** establishes institutional-grade quantitative liquidity boundaries at both position and portfolio levels within the **Institutional Portfolio Risk Dashboard**.

The module enforces liquidity risk limits to prevent positions from becoming illiquid or uneconomic to exit during normal or stressed market conditions:
1. **Minimum Liquidity:** Enforces thresholds for liquidity score (M09.03), order-book depth (M09.02), ADV, and turnover.
2. **Maximum Liquidation Cost:** Caps estimated exit costs in absolute currency amounts, basis points of notional, or percentage of portfolio NAV.
3. **Maximum Liquidation Horizon:** Limits estimated trading sessions required to liquidate positions under configured participation rates.
4. **Stressed Liquidity:** Evaluates positions under severe market shocks (volume contraction, depth reduction, spread widening, and participation adjustments).
5. **Pre-Trade Feasibility:** Evaluates proposed orders and post-trade capacity headroom for M11.07 Pre-Trade Limits.

---

## 2. Mathematical Specifications

### 2.1 Side-Aware Order Book Depth
- For **long positions being liquidated**, executable liquidity is sell-side / bid depth.
- For **short positions being covered**, executable liquidity is buy-side / ask depth.
$$Breach_D = \max(0, D_{\min} - D_{actual})$$
$$U_D = \frac{D_{\min}}{D_{actual}} \times 100$$

### 2.2 Average Daily Volume (ADV) & Turnover (ADTV)
$$ADV = \frac{1}{N} \sum_{d=1}^N Volume_d, \quad ADTV = \frac{1}{N} \sum_{d=1}^N Turnover_d$$

### 2.3 Liquidation Horizon & Participation Constraints
$$DailyCapacity = ADV \times p$$
$$LiquidationHorizon_{days} = \frac{|Q|}{DailyCapacity} = \frac{|Q|}{ADV \times p}$$
- If $ADV$ is missing or zero, the horizon status is `UNAVAILABLE` or `INVALID` (fail-safe; never silently converted to zero).

### 2.4 Liquidation Cost Metrics
$$Cost_{bps} = \frac{C_{total}}{Notional_{liquidated}} \times 10,000, \quad Cost_{\%NAV} = \frac{C_{total,base}}{NAV_p} \times 100$$
$$Breach_C = \max(0, C_{actual} - C_{\max})$$
$$U_C = \frac{C_{actual}}{C_{\max}} \times 100$$

### 2.5 Multiplicative Stress Scenario Transformations
$$ADV_{stress} = ADV_{base} \times (1 - v)$$
$$Depth_{stress} = Depth_{base} \times (1 - d)$$
$$Spread_{stress} = Spread_{base} \times (1 + s)$$
$$p_{stress} = p_{base} \times (1 - r)$$
$$H_{stress} = \frac{|Q|}{ADV_{stress} \times p_{stress}}$$

---

## 3. Database Architecture

Implemented via SQLAlchemy 2.0 async declarative models with exact `Numeric(18, 4)` precision:

1. `m11_liquidity_limit_configurations`: Stores limit thresholds, participation rate, metric, and stress settings.
2. `m11_liquidity_limit_profiles`: Reusable profile bundles for mandates and portfolio groups.
3. `m11_liquidity_limit_assignments`: Target assignments linking profiles to portfolios.
4. `m11_liquidity_limit_evaluations`: Evaluation run header storing NAV, aggregate costs, max horizon, and breach counts.
5. `m11_position_liquidity_evaluation_results`: Granular per-position, per-limit evaluation outputs.
6. `m11_liquidity_limit_breach_events`: Immutable breach logs feeding M11.08.
7. `m11_liquidity_data_exceptions`: Exception records for missing/stale ADV, order-book depth, or cost models.
8. `m11_liquidity_limit_audit_logs`: Append-only governance and configuration audit trail.

---

## 4. Integration Boundaries

- **Upstream Modules:**
  - **M09.01 Bid-Ask Spread:** Spread inputs and widening factors.
  - **M09.02 Order Book Depth:** Side-aware displayed and cumulative depth.
  - **M09.03 Liquidity Estimation:** Canonical liquidity score and regime.
  - **M09.04 Market Impact & M09.05 Slippage:** All-in estimated liquidation costs.
  - **M09.06 Liquidity Stress Testing:** Multi-dimensional stress parameters.
  - **M09.07 Position Liquidation:** Canonical execution schedule.
  - **M05.02 Positions & M05.03 Valuation:** Authoritative position quantities and market values.
- **Downstream Modules:**
  - **M11.07 Pre-Trade Risk Evaluation:** Proposed order validation and post-trade capacity headroom.
  - **M11.08 Breach Management & Escalation:** Immutable breach events with severity and root-cause taxonomy.
