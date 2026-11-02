# M07.08 Sharpe & Sortino Ratios API Reference

Mounted under:
- `/api/v1/market-risk/ratios`
- `/api/v1/portfolios/{portfolio_id}/risk/ratios`

---

## 1. Sharpe Ratio

### `POST /api/v1/market-risk/ratios/sharpe`
Calculates excess return relative to return volatility.

#### Request Body
```json
{
  "scope": "PORTFOLIO",
  "entity_id": "PORT_ALPHA_01",
  "risk_free_series_code": "RF_INR_3M",
  "lookback_days": 60,
  "denominator_policy": "PORTFOLIO_RETURN_VOLATILITY",
  "annualization_factor": 252.0
}
```

#### Response
```json
{
  "calculation_code": "SHARPE_49B2CA987A11",
  "scope": "PORTFOLIO",
  "entity_id": "PORT_ALPHA_01",
  "as_of_date": "2026-11-01T00:00:00Z",
  "lookback_days": 60,
  "currency": "INR",
  "mean_return_period": 0.00084512,
  "mean_risk_free_period": 0.00017124,
  "mean_excess_return_period": 0.00067388,
  "return_volatility_period": 0.00945122,
  "period_sharpe": 0.071301,
  "annualized_sharpe": 1.131868,
  "annualization_factor": 252.0,
  "sample_size": 60,
  "denominator_policy": "PORTFOLIO_RETURN_VOLATILITY",
  "status": "VALID"
}
```

---

## 2. Sortino Ratio

### `POST /api/v1/market-risk/ratios/sortino`
Calculates return above target relative to all-period downside semideviation.

#### Request Body
```json
{
  "scope": "PORTFOLIO",
  "entity_id": "PORT_ALPHA_01",
  "risk_free_series_code": "RF_INR_3M",
  "target_policy": "RISK_FREE_RATE",
  "constant_mar_annual": 0.05,
  "lookback_days": 60,
  "denominator_policy": "ALL_PERIODS_SEMIDEVIATION",
  "annualization_factor": 252.0
}
```

#### Response
```json
{
  "calculation_code": "SORTINO_8A71420C12D5",
  "scope": "PORTFOLIO",
  "entity_id": "PORT_ALPHA_01",
  "as_of_date": "2026-11-01T00:00:00Z",
  "lookback_days": 60,
  "currency": "INR",
  "mean_return_period": 0.00084512,
  "target_return_period": 0.00017124,
  "mean_excess_over_target_period": 0.00067388,
  "downside_deviation_period": 0.00512411,
  "period_sortino": 0.131512,
  "annualized_sortino": 2.087693,
  "annualization_factor": 252.0,
  "sample_size": 60,
  "downside_periods_count": 24,
  "downside_percentage": 40.0,
  "target_policy": "RISK_FREE_RATE",
  "denominator_policy": "ALL_PERIODS_SEMIDEVIATION",
  "status": "VALID"
}
```

---

## 3. Combined & Rolling Endpoints

- `POST /api/v1/market-risk/ratios/combined`: Concurrently evaluates Sharpe and Sortino ratios using the same synchronized return and risk-free series.
- `POST /api/v1/market-risk/ratios/rolling`: Evaluates rolling window Sharpe and Sortino time series.
- `GET /api/v1/portfolios/{portfolio_id}/risk/ratios`: Portfolio-scoped combined Sharpe and Sortino ratio analytics.
