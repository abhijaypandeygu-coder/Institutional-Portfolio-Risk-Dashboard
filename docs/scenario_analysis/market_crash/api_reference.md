# M10.03 — Market Crash Simulation API Reference

The **Market Crash Simulation** API provides endpoints for configuring benchmark market shocks, setting up nonlinear downside parameters, executing stress simulations against portfolios, and retrieving granular attribution and diagnostic results.

Base Path: `/api/v1/scenarios/market-crash`

---

## 1. Scenario Management

### `POST /api/v1/scenarios/market-crash`
Creates a versioned market crash scenario with benchmark shocks and optional nonlinear parameters.

#### Request Body
```json
{
  "scenario_code": "CRASH_GLOBAL_2026",
  "scenario_name": "Synchronized Global Liquidity Crisis",
  "description": "Simultaneous 25% decline in US equities and 20% decline in Indian equities with tech stress amplification",
  "category": "GLOBAL_SYNCHRONIZED",
  "visibility": "ORGANIZATION",
  "author_id": "Ayush Risk Head",
  "benchmark_shocks": [
    {
      "benchmark_id": "SPX",
      "benchmark_name": "S&P 500 Index",
      "market_region": "US",
      "shock_method": "PERCENTAGE",
      "percentage_shock": "-0.25",
      "benchmark_currency": "USD"
    },
    {
      "benchmark_id": "NIFTY_50",
      "benchmark_name": "NIFTY 50 Index",
      "market_region": "INDIA",
      "shock_method": "PERCENTAGE",
      "percentage_shock": "-0.20",
      "benchmark_currency": "INR"
    }
  ],
  "nonlinear_parameters": [
    {
      "sector_id": "TECHNOLOGY",
      "model_type": "STRESS_AMPLIFICATION",
      "threshold": "0.10",
      "stress_multiplier": "0.50",
      "exponent": "1.00",
      "parameter_source": "CALIBRATED"
    }
  ]
}
```

#### Response: `201 Created`
Returns `MarketCrashScenarioResponse`.

---

### `GET /api/v1/scenarios/market-crash`
Lists scenario templates with optional filtering by `category`, `portfolio_id`, and `status`.

---

### `GET /api/v1/scenarios/market-crash/{scenario_id}`
Retrieves scenario configuration and active version details.

---

## 2. Simulation Execution

### `POST /api/v1/scenarios/market-crash/runs`
Executes a market crash simulation run against a given portfolio snapshot.

#### Request Body
```json
{
  "scenario_name": "Q4 Global Crash Simulation Run",
  "portfolio_id": "GLOBAL_EQUITY_PORTFOLIO",
  "scenario_id": "mcsc_4f09a12c8b77",
  "base_currency": "USD",
  "baseline_nav": "2000000.00",
  "response_model": "STRESS_AMPLIFICATION",
  "missing_data_policy": "STRICT",
  "benchmark_shocks": [
    {
      "benchmark_id": "SPX",
      "market_region": "US",
      "shock_method": "PERCENTAGE",
      "percentage_shock": "-0.25",
      "benchmark_currency": "USD"
    },
    {
      "benchmark_id": "NIFTY_50",
      "market_region": "INDIA",
      "shock_method": "PERCENTAGE",
      "percentage_shock": "-0.20",
      "benchmark_currency": "INR"
    }
  ],
  "nonlinear_parameters": [
    {
      "sector_id": "TECHNOLOGY",
      "model_type": "STRESS_AMPLIFICATION",
      "threshold": "0.10",
      "stress_multiplier": "0.50",
      "exponent": "1.00"
    }
  ],
  "positions": [
    {
      "instrument_id": "NVDA_US",
      "listing_id": "NVDA_NASDAQ",
      "signed_quantity": "1000",
      "baseline_price": "500.00",
      "currency": "USD",
      "sector": "TECHNOLOGY",
      "market_region": "US",
      "benchmark_id": "SPX",
      "beta_value": "1.60"
    },
    {
      "instrument_id": "HDFCBANK_IN",
      "listing_id": "HDFCBANK_NSE",
      "signed_quantity": "20000",
      "baseline_price": "20.00",
      "currency": "USD",
      "sector": "FINANCIALS",
      "market_region": "INDIA",
      "benchmark_id": "NIFTY_50",
      "beta_value": "1.20",
      "fx_return": "-0.02"
    },
    {
      "instrument_id": "XOM_US",
      "listing_id": "XOM_NYSE",
      "signed_quantity": "-1000",
      "baseline_price": "100.00",
      "currency": "USD",
      "sector": "ENERGY",
      "market_region": "US",
      "benchmark_id": "SPX",
      "beta_value": "0.80"
    }
  ]
}
```

#### Response: `201 Created`
Returns `SimulationSummaryResponse`:
- `baseline_nav`, `scenario_nav`, `scenario_pnl`, `scenario_loss`, `scenario_return`.
- `mapped_coverage`, `beta_coverage`, `nonlinear_coverage`.
- `position_results`: Linear return, downside adjustment, nonlinear adjustment, final return, position PnL, position loss, return contribution.
- `attribution_results`: Sector attribution, Benchmark attribution, Linear vs Nonlinear impact.
- `warnings`: Audit notices on assumed betas, fallback mappings, or out-of-bounds metrics.

---

### `GET /api/v1/scenarios/market-crash/runs/{run_id}`
Retrieves a complete persisted simulation run by ID.
