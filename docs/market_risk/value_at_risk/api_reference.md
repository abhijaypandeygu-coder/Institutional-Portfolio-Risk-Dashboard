# M07.02 — Value at Risk (VaR) API Reference

## Endpoints Overview

Base path: `/api/v1/portfolios/{portfolio_id}/risk/var` and `/api/v1/risk/var`

---

### 1. Calculate Value at Risk
- **Path**: `POST /api/v1/portfolios/{portfolio_id}/risk/var/calculate`
- **Description**: Executes a VaR calculation for the portfolio using Historical, Parametric, or Monte Carlo methodologies.
- **Request Body**:
```json
{
  "portfolio_id": "PORT_US_EQUITY_01",
  "methodology": "PARAMETRIC",
  "confidence_level": 0.99,
  "holding_horizon_days": 1,
  "distribution_assumption": "NORMAL",
  "lookback_period_days": 252,
  "simulation_count": 10000,
  "random_seed": 42
}
```
- **Response**: `200 OK`
```json
{
  "result_id": "VAR_4F9C21A04B11",
  "portfolio_id": "PORT_US_EQUITY_01",
  "methodology": "PARAMETRIC",
  "confidence_level": "0.9900",
  "holding_horizon_days": 1,
  "as_of_date": "2026-11-02",
  "valuation_base_amount": "100000.00",
  "reporting_currency": "USD",
  "signed_loss_quantile": "0.046527",
  "var_return_percentage": "4.652700",
  "var_monetary_amount": "4652.70",
  "distribution_assumption": "NORMAL",
  "lookback_observations": 252,
  "tail_observations_count": 2,
  "portfolio_period_volatility": "0.02000000",
  "calculation_status": "CALCULATED",
  "data_quality_status": "PASSED",
  "risk_contributions": [
    {
      "entity_id": "INST_AAPL",
      "entity_name": "Apple Inc.",
      "weight_percentage": "60.00",
      "marginal_var": "0.04652700",
      "component_var_amount": "2791.62",
      "percentage_of_total_var": "60.00",
      "is_additive": true
    }
  ]
}
```

---

### 2. Multi-Model VaR Comparison
- **Path**: `GET /api/v1/portfolios/{portfolio_id}/risk/var/model-comparison`
- **Query Parameters**:
  - `confidence_level`: Decimal (default `0.9900`)
  - `holding_horizon_days`: Integer (default `1`)
  - `as_of`: Optional Date (format `YYYY-MM-DD`)
- **Response**: `200 OK`
```json
{
  "portfolio_id": "PORT_US_EQUITY_01",
  "as_of_date": "2026-11-02",
  "reporting_currency": "USD",
  "valuation_base_amount": "100000.00",
  "historical_var": {
    "methodology": "HISTORICAL",
    "var_monetary_amount": "4650.00",
    "var_return_percentage": "4.650000",
    "confidence_level": "0.9900",
    "holding_horizon_days": 1
  },
  "parametric_var": {
    "methodology": "PARAMETRIC",
    "var_monetary_amount": "4652.70",
    "var_return_percentage": "4.652700",
    "confidence_level": "0.9900",
    "holding_horizon_days": 1
  },
  "monte_carlo_var": {
    "methodology": "MONTE_CARLO",
    "var_monetary_amount": "4648.50",
    "var_return_percentage": "4.648500",
    "confidence_level": "0.9900",
    "holding_horizon_days": 1
  },
  "max_absolute_discrepancy_amount": "4.20",
  "divergence_percentage": "0.0903"
}
```

---

### 3. Historical VaR Trend
- **Path**: `GET /api/v1/portfolios/{portfolio_id}/risk/var/historical-trend`
- **Query Parameters**:
  - `methodology`: Optional `VaRMethodology`
  - `lookback_points`: Integer (default `30`)
- **Response**: `200 OK`
```json
{
  "portfolio_id": "PORT_US_EQUITY_01",
  "data_points": [
    {
      "result_id": "VAR_4F9C21A04B11",
      "as_of_date": "2026-11-02",
      "var_monetary_amount": "4652.70",
      "var_return_percentage": "4.652700",
      "trend_direction": "STABLE"
    }
  ],
  "average_var_amount": "4652.70",
  "peak_var_amount": "4652.70",
  "min_var_amount": "4652.70"
}
```
