# M08.06 Idiosyncratic Risk API Reference

## Base Path: `/api/v1/idiosyncratic-risk`

All endpoints return structured JSON with full deterministic audit lineage.

---

### 1. Configuration Management

#### `POST /configs`
Creates or retrieves an existing immutable residual risk configuration.
- **Request Body:**
  ```json
  {
    "config_code": "CFG_IDIO_DAILY",
    "config_name": "Daily Idiosyncratic Risk Config",
    "description": "Standard daily sample config",
    "factor_model_id": "FM_01",
    "factor_model_version_id": "FMV_01",
    "variance_estimator": "SAMPLE",
    "observation_frequency": "DAILY",
    "annualization_factor": 252.0,
    "decay_factor": 0.94,
    "minimum_observations": 20,
    "outlier_z_threshold": 3.0
  }
  ```
- **Response:** `201 Created` with full `ResidualConfigResponse`.

#### `GET /configs`
Lists available configurations.

---

### 2. Instrument Residual Volatility

#### `POST /instruments/calculate`
Calculates residual variance, volatility, and robust MAD scale for a single holding.
- **Request Body:**
  ```json
  {
    "config_id": "IDIO_CFG_01",
    "instrument_id": "INST_AAPL",
    "as_of_date": "2026-10-30"
  }
  ```
- **Response:** `200 OK`
  ```json
  {
    "run_id": "IDIO_VOL_123",
    "instrument_id": "INST_AAPL",
    "as_of_date": "2026-10-30",
    "observation_count": 252,
    "residual_mean": 0.00012,
    "residual_variance_period": 0.00015,
    "residual_volatility_annualized": 0.1945,
    "robust_mad_scale_annualized": 0.1882
  }
  ```

---

### 3. Residual Covariance Matrix

#### `POST /covariance/estimate`
Computes or retrieves a pinned residual covariance matrix snapshot.
- **Request Body:**
  ```json
  {
    "factor_model_version_id": "FMV_01",
    "as_of_date": "2026-10-30",
    "instrument_ids": ["INST_AAPL", "INST_MSFT"],
    "use_diagonal": false
  }
  ```
- **Response:** `200 OK` with spectral diagnostics (`min_eigenvalue`, `condition_number`, `is_positive_semidefinite`).

---

### 4. Portfolio Idiosyncratic Risk & Euler Attribution

#### `POST /portfolios/calculate`
Executes portfolio-level idiosyncratic risk estimation and exact Euler attribution.
- **Request Body:**
  ```json
  {
    "config_id": "IDIO_CFG_01",
    "portfolio_id": "PORT_CORE",
    "as_of_date": "2026-10-30",
    "use_diagonal": false
  }
  ```
- **Response:** `200 OK`
  ```json
  {
    "portfolio_id": "PORT_CORE",
    "as_of_date": "2026-10-30",
    "portfolio_idiosyncratic_variance_annualized": 0.0724,
    "portfolio_idiosyncratic_volatility_annualized": 0.26907,
    "diagonal_baseline_variance_annualized": 0.0580,
    "covariance_effect_annualized": 0.0144,
    "diversification_benefit_annualized": -0.0144,
    "absolute_contribution_hhi": 0.5098,
    "effective_number_of_risk_contributors": 1.961,
    "is_reconciled": true,
    "security_contributions": [...],
    "issuer_contributions": [...]
  }
  ```

---

### 5. Econometric Residual Diagnostics

#### `POST /diagnostics/run`
Runs normality, autocorrelation, heteroskedasticity, and structural break tests.
- **Request Body:**
  ```json
  {
    "config_id": "IDIO_CFG_01",
    "instrument_id": "INST_AAPL",
    "as_of_date": "2026-10-30"
  }
  ```
- **Response:** `200 OK`
  ```json
  {
    "instrument_id": "INST_AAPL",
    "observation_count": 252,
    "skewness": 0.041,
    "excess_kurtosis": 0.125,
    "jarque_bera_p_value": 0.8124,
    "lag1_autocorrelation": -0.014,
    "ljung_box_p_value": 0.745,
    "arch_lm_p_value": 0.652,
    "has_structural_shift": false,
    "model_quality_status": "ACCEPTABLE",
    "warning_messages": [],
    "outliers": []
  }
  ```
