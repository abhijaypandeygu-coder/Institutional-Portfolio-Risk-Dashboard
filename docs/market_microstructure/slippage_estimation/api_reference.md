# M09.05 — Slippage Estimation API Reference

Base Prefix: `/api/v1/market-microstructure/slippage`

## Endpoints

### 1. `POST /benchmark-config`
Creates or retrieves an active benchmark price configuration.
- **Request Body**: `BenchmarkConfigCreate`
  - `config_code`: string
  - `version`: int
  - `description`: string
  - `benchmark_type`: `ARRIVAL_MIDPOINT`, `DECISION_PRICE`, `ARRIVAL_PRICE`, etc.
  - `max_quote_age_seconds`: int
  - `allow_cross_venue_benchmarking`: bool
  - `currency`: string
  - `multiplier`: Decimal string
  - `is_active`: bool
- **Response**: `201 Created` -> `BenchmarkConfigResponse`

### 2. `POST /analyze-execution`
Evaluates realized slippage, fill-by-fill attribution, opportunity cost, and Implementation Shortfall.
- **Request Body**: `SlippageAnalysisRequest`
  - `order_id`: string
  - `symbol`: string
  - `side`: `BUY` | `SELL`
  - `order_created_at`: datetime ISO string
  - `requested_quantity`: Decimal
  - `benchmark_type`: string
  - `benchmark_price`: Decimal
  - `benchmark_timestamp`: Optional datetime
  - `fills`: List of `FillInputSchema`
    - `fill_id`, `fill_timestamp`, `price`, `quantity`, `venue`, `bid_at_fill`, `ask_at_fill`, `midpoint_at_fill`, `fees`
  - `terminal_price`: Optional Decimal
  - `multiplier`: Decimal
- **Response**: `200 OK` -> `SlippageExecutionSummaryResponse`

### 3. `GET /execution-summary/{order_id}`
Retrieves stored execution summary and granular fill attributions by `order_id`.
- **Response**: `200 OK` -> `SlippageExecutionSummaryResponse`

### 4. `POST /calibration/run`
Evaluates calibration bias and dispersion metrics between estimated and realized slippage.
- **Request Body**: `CalibrationRunRequest`
  - `run_code`: string
  - `model_name`: string
  - `observations`: List of `CalibrationObservationInput`
    - `order_id`, `symbol`, `side`, `observation_timestamp`, `estimated_slippage_bps`, `realized_slippage_bps`, `predicted_lower_bound_bps`, `predicted_upper_bound_bps`
- **Response**: `200 OK` -> `CalibrationRunResponse`
  - `observation_count`, `mean_error_bps`, `mean_absolute_error_bps`, `root_mean_squared_error_bps`, `t_statistic`, `p_value`, `is_bias_significant`, `interval_coverage_pct`
