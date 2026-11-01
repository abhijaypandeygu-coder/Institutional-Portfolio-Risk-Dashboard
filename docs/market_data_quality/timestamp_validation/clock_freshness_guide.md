# Module 03.03: Timestamp Validation — Clock Synchronization & Freshness Guide

## 1. Clock Offset and Transport Latency Separation

In high-throughput market data architectures, raw arrival differences between the source timestamp and local receive timestamp cannot blindly be blamed on clock drift:
$$\text{Apparent Difference} = T_{\text{receive}} - T_{\text{source}}$$

This apparent time difference comprises three distinct components:
1. Network transport delay ($D_{\text{transport}}$).
2. Provider queueing/processing delay ($D_{\text{provider}}$).
3. True clock offset ($\theta = C_{\text{local}} - C_{\text{source}}$).

To avoid falsely penalizing normal high-latency network routes:
$$\text{Estimated Clock Offset} = (T_{\text{receive}} - T_{\text{source}}) - \text{Estimated Latency}$$

---

## 2. Multi-Sample Clock Drift Rate Calculation

Clock drift is defined as the change in clock offset over time ($d\theta / dt$). A single observation cannot measure drift. The engine collects a sliding window of recent observations across each provider stream and calculates:
$$\text{Drift Rate} = \frac{\text{Offset}(t_2) - \text{Offset}(t_1)}{t_2 - t_1} \times 60 \quad (\text{ms per minute})$$

If the drift rate exceeds configured thresholds (e.g. 100 ms/min), a `CLOCK_DRIFT_DETECTED` warning is triggered.

---

## 3. Freshness vs Historical / EOD Bypasses

Staleness is strictly processing-context dependent:
- **Real-Time Streaming (`REALTIME`):** Enforces strict warning (5s) and critical (30s) latency limits. Older ticks are flagged as `AGING` or `CRITICALLY_STALE`.
- **Market Closed Awareness:** When the target exchange is closed, stream inactivity is normal and classified as `MARKET_CLOSED` (`VALID`) instead of stale.
- **End-of-Day Data (`EOD`):** Daily bars from Alpha Vantage are evaluated against calendar business day publication dates rather than intraday second clocks.
- **Historical Backfills (`HISTORICAL`):** Real-time freshness rules and future timestamp checks are bypassed.
