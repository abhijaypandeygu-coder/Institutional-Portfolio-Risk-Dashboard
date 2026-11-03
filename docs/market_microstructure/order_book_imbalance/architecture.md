# M09.08 Order Book Imbalance Architecture

## Overview
**M09.08 — Order Book Imbalance** provides institutional-grade market microstructure analytics measuring the distribution and persistence of displayed bid and ask resting liquidity across order-book levels.

It quantifies quote queue pressure, notional pressure, distance-weighted imbalance, microprice deviations, and state persistence/reversals.

```
+--------------------------------------------------------------------------------------------------+
|                                  M09.08 Order Book Imbalance                                     |
+--------------------------------------------------------------------------------------------------+
                                                 |
         +---------------------------------------+---------------------------------------+
         |                                       |                                       |
         v                                       v                                       v
+--------------------------+         +--------------------------+         +--------------------------+
| Best & Multi-Level Ratio |         |   Weighting Methodologies|         |  Microprice & Deviation  |
| - I_1 = (B1-A1)/(B1+A1)  |         | - Equal Weighting        |         | - Queue-weighted price   |
| - I_N = (Bn-An)/(Bn+An)  |         | - Exponential Level Decay|         | - Midpoint deviation bps |
| - Bid/Ask Shares         |         | - Distance-Decay Weight  |         | - Resting asymmetry      |
+--------------------------+         +--------------------------+         +--------------------------+
         |                                       |                                       |
         +---------------------------------------+---------------------------------------+
                                                 |
                                                 v
+--------------------------------------------------------------------------------------------------+
|                                    Temporal Analytics Engine                                     |
|  - Persistence Tracking: Bid-Dominant (I >= theta), Ask-Dominant (I <= -theta), Neutral          |
|  - Run Duration Analytics: Current run, maximum run, average run duration                       |
|  - Reversal Detection: Hysteresis-governed transitions (entry_theta, exit_theta)                 |
|  - Regime Classification: STRONG_BID, MODERATE_BID, NEUTRAL, MODERATE_ASK, STRONG_ASK            |
|  - Historical Z-Score: Parametric standard deviation & robust MAD-based standardization         |
+--------------------------------------------------------------------------------------------------+
```

## Mathematical Conventions
1. **Normalized Imbalance:**
   $$I = \frac{B - A}{B + A},\quad I \in [-1.0, 1.0]$$
2. **Liquidity Shares:**
   $$\text{BidShare} = \frac{B}{B + A},\quad \text{AskShare} = \frac{A}{B + A},\quad \text{BidShare} + \text{AskShare} = 1.0$$
   $$I = \text{BidShare} - \text{AskShare}$$
3. **Microprice:**
   $$\text{Microprice} = \frac{A_1 \cdot Q_{b1} + B_1 \cdot Q_{a1}}{Q_{b1} + Q_{a1}}$$
   $$\text{Microprice Deviation (bps)} = \frac{\text{Microprice} - \text{Midpoint}}{\text{Midpoint}} \times 10,000$$
4. **Weighting Models:**
   - **Exponential Level Decay:** $w_i = \exp(-\lambda (i - 1))$
   - **Distance Decay:** $w_i = \exp(-\lambda \cdot d_i)$
5. **Persistence & Reversals:**
   - Evaluated using duration-weighted intervals $\sum \Delta t_i$ rather than naive snapshot counts.
   - Reversal detection utilizes hysteresis ($\theta_{\text{enter}}, \theta_{\text{exit}}$) to filter snapshot noise.
