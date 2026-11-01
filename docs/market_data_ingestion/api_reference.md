# Module 02: Market Data Ingestion API Reference

All ingestion endpoints are mounted under `/api/v1/market-data`.

### Authentication & Authorization
Requires `X-API-Key` header with RBAC:
- `OPERATOR`: Start/stop feed ingestion, execute backfills.
- `READ_ONLY`: Query telemetry, inspect reconstructed order books.

---

### Ingestion Control Endpoints
- `POST /api/v1/market-data/start`: Start market data streaming for requested instruments and channels (`TICK`, `TRADE`, `ORDER_BOOK_L2`).
- `POST /api/v1/market-data/stop/{feed_id}`: Stop market data streaming and terminate provider connections.

### Order Book Inspection Endpoints
- `GET /api/v1/market-data/order-book/{instrument_id}?depth=5`: Inspect real-time reconstructed order book (depth up to 50 levels) with sequence status and cumulative liquidity.

### Historical Backfill Endpoints
- `POST /api/v1/market-data/backfill`: Trigger historical candle or trade backfill job with idempotent tracking.

### Operational Monitoring Endpoints
- `GET /api/v1/market-data/telemetry`: Query real-time operational metrics:
  - `messages_received`
  - `events_processed`
  - `duplicates_detected`
  - `gaps_detected`
  - `errors_count`
  - `last_latency_ms`
