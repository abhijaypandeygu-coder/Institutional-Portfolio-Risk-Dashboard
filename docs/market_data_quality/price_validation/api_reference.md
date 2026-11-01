# Module 03.02: Price Validation — API Reference

All endpoints are hosted under `/api/v1/quality/price-validation`.
Authentication uses standard header: `X-API-Key`.

---

## 1. Price Observation Validation

### Single Observation Validation
- **POST** `/api/v1/quality/price-validation/validate`
- **RBAC**: `operator` or `admin`
- **Request Body**:
```json
{
  "instrument_id": "RELIANCE",
  "feed_id": "feed_nse_01",
  "provider_id": "SIMULATOR",
  "exchange": "NSE",
  "observation_type": "TICK",
  "price_field": "last_traded_price",
  "raw_price": "2950.00"
}
```
- **Response**: `200 OK`
```json
{
  "id": "7fa...",
  "validation_status": "ACCEPTED",
  "overall_severity": "INFO",
  "is_downstream_eligible": true,
  "failed_rule_count": 0,
  "warning_count": 0,
  "evidence_items": [...]
}
```

### Batch Observation Validation
- **POST** `/api/v1/quality/price-validation/validate/batch`
- **RBAC**: `operator` or `admin`
- **Request Body**:
```json
{
  "observations": [
    {
      "instrument_id": "IBM",
      "feed_id": "feed_nyse_01",
      "provider_id": "ALPHA_VANTAGE",
      "exchange": "NYSE",
      "observation_type": "OHLCV",
      "price_field": "close",
      "raw_price": "210.00",
      "open_price": "205.00",
      "high_price": "212.00",
      "low_price": "204.00",
      "close_price": "210.00"
    }
  ]
}
```
- **Response**: `200 OK` (Array of `ValidationResultResponse`)

---

## 2. Rule Management

### Create Rule
- **POST** `/api/v1/quality/price-validation/rules`
- **RBAC**: `operator` or `admin`
- **Request Body**:
```json
{
  "rule_code": "CUSTOM_PCT_THRESHOLD_NSE",
  "rule_name": "Custom 5% Jump Limit",
  "rule_category": "EXTREME_MOVEMENT",
  "exchange": "NSE",
  "threshold_type": "PERCENTAGE",
  "threshold_value": "5.0",
  "severity": "HIGH",
  "enforcement_action": "WARN"
}
```
- **Response**: `201 Created`

### List Rules
- **GET** `/api/v1/quality/price-validation/rules?enabled_only=true`
- **RBAC**: `readonly`, `operator`, `admin`
- **Response**: `200 OK`

---

## 3. Anomaly Incident Management

### List Anomalies
- **GET** `/api/v1/quality/price-validation/anomalies?status=OPEN`
- **RBAC**: `readonly`, `operator`, `admin`
- **Response**: `200 OK`

### Resolve Anomaly Incident
- **POST** `/api/v1/quality/price-validation/anomalies/{incident_id}/resolve`
- **RBAC**: `operator` or `admin`
- **Request Body**:
```json
{
  "status": "RESOLVED",
  "resolution_reason": "Verified genuine market circuit breaker spike"
}
```
- **Response**: `200 OK`

---

## 4. Cross-Source & Reference Comparisons

### Compare Independent Providers
- **POST** `/api/v1/quality/price-validation/reference-compare`
- **RBAC**: `readonly`, `operator`, `admin`
- **Request Body**:
```json
{
  "instrument_id": "IBM",
  "exchange": "NYSE",
  "price_a": "200.00",
  "provider_a": "PRIMARY_FEED",
  "price_b": "208.00",
  "provider_b": "ALPHA_VANTAGE",
  "max_tolerance_percentage": "1.0"
}
```
- **Response**: `200 OK`
```json
{
  "instrument_id": "IBM",
  "exchange": "NYSE",
  "absolute_difference": 8.0,
  "percentage_discrepancy": 3.85,
  "is_discrepant": true,
  "status": "QUARANTINED"
}
```

---

## 5. Summary Metrics
- **GET** `/api/v1/quality/price-validation/summary`
- **RBAC**: `readonly`, `operator`, `admin`
- **Response**: `200 OK`
```json
{
  "total_observations_validated": 45,
  "accepted_count": 40,
  "warning_count": 3,
  "rejected_count": 1,
  "quarantined_count": 1,
  "open_anomalies_count": 1,
  "eligibility_rate_percentage": 95.56
}
```

