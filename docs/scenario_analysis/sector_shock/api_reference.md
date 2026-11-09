# M10.04 — Sector Shock Simulation API Reference

The **Sector Shock Simulation** API enables institutional risk applications to configure direct sector and industry shocks, define cross-sector and factor spillover transmission networks, execute stress simulations against equity portfolios, and retrieve granular group and channel attribution results.

Base Path: `/api/v1/scenarios/sector-shock`

---

## 1. Scenario Management

### `POST /api/v1/scenarios/sector-shock`
Creates a new versioned sector shock scenario.

#### Request Body
```json
{
  "scenario_code": "SEC_CRISIS_2026",
  "scenario_name": "Financial Contagion & Tech Retrenchment",
  "description": "Direct stress on Financials (-25%) and Tech Software (-30%), cascading to Real Estate (-10%)",
  "category": "CROSS_SECTOR_CONTAGION",
  "visibility": "ORGANIZATION",
  "author_id": "Ayush Sector Risk Lead",
  "group_shocks": [
    {
      "group_identifier": "FINANCIALS",
      "group_type": "SECTOR",
      "classification_system": "GICS",
      "shock_method": "PERCENTAGE",
      "shock_value": "-0.25"
    },
    {
      "group_identifier": "SOFTWARE",
      "group_type": "INDUSTRY",
      "classification_system": "GICS",
      "shock_method": "PERCENTAGE",
      "shock_value": "-0.30"
    }
  ],
  "spillover_relationships": [
    {
      "relationship_code": "REL_FIN_TO_RE_01",
      "source_type": "SECTOR",
      "source_identifier": "FINANCIALS",
      "target_type": "SECTOR",
      "target_identifier": "REAL_ESTATE",
      "spillover_coefficient": "0.40"
    }
  ]
}
```

#### Response: `201 Created`
Returns `SectorShockScenarioResponse`.

---

### `GET /api/v1/scenarios/sector-shock`
Lists sector shock scenarios with optional filtering by `category`, `portfolio_id`, and `status`.

---

### `GET /api/v1/scenarios/sector-shock/{scenario_id}`
Retrieves scenario configuration details by ID.

---

## 2. Simulation Execution

### `POST /api/v1/scenarios/sector-shock/runs`
Executes a sector shock simulation against an equity portfolio.

#### Request Body
```json
{
  "scenario_name": "Q4 Sector Contagion Run",
  "portfolio_id": "INST_EQUITY_SECTOR_PORTFOLIO",
  "scenario_id": "sec_sc_9a01f4c3b2e1",
  "base_currency": "USD",
  "baseline_nav": "2500000.00",
  "conflict_resolution_policy": "MOST_SPECIFIC_WINS",
  "composition_policy": "ADDITIVE",
  "missing_data_policy": "STRICT",
  "group_shocks": [
    {
      "group_identifier": "FINANCIALS",
      "group_type": "SECTOR",
      "shock_method": "PERCENTAGE",
      "shock_value": "-0.25"
    },
    {
      "group_identifier": "SOFTWARE",
      "group_type": "INDUSTRY",
      "shock_method": "PERCENTAGE",
      "shock_value": "-0.30"
    }
  ],
  "spillover_relationships": [
    {
      "relationship_code": "REL_FIN_TO_RE_01",
      "source_type": "SECTOR",
      "source_identifier": "FINANCIALS",
      "target_type": "SECTOR",
      "target_identifier": "REAL_ESTATE",
      "spillover_coefficient": "0.40"
    }
  ],
  "positions": [
    {
      "instrument_id": "JPM_US",
      "listing_id": "JPM_NYSE",
      "signed_quantity": "2000",
      "baseline_price": "150.00",
      "currency": "USD",
      "sector": "FINANCIALS",
      "industry": "BANKS"
    },
    {
      "instrument_id": "MSFT_US",
      "listing_id": "MSFT_NASDAQ",
      "signed_quantity": "1000",
      "baseline_price": "400.00",
      "currency": "USD",
      "sector": "TECHNOLOGY",
      "industry": "SOFTWARE"
    },
    {
      "instrument_id": "AMT_US",
      "listing_id": "AMT_NYSE",
      "signed_quantity": "1000",
      "baseline_price": "200.00",
      "currency": "USD",
      "sector": "REAL_ESTATE",
      "industry": "REITS"
    },
    {
      "instrument_id": "BAC_US",
      "listing_id": "BAC_NYSE",
      "signed_quantity": "-2000",
      "baseline_price": "50.00",
      "currency": "USD",
      "sector": "FINANCIALS",
      "industry": "BANKS"
    }
  ]
}
```

#### Response: `201 Created`
Returns `SectorSimulationSummaryResponse`:
- `baseline_nav`, `scenario_nav`, `scenario_pnl`, `scenario_loss`, `scenario_return`.
- `direct_exposure_coverage`, `spillover_exposure_coverage`, `classification_coverage`, `sensitivity_coverage`.
- `position_results`: Detailed revaluation, direct return, spillover adjustment, factor adjustment, final return, PnL, loss, contribution.
- `group_results`: Sector and industry aggregation metrics.
- `attribution_results`: Channel decomposition (`DIRECT_SECTOR_SHOCK`, `INDIRECT_SPILLOVER`, `FACTOR_MEDIATED`, `MANUAL_ADJUSTMENT`).
- `warnings`: Diagnostic caveats.

---

### `GET /api/v1/scenarios/sector-shock/runs/{run_id}`
Retrieves a complete persisted simulation run by ID.

