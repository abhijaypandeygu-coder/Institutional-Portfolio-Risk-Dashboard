# M10.06 — Liquidity Stress Testing API Reference

Base Endpoint: `/api/v1/risk/scenarios/liquidity-stress`

## Endpoints

### 1. Create Liquidity Stress Scenario
- **Method:** `POST /`
- **Status Code:** `201 Created`
- **Request Body:** `LiquidityStressScenarioCreate`
  ```json
  {
    "scenario_code": "SCEN_SEVERE_LIQ_DETERIORATION",
    "name": "Severe Market Dislocation & Liquidity Freeze",
    "description": "Simulates 200% spread widening, 60% depth reduction, 50% volume contraction, and -10% price shock.",
    "scenario_category": "SEVERE_LIQUIDITY_DETERIORATION",
    "spread_increase_pct": "2.0000",
    "spread_multiplier": "3.0000",
    "bid_depth_multiplier": "0.4000",
    "ask_depth_multiplier": "0.4000",
    "market_volume_multiplier": "0.5000",
    "participation_multiplier": "0.5000",
    "base_participation_cap": "0.1000",
    "impact_multiplier": "1.5000",
    "execution_horizon_sessions": 5,
    "market_price_shock_pct": "-0.1000"
  }
  ```
- **Response Body:** `LiquidityStressScenarioResponse`

---

### 2. List Liquidity Stress Scenarios
- **Method:** `GET /`
- **Response Body:** `List[LiquidityStressScenarioResponse]`

---

### 3. Get Scenario Details
- **Method:** `GET /{scenario_id}`
- **Response Body:** `LiquidityStressScenarioResponse`

---

### 4. Execute Liquidity Stress Simulation Run
- **Method:** `POST /{scenario_id}/runs`
- **Status Code:** `201 Created`
- **Request Body:** `ExecuteLiquidityStressRequest`
  ```json
  {
    "portfolio_id": "INST_TECH_EQUITY_PORTFOLIO",
    "executed_by": "Chief Risk Officer",
    "custom_positions": [
      {
        "instrument_id": "EQ_AAPL",
        "symbol": "AAPL",
        "quantity": "10000",
        "price": "150.00",
        "spread": "0.04",
        "volume": "500000",
        "depth": "100000"
      }
    ]
  }
  ```
- **Response Body:** `LiquidityStressRunResponse`
  Returns aggregate portfolio notional, incremental cost, cost bps, liquidation duration, unliquidated position counts, residual market value, position-level results, progressive horizon breakdowns, and cost attribution components.
