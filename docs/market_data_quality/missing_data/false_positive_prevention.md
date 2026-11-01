# Module 03.01: False-Positive Prevention Guide

## 1. The Challenge in Quantitative Finance

False alarms in data quality pipelines undermine operational credibility and can trigger unnecessary failovers or trading halts. The two most common causes of false positive missing-data alarms are:
1. Expecting high-frequency real-time updates from an end-of-day or REST-polling provider.
2. Expecting market data during weekends, trading holidays, or outside session hours.

---

## 2. Guardrails Implemented in M03.01

### A. Provider Capability Matrix (`ExpectationPolicyResolver`)
The system enforces strict capability definitions for each registered provider.

| Provider ID | Channel | Frequency | Resolution Result | Action Taken |
|---|---|---|---|---|
| `ALPHA_VANTAGE` | TICK | any | `NOT_SUPPORTED` | **No Incident Raised** (Alpha Vantage Free does not stream ticks) |
| `ALPHA_VANTAGE` | ORDER_BOOK | any | `NOT_SUPPORTED` | **No Incident Raised** (Order book is not supported on Free plan) |
| `ALPHA_VANTAGE` | CANDLE | 1m, 5m, 15m | `NOT_SUPPORTED` | **No Incident Raised** (Intraday is reserved for Premium tier) |
| `ALPHA_VANTAGE` | CANDLE | 1d, 1w, 1M | `ACTIVE` | Normal missing bar detection runs |
| `SIMULATOR` | any | any | `ACTIVE` | Real-time ticks, intraday, and order books are actively evaluated |

### B. Session & Holiday Calendar Engine (`ExchangeSessionResolver`)
Before flagging an absent daily candle or a lack of ticks:
1. **Weekend Filter**: Saturdays and Sundays are excluded from daily expectation lists.
2. **Holiday Filter**: Official holidays for NSE/BSE (e.g., 2026-01-26, 2026-08-15, 2026-10-02) and NYSE/NASDAQ (e.g., 2026-01-01, 2026-01-19, 2026-07-04, 2026-12-25) are excluded.
3. **Session Hours**: Inactivity checks (ticks and order-book snapshots) are only evaluated when the exchange is currently within its primary trading session. If the exchange is closed, `is_market_open()` returns `False` and inactivity checks are skipped.

### C. Grace Periods & Late Arrival Handling
- Ticks and candles are subject to configurable `grace_period_seconds` (default: 3.0s - 30.0s).
- If an out-of-order tick arrives within the grace period, the state machine resolves the gap without flagging a dropped message.

