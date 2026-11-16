# M10.09 Stress Loss Attribution — API Reference

Base URL prefix: `/api/v1/stress-loss-attributions`

---

## 1. Attribution Configuration Management

### `POST /`
Creates a new stress loss attribution configuration.

**Request Body:**
```json
{
  "attribution_code": "ATTR_TECH_CRASH_2026",
  "name": "Q4 Tech Crash Loss Decomposition",
  "description": "Explaining losses across positions, sectors, and factors",
  "portfolio_id": "PORT_TECH_EQUITIES",
  "scenario_id": "SCEN_CRASH_2026",
  "scenario_run_id": "RUN_CRASH_01",
  "scenario_type": "MARKET_CRASH",
  "baseline_snapshot_id": "BASE_SNAPSHOT_Q4",
  "base_currency": "USD",
  "attribution_method": "ARITHMETIC_EXACT"
}
```

---

### `GET /`
Lists saved attribution configurations, optionally filtered by `portfolio_id`.

---

### `GET /{attribution_code}`
Retrieves attribution configuration by code or ID.

---

## 2. Attribution Execution & Results

### `POST /{attribution_code}/execute`
Executes multi-dimensional loss decomposition across positions, sectors, factors, and interaction cross-terms.

**Request Body:**
```json
{
  "baseline_nav_override": "1000000.0000",
  "authoritative_pnl_override": "-80000.0000"
}
```

**Response (200 OK):**
```json
{
  "id": "c1a2b3d4-e5f6-47a8-b9c0-112233445566",
  "attribution_id": "99887766-5544-3322-1100-aabbccddeeff",
  "run_code": "ATTR_ATTR_TECH_CRASH_2026_1794829000_A1B2C3",
  "scenario_run_id": "RUN_CRASH_01",
  "execution_status": "COMPLETED",
  "attribution_completeness": "COMPLETE",
  "started_at": "2026-11-16T05:10:00Z",
  "completed_at": "2026-11-16T05:10:01Z",
  "duration_ms": 38,
  "authoritative_total_pnl": "-80000.0000",
  "explained_pnl": "-80000.0000",
  "residual_amount": "0.0000",
  "is_reconciled": true,
  "loss_hhi": 0.4215,
  "effective_contributor_count": 2.37,
  "position_contributions": [
    {
      "symbol": "MSFT",
      "quantity": "400.0000",
      "position_direction": "LONG",
      "baseline_price": "420.0000",
      "stressed_price": "390.0000",
      "baseline_market_value": "168000.0000",
      "stressed_market_value": "156000.0000",
      "price_pnl": "-12000.0000",
      "fx_pnl": "0.0000",
      "liquidity_cost": "300.0000",
      "other_adjustments": "0.0000",
      "total_pnl": "-12300.0000",
      "loss_contribution": "12300.0000",
      "contribution_percentage": "15.3750",
      "sector": "Information Technology",
      "industry": "Software—Infrastructure"
    }
  ],
  "sector_contributions": [
    {
      "sector_name": "Information Technology",
      "holding_count": 3,
      "baseline_market_value": "234000.0000",
      "stressed_market_value": "217500.0000",
      "total_pnl": "-16750.0000",
      "loss_contribution": "16750.0000",
      "contribution_percentage": "20.9375"
    }
  ],
  "industry_contributions": [],
  "factor_contributions": [
    {
      "factor_name": "MARKET",
      "factor_shock": -0.08,
      "factor_exposure": 1.05,
      "contribution_value": "-84000.0000",
      "loss_contribution": "84000.0000"
    }
  ],
  "interaction_effects": [
    {
      "shock_driver_a": "MARKET_INDEX_DECLINE",
      "shock_driver_b": "VOLATILITY_EXPANSION",
      "combined_effect": "-80000.0000",
      "individual_effect_a": "-68000.0000",
      "individual_effect_b": "-8000.0000",
      "interaction_effect": "-4000.0000",
      "interaction_method": "COMBINED_SHOCK_DIFF"
    }
  ],
  "narrative": "Stress Loss Attribution decomposed total stressed P&L of -$80,000.00 across 4 positions. Loss HHI is 0.4215 with 2.4 effective loss drivers. Reconciliation status: RECONCILED (residual: $0.00)."
}
```

---

### `GET /runs/{run_code}`
Retrieves full execution summary by run code or ID.

### `GET /runs/{run_code}/positions`
Retrieves position-level loss contributions.

### `GET /runs/{run_code}/sectors`
Retrieves sector-level aggregated contributions.

### `GET /runs/{run_code}/factors`
Retrieves economic factor shock contributions.
