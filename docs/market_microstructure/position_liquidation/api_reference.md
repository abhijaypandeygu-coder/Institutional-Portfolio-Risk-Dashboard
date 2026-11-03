# M09.07 Position Liquidation API Reference

## Base Path
`/api/v1/market-microstructure/liquidation`

---

### 1. Create Position Liquidation Plan
`POST /plans`

Creates a versioned analytical liquidation plan decomposing the position into cumulative and incremental targets.

**Request Payload:**
```json
{
  "plan_name": "AAPL Position Exit Plan",
  "portfolio_id": "PORT-GROWTH-01",
  "position_id": "POS-AAPL-100",
  "instrument_id": "INST-AAPL",
  "venue_id": "XNAS",
  "starting_signed_quantity": 8000,
  "benchmark_price": 180.0,
  "benchmark_type": "MIDPOINT",
  "spread": 0.05,
  "maximum_participation_rate": 0.10,
  "execution_schedule": "PARTICIPATION_CAPPED"
}
```

**Response (201 Created):**
```json
{
  "plan_id": "PLN-A1B2C3D4E5",
  "plan_name": "AAPL Position Exit Plan",
  "portfolio_id": "PORT-GROWTH-01",
  "position_id": "POS-AAPL-100",
  "instrument_id": "INST-AAPL",
  "liquidation_side": "SELL",
  "starting_signed_quantity": 8000.0,
  "starting_absolute_quantity": 8000.0,
  "starting_market_value": 1440000.0,
  "position_currency": "USD",
  "portfolio_base_currency": "USD",
  "benchmark_price": 180.0,
  "maximum_participation_rate": 0.10,
  "execution_schedule": "PARTICIPATION_CAPPED",
  "plan_status": "ACTIVE",
  "version": 1,
  "targets": [
    {
      "target_id": "T1",
      "target_sequence": 1,
      "target_percentage": 0.10,
      "target_cumulative_quantity": 800.0,
      "target_incremental_quantity": 800.0,
      "remaining_quantity": 7200.0,
      "target_market_value": 144000.0
    },
    ...
  ],
  "horizon_results": [...],
  "cost_results": [...]
}
```

---

### 2. Retrieve Liquidation Plan
`GET /plans/{plan_id}`

Retrieves the persisted liquidation plan, targets, horizon estimates, and reconciled costs.

---

### 3. Partial Liquidation Comparison
`GET /plans/{plan_id}/partial-comparison`

Returns a side-by-side comparison across all reduction targets (10%, 25%, 50%, 75%, 90%, 100%).

**Response (200 OK):**
```json
{
  "plan_id": "PLN-A1B2C3D4E5",
  "instrument_id": "INST-AAPL",
  "liquidation_side": "SELL",
  "starting_quantity": 8000.0,
  "targets": [
    {
      "target_id": "T1",
      "percentage": 10.0,
      "cumulative_quantity": 800.0,
      "incremental_quantity": 800.0,
      "remaining_quantity": 7200.0,
      "duration_seconds": 300,
      "sessions_required": 1,
      "cumulative_cost": 218.4,
      "incremental_cost": 218.4,
      "cost_bps": 15.17,
      "completion_status": "FULLY_LIQUIDATED_ESTIMATED"
    },
    ...
  ]
}
```

---

### 4. Portfolio Liquidation Analysis
`POST /portfolio`

Evaluates concurrent (critical path) or sequential multi-position portfolio liquidations.

**Request Payload:**
```json
{
  "portfolio_id": "PORT-GLOBAL-ALPHA",
  "schedule_mode": "CONCURRENT",
  "participation_rate": 0.10,
  "positions": [
    {"instrument_id": "INST-MSFT", "quantity": 10000, "price": 400.0, "spread": 0.05},
    {"instrument_id": "INST-AMZN", "quantity": -5000, "price": 180.0, "spread": 0.04}
  ]
}
```

---

### 5. Historical Model Calibration
- `POST /calibrations` (Record new calibration run)
- `GET /calibrations` (List historical calibration runs)
