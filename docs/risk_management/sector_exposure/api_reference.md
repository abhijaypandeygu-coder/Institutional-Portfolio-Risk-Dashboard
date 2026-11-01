# API Reference: M06.03 — Sector Exposure

## Endpoints

### 1. Calculate Portfolio Sector Exposure
- **Endpoint:** `POST /api/v1/risk/sector-exposure/calculate`
- **Description:** Computes sector and industry aggregated exposures, coverage, unclassified positions, and benchmark-relative active weights for a single portfolio.
- **Request Body (`SectorExposureCalculateRequest`):**
  ```json
  {
    "portfolio_id": "port-001",
    "as_of_date": "2026-11-01T00:00:00Z",
    "classification_scheme_code": "GICS",
    "classification_version_code": "2024",
    "benchmark_id": "SP500",
    "weight_basis": "NAV_BASED",
    "include_unclassified": true,
    "active_weight_tolerance": "0.0001"
  }
  ```
- **Response (`SectorExposureSummaryResponse`):**
  ```json
  {
    "run_id": "run-uuid",
    "entity_id": "port-001",
    "entity_type": "PORTFOLIO",
    "as_of_date": "2026-11-01T00:00:00Z",
    "classification_scheme_code": "GICS",
    "benchmark_id": "SP500",
    "currency": "USD",
    "nav": "1000000.000000",
    "total_long_exposure": "100000.000000",
    "total_short_exposure": "0.000000",
    "total_gross_exposure": "100000.000000",
    "total_net_exposure": "100000.000000",
    "sectors": [
      {
        "sector_id": "45",
        "sector_name": "Information Technology",
        "long_exposure": "60000.000000",
        "short_exposure": "0.000000",
        "gross_exposure": "60000.000000",
        "net_exposure": "60000.000000",
        "nav_long_weight": "0.060000",
        "allocation_long_weight": "0.600000",
        "industries": [...]
      }
    ],
    "unclassified_holdings": [...],
    "coverage": {
      "classified_count": 2,
      "unclassified_count": 1,
      "coverage_ratio_by_count": "0.666667",
      "coverage_ratio_by_market_value": "0.900000",
      "status": "PARTIAL"
    },
    "relative_exposures": [
      {
        "sector_id": "45",
        "sector_name": "Information Technology",
        "portfolio_weight": "0.600000",
        "benchmark_weight": "0.400000",
        "active_weight": "0.200000",
        "status": "OVERWEIGHT"
      }
    ]
  }
  ```

### 2. Calculate Group Sector Exposure
- **Endpoint:** `POST /api/v1/risk/sector-exposure/group/{group_id}/calculate`
- **Description:** Resolves portfolio group constituents using M05.08 and calculates consolidated sector exposures.

### 3. Register Benchmark Sector Composition
- **Endpoint:** `POST /api/v1/risk/sector-exposure/benchmarks`
- **Description:** Configures benchmark sector weights for active weight analysis.
