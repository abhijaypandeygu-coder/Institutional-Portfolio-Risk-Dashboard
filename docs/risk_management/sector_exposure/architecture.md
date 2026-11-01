# Architecture Document: M06.03 — Sector Exposure

## 1. System Overview

The **M06.03 Sector Exposure Engine** aggregates portfolio market exposure according to authoritative sector and industry classification taxonomies (sourced strictly from M04.02), calculates sector and industry allocation weights across both NAV-based and Invested-Equity allocation bases, tracks unclassified securities without silent omissions, and computes active weights relative to institutional benchmarks.

```
+-----------------------------------------------------------------------------------------+
|                                M06.03 Sector Exposure Engine                             |
+-----------------------------------------------------------------------------------------+
|                                                                                         |
|  +--------------------+    +--------------------+    +-------------------------------+  |
|  | M05.02 / M05.03    |    | M04.02 Security    |    | M06.03 Benchmark              |  |
|  | Positions & Values |    | Classifications    |    | Sector Compositions           |  |
|  +---------+----------+    +---------+----------+    +---------------+---------------+  |
|            |                         |                               |                  |
|            +------------+------------+                               |                  |
|                         |                                            |                  |
|                         v                                            |                  |
|          +------------------------------+                            |                  |
|          | Exposure Aggregation Pipeline|                            |                  |
|          |  - Long, Short, Gross, Net   |                            |                  |
|          |  - Sector & Industry rollup  |                            |                  |
|          |  - Unclassified tracking     |                            |                  |
|          |  - Dual weight bases         |                            |                  |
|          +--------------+---------------+                            |                  |
|                         |                                            |                  |
|                         v                                            v                  |
|          +-----------------------------------------------------------+                  |
|          | Active Weight & Tracking Engine (Relative Exposure)       |                  |
|          |  - Active Weight = Port Weight - Benchmark Weight         |                  |
|          |  - Overweight / Underweight / Approx Neutral              |                  |
|          +------------------------------+----------------------------+                  |
|                                         |                                               |
|                                         v                                               |
|                       +-----------------------------------+                             |
|                       | Persisted Run & Response Schemas  |                             |
|                       +-----------------------------------+                             |
+-----------------------------------------------------------------------------------------+
```

## 2. Mathematical Formulations & Dual Weight Bases

For each sector or industry category $s$:

### 2.1 Exposure Measures
- **Long Exposure ($L_s$):**
  $$L_s = \sum_{i \in s, V_i > 0} V_i$$
- **Absolute Short Exposure ($S_s$):**
  $$S_s = \sum_{i \in s, V_i < 0} |V_i|$$
- **Gross Exposure ($G_s$):**
  $$G_s = L_s + S_s$$
- **Net Exposure ($N_s$):**
  $$N_s = L_s - S_s$$

### 2.2 Dual Weight Bases
Institutional risk reporting requires clarity between NAV leverage and relative allocation:
1. **NAV-Based Weights (`NAV_BASED`):**
   $$W_{\text{long}, s}^{\text{NAV}} = \frac{L_s}{\text{NAV}}, \quad W_{\text{gross}, s}^{\text{NAV}} = \frac{G_s}{\text{NAV}}, \quad W_{\text{net}, s}^{\text{NAV}} = \frac{N_s}{\text{NAV}}$$
2. **Invested-Equity Allocation Weights (`TOTAL_INVESTED_EQUITY`):**
   $$W_{\text{long}, s}^{\text{Alloc}} = \frac{L_s}{\sum_k L_k}, \quad W_{\text{gross}, s}^{\text{Alloc}} = \frac{G_s}{\sum_k G_k}$$

### 2.3 Relative Benchmark Analysis
- **Active Weight:**
  $$\Delta W_s = W_{\text{port}, s} - W_{\text{bm}, s}$$
- **Status Classification:**
  $$\text{Status} = \begin{cases}
  \text{OVERWEIGHT} & \text{if } \Delta W_s > \tau \\
  \text{UNDERWEIGHT} & \text{if } \Delta W_s < -\tau \\
  \text{APPROX\_NEUTRAL} & \text{if } |\Delta W_s| \le \tau
  \end{cases}$$
  (where default tolerance $\tau = 0.0001$, i.e., 1 bps).

## 3. Classification Resolution & Unclassified Handling

1. **Taxonomy Authority:** M06.03 consumes classification schemes and node assignments strictly from `M04.02` (`m04_instrument_classification_assignments`, `m04_classification_schemes`, `m04_classification_nodes`).
2. **Two-Tier Unclassified Tracking:**
   - **Completely Unclassified:** Instrument has no mapping in the target scheme $\rightarrow$ routed to synthetic Sector `"UNCLASSIFIED"`.
   - **Partially Classified:** Instrument mapped to Sector (e.g., Information Technology) but lacks Industry mapping $\rightarrow$ routed to synthetic Industry `"UNCLASSIFIED_INDUSTRY"` under parent sector.
3. **No Silent Drops:** All unclassified securities remain fully included in total long, short, gross, net exposures and denominators.

## 4. Multi-Portfolio Consolidation

Group exposure calculations invoke M05.08 `MultiPortfolioService.resolve_group_portfolios` to obtain unique portfolio constituents, aggregating holdings across all underlying portfolios and netting or summing consistently.
