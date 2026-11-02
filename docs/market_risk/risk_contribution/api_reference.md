# M07.09 Risk Contribution API Reference

## 1. Endpoints Overview

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/market-risk/risk-contribution/calculate` | Execute and persist full portfolio risk decomposition |
| `GET` | `/api/v1/market-risk/risk-contribution/portfolio/{portfolio_id}` | Retrieve latest portfolio risk decomposition |
| `GET` | `/api/v1/market-risk/risk-contribution/portfolio/{portfolio_id}/holdings` | Retrieve granular holding risk contributions |
| `GET` | `/api/v1/market-risk/risk-contribution/portfolio/{portfolio_id}/groups` | Retrieve group-level attribution by dimension |
| `GET` | `/api/v1/market-risk/risk-contribution/reconciliation/{calculation_id}` | Retrieve Euler additivity reconciliation diagnostics |
| `POST` | `/api/v1/market-risk/risk-contribution/scenario` | What-if weight perturbation scenario analysis |
| `GET` | `/api/v1/portfolios/{portfolio_id}/risk/contribution` | Portfolio-scoped nested risk contribution endpoint |

---

## 2. Request & Response Examples

### 2.1 Calculate Portfolio Risk Attribution
`POST /api/v1/market-risk/risk-contribution/calculate`
```json
{
  "portfolio_id": "PORT_ALPHA_001",
  "weight_basis": "MARKET_VALUE",
  "lookback_days": 252,
  "verify_finite_difference": true
}
```

### 2.2 What-If Scenario Perturbation
`POST /api/v1/market-risk/risk-contribution/scenario`
```json
{
  "portfolio_id": "PORT_ALPHA_001",
  "weight_deltas": {
    "INST_RELIANCE": "0.05",
    "INST_TCS": "-0.05"
  }
}
```
Response compares linear Taylor prediction $\mathbf{MRC}^T \Delta \mathbf{w}$ against non-linear exact recalculation $\sigma_p(\mathbf{w} + \Delta \mathbf{w}) - \sigma_p(\mathbf{w})$.
