# Module 03.03: Timestamp Validation — Architecture Specification

## 1. Overview & Objectives

The **M03.03 Timestamp Validation** engine provides institutional-grade timestamp quality, event ordering, clock synchronization, freshness, and market session guarantees across Indian (`NSE`, `BSE`) and US (`NYSE`, `NASDAQ`) venues.

Financial risk models (VaR, Expected Shortfall, Order Book Imbalance, and High-Frequency Microstructure analytics) rely heavily on timestamp truth. If messages arrive out of sequence, or clocks drift silently, or stale quotes are mistaken for active market liquidity, risk metrics miscalculate volatility and portfolio drawdown exposures.

M03.03 establishes a 4-stage validation pipeline:
1. **M03.03.01 — Out-of-Order Events:** Detects event-time regressions (backward timestamps), sequence regressions, late arrivals within vs. beyond tolerance, and handles connection epoch resets.
2. **M03.03.02 — Clock Drift:** Compares source and local receive timestamps, distinguishes true clock offsets from ordinary network transport latency, and computes multi-sample drift rates ($\text{ms/min}$).
3. **M03.03.03 — Stale Timestamps:** Calculates event age, enforces real-time latency thresholds, evaluates M02 order-book synchronization status, and handles market-closed inactivity and historical/EOD backfills without false alarms.
4. **M03.03.04 — Session Alignment:** Validates event timestamps against official exchange calendars, regular trading sessions, pre/post-market windows, auction windows, holidays, and Daylight Saving Time (DST) transitions using IANA timezones (`Asia/Kolkata`, `America/New_York`).

---

## 2. Architectural Pipeline

```
Raw / Normalized Market Observation (Tick, OHLCV, Trade, Order Book)
                    │
                    ▼
 Stage 0: Timestamp Foundation (Parser & Normalizer)
    - Provenance extraction (Exchange, Provider, Receive, Processing)
    - Timezone resolution via IANA (Asia/Kolkata, America/New_York)
    - Normalization to timezone-aware UTC datetime
                    │
                    ▼
 Stage 1: Out-of-Order & Sequence Evaluation
    - Monotonic event-time progression per stream
    - Sequence regressions (e.g. 101 -> 95 within same epoch) -> REJECTED
    - Late arrivals within jitter tolerance -> VALID_WITH_WARNING
    - Material event-time regressions (> tolerance) -> QUARANTINED
                    │
                    ▼
 Stage 2: Clock Drift & Offset Evaluation
    - Apparent divergence: (Local Receive Time - Source Time)
    - Transport latency decoupling: Estimated Offset = Apparent Diff - Latency
    - Multi-sample sliding window drift rate (ms/min)
    - Future-skew detection (> 2s ahead) -> QUARANTINED
                    │
                    ▼
 Stage 3: Freshness & Staleness Evaluation
    - Event age calculation (Validation Time - Event Time)
    - Real-time streaming thresholds (Warning: 5s, Critical: 30s)
    - Order-book synchronization verification from M02
    - Market-closed inactivity awareness (closed market != stale stream)
    - Historical and EOD processing bypasses
                    │
                    ▼
 Stage 4: Session Alignment & Exchange Calendar
    - Regular trading hours, pre-market, auctions, post-market
    - Weekend and official exchange holiday detection -> REJECTED
    - Date-only daily candle association
                    │
                    ▼
 Final Aggregation & Downstream Eligibility
    - Status: VALID, VALID_WITH_WARNING, QUARANTINED, REJECTED, UNKNOWN
    - Downstream Eligibility: True only for VALID or VALID_WITH_WARNING
    - Idempotent Anomaly Incident Upsert & Evidence Item Persistence
```
