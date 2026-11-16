# M10.07 Monte Carlo Scenarios — API Reference

Base URL prefix: `/api/v1/risk/scenarios/monte-carlo`

---

## 1. Scenario Management

### `POST /scenarios`
Creates a new Monte Carlo scenario specification.

**Request Body:**
```json
{
  "scenario_code": "MC_EQUITY_STRESS_20D",
  "name": "Multi-Asset Equity Stress Scenario",
  "description": "20-day horizon simulation with Student-t heavy tails and 1.5x volatility multiplier",
  "horizon_days": 20,
  "time_step_days": 1,
  "distribution_type": "STUDENT_T",
  "degrees_of_freedom": 4.5,
  "expected_return_model": "ZERO_DRIFT",
  "volatility_model": "SAMPLE_ANNUALIZED",
  "volatility_multiplier": 1.5,
  "correlation_repair_method": "EIGENVALUE_CLIPPING"
}
```

**Response (201 Created):**
```json
{
  "id": "e4a2c091-a128-4448-8df0-1033878b663b",
  "scenario_code": "MC_EQUITY_STRESS_20D",
  "name": "Multi-Asset Equity Stress Scenario",
  "description": "20-day horizon simulation with Student-t heavy tails and 1.5x volatility multiplier",
  "horizon_days": 20,
  "time_step_days": 1,
  "distribution_type": "STUDENT_T",
  "degrees_of_freedom": 4.5,
  "expected_return_model": "ZERO_DRIFT",
  "volatility_model": "SAMPLE_ANNUALIZED",
  "volatility_multiplier": 1.5,
  "correlation_repair_method": "EIGENVALUE_CLIPPING",
  "is_active": true,
  "created_at": "2026-11-16T04:40:00Z",
  "updated_at": "2026-11-16T04:40:00Z"
}
```

---

### `GET /scenarios`
Lists all active Monte Carlo scenarios.

**Query Parameters:**
- `active_only`: boolean (default: `true`)

---

### `GET /scenarios/{scenario_code}`
Retrieves a specific scenario specification by code or ID.

---

### `PUT /scenarios/{scenario_code}`
Updates scenario parameters (e.g., horizon, distribution, multipliers).

---

### `DELETE /scenarios/{scenario_code}`
Deletes scenario specification and cascades associated runs.

---

## 2. Simulation Execution & Reporting

### `POST /scenarios/{scenario_code}/run`
Executes a multi-asset stochastic simulation.

**Request Body:**
```json
{
  "portfolio_id": "PORT_TECH_EQUITIES",
  "n_paths": 10000,
  "random_seed": 42,
  "positions_override": [
    {
      "symbol": "AAPL",
      "quantity": "500",
      "baseline_price": "180.00",
      "annualized_volatility": 0.22,
      "annualized_drift": 0.0
    },
    {
      "symbol": "MSFT",
      "quantity": "400",
      "baseline_price": "420.00",
      "annualized_volatility": 0.20,
      "annualized_drift": 0.0
    }
  ],
  "correlation_matrix_override": [
    [1.0, 0.65],
    [0.65, 1.0]
  ]
}
```

**Response (200 OK):**
```json
{
  "run_id": "97e68bc3-3b1a-45c1-8ce2-47530e12d4d8",
  "scenario_code": "MC_EQUITY_STRESS_20D",
  "run_code": "MC_MC_EQUITY_STRESS_20D_1794827000_A1B2C3",
  "portfolio_id": "PORT_TECH_EQUITIES",
  "n_paths": 10000,
  "n_steps": 20,
  "random_seed": 42,
  "generator_algorithm": "PCG64",
  "matrix_was_repaired": false,
  "status": "COMPLETED",
  "execution_duration_ms": 32,
  "input_parameters_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "executed_at": "2026-11-16T04:40:05Z",
  "summary": {
    "baseline_portfolio_value": "258000.0000",
    "mean_terminal_value": "257912.4410",
    "median_terminal_value": "256840.1190",
    "std_terminal_value": "18942.5012",
    "mean_pnl": "-87.5590",
    "median_pnl": "-1159.8810",
    "std_pnl": "18942.5012",
    "skewness_pnl": 0.0412,
    "excess_kurtosis_pnl": 0.8250,
    "loss_probability": 0.5210,
    "min_pnl": "-74210.1200",
    "max_pnl": "83419.8800",
    "percentiles_json": {
      "p1": -43120.50,
      "p5": -30980.20,
      "p10": -24100.80,
      "p25": -12950.40,
      "p50": -1159.88,
      "p75": 11980.30,
      "p90": 24050.10,
      "p95": 31220.40,
      "p99": 45190.70
    }
  },
  "risk_metrics": [
    {
      "confidence_level": 0.90,
      "var_loss_amount": "24100.8000",
      "cvar_loss_amount": "31450.2500",
      "var_percent": 0.0934,
      "cvar_percent": 0.1219,
      "pnl_cutoff_amount": "-24100.8000"
    },
    {
      "confidence_level": 0.95,
      "var_loss_amount": "30980.2000",
      "cvar_loss_amount": "39120.4000",
      "var_percent": 0.1201,
      "cvar_percent": 0.1516,
      "pnl_cutoff_amount": "-30980.2000"
    },
    {
      "confidence_level": 0.99,
      "var_loss_amount": "43120.5000",
      "cvar_loss_amount": "51240.8000",
      "var_percent": 0.1671,
      "cvar_percent": 0.1986,
      "pnl_cutoff_amount": "-43120.5000"
    }
  ],
  "instrument_results": [
    {
      "symbol": "AAPL",
      "quantity": "500.0000",
      "baseline_price": "180.0000",
      "baseline_market_value": "90000.0000",
      "mean_terminal_price": "179.9200",
      "mean_pnl": "-40.0000",
      "pnl_std": "7940.2100",
      "var_95_loss": "12980.4000",
      "annualized_volatility": 0.3300
    },
    {
      "symbol": "MSFT",
      "quantity": "400.0000",
      "baseline_price": "420.0000",
      "baseline_market_value": "168000.0000",
      "mean_terminal_price": "419.8810",
      "mean_pnl": "-47.5590",
      "pnl_std": "13420.1200",
      "var_95_loss": "21950.8000",
      "annualized_volatility": 0.3000
    }
  ],
  "narrative": "Monte Carlo simulation 'MC_MC_EQUITY_STRESS_20D_1794827000_A1B2C3' generated 10000 paths over a 20-day horizon with seed 42. Mean P&L is -$87.56 with 52.1% probability of loss. 95% Monte Carlo VaR is $30,980.20 (12.01% of portfolio)."
}
```

---

### `GET /runs/{run_code}`
Retrieves historical simulation run results, distribution statistics, VaR/ES, and instrument breakdowns.
