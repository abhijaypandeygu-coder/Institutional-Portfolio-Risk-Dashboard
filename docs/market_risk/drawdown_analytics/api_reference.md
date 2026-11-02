# M07.04 — Drawdown Analytics API Reference

## Base Endpoints

- Global Routes: `/api/v1/market-risk/drawdown`
- Portfolio Routes: `/api/v1/portfolios/{portfolio_id}/risk/drawdown`
- Group Routes: `/api/v1/portfolio-groups/{group_id}/risk/drawdown`

---

### 1. Current Drawdown
- **Endpoint**: `GET /api/v1/market-risk/drawdown/current`
- **Query Parameters**:
  - `scope_type`: `PORTFOLIO` | `INSTRUMENT` (default `PORTFOLIO`)
  - `portfolio_id`: string (optional)
  - `instrument_id`: string (optional)
- **Response**: `200 OK`
```json
{
  "scope_type": "PORTFOLIO",
  "portfolio_id": "PORT_US_EQUITY_01",
  "latest_value": "99000.0000",
  "latest_observation_timestamp": "2026-01-14T16:00:00Z",
  "running_high_water_mark": "105000.0000",
  "high_water_mark_timestamp": "2026-01-12T16:00:00Z",
  "current_drawdown_amount": "6000.00",
  "current_signed_drawdown": "-0.05714286",
  "current_drawdown_percentage": "5.714286",
  "days_since_peak": 2,
  "current_status": "CURRENTLY_UNDERWATER",
  "current_episode_id": "DDEP_A1B2C3D4E5F6",
  "reporting_currency": "USD",
  "data_quality_status": "VALID"
}
```

---

### 2. Maximum Drawdown
- **Endpoint**: `GET /api/v1/market-risk/drawdown/maximum`
- **Query Parameters**:
  - `scope_type`: `PORTFOLIO` | `INSTRUMENT`
  - `portfolio_id`: string
  - `lookback_window_name`: string (default `SINCE_INCEPTION`)
- **Response**: `200 OK`
```json
{
  "scope_type": "PORTFOLIO",
  "portfolio_id": "PORT_US_EQUITY_01",
  "lookback_window_name": "SINCE_INCEPTION",
  "lookback_start": "2026-01-01T16:00:00Z",
  "lookback_end": "2026-01-14T16:00:00Z",
  "maximum_drawdown_percentage": "16.666667",
  "signed_maximum_drawdown": "-0.16666667",
  "maximum_drawdown_amount": "17000.00",
  "peak_value": "102000.0000",
  "peak_timestamp": "2026-01-06T16:00:00Z",
  "trough_value": "85000.0000",
  "trough_timestamp": "2026-01-09T16:00:00Z",
  "recovery_timestamp": "2026-01-12T16:00:00Z",
  "peak_to_trough_days": 3,
  "trough_to_recovery_days": 3,
  "underwater_duration_days": 6,
  "recovery_status": "RECOVERED",
  "reporting_currency": "USD",
  "data_quality_status": "VALID"
}
```

---

### 3. Drawdown Episodes List
- **Endpoint**: `GET /api/v1/market-risk/drawdown/episodes`
- **Query Parameters**:
  - `scope_type`: `PORTFOLIO` | `INSTRUMENT`
  - `portfolio_id`: string
  - `limit`: integer (default 50)
- **Response**: `200 OK`
```json
[
  {
    "episode_id": "DDEP_1234567890AB",
    "series_id": "SERIES_PORT_PORT_US_EQUITY_01",
    "scope_type": "PORTFOLIO",
    "peak_value": "102000.0000",
    "peak_timestamp": "2026-01-06T16:00:00Z",
    "trough_value": "85000.0000",
    "trough_timestamp": "2026-01-09T16:00:00Z",
    "recovery_value": "105000.0000",
    "recovery_timestamp": "2026-01-12T16:00:00Z",
    "drawdown_percentage": "16.666667",
    "signed_drawdown": "-0.16666667",
    "absolute_drawdown_amount": "17000.00",
    "peak_to_trough_days": 3,
    "trough_to_recovery_days": 3,
    "underwater_duration_days": 6,
    "episode_status": "RECOVERED"
  }
]
```

---

### 4. Lookback Window Comparisons
- **Endpoint**: `GET /api/v1/market-risk/drawdown/comparison`
- **Response**: `200 OK`
```json
{
  "series_id": "SERIES_PORT_PORT_US_EQUITY_01",
  "scope_type": "PORTFOLIO",
  "portfolio_id": "PORT_US_EQUITY_01",
  "reporting_currency": "USD",
  "as_of_date": "2026-11-02",
  "current_drawdown_percentage": "5.714286",
  "windows": [
    {
      "window_name": "1_MONTH",
      "lookback_days": 30,
      "maximum_drawdown_percentage": "16.666667",
      "maximum_drawdown_amount": "17000.00",
      "peak_timestamp": "2026-01-06T16:00:00Z",
      "trough_timestamp": "2026-01-09T16:00:00Z",
      "recovery_timestamp": "2026-01-12T16:00:00Z",
      "recovery_status": "RECOVERED",
      "peak_to_trough_days": 3,
      "underwater_duration_days": 6
    }
  ]
}
```
