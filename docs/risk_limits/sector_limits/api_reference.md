# M11.03 — Sector Limits API Reference

## Base URL
`/api/v1/risk-limits`

---

## Endpoints

### 1. Health Check
- **Endpoint:** `GET /sector-limits/health`
- **Description:** Verifies service health and operational status.
- **Response:**
  ```json
  {
    "status": "healthy",
    "module": "M11.03 - Sector Limits",
    "description": "Sector & Industry Concentration & Active Exposure Controls Engine"
  }
  ```

---

### 2. Configurations

#### Create Configuration
- **Endpoint:** `POST /sector-limits`
- **Request Body:**
  ```json
  {
    "limit_code": "CFG_TECH_MAX",
    "limit_name": "Tech Sector Cap",
    "sector_id": "Information Technology",
    "sector_name": "Information Technology",
    "limit_type": "MAX_SECTOR_WEIGHT",
    "direction": "GROSS",
    "threshold_value": 35.0,
    "warning_threshold": 30.0,
    "threshold_unit": "PERCENT_NAV"
  }
  ```
- **Response:** `201 Created` with `SectorLimitConfigResponse`.

#### List Configurations
- **Endpoint:** `GET /sector-limits`
- **Query Parameters:** `portfolio_id` (optional).
- **Response:** Array of `SectorLimitConfigResponse`.

---

### 3. Profiles

#### Create Profile
- **Endpoint:** `POST /sector-limit-profiles`
- **Request Body:**
  ```json
  {
    "profile_name": "Global Growth Sector Limits",
    "profile_code": "PROF_GLOBAL_GROWTH",
    "classification_system": "GICS",
    "description": "Standard limits profile for global growth mandates"
  }
  ```
- **Response:** `201 Created` with `SectorProfileResponse`.

#### List Profiles
- **Endpoint:** `GET /sector-limit-profiles`
- **Response:** Array of `SectorProfileResponse`.

---

### 4. Assignments

#### Assign Profile
- **Endpoint:** `POST /sector-limit-assignments`
- **Request Body:**
  ```json
  {
    "profile_id": "profile-uuid",
    "target_type": "PORTFOLIO",
    "target_id": "PORT_TECH_001"
  }
  ```
- **Response:** `201 Created` with `SectorAssignmentResponse`.

---

### 5. Portfolio Evaluation

#### Evaluate Portfolio Sector Limits
- **Endpoint:** `POST /sector-limits/evaluate`
- **Request Body:**
  ```json
  {
    "portfolio_id": "PORT_TECH_001",
    "portfolio_nav": 10000000.0,
    "benchmark_id": "SPX",
    "positions": [
      {
        "instrument_id": "AAPL",
        "quantity": 1000,
        "market_value": 2800000.0,
        "sector_id": "Information Technology",
        "industry_id": "Technology Hardware"
      }
    ],
    "benchmark_weights": {
      "Information Technology": 20.0
    }
  }
  ```
- **Response:** `200 OK` with `SectorEvaluationResponse`:
  ```json
  {
    "id": "eval-uuid",
    "portfolio_id": "PORT_TECH_001",
    "portfolio_nav": "10000000.0000",
    "total_eligible_exposure": "2800000.0000",
    "classified_exposure": "2800000.0000",
    "unclassified_exposure": "0.0000",
    "classification_coverage_pct": "100.00",
    "overall_status": "WITHIN_LIMIT",
    "total_sectors_evaluated": 1,
    "total_industries_evaluated": 1,
    "warning_breaches_count": 0,
    "hard_breaches_count": 0,
    "results": [...]
  }
  ```

---

### 6. Breaches

#### Query Breaches
- **Endpoint:** `GET /sector-limits/breaches`
- **Query Parameters:** `portfolio_id` (optional).
- **Response:** Array of `SectorLimitBreachEvent` records.
