# M09.09 Microstructure Monitoring API Reference

## Base Path
`/api/v1/market-microstructure/monitoring`

---

## 1. Configurations

### `POST /configs`
Creates or updates a versioned surveillance configuration.

**Request:**
```json
{
  "config_name": "NSE_EQUITY_HFT_SURVEILLANCE_2026",
  "description": "High-frequency surveillance configuration for NSE equity universe",
  "market_scope": "INDIA",
  "venue_scope": "NSE",
  "feed_scope": "STREAMING_TICK",
  "instrument_scope": "ALL",
  "monitoring_mode": "STREAMING",
  "spread_window_seconds": 60,
  "depth_window_seconds": 60,
  "update_rate_window_seconds": 10,
  "maximum_spread_age_ms": 3000,
  "maximum_book_age_ms": 5000,
  "expected_update_cadence_ms": 1000,
  "minimum_sample_count": 5,
  "minimum_coverage": 0.85,
  "version": "1.0.0"
}
```

---

## 2. Spread Monitoring

### `POST /spread`
Processes short-horizon spread observations, computing rolling mean, sample standard deviation, CV, time-weighted mean, and robust widening flags.

### `GET /{instrument_id}/spread`
Retrieves historical spread surveillance records.

---

## 3. Depth Monitoring

### `POST /depth`
Monitors displayed depth fluctuations, depletion velocity, and replenishment recovery ratios.

### `GET /{instrument_id}/depth`
Retrieves historical depth surveillance records.

---

## 4. Update Intensity & Burst Detection

### `POST /update-intensity`
Calculates categorized message rates, book-change rates, and burst intensity ratios.

---

## 5. Feed Freshness

### `POST /freshness`
Computes observation age, receive latency, and classifies feed status (`FRESH`, `AGING`, `STALE`, `FEED_UNAVAILABLE`).

---

## 6. Anomaly Lifecycle Management

### `GET /anomalies`
Lists detected anomalies filtered by instrument, severity, or lifecycle status.

### `POST /anomalies/{anomaly_id}/acknowledge`
Transitions anomaly state to `ACKNOWLEDGED` with user attribution and notes.

### `POST /anomalies/{anomaly_id}/resolve`
Transitions anomaly state to `RESOLVED` with explicit resolution reason and closing timestamp.

---

## 7. Current Monitoring Overview

### `GET /{instrument_id}/current`
Provides unified real-time surveillance health across spread, depth, update rate, feed status, and active anomalies.

