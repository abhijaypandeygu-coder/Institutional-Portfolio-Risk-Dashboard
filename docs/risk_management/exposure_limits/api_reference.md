# M06.08 — Exposure Limits: API Reference

## Base Path: `/api/v1/risk/exposure-limits`

### 1. Create Exposure Limit Configuration
- **Method:** `POST /configs`
- **Request Body (`ExposureLimitConfigCreateRequest`):**
```json
{
  "limit_code": "LIM_AAPL_MAX_GROSS",
  "limit_name": "Apple Inc Max Gross Exposure",
  "limit_category": "INSTRUMENT_LIMIT",
  "portfolio_id": "port-institutional-alpha",
  "target_entity_id": "INST_AAPL_EQUITY",
  "exposure_basis": "GROSS_MARKET_VALUE",
  "limit_direction": "MAXIMUM",
  "denominator_type": "ABSOLUTE_AMOUNT",
  "limit_value": "10000.000000",
  "warning_threshold_ratio": "0.850000",
  "severe_breach_threshold_ratio": "1.100000"
}
```
- **Response (`201 Created`):** Returns `ExposureLimitConfigResponse`.

---

### 2. List Exposure Limit Configurations
- **Method:** `GET /configs`
- **Query Parameters:**
  - `portfolio_id` (optional): Filter by single portfolio.
  - `portfolio_group_id` (optional): Filter by multi-portfolio group.
  - `limit_category` (optional): Filter by category enum.
  - `is_active` (default `true`): Filter active limits.

---

### 3. Evaluate Exposure Limits
- **Method:** `POST /evaluate`
- **Request Body (`ExposureLimitEvaluateRequest`):**
```json
{
  "portfolio_id": "port-institutional-alpha",
  "portfolio_group_id": null,
  "as_of_date": null,
  "reporting_currency": "USD"
}
```
- **Response (`200 OK` - `ExposureLimitEvaluationSummaryResponse`):**
```json
{
  "portfolio_id": "port-institutional-alpha",
  "as_of": "2026-11-01T15:00:00Z",
  "total_evaluated_limits": 2,
  "within_limits_count": 1,
  "approaching_limits_count": 0,
  "warning_count": 0,
  "breached_count": 0,
  "severely_breached_count": 1,
  "unavailable_count": 0,
  "items": [
    {
      "evaluation_id": "EVAL_9B2F103A89",
      "limit_id": "LIM_0884A3",
      "limit_code": "LIM_AAPL_MAX_GROSS",
      "limit_name": "Apple Inc Max Gross Exposure",
      "limit_category": "INSTRUMENT_LIMIT",
      "target_entity_id": "INST_AAPL_EQUITY",
      "exposure_basis": "GROSS_MARKET_VALUE",
      "limit_direction": "MAXIMUM",
      "denominator_type": "ABSOLUTE_AMOUNT",
      "measured_exposure": "15000.000000",
      "limit_value": "10000.000000",
      "utilization_percentage": "150.000000",
      "headroom": "-5000.000000",
      "shortfall": "5000.000000",
      "status": "SEVERELY_BREACHED",
      "data_completeness_status": "COMPLETE",
      "source_reference": "INST_AAPL_EQUITY",
      "evaluated_at": "2026-11-01T15:00:00Z"
    }
  ]
}
```

---

### 4. Query Breach History Audit Trail
- **Method:** `GET /breaches`
- **Query Parameters:**
  - `portfolio_id` (optional): Filter events for portfolio.
  - `limit_id` (optional): Filter events for specific limit.
  - `limit` (default `100`, max `500`): Result pagination.

---

### 5. Simulate Pre-Trade Hypothetical Exposure
- **Method:** `POST /simulate`
- **Request Body (`ExposureLimitSimulateRequest`):**
```json
{
  "portfolio_id": "port-institutional-alpha",
  "limit_id": "LIM_0884A3",
  "proposed_exposure_delta": "60000.000000",
  "reporting_currency": "USD"
}
```
- **Response (`200 OK` - `ExposureLimitSimulationResponse`):**
```json
{
  "portfolio_id": "port-institutional-alpha",
  "limit_id": "LIM_0884A3",
  "current_exposure": "25000.000000",
  "proposed_exposure_delta": "60000.000000",
  "projected_exposure": "85000.000000",
  "limit_value": "50000.000000",
  "current_utilization": "50.000000",
  "projected_utilization": "170.000000",
  "current_headroom": "25000.000000",
  "projected_headroom": "-35000.000000",
  "current_status": "WITHIN_LIMIT",
  "projected_status": "SEVERELY_BREACHED"
}
```
