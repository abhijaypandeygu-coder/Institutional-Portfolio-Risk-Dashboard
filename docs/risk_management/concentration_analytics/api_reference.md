# M06.06 Concentration Analytics API Reference

## Endpoints

### 1. Calculate Concentration
- **Endpoint**: `POST /api/v1/risk/concentration/calculate`
- **Description**: Computes CR1..CR20, HHI (decimal & 10,000-point scale), effective groups, and ranked contributors for a portfolio or group across a chosen dimension (`INSTRUMENT`, `ISSUER`, `SECTOR`, `INDUSTRY`, `COUNTRY`, `REGION`) and exposure basis (`GROSS_EXPOSURE`, `LONG_EXPOSURE`, `SHORT_EXPOSURE`, `ABSOLUTE_NET_EXPOSURE`).
- **Request Body**:
```json
{
  "portfolio_id": "port-001",
  "grouping_dimension": "INSTRUMENT",
  "exposure_basis": "GROSS_EXPOSURE",
  "reporting_currency": "USD"
}
```

---

### 2. Get Calculation Result
- **Endpoint**: `GET /api/v1/risk/concentration/results/{result_id}`
- **Description**: Retrieves full breakdown of an existing concentration calculation run including active policy alert flags and top-20 contributors.

---

### 3. Get Concentration Ratios
- **Endpoint**: `GET /api/v1/risk/concentration/ratios?result_id={result_id}`
- **Description**: Retrieves dictionary of cumulative concentration ratios (`CR1`, `CR3`, `CR5`, `CR10`, `CR20`).

---

### 4. Get HHI Metrics
- **Endpoint**: `GET /api/v1/risk/concentration/hhi?result_id={result_id}`
- **Description**: Retrieves decimal HHI, 10,000-point HHI, effective group equivalent ($N_{\text{effective}}$), and categorical interpretation (`DIVERSIFIED`, `MODERATE`, `HIGHLY_CONCENTRATED`).

---

### 5. Compare Concentration Runs
- **Endpoint**: `POST /api/v1/risk/concentration/compare`
- **Description**: Point-to-point comparison between two calculation runs (e.g. historical T vs T-1), measuring $\Delta \text{HHI}$, $\Delta CR_5$, $\Delta CR_{10}$, and trend classification (`INCREASING`, `DECREASING`, `STABLE`).

---

### 6. Create Policy Threshold
- **Endpoint**: `POST /api/v1/risk/concentration/policies`
- **Description**: Defines institutional threshold limits for warning and critical triggers on Top 1, CR5, HHI 10k, and minimum effective groups.

