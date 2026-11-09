# M10.05 — Correlation Shock API Reference

Mounted Base Path: `/api/v1/scenarios/correlation-shock`

## Endpoints

### 1. Create Correlation Shock Scenario
- **Method:** `POST /`
- **Status Code:** `201 Created`
- **Request Body:** `CorrelationShockScenarioCreate`
  ```json
  {
    "scenario_code": "SCEN_CORR_CONTAGION_01",
    "name": "Global Contagion Stress",
    "description": "Increases cross-asset correlations toward 0.85 with Higham repair.",
    "scenario_scope": "FULL_PORTFOLIO",
    "scenario_category": "DIVERSIFICATION_BREAKDOWN",
    "transformation_method": "INCREASE",
    "stress_target": 0.85,
    "stress_intensity": 0.50,
    "volatility_mode": "HOLD_CONSTANT",
    "matrix_repair_method": "EIGENVALUE_CLIPPING",
    "pair_rules": [
      {
        "entity_a_id": "EQ_INFY",
        "entity_b_id": "EQ_TCS",
        "entity_type": "INSTRUMENT",
        "target_correlation": 0.95,
        "stress_intensity": 1.0,
        "transformation_method": "CUSTOM_TARGET"
      }
    ]
  }
  ```
- **Response Body:** `CorrelationShockScenarioResponse`

---

### 2. List Scenarios
- **Method:** `GET /`
- **Query Parameters:** `portfolio_id` (optional)
- **Response Body:** `List[CorrelationShockScenarioResponse]`

---

### 3. Get Scenario Details
- **Method:** `GET /{scenario_id}`
- **Response Body:** `CorrelationShockScenarioResponse`

---

### 4. Standalone Matrix Validation
- **Method:** `POST /validate-matrix`
- **Request Body:** `MatrixValidateRequest`
  ```json
  {
    "matrix_data": [
      [1.0, 0.5],
      [0.5, 1.0]
    ],
    "symmetry_tol": 1e-6,
    "psd_tol": 1e-7
  }
  ```
- **Response Body:** `MatrixValidateResponse`
  ```json
  {
    "status": "VALID",
    "is_symmetric": true,
    "diagonal_valid": true,
    "bounds_valid": true,
    "is_psd": true,
    "minimum_eigenvalue": 0.5,
    "maximum_eigenvalue": 1.5,
    "matrix_rank": 2,
    "condition_number": 3.0,
    "negative_eigenvalue_count": 0,
    "warnings": []
  }
  ```

---

### 5. Execute Correlation Shock Scenario
- **Method:** `POST /{scenario_id}/execute`
- **Request Body:** `ExecuteScenarioRequest`
  Supports either portfolio lookup via database (`portfolio_id`) or custom ad-hoc simulation payloads (`custom_asset_ids`, `custom_weights`, `custom_volatilities`, `custom_matrix_data`).
- **Response Body:** `ExecutionResponse`
  Returns execution status, matrices across stages (baseline, raw stressed, repaired), matrix diagnostics, risk comparison KPIs (volatility, variance, average correlation, diversification benefit), and holding-level Euler risk contributions.
