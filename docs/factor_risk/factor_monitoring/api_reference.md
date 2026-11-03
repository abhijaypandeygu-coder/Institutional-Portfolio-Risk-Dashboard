# M08.08 — Factor Monitoring REST API Reference

Base URL: `/api/v1`

---

## 1. Monitoring Configuration Endpoints

### `POST /factor-monitoring/configs`
Create a new versioned monitoring configuration.

**Request Body:**
```json
{
  "config_code": "CFG_DAILY_GROWTH",
  "name": "Daily Growth Fund Factor Monitoring",
  "portfolio_id": "PF_GROWTH_01",
  "factor_model_id": "f8a9e400-...",
  "factor_model_version_id": "d1c2b3a4-...",
  "evaluation_frequency": "DAILY",
  "drift_reference_type": "PREVIOUS_SNAPSHOT",
  "historical_baseline_window": 60
}
```

**Response (`201 Created`):**
Returns created `FactorMonitoringConfigResponse`.

---

## 2. Factor Exposure Targets Endpoints

### `POST /factor-monitoring/targets`
Register an approved factor exposure target profile.

**Request Body:**
```json
{
  "target_code": "TGT_GROWTH_2026",
  "name": "2026 Factor Target Profile",
  "portfolio_id": "PF_GROWTH_01",
  "factor_model_id": "f8a9e400-...",
  "factor_model_version_id": "d1c2b3a4-...",
  "components": [
    {
      "factor_id": "mkt-uuid",
      "factor_code": "MKT",
      "target_exposure": "1.000000",
      "tolerance": "0.150000"
    },
    {
      "factor_id": "val-uuid",
      "factor_code": "VAL",
      "target_exposure": "0.200000",
      "tolerance": "0.100000"
    }
  ]
}
```

---

## 3. Threshold Policies Endpoints

### `POST /factor-monitoring/threshold-policies`
Create a quantitative threshold policy with hysteresis and persistence requirements.

**Request Body:**
```json
{
  "policy_code": "POL_MKT_CEILING",
  "name": "Market Beta Soft & Hard Ceilings",
  "portfolio_id": "PF_GROWTH_01",
  "factor_id": "mkt-uuid",
  "factor_code": "MKT",
  "metric_type": "ABSOLUTE_FACTOR_EXPOSURE",
  "warning_threshold": "1.100000",
  "breach_threshold": "1.200000",
  "critical_threshold": "1.400000",
  "recovery_threshold": "1.050000",
  "persistence_count": 2,
  "recovery_count": 2,
  "severity": "HIGH"
}
```

---

## 4. Execution and Evaluation Endpoints

### `POST /portfolios/{portfolio_id}/factor-monitoring/run`
Execute an on-demand or scheduled factor surveillance run.

**Request Body:**
```json
{
  "portfolio_id": "PF_GROWTH_01",
  "factor_model_version_id": "d1c2b3a4-...",
  "as_of_date": "2026-02-02",
  "config_id": "cfg-uuid",
  "target_id": "tgt-uuid",
  "evaluate_thresholds": true,
  "publish_events": true
}
```

**Response (`200 OK`):**
Returns `FactorMonitoringRunDetailResponse` containing:
- `run_id`, `as_of_date`, `status`, `result_hash`
- `active_breach_count`, `warning_count`, `has_active_breaches`
- `drifts`: List of factor drift records with signed, absolute, and standardized values.
- `concentration`: Factor exposure and risk-based HHI, $N_{\text{eff}}$, and Top-N shares.
- `evaluations`: Granular metric evaluations with utilization percentages and headrooms.

---

## 5. Query Endpoints

### `GET /portfolios/{portfolio_id}/factor-monitoring`
Get the latest factor monitoring status for a portfolio.

### `GET /portfolios/{portfolio_id}/factor-monitoring/drift`
Query historical factor exposure drift records.

### `GET /portfolios/{portfolio_id}/factor-monitoring/concentration`
Query historical factor concentration metrics.

### `GET /factor-monitoring/breaches`
Query active or historical breaches across portfolios, filtered by `portfolio_id`, `factor_code`, or `status`.

### `POST /factor-monitoring/breaches/{breach_id}/acknowledge`
Acknowledge an active breach with auditor tracking.

**Request Body:**
```json
{
  "user_id": "RISK_OFFICER_01",
  "note": "Temporary tilt due to market rebalance"
}
```

