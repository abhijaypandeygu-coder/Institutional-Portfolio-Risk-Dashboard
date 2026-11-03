# M09.06 — Liquidity Stress Testing API Reference

Base Prefix: `/api/v1/market-microstructure/liquidity-stress`

## Endpoints

### 1. `POST /scenarios`
Create or retrieve an active versioned liquidity stress scenario configuration.
- **Request Body**: `StressConfigCreate`
  - `scenario_code`: string (e.g. `MODERATE_STRESS`)
  - `version`: int
  - `name`: string
  - `description`: Optional string
  - `scenario_type`: `COMBINED_STRESS` | `SINGLE_FACTOR` | `HISTORICAL_EMPIRICAL` | `REVERSE_STRESS` | `CUSTOM`
  - `spread_shock_method`: `MULTIPLIER` | `ADDITIVE_BPS` | `PERCENTAGE`
  - `spread_multiplier`: Decimal (e.g. 1.50)
  - `depth_shock_method`: `UNIFORM` | `LEVEL_SPECIFIC`
  - `bid_depth_reduction`: Decimal (e.g. 0.25)
  - `ask_depth_reduction`: Decimal (e.g. 0.25)
  - `volume_shock_method`: `UNIFORM` | `INTERVAL_SPECIFIC`
  - `volume_contraction`: Decimal (e.g. 0.20)
  - `participation_rate`: Decimal (e.g. 0.10)
  - `execution_horizon_intervals`: int
- **Response**: `201 Created` -> `StressConfigResponse`

### 2. `GET /scenarios`
List all active liquidity stress scenario configurations.
- **Response**: `200 OK` -> `List[StressConfigResponse]`

### 3. `POST /run`
Execute instrument-level liquidity stress test.
- **Request Body**: `StressRunRequest`
  - `run_id`: string
  - `scenario_code`: string
  - `instrument_id`: string
  - `venue`: string
  - `side`: `BUY` | `SELL`
  - `order_quantity`: Decimal
  - `reference_price`: Decimal
  - `baseline_spread`: Decimal
  - `baseline_bids`: List of `BookLevelSchema`
  - `baseline_asks`: List of `BookLevelSchema`
  - `interval_volumes`: List of Decimal volume estimates
  - `explicit_fees`: Decimal
  - `terminal_price`: Optional Decimal
- **Response**: `200 OK` -> `StressRunResponse`
  - Returns baseline vs stressed spread, visible depth, liquidation duration intervals, fillable vs residual quantity, cost decomposition, cost escalation, and full synthetic stressed book.

### 4. `POST /reverse-stress`
Identifies critical liquidity deterioration parameters that breach configured constraints.
- **Request Body**: `ReverseStressRequest`
  - `instrument_id`: string
  - `baseline_spread`: Decimal
  - `baseline_interval_volume`: Decimal
  - `order_quantity`: Decimal
  - `max_acceptable_cost`: Decimal
  - `max_acceptable_intervals`: int
  - `participation_rate`: Decimal
  - `reference_price`: Decimal
- **Response**: `200 OK` -> `ReverseStressResponse`
  - Returns `time_breached_at_baseline`, `critical_volume_contraction_pct`, and `critical_spread_multiplier`.

### 5. `POST /portfolio`
Runs portfolio-level concurrent liquidity stress testing.
- **Request Body**: `PortfolioStressRequest`
  - `portfolio_id`: string
  - `scenario_code`: string
  - `spread_multiplier`: Decimal
  - `volume_contraction`: Decimal
  - `participation_rate`: Decimal
  - `positions`: List of `PortfolioPositionStressItem`
- **Response**: `200 OK` -> `PortfolioStressResponse`
  - Returns total positions, portfolio baseline vs stressed cost, portfolio cost escalation, and critical-path liquidation duration.

