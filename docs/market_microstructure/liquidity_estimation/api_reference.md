# M09.03 — Liquidity Estimation REST API Reference

Base Endpoint: `/api/v1/market-microstructure/liquidity`

All endpoints return JSON responses adhering to OpenAPI 3.1 specifications.

---

### 1. Direct Liquidity Score Calculation
Calculates composite liquidity score and subscores directly from raw or input values without database persistence.

- **Method:** `POST`
- **Path:** `/api/v1/market-microstructure/liquidity/calculate`
- **Request Body:**
```json
{
  "instrument_id": "EQ_INFY_NSE",
  "exchange": "NSE",
  "venue": "NSE_CASH",
  "currency": "INR",
  "spread_bps": 2.5,
  "depth_notional": 5000000.0,
  "turnover_amount": 25000000.0,
  "spread_coverage": 1.0,
  "depth_coverage": 1.0,
  "turnover_coverage": 1.0,
  "peer_spreads": [1.0, 2.5, 5.0, 10.0],
  "peer_depths": [1000000.0, 3000000.0, 5000000.0, 8000000.0],
  "peer_turnovers": [10000000.0, 20000000.0, 25000000.0, 50000000.0]
}
```

- **Response:** `200 OK`
```json
{
  "instrument_id": "EQ_INFY_NSE",
  "as_of_timestamp": "2026-11-03T09:30:00Z",
  "composite_liquidity_score": 75.25,
  "scoring_status": "ACTIVE",
  "status_reason": "Eligibility criteria and coverage gates fully satisfied",
  "spread_subscore": 62.5,
  "depth_subscore": 62.5,
  "turnover_subscore": 62.5,
  "availability_subscore": 100.0,
  "spread_contribution": 15.625,
  "depth_contribution": 18.75,
  "turnover_contribution": 18.75,
  "availability_contribution": 15.0,
  "spread_raw_value": 2.5,
  "depth_raw_value": 5000000.0,
  "turnover_raw_value": 25000000.0,
  "currency": "INR"
}
```

---

### 2. Configuration Management

#### 2.1 Create Metric Configuration
- **Method:** `POST`
- **Path:** `/api/v1/market-microstructure/liquidity/configs/metrics`

#### 2.2 Create Scoring Profile
- **Method:** `POST`
- **Path:** `/api/v1/market-microstructure/liquidity/configs/scoring-profiles`

#### 2.3 Create Bucket Policy
- **Method:** `POST`
- **Path:** `/api/v1/market-microstructure/liquidity/configs/bucket-policies`

---

### 3. Trade Volume & Turnover Aggregations

#### 3.1 Aggregate Trades
- **Method:** `POST`
- **Path:** `/api/v1/market-microstructure/liquidity/trades/aggregate`
- **Query Parameters:** `instrument_id`, `exchange`, `venue`, `start_time`, `end_time`, `currency`
- **Optional Request Body:** List of direct trade executions:
```json
[
  {
    "trade_id": "TR_001",
    "price": 1500.0,
    "quantity": 100,
    "timestamp": "2026-11-03T09:20:00Z",
    "status": "ACTIVE"
  }
]
```

#### 3.2 Compute Rolling Statistics
- **Method:** `POST`
- **Path:** `/api/v1/market-microstructure/liquidity/statistics/rolling`
- **Query Parameters:** `instrument_id`, `venue`, `as_of`, `lookback_sessions`, `currency`

---

### 4. Evaluate Score & Bucket
- **Method:** `POST`
- **Path:** `/api/v1/market-microstructure/liquidity/evaluate`
- Evaluates composite score and bucket, persisting both snapshots and logging bucket transitions.

---

### 5. Overview & Screening

#### 5.1 Current Liquidity Overview
- **Method:** `GET`
- **Path:** `/api/v1/market-microstructure/liquidity/{instrument_id}/current`

#### 5.2 Multi-Dimensional Screening
- **Method:** `POST`
- **Path:** `/api/v1/market-microstructure/liquidity/screen`
- **Request Body:**
```json
{
  "min_score": 60.0,
  "max_score": 100.0,
  "bucket": "VERY_HIGH_LIQUIDITY",
  "limit": 20,
  "offset": 0
}
```
