# M10.02 — Hypothetical Scenarios API Reference

The **Hypothetical Scenarios** REST API allows institutional risk applications to configure, persist, and execute multi-channel hypothetical stress scenarios.

Base Path: `/api/v1/scenarios/hypothetical`

---

## 1. Templates API

### `POST /templates`
Creates a new versioned hypothetical scenario template.

#### Request Body
```json
{
  "template_code": "STRESS_COMBINED_Q4",
  "template_name": "Combined Tech Crash & Liquidity Dislocation",
  "description": "Multi-channel stress testing tech sector decline and volatility spike",
  "category": "COMBINED",
  "tags": "tech,crash,volatility,liquidity",
  "author": "Ayush Risk Lead",
  "price_shocks": [
    {
      "target_type": "SECTOR",
      "target_identifier": "TECHNOLOGY",
      "shock_method": "PERCENTAGE",
      "shock_value": "-0.20"
    }
  ],
  "volatility_shocks": [
    {
      "target_type": "PORTFOLIO",
      "shock_method": "PERCENTAGE",
      "shock_value": "0.50"
    }
  ],
  "liquidity_shocks": [
    {
      "target_type": "PORTFOLIO",
      "spread_shock_pct": "0.50",
      "depth_shock_pct": "0.40",
      "volume_shock_pct": "0.30"
    }
  ]
}
```

#### Response: `201 Created`
Returns `HypotheticalScenarioTemplateResponse`.

---

### `GET /templates`
Lists templates with optional query filters:
- `category`: `PRICE`, `FACTOR`, `VOLATILITY`, `CORRELATION`, `LIQUIDITY`, `COMBINED`
- `status`: `DRAFT`, `ACTIVE`, `ARCHIVED`
- `search`: Case-insensitive substring match on name, code, description, and tags.

---

### `GET /templates/{template_id}`
Returns template details and serialized configuration.

---

## 2. Scenario Execution API

### `POST /runs`
Executes a hypothetical scenario run against a given portfolio snapshot.

#### Request Body
```json
{
  "scenario_name": "Q4 Global Tech Stress Run",
  "portfolio_id": "INST_PORTFOLIO_HEDGE",
  "template_id": "tmpl_36c0a006c406",
  "base_currency": "USD",
  "baseline_nav": "2000000.00",
  "correlation_validation_policy": "NEAREST_CORRELATION_MATRIX_REPAIR",
  "positions": [
    {
      "instrument_id": "AAPL_US",
      "listing_id": "AAPL_NASDAQ",
      "signed_quantity": "2000",
      "baseline_price": "300.00",
      "baseline_volatility": "0.25",
      "currency": "USD",
      "sector": "TECHNOLOGY",
      "baseline_spread": "0.05",
      "baseline_bid_depth": "10000",
      "baseline_ask_depth": "10000",
      "baseline_volume": "1000000"
    },
    {
      "instrument_id": "JPM_US",
      "listing_id": "JPM_NYSE",
      "signed_quantity": "-1000",
      "baseline_price": "150.00",
      "baseline_volatility": "0.20",
      "currency": "USD",
      "sector": "FINANCIALS",
      "baseline_spread": "0.04",
      "baseline_bid_depth": "8000",
      "baseline_ask_depth": "8000",
      "baseline_volume": "800000"
    }
  ]
}
```

#### Response: `201 Created`
Returns `HypotheticalScenarioRunResponse` with full calculation results:
- `run_summary`: Portfolio-level baseline NAV, scenario NAV, NAV change, percentage return.
- `position_results`: Position-level revaluation, baseline/scenario market values, PnL, return contribution.
- `risk_results`: Channel B stressed portfolio volatility, Parametric VaR (95%), Parametric ES (95%).
- `liquidity_results`: Channel C stressed spreads, depth depletion, volume contraction, liquidation cost bps.
- `warnings`: Warning entries (e.g. `CORRELATION_REPAIRED`).

---

### `GET /runs/{run_id}`
Retrieves a complete persisted scenario run by ID.
