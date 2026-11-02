# M08.02 — Factor Exposure: API Reference

## 1. Factor Returns Ingestion

### `POST /api/v1/factor-exposures/returns`
Ingests point-in-time historical factor return series observations.
- **Request Body:**
  ```json
  {
    "factor_id": "factor-uuid",
    "factor_code": "MKT_INDIA",
    "version_id": "version-uuid",
    "market_scope": "INDIA",
    "currency": "INR",
    "frequency": "DAILY",
    "return_convention": "SIMPLE",
    "observations": [
      {
        "trading_date": "2026-10-01",
        "return_value": "0.0085",
        "risk_free_rate": "0.0002"
      }
    ]
  }
  ```

---

## 2. Estimation Configuration Profiles

### `POST /api/v1/factor-exposures/configs`
Registers a version-controlled multi-factor estimation profile with deterministic SHA-256 hash.
- **Request Body:**
  ```json
  {
    "config_code": "ROLLING_252D_OLS",
    "config_name": "Standard Rolling 252-Day Factor Regression",
    "description": "Daily excess-return OLS with HC3 robust standard errors",
    "factor_model_id": "model-uuid",
    "factor_model_version_id": "model-ver-uuid",
    "estimation_method": "ROLLING_OLS",
    "lookback_observations": 252,
    "return_frequency": "DAILY",
    "dependent_return_basis": "EXCESS_TOTAL_RETURN",
    "include_intercept": true,
    "minimum_observations": 30,
    "min_observations_per_param_multiplier": 5,
    "standard_error_method": "HC3_HETEROSKEDASTICITY_ROBUST",
    "currency_basis": "INR"
  }
  ```

### `GET /api/v1/factor-exposures/configs`
Lists all available estimation profiles.

---

## 3. Factor Loading Estimation Execution

### `POST /api/v1/factor-exposures/estimate`
Executes multi-factor regression solver across target securities.
- **Request Body:**
  ```json
  {
    "config_id": "config-uuid",
    "factor_model_id": "model-uuid",
    "factor_model_version_id": "model-version-uuid",
    "as_of_date": "2026-11-02",
    "instrument_ids": ["INST_RELIANCE", "INST_TCS"]
  }
  ```
- **Response:** `FactorLoadingRunResponse`

### `GET /api/v1/factor-exposures/runs/{run_id}`
Retrieves execution run status, data window, successful/failed counts.

---

## 4. Instrument Factor Loadings

### `GET /api/v1/instruments/{instrument_id}/factor-exposures`
Retrieves latest factor loadings, standard errors, t-stats, confidence intervals, R2, and VIF for a security.
- **Query Parameters:**
  - `factor_model_version_id` (optional): Filter by specific model version.

---

## 5. Portfolio Factor Exposure

### `GET /api/v1/portfolios/{portfolio_id}/factor-exposures`
Aggregates security-level loadings into portfolio factor exposure using signed NAV weights.
- **Query Parameters:**
  - `factor_model_version_id`: Target factor model version ID (mandatory).
  - `as_of_date` (optional): Evaluation date.
  - `weighting_basis`: `NAV_WEIGHTED` (default) or `GROSS_NORMALIZED`.
- **Response:** `PortfolioFactorExposureResponse` with signed NAV exposures, tilt classification, and absolute coverage %.

### `GET /api/v1/portfolios/{portfolio_id}/factor-exposures/history`
Retrieves historical snapshots of portfolio factor exposures over time.

---

## 6. Exposure Change Attribution

### `POST /api/v1/factor-exposures/compare`
Compares portfolio exposure between two dates and performs symmetric exact decomposition into Weight vs. Loading effects.
- **Request Body:**
  ```json
  {
    "portfolio_id": "PORT_ALPHA",
    "earlier_date": "2026-10-01",
    "later_date": "2026-11-02",
    "factor_code": "MKT_INDIA",
    "factor_model_version_id": "model-ver-uuid"
  }
  ```
- **Response:**
  ```json
  {
    "portfolio_id": "PORT_ALPHA",
    "factor_code": "MKT_INDIA",
    "earlier_date": "2026-10-01",
    "later_date": "2026-11-02",
    "earlier_exposure": "1.000000",
    "later_exposure": "1.020000",
    "total_change": "0.020000",
    "percentage_change": "2.0000",
    "weight_effect": "0.010000",
    "loading_effect": "0.010000",
    "entry_exit_effect": "0.000000",
    "unreconciled_residual": "0.000000",
    "comparability_status": "COMPARABLE",
    "instruments": [...]
  }
  ```
