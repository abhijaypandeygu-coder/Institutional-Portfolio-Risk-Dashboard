# M03.08 Exception Management API Reference

All endpoints are hosted under `/api/v1/exceptions`.

## 1. Exception Intake & Management

### Register Exception
- **POST** `/api/v1/exceptions/`
- **Headers:** `X-API-Key: operator_dev_secret_key_2026`, `X-Actor: triage_bot`
- **Body:**
```json
{
  "category": "MARKET_DATA_CORRUPTION",
  "exception_type": "MULTIPLE_ANOMALIES",
  "severity": "HIGH",
  "priority": "P1",
  "summary": "Price spike and timestamp skew on TCS",
  "description": "Cross-feed validation identified 5% variance.",
  "findings": [
    {
      "finding_id": "FND_PRICE_9921",
      "source_module": "M03",
      "source_feature": "M03.02",
      "finding_code": "PRICE_SPIKE_DETECTED",
      "source_severity": "HIGH",
      "feed_id": "FEED_NSE_EQUITY",
      "instrument_id": "TCS",
      "observation_id": "OBS_NSE_TCS_101",
      "source_event_timestamp": "2026-11-01T09:30:00Z",
      "raw_payload": {"price": 38000.0, "volume": 100}
    }
  ]
}
```

### List Exceptions
- **GET** `/api/v1/exceptions/?workflow_status=OPEN&severity=HIGH&limit=50`
- **Headers:** `X-API-Key: operator_dev_secret_key_2026`

### Summary Metrics
- **GET** `/api/v1/exceptions/summary`
- **Headers:** `X-API-Key: operator_dev_secret_key_2026`

### Add Investigation Note
- **POST** `/api/v1/exceptions/{exception_id}/notes`
- **Headers:** `X-API-Key: operator_dev_secret_key_2026`, `X-Actor: analyst_bob`
- **Body:**
```json
{
  "note_content": "Confirmed price spike against official exchange terminal.",
  "note_type": "INVESTIGATION",
  "evidence_reference": "NSE_CIRCULAR_2026_11"
}
```

---

## 2. Quarantine Management

### Quarantine Observation
- **POST** `/api/v1/exceptions/{exception_id}/quarantine`
- **Headers:** `X-API-Key: operator_dev_secret_key_2026`
- **Body:**
```json
{
  "observation_id": "OBS_NSE_TCS_101",
  "quarantine_reason_code": "PRICE_SPIKE_DETECTED",
  "quarantine_reason": "Price spike requires secondary exchange confirmation.",
  "payload_snapshot": {"price": 38000.0}
}
```

### Release Quarantined Observation
- **POST** `/api/v1/exceptions/quarantine/{quarantine_id}/release`
- **Headers:** `X-API-Key: operator_dev_secret_key_2026`, `X-Actor: risk_officer`
- **Body:**
```json
{
  "justification": "Confirmed block deal executed on exchange floor.",
  "release_authorization_reference": "AUTH_BLOCK_DEAL_DESK_42"
}
```

---

## 3. Rejection Management

### Reject Observation
- **POST** `/api/v1/exceptions/{exception_id}/reject`
- **Headers:** `X-API-Key: operator_dev_secret_key_2026`
- **Body:**
```json
{
  "observation_id": "OBS_NSE_TCS_101",
  "reason_code": "REJ_INVALID_VALUE",
  "reason_details": "Price reported as negative quantity.",
  "recoverability": "RECOVERABLE"
}
```

---

## 4. Controlled Correction Management

### Propose Correction
- **POST** `/api/v1/exceptions/{exception_id}/corrections`
- **Headers:** `X-API-Key: operator_dev_secret_key_2026`, `X-Actor: analyst_bob`
- **Body:**
```json
{
  "observation_id": "OBS_NSE_TCS_101",
  "correction_category": "TICK_SIZE_ROUNDING",
  "correction_reason": "Round to nearest 0.05 tick per exchange rules.",
  "provenance_reference": "NSE_OFFICIAL_FEED",
  "provenance_source": "REAL_PROVIDER",
  "field_changes": [
    {
      "field_name": "price",
      "before_value": "3800.0333",
      "after_value": "3800.05",
      "change_reason": "Tick size conformance"
    }
  ],
  "resulting_payload_snapshot": {"price": 3800.05}
}
```

### Approve Correction
- **POST** `/api/v1/exceptions/corrections/{correction_id}/approve`
- **Headers:** `X-API-Key: admin_dev_secret_key_2026`, `X-Actor: risk_admin` *(Must not be analyst_bob)*
- **Body:**
```json
{
  "approval_reason": "Verified against exchange reference feed.",
  "policy_reference": "POL_TICK_VERIFICATION_V1"
}
```

---

## 5. Replay Management

### Submit Replay Request
- **POST** `/api/v1/exceptions/{exception_id}/replay`
- **Headers:** `X-API-Key: operator_dev_secret_key_2026`
- **Body:**
```json
{
  "replay_mode": "CORRECTION_REPLAY",
  "correction_id": "COR_1029384756AB",
  "replay_reason": "Reprocess approved tick size correction through ingestion pipeline.",
  "idempotency_key": "IDEMP_REPLAY_CORR_101"
}
```
