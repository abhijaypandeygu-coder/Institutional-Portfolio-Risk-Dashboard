# M07.10 Risk Forecasting API Reference

## 1. Endpoints Overview

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/market-risk/forecast/volatility` | Generate and persist forward risk forecast |
| `GET` | `/api/v1/market-risk/forecast/volatility` | Retrieve latest or rolling risk forecast |
| `POST` | `/api/v1/market-risk/forecast/compare` | Multi-model walk-forward performance comparison |
| `POST` | `/api/v1/market-risk/forecast/{calculation_id}/evaluate` | Ex-post evaluation against subsequent realized outcomes |
| `GET` | `/api/v1/market-risk/forecast/monitoring-events` | Retrieve forecast monitoring alerts |
| `GET` | `/api/v1/portfolios/{portfolio_id}/risk/forecast` | Portfolio-scoped risk forecast endpoint |

---

## 2. Request & Response Examples

### 2.1 Generate Volatility Forecast
`POST /api/v1/market-risk/forecast/volatility`
```json
{
  "scope": "INSTRUMENT",
  "entity_id": "INST_RELIANCE",
  "model_name": "GARCH_1_1",
  "forecast_horizon": 5,
  "lookback_days": 252,
  "annualization_factor": 252.0
}
```

### 2.2 Compare Competing Models
`POST /api/v1/market-risk/forecast/compare`
```json
{
  "scope": "PORTFOLIO",
  "entity_id": "PORT_ALPHA_001",
  "models": ["ROLLING_HISTORICAL", "EWMA", "GARCH_1_1"],
  "forecast_horizon": 1
}
```
Response ranks models by MAE, RMSE, and QLIKE loss over walk-forward origins.
