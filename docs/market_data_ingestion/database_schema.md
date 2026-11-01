# Module 02: Database Persistence Schema

The ingestion tables are managed by SQLAlchemy 2.x and support PostgreSQL and SQLite.

### 1. `raw_market_events`
Preserves complete raw payloads with full source provenance:
- `id`: INTEGER (Primary Key, Autoincrement)
- `feed_id`: VARCHAR(64) (Indexed)
- `provider_id`: VARCHAR(64)
- `event_type`: VARCHAR(32) (Indexed: `TICK`, `OHLCV`, `TRADE`, `SNAPSHOT`, `DELTA`)
- `provider_event_id`: VARCHAR(128)
- `provider_sequence`: BIGINT
- `instrument_reference`: VARCHAR(64) (Indexed)
- `event_timestamp`: TIMESTAMPTZ
- `receive_timestamp`: TIMESTAMPTZ (Indexed)
- `raw_payload`: JSON
- `schema_version`: VARCHAR(16)
- `processing_status`: VARCHAR(32)

### 2. `normalized_market_ticks`
- `id`: INTEGER (Primary Key, Autoincrement)
- `event_id`: VARCHAR(64) UNIQUE NOT NULL (Indexed)
- `feed_id`: VARCHAR(64) (Indexed)
- `instrument_id`: VARCHAR(64) (Indexed)
- `exchange`: VARCHAR(16)
- `symbol`: VARCHAR(32)
- `price`: NUMERIC(18, 4)
- `quantity`: NUMERIC(18, 4)
- `best_bid_price`: NUMERIC(18, 4)
- `best_bid_quantity`: NUMERIC(18, 4)
- `best_ask_price`: NUMERIC(18, 4)
- `best_ask_quantity`: NUMERIC(18, 4)
- `event_timestamp`: TIMESTAMPTZ (Indexed)
- `receive_timestamp`: TIMESTAMPTZ
- `provider_sequence`: BIGINT
- *Composite Index*: (`instrument_id`, `event_timestamp`)

### 3. `market_ohlcv`
- `id`: INTEGER (Primary Key, Autoincrement)
- `event_id`: VARCHAR(64) UNIQUE NOT NULL
- `feed_id`: VARCHAR(64) (Indexed)
- `instrument_id`: VARCHAR(64) (Indexed)
- `interval`: VARCHAR(16)
- `open_price`: NUMERIC(18, 4)
- `high_price`: NUMERIC(18, 4)
- `low_price`: NUMERIC(18, 4)
- `close_price`: NUMERIC(18, 4)
- `volume`: NUMERIC(22, 4)
- `candle_start`: TIMESTAMPTZ (Indexed)
- `candle_end`: TIMESTAMPTZ
- `source_provider`: VARCHAR(64)
- *Unique Constraint*: (`feed_id`, `instrument_id`, `interval`, `candle_start`)

### 4. `market_trade_events`
- `id`: INTEGER (Primary Key, Autoincrement)
- `event_id`: VARCHAR(64) UNIQUE NOT NULL
- `feed_id`: VARCHAR(64) (Indexed)
- `instrument_id`: VARCHAR(64) (Indexed)
- `exchange`: VARCHAR(16)
- `provider_trade_id`: VARCHAR(128)
- `price`: NUMERIC(18, 4)
- `quantity`: NUMERIC(18, 4)
- `trade_timestamp`: TIMESTAMPTZ (Indexed)
- `receive_timestamp`: TIMESTAMPTZ
- `aggressor_side`: VARCHAR(8)
- `sequence_number`: BIGINT

### 5. `order_book_snapshots`
- `id`: INTEGER (Primary Key, Autoincrement)
- `event_id`: VARCHAR(64) UNIQUE NOT NULL
- `feed_id`: VARCHAR(64) (Indexed)
- `instrument_id`: VARCHAR(64) (Indexed)
- `exchange`: VARCHAR(16)
- `sequence_number`: BIGINT (Indexed)
- `snapshot_timestamp`: TIMESTAMPTZ (Indexed)
- `bid_levels`: JSON
- `ask_levels`: JSON
- `receive_timestamp`: TIMESTAMPTZ

### 6. `order_book_deltas`
- `id`: INTEGER (Primary Key, Autoincrement)
- `event_id`: VARCHAR(64) UNIQUE NOT NULL
- `feed_id`: VARCHAR(64) (Indexed)
- `instrument_id`: VARCHAR(64) (Indexed)
- `sequence_number`: BIGINT (Indexed)
- `previous_sequence_number`: BIGINT
- `event_timestamp`: TIMESTAMPTZ (Indexed)
- `side`: VARCHAR(8) (`BID`, `ASK`)
- `price`: NUMERIC(18, 4)
- `quantity`: NUMERIC(18, 4)
- `operation`: VARCHAR(16) (`INSERT`, `UPDATE`, `DELETE`)
- `order_count`: INTEGER
- `receive_timestamp`: TIMESTAMPTZ

### 7. `ingestion_checkpoints`
- `id`: INTEGER (Primary Key, Autoincrement)
- `feed_id`: VARCHAR(64)
- `instrument_id`: VARCHAR(64)
- `channel`: VARCHAR(32)
- `last_processed_sequence`: BIGINT
- `last_processed_timestamp`: TIMESTAMPTZ
- `updated_at`: TIMESTAMPTZ
- *Unique Constraint*: (`feed_id`, `instrument_id`, `channel`)

### 8. `historical_backfill_jobs`
- `id`: VARCHAR(64) (Primary Key)
- `feed_id`: VARCHAR(64) (Indexed)
- `instrument_id`: VARCHAR(64) (Indexed)
- `data_type`: VARCHAR(32) (`OHLCV`, `TRADES`)
- `requested_start`: TIMESTAMPTZ
- `requested_end`: TIMESTAMPTZ
- `job_status`: VARCHAR(32) (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`)
- `records_received`: INTEGER
- `error_summary`: TEXT
- `created_at`: TIMESTAMPTZ
- `completed_at`: TIMESTAMPTZ
