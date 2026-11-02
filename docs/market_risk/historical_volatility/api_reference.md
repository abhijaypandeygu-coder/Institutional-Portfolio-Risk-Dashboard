# M07.01 — Historical Volatility: API Reference

## Base Path: `/api/v1/market-risk/historical-volatility`

### 1. Get Current Historical Volatility
- **Method:** `GET /`
- **Query Parameters:**
  - `instrument_id` (optional): Canonical instrument ID.
  - `portfolio_id` (optional): Portfolio ID (for NAV return volatility).
  - `lookback_window` (default `20`): Number of trading sessions.
  - `return_type` (default `LOGARITHMIC`): `LOGARITHMIC` or `SIMPLE`.
  - `return_frequency` (default `DAILY`): `DAILY`, `INTRADAY_5_MINUTE`, etc.
  - `price_source` (default `OFFICIAL_CLOSE`): Authoritative source.
  - `as_of` (optional): Historical evaluation date (`YYYY-MM-DD`).
- **Response (`200 OK`):**
```json
{
  "result_id": "VOL_B94FA1C82D4A",
  "scope_type": "INSTRUMENT",
  "instrument_id": "INST_AAPL_001",
  "as_of_date": "2026-01-25",
  "window_start": "2026-01-01T00:00:00Z",
  "window_end": "2026-01-25T00:00:00Z",
  "lookback_window": 20,
  "return_type": "LOGARITHMIC",
  "return_frequency": "DAILY",
  "observation_count": 20,
  "expected_observation_count": 20,
  "coverage_percentage": "100.0000",
  "mean_return": "0.00841291",
  "period_volatility": "0.01254102",
  "annualized_volatility": "0.19908253",
  "annualization_factor": "15.874508",
  "periods_per_year": 252,
  "estimator": "SAMPLE_STD_DEV",
  "calculation_status": "CALCULATED",
  "quality_status": "PASSED",
  "calculation_version": "1.0.0",
  "calculated_at": "2026-11-02T06:15:00Z"
}
```

---

### 2. Get Rolling Volatility Time Series
- **Method:** `GET /rolling`
- **Query Parameters:**
  - `instrument_id` (optional): Canonical instrument ID.
  - `portfolio_id` (optional): Portfolio ID.
  - `lookback_window` (default `20`): Lookback sessions.
  - `from_date` (optional): Filter start.
  - `to_date` (optional): Filter end.
- **Response (`200 OK`):**
```json
{
  "instrument_id": "INST_AAPL_001",
  "portfolio_id": null,
  "lookback_window": 20,
  "return_frequency": "DAILY",
  "total_points": 25,
  "series": [
    {
      "point_id": "RP_0812F98C123D",
      "observation_timestamp": "2026-01-20T00:00:00Z",
      "trading_date": "2026-01-20",
      "lookback_window": 20,
      "return_frequency": "DAILY",
      "period_volatility": "0.01211045",
      "annualized_volatility": "0.19224743",
      "observation_count": 20,
      "coverage_percentage": "100.0000",
      "status": "CALCULATED"
    }
  ]
}
```

---

### 3. Window Comparison (Short vs Medium vs Long)
- **Method:** `GET /window-comparison`
- **Query Parameters:**
  - `instrument_id`: Canonical instrument ID.
  - `short_window` (default `20`): Short horizon.
  - `medium_window` (default `60`): Medium horizon.
  - `long_window` (default `252`): Long horizon.
  - `as_of` (optional): Date.
- **Response (`200 OK`):**
```json
{
  "instrument_id": "INST_AAPL_001",
  "as_of_date": "2026-01-25",
  "return_frequency": "DAILY",
  "return_type": "LOGARITHMIC",
  "horizons": [
    {
      "horizon": "SHORT",
      "lookback_sessions": 20,
      "observation_count": 20,
      "expected_observation_count": 20,
      "coverage_percentage": "100.0000",
      "period_volatility": "0.01254102",
      "annualized_volatility": "0.19908253",
      "annualization_factor": "15.874508",
      "status": "CALCULATED"
    }
  ],
  "short_vs_medium_spread": "0.02100000",
  "medium_vs_long_spread": "-0.01500000",
  "short_vs_long_spread": "0.00600000",
  "short_to_long_ratio": "1.031075",
  "comparison_label": "SHORT_TERM_HIGHER",
  "calculated_at": "2026-11-02T06:15:00Z"
}
```

---

### 4. Realized Volatility Trend & Slope
- **Method:** `GET /trend`
- **Query Parameters:**
  - `instrument_id`: Canonical instrument ID.
  - `lookback_window` (default `20`): Rolling window length.
  - `trend_lookback_points` (default `10`): Number of rolling points for OLS slope.
- **Response (`200 OK`):**
```json
{
  "instrument_id": "INST_AAPL_001",
  "lookback_window": 20,
  "return_frequency": "DAILY",
  "current_volatility": "0.19908253",
  "prior_volatility": "0.19224743",
  "volatility_change": "0.00683510",
  "volatility_pct_change": "3.555366",
  "trend_slope": "0.00142100",
  "trend_classification": "VOLATILITY_INCREASING",
  "points_evaluated": 10,
  "as_of_date": "2026-01-25"
}
```

---

### 5. Intraday Realized Volatility
- **Method:** `GET /intraday`
- **Query Parameters:**
  - `instrument_id`: Canonical instrument ID.
  - `sampling_interval` (default `5m`): `1m`, `5m`, `15m`, `30m`.
- **Response (`200 OK`):**
```json
{
  "instrument_id": "INST_AAPL_001",
  "sampling_interval": "5m",
  "price_measure": "CLOSE",
  "price_source": "OHLCV_BAR_CLOSE",
  "session_boundary_policy": "WITHIN_SESSION_ONLY",
  "intraday_period_volatility": "0.00121045",
  "annualized_volatility": "0.16970509",
  "annualization_factor": "140.200000",
  "bars_evaluated": 80,
  "expected_bars": 78,
  "coverage_percentage": "102.5600",
  "microstructure_suitability": "SUITABLE",
  "is_suitable": true,
  "status": "CALCULATED",
  "calculated_at": "2026-11-02T06:15:00Z"
}
```

