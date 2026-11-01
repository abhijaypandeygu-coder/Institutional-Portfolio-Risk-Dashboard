# M03.07 Quality Scoring API Reference

All endpoints are hosted under `/api/v1/quality/scoring`.

## 1. Policies

### Create Scoring Policy
- **POST** `/api/v1/quality/scoring/policies`
- **Headers:** `X-API-Key: admin_dev_secret_key_2026`
- **Body:**
```json
{
  "policy_code": "POL_COMPOSITE_STD",
  "policy_name": "Standard Composite Scoring Policy",
  "score_type": "COMPOSITE",
  "rolling_window": "24h",
  "weight_availability": "0.35",
  "weight_timeliness": "0.35",
  "weight_error_rate": "0.30"
}
```

### List Scoring Policies
- **GET** `/api/v1/quality/scoring/policies`
- **Headers:** `X-API-Key: operator_dev_secret_key_2026`

---

## 2. Calculation & Snapshots

### Calculate Composite Snapshot
- **POST** `/api/v1/quality/scoring/calculate`
- **Headers:** `X-API-Key: operator_dev_secret_key_2026`
- **Body:**
```json
{
  "provider_id": "SIMULATOR",
  "feed_id": "FEED_EQUITY_L2",
  "instrument_id": "TCS",
  "data_type": "ORDER_BOOK",
  "data_origin": "SIMULATED",
  "reliability": {
    "provider_id": "SIMULATOR",
    "feed_id": "FEED_EQUITY_L2",
    "expected_duration_seconds": 3600,
    "unavailable_duration_seconds": 60,
    "eligible_operations": 1000,
    "failed_operations": 5,
    "eligible_expected_observations": 1000,
    "timely_observations": 980
  },
  "completeness": {
    "provider_id": "SIMULATOR",
    "feed_id": "FEED_EQUITY_L2",
    "instrument_id": "TCS",
    "expected_records": 1000,
    "observed_unique_records": 980,
    "valid_records": 980
  },
  "freshness": {
    "provider_id": "SIMULATOR",
    "feed_id": "FEED_EQUITY_L2",
    "instrument_id": "TCS",
    "target_age_ms": 500,
    "maximum_age_ms": 3000,
    "observed_age_ms": 350
  }
}
```

### Retrieve Snapshots
- **GET** `/api/v1/quality/scoring/snapshots?feed_id=FEED_EQUITY_L2&limit=50`
- **Headers:** `X-API-Key: operator_dev_secret_key_2026`

---

## 3. Use Eligibility

### Evaluate Use Eligibility
- **POST** `/api/v1/quality/scoring/eligibility/evaluate`
- **Headers:** `X-API-Key: operator_dev_secret_key_2026`
- **Body:**
```json
{
  "profile_code": "HISTORICAL_VAR",
  "provider_id": "ALPHA_VANTAGE",
  "feed_id": "AV_DAILY_EOD",
  "instrument_id": "AAPL",
  "reliability_score": "95.00",
  "completeness_score": "99.00",
  "freshness_score": "100.00",
  "price_validity_passed": true,
  "timestamp_integrity_passed": true,
  "book_continuity_passed": true,
  "consistency_passed": true,
  "supported_by_capability": true
}
```

### List Eligibility Decisions
- **GET** `/api/v1/quality/scoring/eligibility?profile_code=HISTORICAL_VAR`
- **Headers:** `X-API-Key: operator_dev_secret_key_2026`

### Summary Metrics
- **GET** `/api/v1/quality/scoring/summary`
- **Headers:** `X-API-Key: operator_dev_secret_key_2026`

