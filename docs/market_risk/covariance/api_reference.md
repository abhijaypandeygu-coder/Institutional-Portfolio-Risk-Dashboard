# M07.06 — Covariance Analysis API Reference

## 1. Overview
The **Covariance Analysis Engine** endpoints are mounted under:
- `/api/v1/market-risk/covariance` (Pairwise, full matrix, rolling, portfolio variance, and cross-portfolio endpoints)
- `/api/v1/portfolios/{portfolio_id}/risk/covariance` (Portfolio-specific covariance matrix and risk contributions)

All operations are executed strictly on aligned return vectors ($R_t$) using decimal-return squared units ($R^2$).

---

## 2. API Endpoints

### 2.1 Calculate Pairwise Covariance
**`POST /api/v1/market-risk/covariance/pairwise`**

#### Request Body:
```json
{
  "asset_a_id": "INST_AAPL_01",
  "asset_b_id": "INST_MSFT_01",
  "lookback_days": 60,
  "as_of": "2026-02-04",
  "estimator": "SAMPLE",
  "denominator_policy": "UNBIASED_SAMPLE",
  "annualize": true,
  "annualization_factor": 252.0
}
```

#### Response (200 OK):
```json
{
  "asset_a_id": "INST_AAPL_01",
  "asset_b_id": "INST_MSFT_01",
  "asset_a_symbol": "AAPL",
  "asset_b_symbol": "MSFT",
  "as_of_date": "2026-02-04T00:00:00Z",
  "lookback_days": 60,
  "estimator": "SAMPLE",
  "denominator_policy": "UNBIASED_SAMPLE",
  "covariance_value": "0.00018452",
  "annualized_covariance": "0.04649904",
  "variance_a": "0.00021420",
  "variance_b": "0.00028912",
  "std_dev_a": "0.014635",
  "std_dev_b": "0.017003",
  "correlation_coefficient": "0.741520",
  "sample_size": 42,
  "units": "decimal-return squared"
}
```

---

### 2.2 Generate Covariance Matrix with PSD Diagnostics
**`POST /api/v1/market-risk/covariance/matrix`**

#### Request Body:
```json
{
  "portfolio_id": "PORT_TECH_01",
  "lookback_days": 60,
  "as_of": "2026-02-04",
  "estimator": "SAMPLE",
  "denominator_policy": "UNBIASED_SAMPLE",
  "repair_psd": true,
  "transformation_method": "SPECTRAL_CLIPPING"
}
```

#### Response (200 OK):
```json
{
  "matrix_id": "281b6f98-...",
  "matrix_code": "COV_MAT_790F32AA9A12",
  "portfolio_id": "PORT_TECH_01",
  "as_of_date": "2026-02-04T00:00:00Z",
  "lookback_days": 60,
  "estimator": "SAMPLE",
  "dimension": 2,
  "asset_ids": ["INST_AAPL_01", "INST_MSFT_01"],
  "asset_symbols": ["AAPL", "MSFT"],
  "matrix": [
    ["0.00021420", "0.00018452"],
    ["0.00018452", "0.00028912"]
  ],
  "psd_status": "VALID_PSD",
  "min_eigenvalue": "0.00006241",
  "max_eigenvalue": "0.00044091",
  "condition_number": "7.0647",
  "negative_eigenvalues_count": 0,
  "is_symmetric": true,
  "max_symmetry_discrepancy": "0.0000000000",
  "completeness_ratio": "1.0000",
  "average_variance": "0.00025166",
  "transformed_matrix": null,
  "transformation_info": null
}
```

---

### 2.3 Calculate Portfolio Covariance & Risk Contributions
**`POST /api/v1/market-risk/covariance/portfolio`**

Computes portfolio variance ($\sigma_p^2 = \mathbf{w}^T \Sigma \mathbf{w}$), portfolio volatility, and asset-level marginal and component contributions.

#### Request Body:
```json
{
  "portfolio_id": "PORT_TECH_01",
  "lookback_days": 60,
  "as_of": "2026-02-04",
  "weight_basis": "PORTFOLIO_NAV",
  "annualization_factor": 252.0
}
```

#### Response (200 OK):
```json
{
  "calculation_code": "PORT_COV_89ABCDEF0123",
  "portfolio_id": "PORT_TECH_01",
  "as_of_date": "2026-02-04T00:00:00Z",
  "matrix_id": "281b6f98-...",
  "weight_basis": "PORTFOLIO_NAV",
  "period_portfolio_variance": "0.00021809",
  "period_portfolio_volatility": "0.014768",
  "annualized_portfolio_variance": "0.05495868",
  "annualized_portfolio_volatility": "0.234433",
  "annualization_factor": "252.0",
  "contributions": [
    {
      "asset_id": "INST_AAPL_01",
      "symbol": "AAPL",
      "weight": "0.500000",
      "marginal_contribution_variance": "0.00019936",
      "component_contribution_variance": "0.00009968",
      "variance_contribution_percentage": "45.7059",
      "marginal_contribution_volatility": "0.013499",
      "component_contribution_volatility": "0.006750",
      "volatility_contribution_percentage": "45.7059"
    },
    {
      "asset_id": "INST_MSFT_01",
      "symbol": "MSFT",
      "weight": "0.500000",
      "marginal_contribution_variance": "0.00023682",
      "component_contribution_variance": "0.00011841",
      "variance_contribution_percentage": "54.2941",
      "marginal_contribution_volatility": "0.016036",
      "component_contribution_volatility": "0.008018",
      "volatility_contribution_percentage": "54.2941"
    }
  ],
  "reconciliation_variance_sum": "0.00021809",
  "reconciliation_volatility_sum": "0.014768",
  "variance_discrepancy": "0.0000000000",
  "volatility_discrepancy": "0.0000000000"
}
```

---

### 2.4 Calculate Cross-Portfolio Covariance
**`POST /api/v1/market-risk/covariance/portfolio-pair`**

#### Request Body:
```json
{
  "portfolio_a_id": "PORT_GROWTH_01",
  "portfolio_b_id": "PORT_VALUE_01",
  "lookback_days": 60,
  "annualize": true
}
```

#### Response (200 OK):
```json
{
  "portfolio_a_id": "PORT_GROWTH_01",
  "portfolio_b_id": "PORT_VALUE_01",
  "as_of_date": "2026-02-04T00:00:00Z",
  "period_covariance": "0.00015420",
  "annualized_covariance": "0.03885840",
  "portfolio_a_variance": "0.00021809",
  "portfolio_b_variance": "0.00018540",
  "portfolio_a_volatility": "0.014768",
  "portfolio_b_volatility": "0.013616",
  "derived_correlation": "0.766842"
}
```

