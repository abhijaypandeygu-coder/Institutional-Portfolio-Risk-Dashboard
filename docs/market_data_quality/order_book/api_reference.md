# M03.04 — Order Book Validation API Reference

Base URL prefix: `/api/v1/quality/order-book`

## Authentication
All endpoints require standard institutional API key authentication headers:
- `X-API-Key`: Required (`admin_dev_secret_key_2026`, `operator_dev_secret_key_2026`, or `readonly_dev_secret_key_2026`).

---

## Endpoints

### 1. Validate Single Order Book
- **Path:** `POST /validate`
- **Role:** `OPERATOR` or `ADMIN`
- **Description:** Validates a snapshot or incremental delta update.
- **Request Body:**
  ```json
  {
    "feed_id": "feed_simulator_01",
    "symbol": "RELIANCE",
    "venue": "NSE",
    "session_phase": "CONTINUOUS_TRADING",
    "data_origin": "SIMULATOR",
    "is_snapshot": true,
    "sequence_number": 100,
    "bids": [
      {"price": "2950.00", "quantity": "100", "level_position": 1},
      {"price": "2949.50", "quantity": "250", "level_position": 2}
    ],
    "asks": [
      {"price": "2950.50", "quantity": "150", "level_position": 1},
      {"price": "2951.00", "quantity": "300", "level_position": 2}
    ]
  }
  ```
- **Response:** `200 OK`
  ```json
  {
    "validation_id": "OBV_76D1F0E48B01",
    "feed_id": "feed_simulator_01",
    "symbol": "RELIANCE",
    "venue": "NSE",
    "session_phase": "CONTINUOUS_TRADING",
    "is_snapshot": true,
    "best_bid_price": 2950.0,
    "best_ask_price": 2950.5,
    "is_valid": true,
    "is_crossed": false,
    "is_locked": false,
    "has_quantity_anomaly": false,
    "has_continuity_break": false,
    "spread_eligible": true,
    "imbalance_eligible": true,
    "depth_eligible": true,
    "liquidity_eligible": true,
    "severity": "PASS",
    "resync_requested": false
  }
  ```

---

### 2. Batch Validation
- **Path:** `POST /validate/batch`
- **Role:** `OPERATOR` or `ADMIN`
- **Description:** Validates an ordered batch of snapshots or deltas in a single call.

---

### 3. Rules Configuration
- **Path:** `POST /rules` (Create Rule, `ADMIN`)
- **Path:** `GET /rules` (List Rules, `READ_ONLY`)
- **Parameters:** Configures transient crossing duration limits, maximum cross amounts, auction allowances, lot size constraints, and sequence gap tolerances.

---

### 4. Integrity Incidents & Resync
- **Path:** `GET /incidents?feed_id=&symbol=&status=` (List incidents, `READ_ONLY`)
- **Path:** `POST /resync` (Trigger manual M02 resynchronization, `OPERATOR`)
- **Path:** `GET /summary?feed_id=&symbol=` (Aggregated metrics & eligibility ratios, `READ_ONLY`)
