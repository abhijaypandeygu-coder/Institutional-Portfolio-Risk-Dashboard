# M09.01 — Bid-Ask Spread REST API Reference

Base URL: `/api/v1`

---

## 1. Configurations

### `POST /spreads/configurations`
Create or version a spread calculation policy.

**Request Body:**
```json
{
  "config_code": "CFG_HFT_01",
  "name": "High Frequency Surveillance",
  "book_scope": "VENUE_SPECIFIC",
  "relative_spread_method": "MIDPOINT_NORMALIZED",
  "locked_book_policy": "INCLUDE_AS_ZERO",
  "maximum_quote_age_seconds": 2.0,
  "maximum_quote_skew_seconds": 0.5,
  "session_policy": "CONTINUOUS_ONLY",
  "tick_validation_policy": "STRICT_ALIGNMENT"
}
```

### `GET /spreads/configurations/{config_code}`
Fetch configuration by code.

---

## 2. Calculation & Ingestion

### `POST /spreads/calculate`
Calculate and record bid-ask spread directly from a quote state.

**Request Body:**
```json
{
  "instrument_id": "INST_RELIANCE",
  "exchange": "NSE",
  "venue": "NSE",
  "book_scope": "VENUE_SPECIFIC",
  "source_feed_id": "FEED_DIRECT",
  "best_bid": "2850.10",
  "best_ask": "2850.35",
  "bid_quantity": "1500",
  "ask_quantity": "1200",
  "tick_size": "0.05",
  "persist_observation": true
}
```

---

## 3. Instrument Spread Analytics

### `GET /instruments/{instrument_id}/spread/current`
Query current or latest displayed spread. Resolves from M02 `NormalizedMarketTick` table if no spread has been explicitly cached yet.

### `GET /instruments/{instrument_id}/spread/history`
Query paginated historical spread observations. Supports filtering by `start_time`, `end_time`, `venue`, and `quality_status`.

### `GET /instruments/{instrument_id}/spread/statistics`
Retrieve observation-weighted (mean, median, P5-P99) and time-weighted spread statistics with coverage percentage.

### `GET /instruments/{instrument_id}/spread/quality`
Retrieve quality check diagnostic logs and rejection reasons.

### `GET /instruments/{instrument_id}/spread/venues`
Compare displayed spreads and coverage across multiple exchanges and venues (e.g. NSE, BSE, NYSE, NASDAQ) without synthetic book blending.

