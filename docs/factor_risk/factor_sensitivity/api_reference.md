# M08.03 Factor Sensitivity API Reference

Base URL: `/api/v1`

---

### 1. Model Configuration Endpoints

#### `POST /api/v1/factor-sensitivity/configs`
Registers an immutable, versioned factor sensitivity regression configuration profile.
- **Request Body:**
  ```json
  {
    "config_code": "OLS_HC3_1Y_DAILY",
    "config_name": "Standard 1Y Rolling OLS Profile",
    "description": "Multi-factor time-series regression with HC3 robust standard errors",
    "model_family": "OLS",
    "factor_model_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "factor_model_version_id": "3fa85f64-5717-4562-b3fc-2c963f66afa7",
    "include_intercept": true,
    "standard_error_method": "HC3_HETEROSKEDASTICITY_ROBUST",
    "confidence_level": "0.95",
    "ewls_decay_factor": "0.9400",
    "ridge_lambda": "0.0100",
    "quantile_tau": "0.50",
    "dependent_return_basis": "EXCESS_TOTAL_RETURN",
    "return_type": "SIMPLE",
    "currency_basis": "INR",
    "window_config": {
      "window_type": "ROLLING",
      "lookback_observations": 252,
      "frequency": "DAILY",
      "missing_data_policy": "LISTWISE_COMPLETE",
      "minimum_observations": 30,
      "min_observations_per_param_multiplier": 5,
      "minimum_coverage_percentage": "80.00"
    }
  }
  ```
- **Response:** `201 Created` with `ModelConfigResponse` containing SHA-256 `config_hash`.

#### `GET /api/v1/factor-sensitivity/configs`
Lists all factor sensitivity configurations.

#### `GET /api/v1/factor-sensitivity/configs/{config_id}`
Retrieves configuration profile by unique `config_id`.

---

### 2. Estimation Execution Endpoints

#### `POST /api/v1/factor-sensitivity/estimate`
Executes multi-factor regression sensitivity estimation for an individual instrument or direct portfolio.
- **Request Body:**
  ```json
  {
    "config_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "target_type": "INSTRUMENT",
    "target_id": "INST_INFY",
    "target_listing_id": null,
    "as_of_date": "2026-10-30",
    "custom_window_start": null,
    "custom_window_end": null
  }
  ```
- **Response:** `200 OK` with `SensitivityRunResponse`, containing estimated factor coefficients (`beta_k`), standard errors, t-statistics, raw and FDR-adjusted p-values, confidence intervals, and complete model diagnostics (`r_squared`, `condition_number`, `vif`, `durbin_watson_stat`, `jarque_bera_p_value`).

#### `GET /api/v1/factor-sensitivity/runs/{run_id}`
Retrieves the execution details and persistent diagnostic output of a sensitivity run.

#### `GET /api/v1/factor-sensitivity/{target_type}/{target_id}/coefficients`
Retrieves point-in-time historical estimated coefficients for a target security or portfolio.
- **Query Parameters:** `factor_code` (optional), `start_date` (optional), `end_date` (optional).

---

### 3. Stability & Structural Breaks

#### `GET /api/v1/factor-sensitivity/{target_type}/{target_id}/stability`
Computes rolling stability metrics (mean, std, min, max, sign inversions, relative change, and stability status) across historical runs.
- **Query Parameters:** `factor_code` (required).
- **Response:** `SensitivityStabilityResponse`.

#### `POST /api/v1/factor-sensitivity/stability/break-test`
Executes a formal Chow F-test for structural breaks around a candidate date.
- **Request Body:**
  ```json
  {
    "stability_id": "3fa85f64-5717-4562-b3fc-2c963f66afa8",
    "candidate_break_date": "2026-06-01",
    "test_type": "CHOW_TEST"
  }
  ```
- **Response:** `StructuralBreakTestResponse` with F-statistic, p-value, 95% critical value, and `result_status` (`BREAK_DETECTED` or `NO_BREAK_DETECTED`).

---

### 4. Direct Sensitivity vs. Weighted Exposure Reconciliation

#### `GET /api/v1/portfolios/{portfolio_id}/factor-sensitivity/reconciliation`
Compares direct portfolio return time-series regression sensitivity ($R_{p,t} = \alpha_p + \sum \beta_{p,k} F_{k,t} + \epsilon_{p,t}$) against bottom-up holdings-weighted factor exposure ($\sum w_i \beta_{i,k}$) from M08.02.
- **Query Parameters:** `as_of_date` (optional), `config_id` (optional).
- **Response:** `PortfolioSensitivityReconciliationResponse` isolating discrepancies attributable to active rebalancing, cash drag, or idiosyncratic non-linearities.
