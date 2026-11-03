# M09.02 — Order Book Depth REST API Reference

Base Endpoint: `/api/v1/market-microstructure/depth`

All endpoints return JSON responses adhering to OpenAPI 3.1 specifications.

---

### 1. Direct Order Book Depth Calculation
Calculate displayed depth, level metrics, notional depth, distance from mid, price bands, and imbalances directly from raw or submitted quote levels without persisting to the database.

- **Method:** `POST`
- **Path:** `/api/v1/market-microstructure/depth/calculate`
- **Request Body:**
```json
{
  "instrument_id": "EQ_RELIANCE_NSE",
  "exchange": "NSE",
  "venue": "NSE_CASH",
  "timestamp": "2026-11-03T10:00:00Z",
  "tick_size": 0.05,
  "decay_lambda": 0.01,
  "bids": [
    {"price": 2500.0, "quantity": 100},
    {"price": 2499.5, "quantity": 150},
    {"price": 2499.0, "quantity": 250}
  ],
  "asks": [
    {"price": 2500.5, "quantity": 80},
    {"price": 2501.0, "quantity": 120},
    {"price": 2501.5, "quantity": 300}
  ],
  "bands": [
    {"name": "0_5_bps", "min_bps": 0.0, "max_bps": 5.0},
    {"name": "5_15_bps", "min_bps": 5.0, "max_bps": 15.0}
  ]
}
```

- **Response:** `200 OK`
```json
{
  "instrument_id": "EQ_RELIANCE_NSE",
  "exchange": "NSE",
  "venue": "NSE_CASH",
  "timestamp": "2026-11-03T10:00:00Z",
  "mid_price": 2500.25,
  "best_bid": 2500.0,
  "best_ask": 2500.5,
  "top_levels": [
    {
      "side": "BID",
      "level": 1,
      "price": 2500.0,
      "quantity": 100.0,
      "notional": 250000.0,
      "distance_abs": 0.25,
      "distance_bps": 1.0,
      "distance_ticks": 5.0
    }
  ],
  "cumulative": {
    "bid_quantity_top1": 100.0,
    "ask_quantity_top1": 80.0,
    "bid_notional_top1": 250000.0,
    "ask_notional_top1": 200040.0,
    "bid_quantity_top5": 500.0,
    "ask_quantity_top5": 500.0,
    "bid_notional_top5": 1249700.0,
    "ask_notional_top5": 1250600.0
  },
  "imbalance": {
    "quantity_imbalance_top1": 0.111111,
    "notional_imbalance_top1": 0.111012,
    "weighted_imbalance": 0.085431
  },
  "bands": [
    {
      "band_name": "0_5_bps",
      "min_bps": 0.0,
      "max_bps": 5.0,
      "bid_quantity": 250.0,
      "ask_quantity": 200.0,
      "bid_notional": 624925.0,
      "ask_notional": 500140.0
    }
  ]
}
```

---

### 2. Configuration Management

#### 2.1 Create Depth Calculation Configuration
- **Method:** `POST`
- **Path:** `/api/v1/market-microstructure/depth/configs`
- **Request Body:**
```json
{
  "config_code": "CFG_DEPTH_INST_DEFAULT",
  "name": "Standard Institutional Depth Policy",
  "decay_lambda": 0.005,
  "max_stale_seconds": 2.0,
  "bands": [
    {"name": "0_5bps", "min_bps": 0.0, "max_bps": 5.0},
    {"name": "5_15bps", "min_bps": 5.0, "max_bps": 15.0},
    {"name": "15_30bps", "min_bps": 15.0, "max_bps": 30.0}
  ]
}
```

#### 2.2 Get Active Configuration
- **Method:** `GET`
- **Path:** `/api/v1/market-microstructure/depth/configs/{config_code}`

---

### 3. Record Snapshot & Upstream Ingestion

#### 3.1 Record Snapshot from Direct Level Inputs
- **Method:** `POST`
- **Path:** `/api/v1/market-microstructure/depth/snapshots/record`
- **Description:** Parses and validates bid and ask quote levels, calculates cumulative depth and imbalance, saves the snapshot, individual levels, and band summaries to the database.

#### 3.2 Ingest from M02 Limit Order Book Record
- **Method:** `POST`
- **Path:** `/api/v1/market-microstructure/depth/snapshots/from-m02/{snapshot_id}`
- **Description:** Directly consumes reconstructed order books from `m02_order_book_snapshots`, verifies integrity, and generates full M09.02 analytics.

---

### 4. Query Historical Depth & Persistence

#### 4.1 Get Latest Depth Snapshot
- **Method:** `GET`
- **Path:** `/api/v1/market-microstructure/depth/snapshots/{instrument_id}/latest`

#### 4.2 Query Depth Snapshots Window
- **Method:** `GET`
- **Path:** `/api/v1/market-microstructure/depth/snapshots/{instrument_id}/history`
- **Query Parameters:** `start_time`, `end_time`, `limit`

#### 4.3 Query Detailed Depth Ladder
- **Method:** `GET`
- **Path:** `/api/v1/market-microstructure/depth/snapshots/{snapshot_id}/ladder`

#### 4.4 Calculate Time-Weighted Depth Persistence
- **Method:** `POST`
- **Path:** `/api/v1/market-microstructure/depth/persistence/calculate`
- **Request Body:**
```json
{
  "instrument_id": "EQ_RELIANCE_NSE",
  "start_time": "2026-11-03T09:15:00Z",
  "end_time": "2026-11-03T10:15:00Z",
  "threshold_quantity": 1000.0,
  "level_depth": 5,
  "max_stale_seconds": 2.0
}
```
- **Response:**
```json
{
  "instrument_id": "EQ_RELIANCE_NSE",
  "start_time": "2026-11-03T09:15:00Z",
  "end_time": "2026-11-03T10:15:00Z",
  "level_depth": 5,
  "time_weighted_mean_bid_depth": 1450.25,
  "time_weighted_mean_ask_depth": 1390.80,
  "time_weighted_variance": 45210.5,
  "time_weighted_std_dev": 212.63,
  "coefficient_of_variation": 0.1466,
  "bid_threshold_persistence_pct": 98.45,
  "ask_threshold_persistence_pct": 96.20,
  "coverage_ratio_pct": 99.85,
  "total_interval_seconds": 3600.0
}
```

