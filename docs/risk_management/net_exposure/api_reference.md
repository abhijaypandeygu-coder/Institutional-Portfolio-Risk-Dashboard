# M06.02 Net Exposure API Reference

## Base Path
Base route: `/api/v1`
Tags: `Risk Management - Net Exposure (M06.02)`

---

## Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/portfolios/{portfolio_id}/risk/net-exposure` | Query current net exposure and directional state for a portfolio. |
| `POST` | `/portfolios/{portfolio_id}/risk/net-exposure/calculate` | Execute a point-in-time net exposure calculation for a portfolio. |
| `GET` | `/portfolio-groups/{group_id}/risk/net-exposure` | Query consolidated net exposure across a portfolio group. |
| `POST` | `/portfolio-groups/{group_id}/risk/net-exposure/calculate` | Execute consolidated net exposure calculation across a portfolio group. |
| `GET` | `/risk/net-exposure/runs/{run_id}/contributions` | Retrieve granular signed position contributions and lineage for a run. |
| `GET` | `/risk/net-exposure/runs/{run_id}/breakdowns` | Retrieve multi-dimensional exposure breakdowns (instrument, account, currency). |
| `GET` | `/risk/net-exposure/runs/{run_id}/threshold-events` | Retrieve limit or neutrality breach/warning audit records. |
| `POST` | `/risk/net-exposure/policies` | Register a new directional net exposure policy with limits and thresholds. |

---

## Detailed Request & Response Examples

### Calculate Portfolio Net Exposure
`POST /api/v1/portfolios/{portfolio_id}/risk/net-exposure/calculate`

**Request Body:**
```json
{
  "reporting_currency": "USD",
  "denominator_type": "NAV",
  "custom_denominator_value": "100000.000000",
  "neutrality_threshold_type": "RELATIVE",
  "relative_neutrality_threshold": "0.020000",
  "fx_rates_to_reporting": {
    "INR": "0.012000"
  }
}
```

**Response (201 Created):**
```json
{
  "run_id": "NET-RUN-8A2F1C349D0E",
  "portfolio_id": "PORT-01",
  "scope": "PORTFOLIO",
  "reporting_currency": "USD",
  "long_exposure": "75000.000000",
  "absolute_short_exposure": "60000.000000",
  "net_market_value": "15000.000000",
  "gross_exposure_reference": "135000.000000",
  "denominator_type": "NAV",
  "denominator_value": "100000.000000",
  "net_exposure_ratio": "0.150000",
  "net_exposure_ratio_percentage": "15.0000",
  "ratio_status": "VALID",
  "ratio_explanation": "Net Exposure Ratio: 0.150000x (15.0000%).",
  "directional_classification": "NET_LONG",
  "neutrality_threshold_type": "RELATIVE",
  "neutrality_threshold_applied": "Relative Threshold: 0.020000 (Observed: 0.150000)",
  "threshold_status": "WITHIN_LIMIT",
  "completeness_status": "COMPLETE",
  "eligible_position_count": 2,
  "excluded_position_count": 0,
  "contributions": [...],
  "breakdowns": [...]
}
```
