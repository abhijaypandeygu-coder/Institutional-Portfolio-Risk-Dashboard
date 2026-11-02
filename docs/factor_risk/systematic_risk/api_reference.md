# M08.05 — Systematic Risk API Reference

Base URL prefix: `/api/v1/systematic-risk`

---

## 1. Risk Configurations

### POST `/api/v1/systematic-risk/configs`
Create a versioned systematic risk configuration.

**Request:**
```json
{
  "config_code": "SYS_FF3_DAILY",
  "config_name": "Fama-French 3-Factor Daily Risk Profile",
  "description": "Daily sample covariance systematic risk configuration",
  "factor_model_id": "MOD_FF3_01",
  "factor_model_version_id": "VER_FF3_01",
  "covariance_method": "SAMPLE",
  "observation_frequency": "DAILY",
  "annualization_factor": "252.00",
  "decay_factor": "0.94",
  "minimum_observations": 20,
  "coverage_threshold_pct": "80.00",
  "currency_basis": "INR"
}
```

---

## 2. Factor Covariance Estimation

### POST `/api/v1/systematic-risk/covariance/estimate`
Estimate or retrieve pinned factor covariance matrix snapshot with PSD and condition number verification.

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

## 3. Risk Calculations

### POST `/api/v1/systematic-risk/instruments/calculate`
Calculate instrument common-factor variance, volatility, and residual metrics.

**Request:**
```json
{
  "instrument_id": "INST_TCS_NSE",
  "config_id": "SYS_CFG_01",
  "as_of_date": "2026-10-30",
  "lookback_days": 252
}
```

### POST `/api/v1/systematic-risk/portfolios/calculate`
Calculate portfolio common-factor variance, cross-security covariance reconciliation, and model coverage.

**Request:**
```json
{
  "portfolio_id": "PORT_INDIA_01",
  "config_id": "SYS_CFG_01",
  "as_of_date": "2026-10-30",
  "lookback_days": 252
}
```

---

## 4. Factor Shock Scenarios

### POST `/api/v1/systematic-risk/scenarios`
Register a versioned factor shock scenario.

**Request:**
```json
{
  "scenario_code": "SCEN_MACRO_STRESS",
  "scenario_name": "Macro Market Stress Scenario",
  "factor_model_id": "MOD_FF3_01",
  "factor_model_version_id": "VER_FF3_01",
  "scenario_type": "MULTI_FACTOR",
  "shock_unit": "PERCENTAGE",
  "shocks": [
    {"factor_code": "MKT_INDIA", "shock_value": "-0.05"},
    {"factor_code": "SMB_INDIA", "shock_value": "-0.015"},
    {"factor_code": "HML_INDIA", "shock_value": "0.02"}
  ]
}
```

### POST `/api/v1/systematic-risk/scenarios/run`
Simulate the return and monetary impact of factor shocks.

---

## 5. Model Coverage Diagnostics

### GET `/api/v1/systematic-risk/portfolios/{portfolio_id}/coverage?as_of_date=2026-10-30`
Query portfolio coverage summary, holding-level statuses, absolute market weights, and missing factor diagnostics.

