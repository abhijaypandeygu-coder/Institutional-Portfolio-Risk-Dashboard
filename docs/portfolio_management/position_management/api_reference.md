# API Reference: M05.02 — Position Management

## Base Path: `/api/v1/positions`

### 1. Position Book Registration & Snapshots
- **POST** `/`
  - Register or retrieve a unique position book for `(portfolio_id, account_id, instrument_id, [listing_id])`.
- **GET** `/{position_id}`
  - Retrieve position book metadata, current status, and current snapshot version.
- **GET** `/{position_id}/snapshot`
  - Retrieve latest calculated position snapshot (gross long, gross short, net signed, settled, unsettled, economic).
- **GET** `/{position_id}/snapshot/as-of?as_of_dt=YYYY-MM-DDTHH:MM:SS`
  - Retrieve historical position snapshot active as of an exact timestamp.

### 2. Position Event Ingestion & Ledger
- **POST** `/events`
  - Ingest an immutable position event (`TRADE_BUY`, `TRADE_SELL`, `SHORT_OPEN`, `SHORT_COVER`, `SETTLEMENT`, `STOCK_SPLIT`, etc.). Enforces idempotency via `idempotency_key` and automatically recalculates projections.
- **GET** `/{position_id}/events`
  - List all applied events for a position book in chronological sequence.

### 3. Account & Portfolio Level Inquiries
- **GET** `/accounts/{account_id}`
  - List all position books belonging to a specific trading or custody account.
- **GET** `/portfolios/{portfolio_id}`
  - List all position books belonging to a portfolio.
- **GET** `/portfolios/{portfolio_id}/aggregates`
  - Retrieve portfolio-level position aggregates across contributing accounts, preserving gross long and gross short exposure.

### 4. Inter-Account Transfers
- **POST** `/transfers`
  - Initiate an atomic internal or external transfer between two accounts. Creates synchronized outbound (`TRANSFER_OUT`) and inbound (`TRANSFER_IN`) event legs.

### 5. Short Position Borrow Metadata
- **POST** `/{position_id}/borrow`
  - Record borrow locate ID, lender reference, borrow rate, and recall date for short positions.
- **GET** `/{position_id}/borrow`
  - Retrieve current active borrow metadata.

### 6. Reconciliation & Discrepancies
- **POST** `/reconciliation`
  - Submit external broker/custodian holdings and identify position or quantity discrepancies.
- **GET** `/reconciliation`
  - Query reconciliation records with discrepancy filtering.

### 7. Deterministic Replay & Rebuild
- **POST** `/{position_id}/rebuild`
  - Recomputes all position snapshot versions deterministically from the beginning of the immutable event ledger.
