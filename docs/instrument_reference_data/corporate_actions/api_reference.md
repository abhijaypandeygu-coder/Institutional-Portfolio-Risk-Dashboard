# M04.03 Corporate Actions REST API Reference

All endpoints are mounted under the `/api/v1/corporate-actions` namespace.

---

## 1. Register Corporate Action
**`POST /api/v1/corporate-actions`**

Creates a new corporate action with terms and snapshot version 1.

### Request Body (Stock Split Example)
```json
{
  "event_id": "CA_SPLIT_AAPL_2026",
  "corporate_action_type": "STOCK_SPLIT",
  "lifecycle_status": "CONFIRMED",
  "primary_instrument_id": "INST_AAPL_001",
  "declaration_date": "2026-05-15",
  "ex_date": "2026-06-01",
  "record_date": "2026-06-02",
  "payment_date": "2026-06-05",
  "effective_date": "2026-06-01",
  "ratio_detail": {
    "numerator": 4,
    "denominator": 1
  }
}
```

### Response (`201 Created`)
```json
{
  "event_id": "CA_SPLIT_AAPL_2026",
  "corporate_action_type": "STOCK_SPLIT",
  "lifecycle_status": "CONFIRMED",
  "primary_instrument_id": "INST_AAPL_001",
  "ex_date": "2026-06-01",
  "effective_date": "2026-06-01",
  "current_version": 1,
  "source_name": "MANUAL",
  "description": null,
  "created_at": "2026-11-01T07:22:00.000000",
  "updated_at": "2026-11-01T07:22:00.000000"
}
```

---

## 2. Get Corporate Action by ID
**`GET /api/v1/corporate-actions/{event_id}`**

### Response (`200 OK`)
```json
{
  "event_id": "CA_SPLIT_AAPL_2026",
  "corporate_action_type": "STOCK_SPLIT",
  "lifecycle_status": "CONFIRMED",
  "primary_instrument_id": "INST_AAPL_001",
  "ex_date": "2026-06-01",
  "effective_date": "2026-06-01",
  "current_version": 1,
  "source_name": "MANUAL",
  "description": null,
  "created_at": "2026-11-01T07:22:00.000000",
  "updated_at": "2026-11-01T07:22:00.000000"
}
```

---

## 3. Update / Amend Corporate Action
**`PUT /api/v1/corporate-actions/{event_id}`**

Increments `current_version` and stores an immutable audit snapshot in `corporate_action_versions`.

### Request Body
```json
{
  "lifecycle_status": "EFFECTIVE",
  "reason": "Ex-date passed and verified by exchange circular"
}
```

---

## 4. List Actions by Instrument
**`GET /api/v1/corporate-actions/instrument/{instrument_id}?limit=100&offset=0`**

Retrieves chronologically ordered corporate actions associated with the instrument.

---

## 5. Calculate Adjustments & Generate Lineage
**`POST /api/v1/corporate-actions/calculate-adjustments`**

Applies cumulative factors and records an immutable adjustment audit run.

### Request Body
```json
{
  "instrument_id": "INST_AAPL_001",
  "unadjusted_price": 200.00,
  "unadjusted_quantity": 50.00,
  "as_of_date": "2026-05-20",
  "policy_version": "v1.0"
}
```

### Response (`200 OK`)
```json
{
  "run_id": "RUN_A1B2C3D4E5F6",
  "instrument_id": "INST_AAPL_001",
  "as_of_date": "2026-05-20",
  "policy_version": "v1.0",
  "cumulative_price_factor": 0.250000000000,
  "cumulative_quantity_factor": 4.000000000000,
  "final_adjusted_price": 50.000000,
  "final_adjusted_quantity": 200.0000,
  "total_events_applied": 1,
  "input_checksum": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
  "output_checksum": "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",
  "lineage": [
    {
      "event_id": "CA_SPLIT_AAPL_2026",
      "event_version": 1,
      "event_type": "STOCK_SPLIT",
      "observation_date": "2026-06-01",
      "unadjusted_price": 200.00,
      "step_price_factor": 0.250000000000,
      "adjusted_price": 50.000000,
      "unadjusted_quantity": 50.00,
      "step_quantity_factor": 4.000000000000,
      "adjusted_quantity": 200.0000,
      "formula_description": "Split 4:1 -> FP=0.250000000000, FQ=4.000000000000"
    }
  ]
}
```

