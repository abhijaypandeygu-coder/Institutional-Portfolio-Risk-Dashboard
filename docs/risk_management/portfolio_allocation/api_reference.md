# M06.07 Portfolio Allocation API Reference

## Endpoints

### 1. Calculate Portfolio Allocation
- **Endpoint**: `POST /api/v1/risk/portfolio-allocation/calculate`
- **Description**: Calculates security and cash capital allocations, NAV-based weights, normalized weights, gross exposure weights, and NAV balance sheet reconciliation.
- **Request Body**:
```json
{
  "portfolio_id": "port-001",
  "grouping_dimension": "SECURITY",
  "allocation_view_type": "NAV_CAPITAL_ALLOCATION",
  "reporting_currency": "USD",
  "include_cash_in_breakdown": true
}
```

---

### 2. Get Calculation Result
- **Endpoint**: `GET /api/v1/risk/portfolio-allocation/results/{result_id}`
- **Description**: Retrieves full allocation details, NAV breakdown, reconciliation residual, and ranked component allocations.

---

### 3. Create Allocation Target
- **Endpoint**: `POST /api/v1/risk/portfolio-allocation/targets`
- **Description**: Defines an effective-dated target weight for an entity or grouping dimension with configurable tolerance band.
- **Request Body**:
```json
{
  "portfolio_id": "port-001",
  "grouping_dimension": "CASH",
  "group_id": "CASH_NAV",
  "target_weight": "0.200000",
  "tolerance_band_pp": "0.050000"
}
```

---

### 4. Get Allocation Drift
- **Endpoint**: `GET /api/v1/risk/portfolio-allocation/drift?result_id={result_id}`
- **Description**: Evaluates actual allocation weights against active targets and returns absolute drift in percentage points, capital difference, and drift status (`OVERWEIGHT`, `UNDERWEIGHT`, `MATERIAL_DRIFT`, `WITHIN_TARGET`).

---

### 5. Compare Allocation Runs
- **Endpoint**: `POST /api/v1/risk/portfolio-allocation/compare`
- **Description**: Compares two allocation runs (e.g. historical T vs T-1), measuring $\Delta \text{NAV}$, cash weight change in percentage points, and invested weight change.

