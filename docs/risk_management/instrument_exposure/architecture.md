# Architecture Document: M06.04 — Instrument Exposure

## 1. System Overview

The **M06.04 Instrument Exposure Engine** provides institutional-grade single-name instrument exposure visibility across portfolios and consolidated portfolio groups. It calculates signed and absolute market values, dual portfolio weight bases (NAV-based weights and Gross Contribution weights), deterministic rankings across four dimensions, automated dominance threshold detection, and historical snapshot comparisons.

```
+-----------------------------------------------------------------------------------------+
|                              M06.04 Instrument Exposure Engine                           |
+-----------------------------------------------------------------------------------------+
|                                                                                         |
|  +--------------------+    +--------------------+    +-------------------------------+  |
|  | M05.02 Positions   |    | M05.03 Valuations  |    | M04.01 Canonical              |  |
|  | (Quantities, Books)|    | (Mark Prices, MVs) |    | Instrument Master             |  |
|  +---------+----------+    +---------+----------+    +---------------+---------------+  |
|            |                         |                               |                  |
|            +------------+------------+-------------------------------+                  |
|                         |                                                               |
|                         v                                                               |
|          +----------------------------------------------+                               |
|          | Exposure Aggregation Pipeline                |                               |
|          |  - Long ($L_i$), Short ($S_i$)               |                               |
|          |  - Gross ($G_i = L_i + S_i$)                 |                               |
|          |  - Net ($N_i = L_i - S_i$)                   |                               |
|          |  - Dual weight calculation (NAV vs Gross)    |                               |
|          +----------------------+-----------------------+                               |
|                                 |                                                       |
|             +-------------------+-------------------+                                   |
|             |                                       |                                   |
|             v                                       v                                   |
|  +------------------------+             +------------------------+                      |
|  | Rankings Engine        |             | Dominance Detector     |                      |
|  | (LONG, SHORT, GROSS,   |             | (NORMAL, ELEVATED,     |                      |
|  |  ABSOLUTE_NET)         |             |  HIGH, CRITICAL)       |                      |
|  +------------------------+             +------------------------+                      |
|             |                                       |                                   |
|             +-------------------+-------------------+                                   |
|                                 |                                                       |
|                                 v                                                       |
|          +----------------------------------------------+                               |
|          | Historical Snapshot Comparator (M05.07)      |                               |
|          |  - Delta L, S, G, N                          |                               |
|          |  - Percentage change & Weight change pp      |                               |
|          |  - Lifecycle indicators                      |                               |
|          +----------------------------------------------+                               |
+-----------------------------------------------------------------------------------------+
```

## 2. Mathematical Formulations

For each canonical instrument $i$:

### 2.1 Exposure Measures
- **Long Exposure ($L_i$):**
  $$L_i = \sum_{p \in \text{Long}_i} MV_p, \quad L_i \ge 0$$
- **Absolute Short Exposure ($S_i$):**
  $$S_i = \sum_{p \in \text{Short}_i} |MV_p|, \quad S_i \ge 0$$
- **Gross Market Value ($G_i$):**
  $$G_i = L_i + S_i$$
- **Signed Net Market Value ($N_i$):**
  $$N_i = L_i - S_i$$

### 2.2 Portfolio-Level Reconciliation
$$\sum_i L_i = L_P, \quad \sum_i S_i = S_P, \quad \sum_i G_i = G_P, \quad \sum_i N_i = N_P$$
Reconciles exactly with M06.01 Gross Exposure and M06.02 Net Exposure totals.

### 2.3 Dual Portfolio Weights
1. **NAV-Based Weights:**
   $$W_i^{\text{Long,NAV}} = \frac{L_i}{\text{NAV}} \times 100, \quad W_i^{\text{Short,NAV}} = \frac{S_i}{\text{NAV}} \times 100, \quad W_i^{\text{Gross,NAV}} = \frac{G_i}{\text{NAV}} \times 100, \quad W_i^{\text{Net,NAV}} = \frac{N_i}{\text{NAV}} \times 100$$
2. **Gross-Exposure Contribution Weights:**
   $$W_i^{\text{GrossContribution}} = \frac{G_i}{G_P} \times 100$$
   $$\sum_i W_i^{\text{GrossContribution}} = 100\%$$

## 3. Dominance Detection Logic

Configurable thresholds flag dominant single-name concentrations without arbitrary hardcoding:
- Gross NAV weight $\ge 20\% \implies \text{CRITICAL}$
- Gross NAV weight $\ge 10\% \implies \text{ELEVATED}$
- Long NAV weight $\ge 8\% \implies \text{ELEVATED}$
- Short NAV weight $\ge 5\% \implies \text{ELEVATED}$

## 4. Historical Snapshot Comparisons (M05.07)

Compares current and prior snapshots bitemporally:
- $\Delta G_i = G_{i,current} - G_{i,prior}$
- $\%\Delta G_i = \frac{G_{i,current} - G_{i,prior}}{G_{i,prior}} \times 100$
- Derived lifecycle indicators: `NEW_POSITION`, `CLOSED_POSITION`, `INCREASED_EXPOSURE`, `REDUCED_EXPOSURE`, `DIRECTION_CHANGED`, `UNCHANGED_EXPOSURE`.
