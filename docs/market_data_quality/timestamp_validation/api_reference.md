# Module 03.03: Timestamp Validation — API Reference

All endpoints are hosted under `/api/v1/quality/timestamp-validation`.
Authentication uses standard header: `X-API-Key`.

---

## 1. Timestamp Observation Validation

### Single Observation Validation
- **POST** `/api/v1/quality/timestamp-validation/validate`
- **RBAC**: `operator` or `admin`
- **Request Body**:
```json
{
  "instrument_id": "RELIANCE",
  "feed_id": "feed_nse_01",
  "provider_id": "SIMULATOR",
  "exchange": "NSE",
  "event_type": "TICK",
  "processing_context": "REALTIME",
  "source_timestamp": "2026-11-02T05:00:00Z",
  "sequence_number": 1
}
```
- **Response**: `200 OK`
```json
{
  "id": "7fa...",
  "final_status": "VALID",
  "ordering_status": "IN_ORDER",
  "clock_status": "CLOCK_NORMAL",
  "freshness_status": "FRESH",
  "session_status": "REGULAR_SESSION",
  "is_downstream_eligible": true,
  "evidence_items": [...]
}
```

### Batch Observation Validation
- **POST** `/api/v1/quality/timestamp-validation/validate/batch`
- **RBAC**: `operator` or `admin`
- **Request Body**:
```json
{
  "observations": [
    {
      "instrument_id": "INFY",
      "feed_id": "feed_sim_01",
      "provider_id": "SIMULATOR",
      "exchange": "NSE",
      "event_type": "TICK",
      "source_timestamp": "2026-11-02T05:00:00Z"
    }
  ]
}
```
- **Response**: `200 OK` (Array of `TimestampValidationResultResponse`)

---

## 2. Session Alignment & Checking

### Check Session Alignment
- **POST** `/api/v1/quality/timestamp-validation/session-check`
- **RBAC**: `readonly`, `operator`, `admin`
- **Request Body**:
```json
{
  "exchange": "NSE",
  "timestamp": "2026-11-02T05:00:00Z",
  "allow_extended_hours": true
}
```
- **Response**: `200 OK`
```json
{
  "exchange": "NSE",
  "normalized_utc_timestamp": "2026-11-02T05:00:00Z",
  "exchange_local_time": "10:30:00",
  "trading_date": "2026-11-02",
  "session_status": "REGULAR_SESSION",
  "is_auction": false,
  "session_name": "REGULAR_HOURS",
  "is_valid": true,
  "reason": "Timestamp within regular session (09:15:00 - 15:30:00) on NSE."
}
```

---

## 3. Anomaly Incident Management

### List Anomalies
- **GET** `/api/v1/quality/timestamp-validation/incidents?status=OPEN`
- **RBAC**: `readonly`, `operator`, `admin`
- **Response**: `200 OK`

### Resolve Incident
- **POST** `/api/v1/quality/timestamp-validation/incidents/{incident_id}/resolve`
- **RBAC**: `operator` or `admin`
- **Request Body**:
```json
{
  "status": "RESOLVED",
  "resolution_reason": "Verified stream reconnection and sequence resync."
}
```
- **Response**: `200 OK`

---

## 4. Summary Metrics
- **GET** `/api/v1/quality/timestamp-validation/summary`
- **RBAC**: `readonly`, `operator`, `admin`
- **Response**: `200 OK`
```json
{
  "total_observations_validated": 42,
  "valid_count": 39,
  "warning_count": 2,
  "rejected_count": 1,
  "quarantined_count": 0,
  "ordering_anomalies_count": 1,
  "clock_anomalies_count": 0,
  "stale_observations_count": 0,
  "session_misalignments_count": 0,
  "open_incidents_count": 1,
  "downstream_eligibility_rate_percentage": 97.62
}
```
