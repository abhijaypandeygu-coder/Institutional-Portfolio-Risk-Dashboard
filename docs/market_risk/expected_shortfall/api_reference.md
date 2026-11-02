# M07.03 — Expected Shortfall (ES) API Reference

## Base Endpoints

- Portfolio Routes: `/api/v1/portfolios/{portfolio_id}/risk/expected-shortfall`
- Portfolio Group Routes: `/api/v1/portfolio-groups/{group_id}/risk/expected-shortfall`
- Configuration Routes: `/api/v1/risk/expected-shortfall`

---

### 1. Calculate Expected Shortfall
- **Endpoint**: `POST /api/v1/portfolios/{portfolio_id}/risk/expected-shortfall/calculate`
- **Request Body**:
```json
{
  "portfolio_id": "PORT_US_EQUITY_01",
  "methodology": "HISTORICAL_PORTFOLIO_RETURNS",
  "confidence_level": 0.975,
  "holding_horizon_days": 1,
  "lookback_period_days": 252,
  "quantile_method": "LINEAR_INTERPOLATION",
  "tail_weighting_method": "FRACTIONAL_BOUNDARY"
}
```
- **Response**: `200 OK`
```json
{
  "result_id": "ES_E49A28B3C10D",
  "portfolio_id": "PORT_US_EQUITY_01",
  "methodology": "HISTORICAL_PORTFOLIO_RETURNS",
  "confidence_level": "0.9750",
  "tail_probability": "0.0250",
  "holding_horizon_days": 1,
  "as_of_date": "2026-11-02",
  "valuation_base_amount": "100000.00",
  "reporting_currency": "USD",
  "var_return_percentage": "2.150000",
  "var_monetary_amount": "2150.00",
  "es_return_percentage": "2.850000",
  "es_monetary_amount": "2850.00",
  "tail_excess_monetary_amount": "700.00",
  "tail_excess_percentage": "32.558140",
  "es_to_var_ratio": "1.3256",
  "total_observations_count": 252,
  "expected_tail_observations": "6.30",
  "full_tail_observations_count": 7,
  "effective_tail_sample_size": "6.12",
  "boundary_weight": "0.300000",
  "tail_stability_status": "MODERATELY_STABLE",
  "calculation_status": "CALCULATED"
}
```

---

### 2. Confidence-Level Sensitivity
- **Endpoint**: `GET /api/v1/portfolios/{portfolio_id}/risk/expected-shortfall/confidence-comparison`
- **Query Parameters**:
  - `methodology`: `HISTORICAL_PORTFOLIO_RETURNS` | `HISTORICAL_SIMULATION` | `MONTE_CARLO`
  - `holding_horizon_days`: integer (default `1`)
- **Response**: `200 OK`
```json
{
  "portfolio_id": "PORT_US_EQUITY_01",
  "as_of_date": "2026-11-02",
  "methodology": "HISTORICAL_PORTFOLIO_RETURNS",
  "reporting_currency": "USD",
  "valuation_base_amount": "100000.00",
  "levels": [
    {
      "confidence_level": "0.9000",
      "tail_probability": "0.1000",
      "var_monetary_amount": "1450.00",
      "es_monetary_amount": "2120.00",
      "tail_excess_monetary_amount": "670.00",
      "tail_excess_percentage": "46.206897",
      "tail_stability": "STABLE"
    },
    {
      "confidence_level": "0.9500",
      "tail_probability": "0.0500",
      "var_monetary_amount": "1850.00",
      "es_monetary_amount": "2500.00",
      "tail_excess_monetary_amount": "650.00",
      "tail_excess_percentage": "35.135135",
      "tail_stability": "STABLE"
    },
    {
      "confidence_level": "0.9750",
      "tail_probability": "0.0250",
      "var_monetary_amount": "2150.00",
      "es_monetary_amount": "2850.00",
      "tail_excess_monetary_amount": "700.00",
      "tail_excess_percentage": "32.558140",
      "tail_stability": "MODERATELY_STABLE"
    }
  ]
}
```

---

### 3. Methodology Comparison
- **Endpoint**: `GET /api/v1/portfolios/{portfolio_id}/risk/expected-shortfall/methodology-comparison`
- **Query Parameters**:
  - `confidence_level`: Decimal (default `0.9750`)
- **Response**: `200 OK`
```json
{
  "portfolio_id": "PORT_US_EQUITY_01",
  "as_of_date": "2026-11-02",
  "reporting_currency": "USD",
  "valuation_base_amount": "100000.00",
  "confidence_level": "0.9750",
  "holding_horizon_days": 1,
  "historical_portfolio_returns": {
    "methodology": "HISTORICAL_PORTFOLIO_RETURNS",
    "var_monetary_amount": "2150.00",
    "es_monetary_amount": "2850.00",
    "tail_excess_monetary_amount": "700.00"
  },
  "historical_simulation": {
    "methodology": "HISTORICAL_SIMULATION",
    "var_monetary_amount": "2140.00",
    "es_monetary_amount": "2835.00",
    "tail_excess_monetary_amount": "695.00"
  },
  "monte_carlo": {
    "methodology": "MONTE_CARLO",
    "var_monetary_amount": "2155.00",
    "es_monetary_amount": "2860.00",
    "tail_excess_monetary_amount": "705.00"
  },
  "max_absolute_es_difference": "25.00",
  "divergence_percentage": "0.874126"
}
```

