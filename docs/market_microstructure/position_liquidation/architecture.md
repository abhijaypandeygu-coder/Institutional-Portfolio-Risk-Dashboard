# M09.07 Position Liquidation Architecture

## Overview
**M09.07 Position Liquidation** is an institutional execution planning and risk estimation engine. It evaluates how long and at what transaction cost an existing position (long equity or short equity) can be reduced or closed under specified market participation rates and execution horizons.

It operates strictly as an analytical decision-support layer:
- It **never** mutates the authoritative position ledger (M05.02).
- It **never** places, routes, or modifies live orders.
- It decomposes full exit into standard and custom partial targets (10%, 25%, 50%, 75%, 90%, 100%) reporting both cumulative and incremental duration and costs.

```
+------------------------------------------------------------------------------------------------+
|                                    M09.07 Position Liquidation                                |
+------------------------------------------------------------------------------------------------+
                                              |
    +-----------------------------------------+-----------------------------------------+
    |                                         |                                         |
    v                                         v                                         v
+-----------------------+         +-----------------------+         +-----------------------+
|  Position Retrieval   |         |  Reduction Targets    |         | Execution Schedules   |
|  - Signed position    |         |  - T1 (10%)           |         |  - Uniform            |
|  - Long -> SELL       |         |  - T2 (25%)           |         |  - Volume Proport.    |
|  - Short -> BUY       |         |  - T3-T6 (50%-100%)   |         |  - Participation Cap  |
+-----------------------+         +-----------------------+         +-----------------------+
            |                                 |                                 |
            +---------------------------------+---------------------------------+
                                              |
                                              v
+-----------------------------------------------------------------------------------------------+
|                            Multi-Component Cost Reconciliation                                |
|  - Spread Crossing: Q_filled * (Spread / 2)                                                   |
|  - Depth Walk Price Concession: Q_filled * P_ref * (5 bps * p)                                |
|  - Market Impact: Q_filled * P_ref * (10 bps * sqrt(p))                                       |
|  - Slippage: Q_filled * P_ref * (3 bps * p)                                                   |
|  - Explicit Fees: Q_filled * P_ref * (fee_bps / 10000)                                         |
|  - Opportunity Cost: Q_residual * P_ref * (opp_cost_bps / 10000)                              |
+-----------------------------------------------------------------------------------------------+
                                              |
                                              v
+-----------------------------------------------------------------------------------------------+
|                                Portfolio-Level Aggregation                                    |
|  - Concurrent: Critical Path = max(T_i)                                                       |
|  - Sequential: Sum of Durations = sum(T_i)                                                    |
|  - Separated Long Liquidation & Short Covering Costs                                          |
+-----------------------------------------------------------------------------------------------+
```

## Architectural Principles
1. **Side-Aware Execution Direction:**
   - Long positions ($Q > 0$) require selling ($Side = \text{SELL}$) and consume bid-side liquidity.
   - Short positions ($Q < 0$) require buying to cover ($Side = \text{BUY}$) and consume ask-side liquidity.
2. **Monotonic Target Decomposition:**
   - Evaluates cumulative target percentages $r_k$ ($0 < r_k \le 1.0$) and incremental tranches $Q_k - Q_{k-1}$.
   - Incremental costs and durations represent the marginal cost of extending liquidation to the next checkpoint.
3. **Execution Capacity & Volume Boundaries:**
   - Volume-based capacity: $C_i = p \cdot V_i$.
   - Never reuses static displayed depth as continuously replenished liquidity.
4. **Reconciled Cost Accounting:**
   - Ensures zero double-counting across spread crossing, depth walk concessions, market impact, slippage, explicit brokerage/fees, and unliquidated opportunity costs.
5. **Portfolio Aggregation:**
   - Concurrent portfolio liquidation is bounded by the critical path ($\max(T_i)$), preventing erroneous summation of overlapping multi-position liquidations.
