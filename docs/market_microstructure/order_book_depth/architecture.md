# M09.02 — Order Book Depth Architecture & Mathematical Formulation

## 1. Overview & Architectural Role

**M09.02 Order Book Depth** provides institutional-grade market microstructure analytics measuring displayed liquidity, depth distribution across price levels, cumulative liquidity ladders, notional depth, order book imbalance, price-band clustering, and time-weighted liquidity persistence.

### Architectural Position
- **Upstream Dependencies:**
  - `M02 Market Data Aggregation`: Consumes reconstructed limit order books (`ReconstructedOrderBook`, `OrderBookSnapshotRecord`, `OrderBookLevel`).
  - `M03 Data Quality & Integrity`: Enforces timestamp sanity, crossed-book detection, and stale quote fencing.
  - `M04 Instrument Master`: Resolves `instrument_id`, `listing_id`, venue ticker, lot sizes, tick sizes, and listing status.
- **Downstream Consumers:**
  - `M09.03 Slippage & Market Impact Estimation`: Utilizes cumulative depth and liquidity consumption curves to compute pre-trade implementation shortfall.
  - `M09.04 Execution Quality Analytics`: Benchmark displayed liquidity against executed volume.
  - `M09.05 Liquidity Risk & Real-Time Portfolio Liquidity Metrics`: Measures liquidation horizons and position-to-depth ratios.

---

## 2. Mathematical Formulation & Definitions

### 2.1 Order Book Level Ordering & Sorting
Let $\mathcal{B} = \{(p_i^b, q_i^b)\}_{i=1}^{N_b}$ represent the set of bid quotes, and $\mathcal{A} = \{(p_i^a, q_i^a)\}_{i=1}^{N_a}$ represent the set of ask quotes.
- **Bids are sorted strictly descending by price**:
  $$p_1^b > p_2^b > \dots > p_{N_b}^b$$
  where Level 1 is the Best Bid ($p_1^b = p_{\text{best}}^b$).
- **Asks are sorted strictly ascending by price**:
  $$p_1^a < p_2^a < \dots < p_{N_a}^a$$
  where Level 1 is the Best Ask ($p_1^a = p_{\text{best}}^a$).

### 2.2 Level Notional & Cumulative Depth
For any level $k$:
- **Level Notional Value:**
  $$ND_k = p_k \times q_k$$
- **Cumulative Quantity at Depth $L$:**
  $$CD_L^b = \sum_{i=1}^{L} q_i^b, \quad CD_L^a = \sum_{i=1}^{L} q_i^a$$
- **Cumulative Notional at Depth $L$:**
  $$CND_L^b = \sum_{i=1}^{L} p_i^b q_i^b, \quad CND_L^a = \sum_{i=1}^{L} p_i^a q_i^a$$

### 2.3 Distance Metrics from Midpoint
Let Midpoint $M = \frac{p_1^b + p_1^a}{2}$.
- **Absolute Distance:**
  $$d_{\text{abs}, i}^b = M - p_i^b, \quad d_{\text{abs}, i}^a = p_i^a - M$$
- **Relative Distance (Basis Points):**
  $$d_{\text{bps}, i} = \frac{|p_i - M|}{M} \times 10,000$$
- **Distance in Ticks:**
  $$\tau_i = \frac{|p_i - M|}{\Delta_{\text{tick}}}$$

### 2.4 Order Book Imbalance Metrics
Order book imbalance measures asymmetry between buying and selling interest in $[-1.0, +1.0]$.

1. **Quantity Imbalance:**
   $$I_Q = \frac{D_b - D_a}{D_b + D_a}$$
2. **Notional Imbalance:**
   $$I_N = \frac{ND_b - ND_a}{ND_b + ND_a}$$
3. **Distance-Weighted Imbalance:**
   Levels closer to the mid-price receive higher weighting via exponential decay:
   $$w_i = \exp(-\lambda \cdot d_{\text{bps}, i})$$
   $$WD_b = \sum_{i=1}^{N_b} q_i^b w_i^b, \quad WD_a = \sum_{i=1}^{N_a} q_i^a w_i^a$$
   $$I_W = \frac{WD_b - WD_a}{WD_b + WD_a}$$

*Guardrail Rule:* If $D_b + D_a = 0$, $I$ evaluates to `None` (never substituted with artificial 0.0).

### 2.5 Price-Band Depth Aggregation
Given defined distance bands $[b_{\text{min}}, b_{\text{max}})$ in basis points (e.g. 0-5 bps, 5-10 bps, 10-25 bps, 25-50 bps):
$$D_{\text{band}}^b = \sum_{i: d_{\text{bps}, i}^b \in [b_{\text{min}}, b_{\text{max}})} q_i^b$$
$$D_{\text{band}}^a = \sum_{i: d_{\text{bps}, i}^a \in [b_{\text{min}}, b_{\text{max}})} q_i^a$$

### 2.6 Depth Persistence & Stability Metrics
Let $D_j$ be the displayed depth observed during time interval $\Delta t_j = t_{j+1} - t_j$, where $\Delta t_j \le \Delta t_{\text{max\_stale}}$.

1. **Time-Weighted Mean Depth:**
   $$\overline{D}_{\text{TW}} = \frac{\sum_{j=1}^{M} D_j \Delta t_j}{\sum_{j=1}^{M} \Delta t_j}$$
2. **Time-Weighted Variance & Standard Deviation:**
   $$\sigma_{D, \text{TW}}^2 = \frac{\sum_{j=1}^{M} (D_j - \overline{D}_{\text{TW}})^2 \Delta t_j}{\sum_{j=1}^{M} \Delta t_j}, \quad \sigma_{D, \text{TW}} = \sqrt{\sigma_{D, \text{TW}}^2}$$
3. **Coefficient of Variation ($CV_D$):**
   $$CV_D = \frac{\sigma_{D, \text{TW}}}{\overline{D}_{\text{TW}}}$$
4. **Threshold Persistence:**
   The fraction of active trading time where depth meets or exceeds a target liquidity threshold $D_{\text{target}}$:
   $$\text{Persistence}(D \ge D_{\text{target}}) = \frac{\sum_{j: D_j \ge D_{\text{target}}} \Delta t_j}{\sum_{j=1}^{M} \Delta t_j} \times 100\%$$
5. **Coverage Ratio:**
   $$\text{Coverage} = \frac{\sum_{j=1}^M \Delta t_j}{T_{\text{window}}} \times 100\%$$

---

## 3. Database Schema Architecture

Six dedicated SQLAlchemy 2.x declarative tables manage order book depth configuration, snapshots, ladders, bands, persistence, and rolling histories:

1. `m09_02_depth_calculation_configs`: Versioned calculation parameters (band definitions, decay factors, stale thresholds).
2. `m09_02_order_book_depth_snapshots`: Point-in-time depth records capturing top 1, 3, 5, 10 cumulative depth, notionals, and imbalance.
3. `m09_02_order_book_depth_levels`: Normalized individual depth levels with distance-to-mid, notional, and tick offsets.
4. `m09_02_order_book_depth_bands`: Price-band aggregated liquidity across configured basis point ranges.
5. `m09_02_order_book_depth_persistence`: Time-weighted rolling persistence statistics ($CV_D$, threshold retention, coverage).
6. `m09_02_order_book_depth_history_aggregates`: Fixed-interval aggregated metrics (1m, 5m, 1h) for long-horizon liquidity trend analysis.
