# Module 03.01: API Reference

All Missing Data Detection endpoints are registered under `/api/v1/quality/missing-data`.
Authentication and RBAC follow the standard header: `X-API-Key`.

---

## 1. Expected Observation Policies

### Create Policy
- **POST** `/api/v1/quality/missing-data/policies`
- **RBAC**: `operator` or `admin`
- **Request Body**:
```json
{
  "policy_code": "POL_NSE_SIM_TICK",
  "instrument_id": "RELIANCE.BSE",
  "exchange": "NSE",
  "provider_id": "SIMULATOR",
  "feed_id": "feed_sim_01",
  "data_channel": "TICK",
  "observation_type": "REALTIME",
  "expected_frequency": "1s",
  "grace_period_seconds": 3.0,
  "inactivity_threshold_seconds": 15.0,
  "policy_parameters": {},
  "priority": 100
}
```
- **Response**: `201 Created`

### List Policies
- **GET** `/api/v1/quality/missing-data/policies`
- **RBAC**: `readonly`, `operator`, `admin`
- **Response**: `200 OK` (Array of policy objects)

---

## 2. Real-Time Missing Data Detection

### Evaluate Missing Ticks
- **POST** `/api/v1/quality/missing-data/detect/ticks`
- **RBAC**: `operator` or `admin`
- **Request Body**:
```json
{
  "instrument_id": "RELIANCE.BSE",
  "exchange": "NSE",
  "provider_id": "SIMULATOR",
  "feed_id": "feed_sim_01",
  "data_channel": "TICK",
  "expected_seq": 10,
  "observed_seq": 13,
  "observation_time": "2026-11-01T04:30:00Z"
}
```
- **Response**: `200 OK` (Array of generated `MissingDataIncident` records)

### Evaluate Missing Daily / Intraday Candles
- **POST** `/api/v1/quality/missing-data/detect/candles`
- **RBAC**: `operator` or `admin`
- **Request Body**:
```json
{
  "instrument_id": "IBM",
  "exchange": "NYSE",
  "provider_id": "ALPHA_VANTAGE",
  "feed_id": "feed_av_01",
  "interval": "1d",
  "observed_timestamps": ["2026-10-26T00:00:00Z", "2026-10-27T00:00:00Z"],
  "start_date": "2026-10-26",
  "end_date": "2026-10-30"
}
```
- **Response**: `200 OK` (Identifies missing business days, e.g. Oct 28, 29, 30)

---

## 3. Coverage Windows & Incident Management

### Calculate Coverage Window
- **POST** `/api/v1/quality/missing-data/coverage/calculate`
- **RBAC**: `operator` or `admin`
- **Request Body**:
```json
{
  "instrument_id": "INFY.BSE",
  "exchange": "NSE",
  "provider_id": "SIMULATOR",
  "window_type": "SESSION",
  "channel": "TICK",
  "expected_units": 100,
  "observed_units": 95,
  "window_start": "2026-11-01T03:45:00Z",
  "window_end": "2026-11-01T10:00:00Z"
}
```
- **Response**: `200 OK`
```json
{
  "coverage_percentage": 95.0,
  "classification": "PARTIAL",
  "missing_units": 5
}
```

### List Incidents
- **GET** `/api/v1/quality/missing-data/incidents`
- **Filters**: `status`, `severity`, `feed_id`, `instrument_id`
- **Response**: `200 OK`

### Update Incident Status
- **PATCH** `/api/v1/quality/missing-data/incidents/{incident_id}/status`
- **Request Body**:
```json
{
  "status": "RESOLVED",
  "resolved_reason": "Late arrival backfilled via Alpha Vantage EOD job"
}
```
- **Response**: `200 OK`
