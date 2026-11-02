# M08.07 Factor Correlation API Reference

Base URL: `/api/v1/factor-correlation`

---

## 1. Configurations

### POST `/configs`
Create an immutable, versioned Factor Correlation Configuration.

**Request Body:**
```json
{
  "config_code": "CFG_CORR_DAILY_60D",
  "config_name": "Standard Pearson 60D Factor Correlation",
  "description": "Daily factor correlation with 60-day window",
  "factor_model_id": "model_uuid",
  "factor_model_version_id": "model_ver_uuid",
  "correlation_method": "PEARSON",
  "observation_frequency": "DAILY",
  "return_convention": "SIMPLE",
  "currency_basis": "INR",
  "missing_data_policy": "LISTWISE_COMPLETE",
  "estimation_window": 60,
  "minimum_observations": 20,
  "confidence_level": "0.95"
}
```

**Response (`201 Created`):**
Returns `FactorCorrelationConfigResponse` with deterministic `config_hash`.

### GET `/configs`
List all registered factor correlation configurations.

### GET `/configs/{config_id}`
Retrieve a specific configuration by ID.

---

## 2. Correlation Matrix Calculation & Snapshots

### POST `/calculate`
Compute full $K \times K$ inter-factor correlation matrix and pairwise statistics.

**Request Body:**
```json
{
  "config_id": "CORR_CFG_BFCCAC2D1CA3",
  "factor_model_version_id": "model_ver_uuid",
  "as_of_date": "2026-02-15",
  "correlation_method": "PEARSON",
  "estimation_window": 60
}
```

**Response (`200 OK`):**
Returns `FactorCorrelationRunResponse` with execution metadata, observation counts, spectral diagnostics (`is_positive_semidefinite`, `condition_number`, `matrix_rank`), and all evaluated pairs.

### GET `/matrices/{matrix_id}`
Retrieve a pinned $K \times K$ factor correlation matrix snapshot by ID.

**Response (`200 OK`):**
```json
{
  "matrix_id": "SNAP_MAT_UUID",
  "run_id": "RUN_UUID",
  "dimension": 5,
  "factor_ordering": ["MKT", "SMB", "HML", "MOM", "QMJ"],
  "correlation_matrix": [[1.0, 0.15, ...], ...],
  "is_symmetric": true,
  "is_positive_semidefinite": true,
  "condition_number": 8.42,
  "result_hash": "..."
}
```

---

## 3. Authoritative Factor Covariance Estimation

### POST `/covariance/calculate`
Calculates and caches the authoritative factor covariance matrix consumed by M08.05 Systematic Risk and M08.04 Factor Attribution.

**Request Body:**
```json
{
  "factor_model_id": "model_uuid",
  "factor_model_version_id": "model_ver_uuid",
  "as_of_date": "2026-02-15",
  "covariance_method": "LEDOIT_WOLF",
  "estimation_window": 252,
  "observation_frequency": "DAILY",
  "annualization_factor": "252.00",
  "decay_factor": "0.94",
  "shrinkage_target": "IDENTITY",
  "regularize_if_non_psd": true
}
```

**Response (`200 OK`):**
Returns `FactorCovarianceSnapshotResponse` containing `covariance_matrix_period`, `covariance_matrix_annualized`, `correlation_matrix`, and `factor_volatilities_annualized`. Guarantees mathematical consistency:
$$\boldsymbol{\Sigma}_F = \mathbf{D} \mathbf{P}_F \mathbf{D}$$

### GET `/covariance/{snapshot_id}`
Retrieve an authoritative factor covariance snapshot by ID.

---

## 4. Rolling Relationships

### POST `/rolling`
Calculate rolling correlation, covariance, signed delta, absolute strength delta, percentile rank, and stability category.

**Request Body:**
```json
{
  "factor_model_version_id": "model_ver_uuid",
  "factor_a_code": "MKT",
  "factor_b_code": "VAL",
  "as_of_date": "2026-02-15",
  "window_length": 60,
  "min_observations": 20,
  "baseline_window": 252
}
```

**Response (`200 OK`):**
Returns `RollingFactorCorrelationResponse` with point-in-time metrics, historical series, and `stability_status` (`STABLE_POSITIVE`, `SIGN_REVERSAL`, `HIGH_VOLATILITY_RELATIONSHIP`, etc.).

---

## 5. Regime Detection & Alerts

### POST `/regimes/evaluate`
Evaluate factor co-movement regimes and detect structural breaks for all factor pairs in a model version.

**Request Body:**
```json
{
  "factor_model_version_id": "model_ver_uuid",
  "as_of_date": "2026-02-15",
  "window_length": 60,
  "high_positive_threshold": "0.75",
  "high_negative_threshold": "-0.75",
  "rapid_change_threshold": "0.30",
  "confirmation_observations": 2
}
```

**Response (`200 OK`):**
Returns `FactorRegimeEvaluationResponse` with evaluated pairs count, active alerts count, and detailed alert records.

### GET `/regimes/alerts`
Query active or historical regime alerts filtered by model version and date.

**Query Parameters:**
- `factor_model_version_id` (required): Target factor model version ID
- `as_of_date` (optional): Query date
- `status` (optional): Filter by `ACTIVE`, `ACKNOWLEDGED`, `RECOVERED`

