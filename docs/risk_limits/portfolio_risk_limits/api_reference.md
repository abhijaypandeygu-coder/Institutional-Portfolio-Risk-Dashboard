# M11.01 — Portfolio Risk Limits: API Reference

## Base Path
`/api/v1/risk-limits`

---

## Endpoints

### 1. Health Check
- **Endpoint:** `GET /health`
- **Description:** Verifies that the Portfolio Risk Limits engine is operational.
- **Response:**
  ```json
  {
    "status": "healthy",
    "module": "M11.01 - Portfolio Risk Limits",
    "description": "Portfolio Risk Limits & Threshold Evaluation Engine"
  }
  ```

---

### 2. Create Risk Limit Profile
- **Endpoint:** `POST /profiles`
- **Status Code:** `201 Created`
- **Request Body:**
  ```json
  {
    "profile_code": "CONS_WEALTH_01",
    "profile_name": "Conservative Wealth Profile",
    "description": "Conservative profile with tight drawdown and VaR controls",
    "profile_category": "CONSERVATIVE",
    "mandate_type": "WEALTH_PRESERVATION",
    "base_currency_policy": "USD",
    "initial_limits": [
      {
        "limit_code": "VAR_NAV_CONS",
        "limit_name": "99% 1D VaR",
        "risk_category": "VAR",
        "metric_identifier": "VAR_99_1D",
        "limit_type": "NAV_RELATIVE",
        "warning_threshold": "1.0",
        "hard_threshold": "1.5",
        "threshold_unit": "PERCENT_NAV",
        "confidence_level": 0.99,
        "risk_horizon_days": 1,
        "risk_methodology": "HISTORICAL"
      },
      {
        "limit_code": "VOL_CONS",
        "limit_name": "Max Volatility",
        "risk_category": "VOLATILITY",
        "metric_identifier": "REALIZED_VOL",
        "limit_type": "PERCENTAGE",
        "warning_threshold": "0.08",
        "hard_threshold": "0.10",
        "threshold_unit": "ANNUALIZED_VOL"
      }
    ]
  }
  ```

---

### 3. List Profiles
- **Endpoint:** `GET /profiles`
- **Response:** Array of `ProfileResponse` objects.

---

### 4. Get Profile Details
- **Endpoint:** `GET /profiles/{profile_code}`
- **Response:** Single `ProfileResponse` matching code or ID.

---

### 5. Assign Profile to Portfolio
- **Endpoint:** `POST /assignments`
- **Status Code:** `201 Created`
- **Request Body:**
  ```json
  {
    "profile_id": "PROFILE_UUID",
    "target_type": "PORTFOLIO",
    "target_id": "PORT_API_902",
    "precedence": 1,
    "assigned_by": "risk_officer"
  }
  ```

---

### 6. Evaluate Portfolio Limits
- **Endpoint:** `POST /portfolios/{portfolio_id}/evaluate`
- **Request Body:**
  ```json
  {
    "portfolio_id": "PORT_API_902",
    "observed_var_monetary": "85000.0",
    "observed_volatility_annualized": "0.065",
    "portfolio_nav": "5000000.0"
  }
  ```
- **Response:**
  ```json
  {
    "portfolio_id": "PORT_API_902",
    "profile_code": "CONS_WEALTH_01",
    "profile_version_number": 1,
    "evaluated_at": "2026-11-16T10:52:30.123456Z",
    "overall_status": "HARD_LIMIT_EXCEEDED",
    "utilizations": [
      {
        "limit_id": "...",
        "limit_code": "VAR_NAV_CONS",
        "risk_category": "VAR",
        "metric_identifier": "VAR_99_1D",
        "observed_metric_value": "1.7000",
        "warning_threshold": "1.0000",
        "hard_threshold": "1.5000",
        "warning_utilization_pct": "170.00",
        "hard_utilization_pct": "113.33",
        "headroom": "-0.2000",
        "unit": "PERCENT_NAV",
        "evaluation_status": "HARD_LIMIT_EXCEEDED"
      }
    ],
    "narrative": "Portfolio 'PORT_API_902' evaluated against profile 'CONS_WEALTH_01'. Overall state: HARD_LIMIT_EXCEEDED."
  }
  ```
