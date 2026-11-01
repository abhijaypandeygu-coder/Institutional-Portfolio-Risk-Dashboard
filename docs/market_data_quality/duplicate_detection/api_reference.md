# M03.05 — Duplicate Detection API Reference

Base URL prefix: `/api/v1/quality/duplicates`

## Authentication
Requires standard institutional API key authentication headers:
- `X-API-Key`: `admin_dev_secret_key_2026`, `operator_dev_secret_key_2026`, or `readonly_dev_secret_key_2026`.

---

## Endpoints

### 1. Detect Duplicate Market Event
- **Path:** `POST /detect`
- **Role:** `OPERATOR` or `ADMIN`
- **Description:** Evaluates an incoming event against registered canonical identities.
- **Request Body:**
  ```json
  {
    "provider_id": "SIMULATOR",
    "feed_id": "SIM_TRADE_FEED",
    "instrument_id": "RELIANCE",
    "exchange": "NSE",
    "event_type": "TRADE",
    "provider_event_id": "TRD_1001",
    "event_timestamp": "2026-11-01T10:00:00Z",
    "price": "2950.00",
    "quantity": "100",
    "side": "BID"
  }
  ```
- **Response:** `200 OK`
  ```json
  {
    "classification": "NEW_EVENT",
    "is_duplicate": false,
    "is_new": true,
    "is_conflict": false,
    "identity_strategy": "PROVIDER_EVENT_ID",
    "idempotency_key": "PRV_EVT:SIMULATOR:SIM_TRADE_FEED:RELIANCE:TRADE:TRD_1001",
    "payload_fingerprint": "a4d3e5...",
    "canonical_event_id": "EVT_76F90E11AB23",
    "canonical_record_table": "market_trade_events",
    "duplicate_reason": null,
    "existing_delivery_count": 1
  }
  ```

---

### 2. Batch Event Detection
- **Path:** `POST /detect/batch`
- **Role:** `OPERATOR` or `ADMIN`
- **Description:** Evaluates a list of incoming market data events in a single call.

---

### 3. Duplicate Receipts & Audit
- **Path:** `GET /receipts?instrument_id=&event_type=&limit=` (`READ_ONLY`)
- **Path:** `GET /audit/summary?provider_id=&instrument_id=` (`READ_ONLY`)
  - Exposes `total_deliveries`, `unique_canonical_events`, `confirmed_duplicates`, `prevented_volume`, `prevented_turnover`, and `duplicate_rate_percentage`.

---

### 4. Identity Conflicts & Resolution
- **Path:** `GET /conflicts?status=` (`READ_ONLY`)
- **Path:** `POST /conflicts/{conflict_id}/resolve` (`OPERATOR` / `ADMIN`)
  - Resolves payload collisions with explicit audit reason (`ACCEPT_REVISION`, `OVERWRITE_CANONICAL`, `REJECT_INCOMING`).

---

### 5. Detection Rules
- **Path:** `POST /rules` (`ADMIN`)
- **Path:** `GET /rules` (`READ_ONLY`)
