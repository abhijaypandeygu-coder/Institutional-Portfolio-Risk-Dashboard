# M11.04 — Liquidity Limits API Reference

## Base URL
`/api/v1/risk-limits`

---

## Endpoints

### 1. Health Check
- **Endpoint:** `GET /liquidity-limits/health`
- **Description:** Verifies service health and operational status.
- **Response:**
  ```json
  {
    "status": "healthy",
    "module": "M11.04 - Liquidity Limits",
    "description": "Position & Portfolio Liquidity Restrictions & Horizon Controls Engine"
  }
  ```

---

### 2. Configurations

#### Create Configuration
- **Endpoint:** `POST /liquidity-limits`
- **Request Body:**
  ```json
  {
    "limit_code": "CFG_LIQ_HORIZON_5D",
    "limit_name": "Max Liquidation Horizon 5 Days",
    "limit_type": "MAX_LIQUIDATION_HORIZON",
    "metric_name": "horizon_days",
    "maximum_threshold": 5.0,
    "warning_threshold": 4.0,
    "threshold_unit": "TRADING_DAYS",
    "participation_rate": 0.10
  }
  ```
- **Response:** `201 Created` with `LiquidityLimitConfigResponse`.

#### List Configurations
- **Endpoint:** `GET /liquidity-limits`
- **Query Parameters:** `portfolio_id` (optional).
- **Response:** Array of `LiquidityLimitConfigResponse`.

---

### 3. Profiles

#### Create Profile
- **Endpoint:** `POST /liquidity-limit-profiles`
- **Request Body:**
  ```json
  {
    "profile_name": "Global Equity Liquidity Profile",
    "profile_code": "PROF_GLOBAL_LIQ",
    "description": "Standard limits profile for global equity mandates"
  }
  ```
- **Response:** `201 Created` with `LiquidityProfileResponse`.

#### List Profiles
- **Endpoint:** `GET /liquidity-limit-profiles`
- **Response:** Array of `LiquidityProfileResponse`.

---

### 4. Assignments

#### Assign Profile
- **Endpoint:** `POST /liquidity-limit-assignments`
- **Request Body:**
  ```json
  {
    "profile_id": "profile-uuid",
    "target_type": "PORTFOLIO",
    "target_id": "PORT_TECH_001"
  }
  ```
- **Response:** `201 Created` with `LiquidityAssignmentResponse`.

---

### 5. Evaluations

#### Evaluate Portfolio Liquidity Limits
- **Endpoint:** `POST /liquidity-limits/evaluate`
- **Request Body:**
  ```json
  {
    "portfolio_id": "PORT_TECH_001",
    "portfolio_nav": 10000000.0,
    "positions": [
      {
        "instrument_id": "AAPL",
        "position_side": "LONG",
        "quantity": 1000.0,
        "market_value": 2500000.0,
        "liquidity_score": 85.0,
        "bid_depth": 10000.0,
        "adv": 50000.0,
        "estimated_liquidation_cost": 15000.0
      }
    ],
    "stress_parameters": {
      "scenario_id": "STRESS_CRASH_2026",
      "volume_contraction_pct": 40.0,
      "depth_reduction_pct": 30.0,
      "spread_widening_pct": 50.0,
      "participation_reduction_pct": 20.0
    }
  }
  ```
- **Response:** `200 OK` with `LiquidityEvaluationResponse`.

---

### 6. Pre-trade Simulation

#### Evaluate Proposed Order
- **Endpoint:** `POST /liquidity-limits/evaluate/proposed-order`
- **Request Body:**
  ```json
  {
    "portfolio_id": "PORT_TECH_001",
    "instrument_id": "AAPL",
    "order_side": "BUY",
    "proposed_quantity": 5000.0,
    "current_quantity": 1000.0,
    "adv": 50000.0,
    "participation_rate": 0.10,
    "max_horizon_days_limit": 3.0
  }
  ```
- **Response:** `200 OK` with `ProposedOrderLiquidityResponse`.

---

### 7. Breaches & Exceptions

- **Query Breaches:** `GET /liquidity-limits/breaches?portfolio_id={portfolio_id}`
- **Query Exceptions:** `GET /liquidity-limits/exceptions?portfolio_id={portfolio_id}`
