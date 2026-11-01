# API Reference: M06.04 — Instrument Exposure

## Endpoints

### 1. Calculate Portfolio Instrument Exposure
- **Endpoint:** `POST /api/v1/portfolios/{portfolio_id}/risk/instrument-exposure/calculate`
- **Description:** Runs exposure aggregation, weight calculations, rankings, and dominance detection for an individual portfolio.
- **Request Body (`InstrumentExposureCalculateRequest`):**
  ```json
  {
    "portfolio_id": "port-001",
    "weight_basis": "NAV_BASED",
    "ranking_basis": "GROSS",
    "reporting_currency": "USD"
  }
  ```
- **Response (`InstrumentExposureSummaryResponse`):**
  ```json
  {
    "run_id": "INST-RUN-XXXX",
    "portfolio_id": "port-001",
    "entity_type": "PORTFOLIO",
    "as_of": "2026-11-01T12:00:00Z",
    "reporting_currency": "USD",
    "weight_basis": "NAV_BASED",
    "nav": "50000.000000",
    "total_long_exposure": "21000.000000",
    "total_short_exposure": "10000.000000",
    "total_gross_exposure": "31000.000000",
    "total_net_exposure": "11000.000000",
    "total_instruments_count": 3,
    "long_instruments_count": 2,
    "short_instruments_count": 1,
    "hedged_instruments_count": 0,
    "valuation_coverage_ratio": "1.000000",
    "data_completeness_status": "COMPLETE",
    "denominator_status": "CALCULATED",
    "largest_gross_instrument": "INST-AAPL",
    "dominant_exposures_count": 1,
    "instruments": [...]
  }
  ```

### 2. Calculate Group Instrument Exposure
- **Endpoint:** `POST /api/v1/portfolio-groups/{group_id}/risk/instrument-exposure/calculate`
- **Description:** Consolidates multi-portfolio member holdings via M05.08 `resolve_group_portfolios`.

### 3. Get Ranked Holdings
- **Endpoint:** `GET /api/v1/portfolios/{portfolio_id}/risk/instrument-exposure/rankings`
- **Query Parameters:**
  - `mode`: `LONG` | `SHORT` | `GROSS` | `ABSOLUTE_NET`
  - `limit`: integer (default 10)

### 4. Historical Snapshot Comparison
- **Endpoint:** `GET /api/v1/portfolios/{portfolio_id}/risk/instrument-exposure/comparison`
- **Query Parameters:**
  - `current_snapshot_id`: string
  - `prior_snapshot_id`: string

### 5. Dominant Holdings
- **Endpoint:** `GET /api/v1/portfolios/{portfolio_id}/risk/instrument-exposure/dominant`
- **Description:** Returns instruments triggering configured concentration/dominance thresholds.

