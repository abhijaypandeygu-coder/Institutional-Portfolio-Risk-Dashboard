# M11.02 — Position Limits: API Reference

## Base Path
`/api/v1/risk-limits`

---

## Endpoints

### 1. Health Check
- **Endpoint:** `GET /position-limits/health`
- **Description:** Verifies that the position limits engine is healthy.
- **Response:**
  ```json
  {
    "status": "healthy",
    "module": "M11.02 - Position Limits",
    "description": "Position Limits & Concentration Controls Engine"
  }
  ```

---

### 2. Create Position Limit Configuration
- **Endpoint:** `POST /position-limits`
- **Status Code:** `201 Created`
- **Request Body:**
  ```json
  {
    "limit_code": "MAX_WT_10",
    "limit_name": "10% Max Position Weight",
    "limit_type": "MAX_POSITION_WEIGHT",
    "direction": "ANY",
    "aggregation_level": "INSTRUMENT",
    "threshold_value": "10.0",
    "warning_threshold": "8.0",
    "threshold_unit": "PERCENT_NAV"
  }
  ```

---

### 3. List Configurations
- **Endpoint:** `GET /position-limits`
- **Parameters:** `portfolio_id` (optional)
- **Response:** Array of `ConfigurationResponse` objects.

---

### 4. Create Limit Profile
- **Endpoint:** `POST /position-limit-profiles`
- **Status Code:** `201 Created`
- **Request Body:**
  ```json
  {
    "profile_code": "EQUITY_CORE_01",
    "profile_name": "Equity Core Profile",
    "profile_tier": "MODERATE",
    "initial_limits": [
      {
        "limit_code": "MAX_WT_10",
        "limit_name": "10% Max Weight",
        "limit_type": "MAX_POSITION_WEIGHT",
        "threshold_value": "10.0",
        "warning_threshold": "8.0",
        "threshold_unit": "PERCENT_NAV"
      }
    ]
  }
  ```

---

### 5. Assign Profile to Target
- **Endpoint:** `POST /position-limit-assignments`
- **Status Code:** `201 Created`
- **Request Body:**
  ```json
  {
    "profile_id": "PROFILE_UUID",
    "target_type": "PORTFOLIO",
    "target_id": "PORT_101",
    "precedence": 1
  }
  ```

---

### 6. Evaluate Portfolio Positions
- **Endpoint:** `POST /position-limits/evaluate`
- **Request Body:**
  ```json
  {
    "portfolio_id": "PORT_101",
    "portfolio_nav": "5000000.0",
    "base_currency": "USD",
    "positions": [
      {
        "instrument_id": "AAPL_US",
        "symbol": "AAPL",
        "issuer_id": "ISSUER_APPLE",
        "quantity": "3000",
        "market_value": "450000.0",
        "currency": "USD"
      }
    ]
  }
  ```
- **Response:**
  ```json
  {
    "id": "EVAL_UUID",
    "portfolio_id": "PORT_101",
    "evaluation_type": "PORTFOLIO_WIDE",
    "evaluation_timestamp": "2026-11-16T11:10:00Z",
    "portfolio_nav": "5000000.0000",
    "base_currency": "USD",
    "overall_status": "WARNING",
    "total_positions_evaluated": 1,
    "warning_breaches_count": 1,
    "hard_breaches_count": 0,
    "results": [
      {
        "limit_code": "MAX_WT_10",
        "limit_type": "MAX_POSITION_WEIGHT",
        "instrument_id": "AAPL_US",
        "symbol": "AAPL",
        "actual_exposure": "9.0000",
        "warning_threshold": "8.0000",
        "hard_threshold": "10.0000",
        "threshold_unit": "PERCENT_NAV",
        "warning_utilization_pct": "112.50",
        "hard_utilization_pct": "90.00",
        "remaining_capacity": "1.0000",
        "breach_amount": "0.0000",
        "evaluation_status": "WARNING"
      }
    ],
    "execution_duration_ms": 45
  }
  ```

---

### 7. Evaluate Proposed Order (Pre-Trade Simulation)
- **Endpoint:** `POST /position-limits/evaluate/proposed-order`
- **Request Body:**
  ```json
  {
    "portfolio_id": "PORT_101",
    "portfolio_nav": "5000000.0",
    "instrument_id": "AAPL_US",
    "symbol": "AAPL",
    "order_side": "BUY",
    "order_quantity": "500",
    "reference_price": "180.0",
    "current_quantity": "3000",
    "current_market_value": "450000.0"
  }
  ```
- **Response:**
  ```json
  {
    "portfolio_id": "PORT_101",
    "instrument_id": "AAPL_US",
    "symbol": "AAPL",
    "order_side": "BUY",
    "order_quantity": "500",
    "reference_price": "180.0",
    "current_market_value": "450000.0",
    "projected_market_value": "630000.0",
    "current_weight_pct": "9.0000",
    "projected_weight_pct": "12.6000",
    "projected_notional": "630000.0",
    "overall_status": "HARD_LIMIT_EXCEEDED",
    "evaluations": [...],
    "is_pretrade_approved": false
  }
  ```

---

### 8. List Breach Events
- **Endpoint:** `GET /position-limits/breaches`
- **Parameters:** `portfolio_id` (optional)
- **Response:** Array of `PositionLimitBreachEvent` records.
