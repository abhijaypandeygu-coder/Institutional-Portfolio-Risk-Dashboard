# Module 03.01: Missing Data Detection — Architecture Specification

## 1. Overview & Objectives

The **M03.01 Missing Data Detection** subsystem provides institutional-grade market data quality guarantees for equity data feeds across US (NYSE, NASDAQ) and Indian (NSE, BSE) markets.

High-frequency, quantitative risk and valuation models (e.g., VaR, Expected Shortfall, volatility clustering, beta calculations) are catastrophically sensitive to missing observations. If an asset has dropped 15 minutes of ticks or a missed daily candle is blindly forward-filled, risk models underestimate covariance or overestimate liquidity.

M03.01 establishes deterministic detection of:
1. **Missing Ticks:** Sequence gaps, transmission dropouts, quote/trade inactivity.
2. **Missing Candles:** Daily OHLCV bars across business days, intraday bars.
3. **Missing Order-Book Updates:** L2 snapshot/delta sequence discontinuities and order-book freeze/staleness during open market hours.
4. **Coverage Windows:** Quantitative calculation of observed vs. expected observations with division-by-zero safety.

---

## 2. Core Architectural Principles

### 2.1 Provider Expectation Awareness & False-Positive Prevention
- Ingestion providers possess different contractual entitlements.
- **Alpha Vantage Free Plan**: Does not provide intraday streaming or tick-by-tick websockets; only daily, weekly, monthly, and compact quotes. Attempting to detect missing real-time tick sequences on Alpha Vantage Free would yield 100% false positives.
- `ExpectationPolicyResolver` evaluates provider capabilities before running detectors. If a channel/frequency is unsupported, the policy status resolves to `NOT_SUPPORTED` / `NOT_APPLICABLE` and halts detector invocation.

### 2.2 Exchange Calendar & Session Rules
- **No missing candles on weekends or market holidays**: The detector generates expected timestamps by consulting `ExchangeSessionResolver`.
- Supported trading centers:
  - **NSE / BSE**: 09:15 - 15:30 IST (`Asia/Kolkata`)
  - **NYSE / NASDAQ**: 09:30 - 16:00 EST/EDT (`America/New_York`)
- Expected dates skip recognized market holidays (e.g., Republic Day, Independence Day, Diwali, Martin Luther King Jr. Day, Memorial Day, Juneteenth, Christmas).

---

## 3. Component Hierarchy

```
backend/app/modules/market_data_quality/missing_data/
├── models.py                  # SQLAlchemy 2.x models (policies, incidents, evidence, coverage)
├── schemas.py                 # Pydantic 2.x request & response contracts
├── service.py                 # Application service orchestrating detectors and persistence
├── router.py                  # FastAPI REST endpoints (/api/v1/quality/missing-data/*)
├── policies/
│   └── resolver.py            # Expectation policy resolution & capability guardrails
├── detectors/
│   ├── tick_detector.py       # Sequence gap & inactivity detector
│   ├── candle_detector.py     # Calendar-aware OHLCV bar detector
│   └── orderbook_detector.py  # L2 sequence gap & book staleness detector
├── coverage/
│   └── calculator.py          # Window coverage percentage & classification calculator
├── incidents/
│   └── repository.py          # Idempotent persistence layer for incidents & coverage
└── integrations/
    └── calendar_interface.py  # Exchange session hours, timezones, and holidays
```

---

## 4. Idempotence & State Management

- **Deterministic Incident Keys**: Every incident has a unique key:
  - Ticks: `gap-{feed_id}-{instrument_id}-{channel}-{expected_seq}-{observed_seq}`
  - Inactivity: `inactivity-{feed_id}-{instrument_id}-{channel}-{last_timestamp}`
  - Candles: `candle-{feed_id}-{instrument_id}-{interval}-{timestamp}`
  - Order Book: `book-gap-{feed_id}-{instrument_id}-{expected_seq}-{observed_seq}`
- **Upsert Semantics**: If an incident is re-detected, existing records are updated with latest evidence rather than duplicated.
- **Resolution Tracking**: Incidents can transition through `OPEN` -> `INVESTIGATING` -> `RESOLVED` / `SUPPRESSED` / `FALSE_POSITIVE`.
