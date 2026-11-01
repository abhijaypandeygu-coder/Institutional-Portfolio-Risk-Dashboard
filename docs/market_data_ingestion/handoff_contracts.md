# M02 Hand-Off Contracts (M03 Quality & M04 Instrument Reference)

## 1. M02 -> M03 (Market Data Quality & Validation)
M02 is responsible for basic syntactic parsing, sequence continuity, and deduplication.
M02 forwards validated canonical events via `global_event_bus` or direct dependency:
- `MarketDataChannel.TICK` -> `MarketTick`
- `MarketDataChannel.TRADE` -> `TradeEvent`
- `MarketDataChannel.ORDER_BOOK_L2` -> `OrderBookSnapshot` / `OrderBookDelta`

M03 subscribes to these streams to apply deeper quantitative checks:
- Stale price movement detection.
- Cross-feed arbitrage anomaly detection.
- Bid/ask spread inversion detection.
- Quality score computation.

## 2. M02 -> M04 (Instrument & Reference Data Management)
M02 uses `instrument_id` (e.g. `EQ_RELIANCE`, `EQ_TCS`).
When M04 is deployed, it provides symbol-to-ISIN translation and tick-size rule lookups. M02 consumes M04's mapping interface without owning instrument reference master tables.
