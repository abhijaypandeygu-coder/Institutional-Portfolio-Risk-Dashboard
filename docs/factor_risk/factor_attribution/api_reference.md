# M08.04 — Factor Attribution API Reference

Base URL prefix: `/api/v1/factor-attribution`

---

## 1. Configurations

### POST `/api/v1/factor-attribution/configs`
Create an authoritative versioned attribution configuration.

**Request:**
```json
{
  "config_code": "ATTR_FF3_DAILY",
  "config_name": "Fama-French 3-Factor Attribution Profile",
  "description": "Standard daily Carino linking with sample covariance",
  "factor_model_id": "MOD_FF3_01",
  "factor_model_version_id": "VER_FF3_01",
  "attribution_mode": "TOP_DOWN",
  "return_basis": "EXCESS_RETURN",
  "linking_method": "CARINO_LOGARITHMIC",
  "covariance_method": "SAMPLE",
  "annualization_factor": "252.00",
  "reconciliation_tolerance": "0.000001",
  "coverage_threshold_pct": "80.00",
  "currency_basis": "INR"
}
```

**Response:** `201 Created` with `FactorAttributionConfigResponse`.

---

### GET `/api/v1/factor-attribution/configs`
List all registered attribution configurations.

### GET `/api/v1/factor-attribution/configs/{config_id}`
Retrieve a specific configuration by ID.

---

## 2. Factor Covariance Matrix

### POST `/api/v1/factor-attribution/covariance/estimate`
Estimate and persist a factor covariance matrix snapshot with PSD and condition number verification.

**Request:**
```json
{
  "factor_model_version_id": "VER_FF3_01",
  "as_of_date": "2026-10-30",
  "lookback_days": 252,
  "covariance_method": "SAMPLE",
  "annualization_factor": "252.00"
}
```

---

## 3. Factor Return Attribution

### POST `/api/v1/factor-attribution/return/run`
Execute factor return attribution across a historical window using single-period or Carino multi-period compounding.

**Request:**
```json
{
  "config_id": "CFG_ATTR_01",
  "portfolio_id": "PORT_INDIA_01",
  "start_date": "2026-09-15",
  "end_date": "2026-10-30",
  "attribution_mode": "TOP_DOWN",
  "linking_method": "CARINO_LOGARITHMIC"
}
```

---

## 4. Factor Risk Attribution

### POST `/api/v1/factor-attribution/risk/run`
Execute systematic Euler factor risk decomposition into variance, volatility, and marginal risk contributions.

**Request:**
```json
{
  "config_id": "CFG_ATTR_01",
  "portfolio_id": "PORT_INDIA_01",
  "as_of_date": "2026-10-30",
  "attribution_mode": "TOP_DOWN",
  "covariance_method": "SAMPLE"
}
```

---

## 5. Audit & Comparison

### GET `/api/v1/factor-attribution/reconciliation/{reconciliation_id}`
Retrieve the mathematical reconciliation bridge validating return or risk allocation integrity.

### POST `/api/v1/factor-attribution/compare`
Compare return and risk attributions across consecutive periods or between multiple portfolios.

