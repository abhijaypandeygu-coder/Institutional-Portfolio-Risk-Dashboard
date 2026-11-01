# M06.05 Geographic Exposure API Reference

## Endpoints

### 1. Calculate Geographic Exposure
- **Endpoint**: `POST /api/v1/risk/geographic-exposure/calculate`
- **Description**: Computes long, short, gross, net exposure and dual portfolio weights grouped by country and region for a portfolio or portfolio group.
- **Request Body**:
```json
{
  "portfolio_id": "port-001",
  "portfolio_group_id": null,
  "basis": "ISSUER_DOMICILE",
  "as_of_date": "2026-11-01T00:00:00Z",
  "reporting_currency": "USD"
}
```
- **Response**: `GeographicExposureCalculationRunResponse` detailing calculation run metadata, country-level results, regional rollups, and any unknown/unmapped exposures.

---

### 2. Get Calculation Run
- **Endpoint**: `GET /api/v1/risk/geographic-exposure/runs/{run_id}`
- **Description**: Retrieves full breakdown of an existing calculation run.

---

### 3. Compare Geographic Exposures
- **Endpoint**: `POST /api/v1/risk/geographic-exposure/compare`
- **Description**: Performs differential exposure analysis across two calculation runs (e.g., T vs T-1 snapshot comparison).
- **Request Body**:
```json
{
  "base_run_id": "run-uuid-1",
  "comparison_run_id": "run-uuid-2"
}
```
- **Response**: List of `GeographicExposureComparisonResponse` items with absolute delta, percentage changes, and status classification (`NEW_EXPOSURE`, `ELIMINATED_EXPOSURE`, `INCREASED_EXPOSURE`, `REDUCED_EXPOSURE`, `UNCHANGED`).

---

### 4. Reference Data Endpoints
- `POST /api/v1/risk/geographic-exposure/countries`: Register country master entry.
- `GET /api/v1/risk/geographic-exposure/countries`: List active countries.
- `POST /api/v1/risk/geographic-exposure/regions`: Register region master entry.
- `GET /api/v1/risk/geographic-exposure/regions`: List active regions.
- `POST /api/v1/risk/geographic-exposure/country-region-assignments`: Map country to region.
- `POST /api/v1/risk/geographic-exposure/issuer-assignments`: Assign issuer domicile/headquarters.
- `POST /api/v1/risk/geographic-exposure/issuer-revenue`: Record disclosed issuer revenue geographic breakdown.
