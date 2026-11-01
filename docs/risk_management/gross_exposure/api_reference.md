# M06.01 Gross Exposure API Reference

## Endpoints Summary

Base Path: `/api/v1`
Tags: `Gross Exposure`

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/portfolios/{portfolio_id}/risk/gross-exposure/calculate` | Calculates gross exposure for an individual portfolio. |
| `POST` | `/portfolio-groups/{group_id}/risk/gross-exposure/calculate` | Calculates consolidated gross exposure across a portfolio group. |
| `GET` | `/risk/gross-exposure/runs/{run_id}` | Retrieves execution details for a calculation run. |
| `GET` | `/risk/gross-exposure/runs/{run_id}/summary` | Retrieves high-level exposure summary and ratios. |
| `GET` | `/risk/gross-exposure/runs/{run_id}/contributions` | Retrieves granular position contributions and lineage. |
| `GET` | `/risk/gross-exposure/runs/{run_id}/breakdowns` | Retrieves multidimensional breakdown (instrument, account, currency, portfolio). |
| `GET` | `/risk/gross-exposure/runs/{run_id}/threshold-events` | Retrieves any threshold breach or warning events. |
| `POST` | `/risk/gross-exposure/policies` | Creates or updates an exposure policy and risk limit configuration. |
| `GET` | `/portfolios/{portfolio_id}/risk/gross-exposure/policies` | Fetches active exposure policies for a portfolio. |

---

## Endpoint Details

### 1. Calculate Single Portfolio Gross Exposure
`POST /portfolios/{portfolio_id}/risk/gross-exposure/calculate`

**Request Body:**
```json
{
  "as_of": "2026-11-01T10:00:00Z",
  "knowledge_as_of": "2026-11-01T10:00:00Z",
  "reporting_currency": "USD",
  "denominator_type": "NAV",
  "custom_denominator_value": "100000.000000",
  "fx_rates_to_reporting": {
    "INR": "0.012000"
  }
}
```

**Response (200 OK):**
```json
{
  "run_id": "RUN-ABC123XYZ",
  "portfolio_id": "PORT-01",
  "scope": "PORTFOLIO",
  "reporting_currency": "USD",
  "long_exposure": "75000.000000",
  "short_exposure": "60000.000000",
  "gross_exposure": "135000.000000",
  "net_exposure": "15000.000000",
  "denominator_type": "NAV",
  "denominator_value": "100000.000000",
  "gross_exposure_ratio": "1.350000",
  "gross_exposure_ratio_percentage": "135.0000",
  "ratio_status": "VALID",
  "ratio_explanation": "Gross Exposure Ratio calculated successfully: 1.35x (135.0000%).",
  "threshold_status": "NORMAL",
  "contributions": [...],
  "breakdowns": [...],
  "threshold_events": []
}
```

### 2. Calculate Group Consolidated Gross Exposure
`POST /portfolio-groups/{group_id}/risk/gross-exposure/calculate`

**Request Body:**
```json
{
  "reporting_currency": "USD",
  "denominator_type": "COMMITTED_CAPITAL",
  "custom_denominator_value": "500000.000000"
}
```

**Response (200 OK):**
Returns consolidated gross exposure across all deduplicated member portfolios within the hierarchy, with breakdown buckets by both instrument and underlying portfolio.

