# M10.08 Scenario Comparison — API Reference

Base URL prefix: `/api/v1/scenario-comparisons`

---

## 1. Comparison Set Management

### `POST /`
Creates a comparison configuration with optional initial scenario members.

**Request Body:**
```json
{
  "comparison_code": "CMP_STRESS_2026_Q4",
  "name": "Q4 Executive Stress Testing Comparison",
  "description": "Comparing broad crash, sector shock, and liquidity stress",
  "portfolio_id": "PORT_TECH_EQUITIES",
  "baseline_snapshot_id": "BASE_SNAPSHOT_Q4",
  "base_currency": "USD",
  "ranking_metric": "loss_amount",
  "ranking_direction": "DESCENDING",
  "normalization_method": "MIN_MAX",
  "weights_json": {
    "loss_amount": 0.6,
    "var_95_amount": 0.4
  },
  "initial_members": [
    {
      "scenario_id": "CRASH_2026",
      "scenario_run_id": "RUN_CRASH_01",
      "scenario_type": "MARKET_CRASH",
      "scenario_name": "Broad Market Tech Crash"
    },
    {
      "scenario_id": "LIQ_STRESS_01",
      "scenario_run_id": "RUN_LIQ_01",
      "scenario_type": "LIQUIDITY_STRESS",
      "scenario_name": "Severe Liquidity Contraction"
    }
  ]
}
```

---

### `GET /`
Lists saved scenario comparisons, optionally filtered by `portfolio_id`.

---

### `GET /{comparison_code}`
Retrieves a comparison configuration by code or ID.

---

### `POST /{comparison_code}/members`
Adds a scenario run member to the comparison set.

**Request Body:**
```json
{
  "scenario_id": "MC_20D_STRESS",
  "scenario_run_id": "MC_RUN_99",
  "scenario_type": "MONTE_CARLO",
  "scenario_name": "Monte Carlo 20-Day Heavy Tail Simulation"
}
```

---

### `DELETE /{comparison_code}/members/{member_id}`
Removes a scenario run member from the comparison set.

---

### `POST /{comparison_code}/validate`
Validates scenario readiness, scope compatibility, currency alignment, and data quality.

---

## 2. Comparison Execution & Results

### `POST /{comparison_code}/execute`
Executes comparative evaluation across all member scenarios and baseline.

**Request Body:**
```json
{
  "baseline_nav_override": "2000000.0000",
  "ranking_metric_override": "loss_amount",
  "ranking_direction_override": "DESCENDING"
}
```

**Response (200 OK):**
```json
{
  "id": "e81f129a-5431-4091-a129-923187a19c28",
  "comparison_id": "a988d871-3319-48ab-bbf0-891a27e77b10",
  "run_code": "CMP_CMP_STRESS_2026_Q4_1794828000_F1E2D3",
  "configuration_version": 1,
  "baseline_snapshot_id": "BASE_SNAPSHOT_Q4",
  "execution_status": "COMPLETED",
  "started_at": "2026-11-16T05:00:00Z",
  "completed_at": "2026-11-16T05:00:01Z",
  "duration_ms": 45,
  "application_version": "1.0.0",
  "calculation_engine_version": "1.0.0",
  "validation_summary": { "status": "PASSED" },
  "metric_results": [
    {
      "scenario_run_id": "RUN_CRASH_01",
      "scenario_name": "Broad Market Tech Crash",
      "scenario_type": "MARKET_CRASH",
      "baseline_nav": "2000000.0000",
      "scenario_nav": "1840000.0000",
      "pnl": "-160000.0000",
      "return_pct": "-8.0000",
      "loss_amount": "160000.0000",
      "loss_pct": "8.0000",
      "var_95_amount": "170000.0000",
      "cvar_95_amount": "190000.0000",
      "max_drawdown_pct": "9.5000",
      "liquidity_cost_amount": "9000.0000",
      "quality_status": "AVAILABLE",
      "currency": "USD"
    }
  ],
  "rankings": [
    {
      "scenario_run_id": "RUN_CRASH_01",
      "scenario_name": "Broad Market Tech Crash",
      "ranking_metric": "loss_amount",
      "ranking_direction": "DESCENDING",
      "rank_position": 1,
      "raw_metric_value": "160000.0000",
      "normalized_score": 1.0,
      "composite_score": 1.0,
      "tie_group": 1,
      "eligibility_status": "ELIGIBLE"
    }
  ],
  "sensitivities": [],
  "attributions": [],
  "narrative": "Scenario comparison 'CMP_...' executed across 2 scenarios. Top ranked scenario is 'Broad Market Tech Crash' by loss_amount with raw value 160,000.00."
}
```

---

### `GET /runs/{run_code}`
Retrieves a full saved comparison run record.

### `GET /runs/{run_code}/rankings`
Retrieves scenario ranking results for a run.

### `GET /runs/{run_code}/sensitivities`
Retrieves assumption sensitivity comparisons between scenarios.

### `GET /runs/{run_code}/attribution`
Retrieves component difference attribution and reconciliation residuals.
