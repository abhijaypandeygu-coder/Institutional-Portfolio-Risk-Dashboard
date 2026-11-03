# M09.01 — Bid-Ask Spread Architecture & Mathematical Specification

## 1. Overview and Engineering Context

**M09.01 Bid-Ask Spread** is the foundational market microstructure analytics module of the Institutional Portfolio Risk Dashboard. It operates directly downstream of market data ingestion (M02), feed registries (M01), market data quality (M03), and instrument/calendar master engines (M04).

The module measures displayed trading costs represented by the top-of-book difference between the best available ask ($A_t$) and best available bid ($B_t$), using valid, synchronized, and fresh order-book observations. It strictly rejects stale, invalid, crossed, or unverified quotes from published statistics.

```
┌────────────────────────────────────────────────────────────────────────┐
│                   Upstream Market Data & Reference                     │
│   M01 Feed Registry & Ingestion Feeds (Capabilities & Priority)        │
│   M02 NormalizedMarketTicks & ReconstructedOrderBooks (L1/L2)          │
│   M03 Market Data Quality & Hard Validation Gates                      │
│   M04 Instrument Master & Exchange Trading Calendars                   │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   M09.01 Bid-Ask Spread Engine                         │
│                                                                        │
│  ┌────────────────────────┐  ┌──────────────────────────────────────┐  │
│  │ Spread Quality Gate    │  │ Absolute Spread Engine               │  │
│  │ • Freshness & Age Check│  │ • S_t = A_t - B_t                    │  │
│  │ • Side Skew Sync Check │  │ • Locked book (S_t = 0)              │  │
│  │ • Crossed Book Filter  │  │ • Rejection of Crossed Books         │  │
│  │ • Session Eligibility  │  │ • Tick Alignment Validation          │  │
│  └───────────┬────────────┘  └──────────────────┬───────────────────┘  │
│              │                                  │                      │
│              └─────────────────┬────────────────┘                      │
│                                │                                       │
│                                ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Relative Spread & Normalization Engine                           │  │
│  │ • Midpoint: M_t = (A_t + B_t) / 2                                │  │
│  │ • RS Decimal: S_t / M_t                                          │  │
│  │ • RS Percentage: RS * 100                                        │  │
│  │ • RS Basis Points: RS * 10,000                                   │  │
│  │ • Alternative Denominators (Bid / Ask / Reference Price)         │  │
│  │ • Spread in Ticks: S_t / TickSize                                │  │
│  └─────────────────────────────┬────────────────────────────────────┘  │
│                                │                                       │
│                                ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Aggregation & Historical Analytics Engine                        │  │
│  │ • Observation-Weighted: Mean, Median, Min, Max, P5-P99           │  │
│  │ • Time-Weighted: S_TW = sum(S_j * Δt_j) / sum(Δt_j)              │  │
│  │ • Time Coverage % against Expected Session Duration              │  │
│  │ • Venue Comparison & Multi-Exchange Analytics                    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Mathematical Formulations

### 2.1 Absolute Spread
Given best buying price $B_t$ and best selling price $A_t$:
$$S_t = A_t - B_t$$
- **Units:** Exact native instrument price units (INR, USD).
- **Locked Book:** $A_t = B_t \implies S_t = 0$ (handled under configurable policy `INCLUDE_AS_ZERO`).
- **Crossed Book:** $A_t < B_t \implies$ **Hard rejection** (`CROSSED_BOOK`). Negative spread is never calculated.
- **One-Sided Books:** Missing bid or ask is flagged as `MISSING_BID` or `MISSING_ASK`; no numerical spread is produced.

### 2.2 Relative Spread
1. **Quote Midpoint:**
   $$M_t = \frac{A_t + B_t}{2}$$
2. **Midpoint-Normalized Relative Spread:**
   $$RS_t = \frac{A_t - B_t}{M_t}$$
3. **Percentage Representation:**
   $$RS_t^{\%} = RS_t \times 100$$
4. **Basis Points Representation:**
   $$RS_t^{\text{bps}} = RS_t \times 10,000$$
5. **Spread in Ticks:**
   $$\text{SpreadTicks}_t = \frac{S_t}{\text{TickSize}_t}$$

### 2.3 Time-Weighted Spread ($S_{\text{TW}}$)
Given $J$ valid quote states where each state lasts duration $\Delta t_j$, clamped by maximum quote age $T_{\text{max}}$:
$$S_{\text{TW}} = \frac{\sum_{j=1}^J S_j \Delta t_j}{\sum_{j=1}^J \Delta t_j}$$
- **Time Coverage:**
  $$\text{Coverage}_{\text{time}} = \frac{\sum_{j=1}^J \Delta t_j}{\text{ExpectedEligibleMarketDuration}} \times 100$$

---

## 3. Database Schema

1. `m09_01_spread_calculation_configs`: Versioned policies, staleness limits, skew tolerance, and locked-book rules.
2. `m09_01_spread_observations`: Stored quote-level spreads with source provenance references.
3. `m09_01_spread_quality_results`: Granular diagnostic checks per observation.
4. `m09_01_spread_interval_aggregates`: High-frequency and intraday interval aggregates (1s, 5s, 1m, 5m, 15m, 1h).
5. `m09_01_spread_session_summaries`: Daily and trading session rollups.
6. `m09_01_spread_quality_summaries`: Rolling quality health indicators across venues.

