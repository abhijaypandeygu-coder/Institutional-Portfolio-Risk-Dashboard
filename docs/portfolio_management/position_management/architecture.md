# Architecture: M05.02 — Position Management

## 1. Executive Summary
**M05.02 — Position Management** is the authoritative position-quantity layer and immutable event ledger for the Institutional Portfolio Risk Dashboard. It establishes account-level holdings, portfolio-level aggregated exposures, signed long/short accounting, settlement component tracking (settled vs. unsettled vs. available), borrow metadata, inter-account transfers, and corporate action adjustments.

Crucially:
- **Longs are strictly positive ($Q > 0$)** and **Shorts are strictly negative ($Q < 0$)**.
- Gross long and gross short quantities are preserved independently ($Q_{\text{gross long}} = \sum \max(Q_i, 0)$, $Q_{\text{gross short}} = \sum \max(-Q_i, 0)$).
- Position snapshots are derived projections; the event ledger is immutable and authoritative.
- Position management does not execute orders, route trades, or calculate daily portfolio NAVs/P&L.

---

## 2. Core Architecture

```
                 Authorized Trade / Corporate Action / Transfer Event
                                          |
                                          v
                         +---------------------------------+
                         |      Event Ingestion Engine     |
                         | - Idempotency check             |
                         | - Sign convention verification  |
                         | - Deterministic sequence        |
                         +---------------------------------+
                                          |
                                          v
                         +---------------------------------+
                         |   Immutable Position Event Log  |
                         |   (`m05_position_events`)       |
                         +---------------------------------+
                                          |
                                          v
                         +---------------------------------+
                         |   Position Projection Engine    |
                         | - Updates settled & unsettled   |
                         | - Updates net, gross L, gross S |
                         | - Rebuildable from ledger       |
                         +---------------------------------+
                                    /           \
                                   v             v
             +-----------------------+     +--------------------------+
             | Account Position Book |     | Portfolio Aggregate Book |
             | (`m05_position_books`)|     | (`m05_portfolio_agg...`) |
             | - Borrow metadata     |     | - Multi-account gross L  |
             | - Snapshots & History |     | - Multi-account gross S  |
             +-----------------------+     +--------------------------+
```

---

## 3. Database Schema Entities

All entities are managed via SQLAlchemy 2.x and prefixed with `m05_`:
1. `m05_position_books`: Unique identity per `(portfolio_id, account_id, instrument_id, listing_id)`. Tracks current status (`OPEN`, `ACTIVE`, `CLOSED`, `RESTRICTED`) and snapshot version.
2. `m05_position_events`: Immutable event ledger capturing `TRADE_BUY`, `TRADE_SELL`, `SHORT_OPEN`, `SHORT_COVER`, `TRANSFER_IN`, `TRANSFER_OUT`, `SETTLEMENT`, `STOCK_SPLIT`, etc., with signed deltas and idempotency keys.
3. `m05_position_snapshots`: Derived bitemporal snapshots of signed net, gross long, gross short, settled, unsettled, and available quantities.
4. `m05_portfolio_position_aggregates`: Aggregated portfolio positions across contributing accounts preserving gross long and short exposure.
5. `m05_position_borrow_metadata`: Locates, lender references, annual borrow rates, and recall dates for short positions.
6. `m05_position_transfers`: Inter-account and inter-portfolio transfers with linked debit/credit legs.
7. `m05_position_reconciliations`: Broker/custodian vs. internal position discrepancy records for M03.08 exception routing.

