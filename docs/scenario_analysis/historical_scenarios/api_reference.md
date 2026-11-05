# M10.01 Historical Scenarios API Reference

## Base Path
`/api/v1/scenarios/historical`

---

## 1. Event Library

### `POST /events`
Creates a historical market episode.

**Request Body:**
```json
{
  "event_code": "COVID_CRASH_2020",
  "event_name": "COVID-19 Global Market Crash",
  "description": "Rapid market downturn across global equity indices in Q1 2020",
  "category": "CRISIS",
  "tags": "pandemic,volatility,global_drawdown",
  "global_scope": true,
  "affected_regions": "GLOBAL",
  "affected_markets": "NSE,BSE,NYSE,NASDAQ",
  "start_date": "2020-02-20T00:00:00Z",
  "end_date": "2020-03-23T00:00:00Z",
  "reference_timezone": "UTC",
  "primary_reference_index": "SPX",
  "data_coverage_status": "ADEQUATE",
  "current_version": "1.0.0"
}
```

### `GET /events`
Lists all registered historical events with optional category, region, and status filters.

### `GET /events/{event_id}`
Retrieves event details by ID.

### `POST /events/{event_id}/observations`
Ingests normalized historical asset or factor return observations for an event.

---

## 2. Replay Execution & Results

### `POST /replays`
Executes portfolio shock replay against current or historical holdings.

**Request Body:**
```json
{
  "portfolio_id": "INST_PORTFOLIO_ALPHA",
  "event_id": "hevt_12345",
  "replay_mode": "CURRENT_PORTFOLIO",
  "return_definition": "TOTAL_RETURN",
  "base_currency": "USD",
  "missing_data_policy": "PARTIAL",
  "valuation_baseline": "PRE_EVENT_CLOSE",
  "baseline_nav": "2000000.00",
  "positions": [
    {
      "instrument_id": "AAPL_US",
      "listing_id": "AAPL_NASDAQ",
      "signed_quantity": "2000",
      "baseline_price": "300.00",
      "currency": "USD"
    }
  ],
  "manual_proxy_mappings": {
    "TECH_ETF": "SPY_US"
  },
  "include_daily_path": true
}
```

**Response:**
Returns complete `ReplayRunSummaryResponse` including baseline NAV, scenario NAV, scenario P&L, scenario return, direct/proxy/factor coverage ratios, position-level revaluations, caveats, and warnings.

### `GET /replays/{replay_id}/comparison`
Returns a `HistoricalDifferenceReport` comparing the tested portfolio composition with the historical reference market.

