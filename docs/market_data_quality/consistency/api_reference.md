# M03.06 — Data Consistency API Reference

Base URL prefix: `/api/v1/quality/consistency`

## Authentication
Requires standard institutional API key authentication headers:
- `X-API-Key`: `admin_dev_secret_key_2026`, `operator_dev_secret_key_2026`, or `readonly_dev_secret_key_2026`.

---

## Endpoints

### 1. Cross-Feed Comparison
- **Path:** `POST /compare`
- **Role:** `OPERATOR` or `ADMIN`
- **Description:** Evaluates price divergence between two independent observations.
- **Request Body:**
  ```json
  {
    "instrument_id": "RELIANCE",
    "exchange": "NSE",
    "currency": "INR",
    "observation_type": "TICK",
    "source_a": {
      "observation_id": "OBS_A_101",
      "provider_id": "FEED_PRIMARY",
      "feed_id": "NSE_L1",
      "instrument_id": "RELIANCE",
      "timestamp": "2026-11-01T11:00:00Z",
      "value": "2950.00",
      "data_origin": "SIMULATOR"
    },
    "source_b": {
      "observation_id": "OBS_B_202",
      "provider_id": "FEED_SECONDARY",
      "feed_id": "NSE_TICK",
      "instrument_id": "RELIANCE",
      "timestamp": "2026-11-01T11:00:00Z",
      "value": "2951.00",
      "data_origin": "SIMULATOR"
    },
    "percentage_tolerance": "0.5000"
  }
  ```
- **Response:** `200 OK`
  ```json
  {
    "result_id": "CMP_78D0B129EA31",
    "instrument_id": "RELIANCE",
    "exchange": "NSE",
    "observation_type": "TICK",
    "absolute_difference": 1.0,
    "percentage_difference": 0.0339,
    "tolerance_applied": 0.5,
    "comparison_status": "CONSISTENT",
    "severity": "PASS",
    "conflict_created": false
  }
  ```

---

### 2. Field Consistency Validation
- **Path:** `POST /validate-fields/ohlc` (Validates High/Low/Open/Close boundaries)
- **Path:** `POST /validate-fields/quote` (Validates displayed quantities and positive prices)
- **Role:** `OPERATOR` or `ADMIN`

---

### 3. Conflict Lifecycle & Precedence Rules
- **Path:** `GET /conflicts?status=&instrument_id=` (`READ_ONLY`)
- **Path:** `POST /conflicts/{conflict_key}/resolve` (`OPERATOR` / `ADMIN`)
  - Resolves conflict with explicit operator justification (`ACCEPT_SOURCE_A`, `ACCEPT_SOURCE_B`, `REJECT_BOTH`, `MANUAL_OVERRIDE`).
- **Path:** `POST /source-precedence` (`ADMIN`)
- **Path:** `GET /source-precedence` (`READ_ONLY`)
- **Path:** `GET /summary?instrument_id=` (`READ_ONLY`)
