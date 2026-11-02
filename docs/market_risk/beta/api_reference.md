# M07.07 Portfolio Beta API Reference

The Portfolio Beta module exposes RESTful endpoints mounted under:
- `/api/v1/market-risk/beta`
- `/api/v1/portfolios/{portfolio_id}/risk/beta`

---

## 1. Security Beta Analysis

### `POST /api/v1/market-risk/beta/security`
Calculates OLS regression beta and econometric statistics for an individual security against a selected benchmark.

#### Request Body
```json
{
  "instrument_id": "INST_TCS_NSE",
  "benchmark_code": "NIFTY_50",
  "lookback_days": 60,
  "as_of": "2026-11-01",
  "model_type": "OLS_WITH_INTERCEPT"
}
```

#### Response
```json
{
  "instrument_id": "INST_TCS_NSE",
  "instrument_symbol": "TCS",
  "benchmark_id": "b1b75fa6-1e66-47b2-bdcf-fc8b1e4a11c2",
  "benchmark_code": "NIFTY_50",
  "benchmark_name": "Nifty 50 Index",
  "as_of_date": "2026-11-01T00:00:00Z",
  "lookback_days": 60,
  "beta_value": 0.842310,
  "alpha_value": 0.00014231,
  "r_squared": 0.5421,
  "adjusted_r_squared": 0.5342,
  "beta_standard_error": 0.098421,
  "beta_t_statistic": 8.5582,
  "p_value": 0.00000002,
  "ci_lower_95": 0.645312,
  "ci_upper_95": 1.039308,
  "residual_std_error": 0.008412,
  "sample_size": 60,
  "regression_status": "VALID"
}
```

---

## 2. Portfolio Beta Calculation

### `POST /api/v1/market-risk/beta/portfolio`
Calculates portfolio beta via either direct portfolio return regression or current-weight constituent implied aggregation.

#### Request Body (Weighted Implied)
```json
{
  "portfolio_id": "PORT_ALPHA_01",
  "benchmark_code": "NIFTY_50",
  "method": "CURRENT_WEIGHT_IMPLIED",
  "lookback_days": 60
}
```

#### Response
```json
{
  "calculation_code": "PORT_BETA_94D74381C4AB",
  "portfolio_id": "PORT_ALPHA_01",
  "benchmark_id": "b1b75fa6-1e66-47b2-bdcf-fc8b1e4a11c2",
  "benchmark_code": "NIFTY_50",
  "benchmark_name": "Nifty 50 Index",
  "as_of_date": "2026-11-01T00:00:00Z",
  "lookback_days": 60,
  "method": "CURRENT_WEIGHT_IMPLIED",
  "portfolio_beta": 1.064210,
  "sample_size": 60,
  "weight_basis": "CURRENT_WEIGHTS",
  "contributions": [
    {
      "asset_id": "INST_RELIANCE",
      "symbol": "RELIANCE",
      "weight": 0.600000,
      "individual_beta": 1.214000,
      "beta_contribution": 0.728400,
      "contribution_percentage": 68.4451
    },
    {
      "asset_id": "INST_INFY",
      "symbol": "INFY",
      "weight": 0.400000,
      "individual_beta": 0.839525,
      "beta_contribution": 0.335810,
      "contribution_percentage": 31.5549
    }
  ],
  "reconciliation_sum": 1.064210,
  "reconciliation_discrepancy": 0.0000000000,
  "regression_status": "VALID"
}
```

---

## 3. Direct vs Weighted Reconciliation

### `GET /api/v1/market-risk/beta/reconciliation`
Compares direct historical portfolio regression with constituent implied beta to analyze rebalancing and drift.

#### Parameters
- `portfolio_id`: Target portfolio UUID.
- `benchmark_code`: Benchmark identifier (default: `NIFTY_50`).
- `lookback_days`: Lookback window in days (default: 60).
- `as_of`: Evaluation date.

#### Response
```json
{
  "portfolio_id": "PORT_ALPHA_01",
  "benchmark_code": "NIFTY_50",
  "as_of_date": "2026-11-01T00:00:00Z",
  "direct_beta": 1.042100,
  "weighted_beta": 1.064210,
  "beta_discrepancy": -0.022110,
  "direct_r_squared": 0.8241,
  "explanation": "Differences between direct portfolio beta and current-weight implied beta arise from historical rebalancing, time-varying constituent weights, cash flow timing, and fee drag."
}
```

---

## 4. Benchmark Reference Management

- `POST /api/v1/market-risk/beta/benchmarks`: Register a market benchmark (code, name, market, currency, provider, return basis, time zone).
- `GET /api/v1/market-risk/beta/benchmarks`: List active registered benchmarks.
