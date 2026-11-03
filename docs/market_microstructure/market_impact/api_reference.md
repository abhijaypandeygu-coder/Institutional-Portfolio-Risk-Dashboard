# M09.04 — Market Impact REST API Reference

Base Endpoint: `/api/v1/market-microstructure/impact`

All endpoints return JSON responses adhering to OpenAPI 3.1 specifications.

---

### 1. Direct Static Depth Walk Simulation
Simulates immediate level consumption directly from raw levels without database persistence.

- **Method:** `POST`
- **Path:** `/api/v1/market-microstructure/impact/depth-walk/simulate`
- **Request Body:**
```json
{
  "side": "BUY",
  "proposed_quantity": 1500,
  "reference_price": 100.025,
  "levels": [
    {"price": 100.05, "quantity": 500},
    {"price": 100.10, "quantity": 700},
    {"price": 100.15, "quantity": 1000},
    {"price": 100.20, "quantity": 1200}
  ]
}
```

- **Response:** `200 OK`
```json
{
  "side": "BUY",
  "proposed_quantity": 1500.0,
  "reference_price": 100.025,
  "visible_fill_quantity": 1500.0,
  "residual_unfilled_quantity": 0.0,
  "fill_percentage": 100.0,
  "average_execution_price": 100.093333,
  "marginal_execution_price": 100.15,
  "gross_execution_value": 150140.0,
  "estimated_cost_amount": 102.50,
  "estimated_cost_bps": 6.8318,
  "spread_crossing_bps": 2.4994,
  "additional_depth_bps": 4.3323,
  "consumed_level_count": 3,
  "available_level_count": 4,
  "consumed_levels": [
    {
      "level_index": 1,
      "price": 100.05,
      "available_quantity": 500.0,
      "consumed_quantity": 500.0,
      "remaining_quantity": 0.0,
      "executed_value": 50025.0
    }
  ]
}
```

---

### 2. Order-Size Sensitivity & Marginal Cost
- **Method:** `POST`
- **Path:** `/api/v1/market-microstructure/impact/sensitivity`
- **Request Body:**
```json
{
  "side": "BUY",
  "sizes": [500, 1000, 1500, 2000],
  "reference_price": 100.0,
  "levels": [
    {"price": 100.05, "quantity": 500},
    {"price": 100.10, "quantity": 700},
    {"price": 100.15, "quantity": 1000}
  ]
}
```

---

### 3. Empirical Model Prediction
- **Method:** `POST`
- **Path:** `/api/v1/market-microstructure/impact/predict`
- **Request Body:**
```json
{
  "model_type": "SQUARE_ROOT",
  "order_quantity": 10000,
  "expected_horizon_volume": 1000000,
  "volatility": 0.02,
  "impact_coefficient_y": 0.50
}
```
- **Response:**
```json
{
  "model_type": "SQUARE_ROOT",
  "impact_bps": 10.0,
  "standard_error_bps": 2.0,
  "prediction_lower_bps": 6.08,
  "prediction_upper_bps": 13.92,
  "status": "VALID"
}
```

---

### 4. Configuration & Scenarios

#### 4.1 Create Policy Configuration
- **Method:** `POST`
- **Path:** `/api/v1/market-microstructure/impact/configs`

#### 4.2 Register Impact Model
- **Method:** `POST`
- **Path:** `/api/v1/market-microstructure/impact/models`

#### 4.3 Create Scenario
- **Method:** `POST`
- **Path:** `/api/v1/market-microstructure/impact/scenarios`

#### 4.4 Execute Persistent Depth Walk
- **Method:** `POST`
- **Path:** `/api/v1/market-microstructure/impact/scenarios/{scenario_id}/execute-depth-walk`

---

### 5. Horizon Comparison
- **Method:** `POST`
- **Path:** `/api/v1/market-microstructure/impact/horizons/compare`
- **Query Parameters:** `order_quantity`, `daily_volume`, `daily_volatility`, `horizons_minutes`

---

### 6. Validation Run Recording
- **Method:** `POST`
- **Path:** `/api/v1/market-microstructure/impact/validation/record`

