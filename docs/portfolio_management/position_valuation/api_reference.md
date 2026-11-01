# API Reference: M05.03 — Position Valuation

## Base Path: `/api/v1/valuations`

### 1. Run Portfolio Valuation
- **POST** `/run`
  - Calculates market value, remaining cost basis, and unrealized P&L for all open holdings in a portfolio as of a given timestamp.
  - Request Body:
  ```json
  {
    "portfolio_id": "PF_12345",
    "valuation_date": "2026-04-01T16:00:00Z",
    "mark_prices": {
      "INST_AAPL": "150.00",
      "INST_RELIANCE": "2500.00"
    },
    "fx_rates_to_base": {
      "INR": "0.012"
    }
  }
  ```
  - Returns `PortfolioValuationSnapshotResponse` with gross long, gross short, net market value, total cost basis, and unrealized P&L in the portfolio's base currency.

### 2. Position Valuations Retrieval
- **GET** `/portfolios/{portfolio_id}/positions`
  - Retrieve calculated holding valuations. Filterable by `calculation_id`.
- **GET** `/portfolios/{portfolio_id}/positions/{instrument_id}`
  - Retrieve latest calculated valuation for a specific instrument. Exposes signed quantity, signed market value, signed cost basis, and unrealized P&L percentage.

### 3. Portfolio Summary & Snapshots
- **GET** `/portfolios/{portfolio_id}/summary`
  - Retrieve the latest high-level portfolio valuation snapshot. Automatically computes valuation if none exists.
- **GET** `/portfolios/{portfolio_id}/history`
  - Retrieve historical valuation run snapshots over time.

### 4. Realized Profit and Loss
- **GET** `/portfolios/{portfolio_id}/realized-pnl`
  - Retrieve all closed-lot realization records (`CostBasisAllocationResponse`) with query filters for `period_start`, `period_end`, `account_id`, and `instrument_id`.
  - Exposes realized P&L in native currency and portfolio base currency.

### 5. Cost Basis Lots
- **GET** `/portfolios/{portfolio_id}/lots`
  - Inspect active and historical acquisition lots (`CostBasisLotResponse`) including remaining shares, remaining consideration, original price, and accounting status (`OPEN`, `PARTIALLY_CLOSED`, `CLOSED`).
