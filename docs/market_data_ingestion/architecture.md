# Module 02: Market Data Ingestion Engine — Architecture

## Overview
Module 02 (**Market Data Ingestion Engine**) is the high-throughput, multi-provider real-time and historical market data ingestion platform of the *Institutional Portfolio Risk Dashboard*.

### Architectural Separation
- **M01 Feed Registry (Control Plane)**: Maintains feed identity, desired state (`ACTIVE`, `INACTIVE`), credentials (`SecretReference`), trading windows, and failover hierarchies.
- **M02 Ingestion Engine (Data Plane)**: Connects to market data sockets, streams ticks/trades/order-book events, normalizes payloads to canonical structures, reconstructs limit order books, deduplicates streams, persists data, and dispatches to downstream consumers (`M03`, `M05`, `M13`).

```
 +---------------------------------------------------------+
 |             M01 Feed Registry (Control Plane)           |
 +----------------------------+----------------------------+
                              | Config & Transactional Outbox
                              v
 +---------------------------------------------------------+
 |      Provider Adapters (Simulated / Real Brokers)       |
 +----------------------------+----------------------------+
                              | Raw Payloads
                              v
 +---------------------------------------------------------+
 |                 Data Normalization Engine               |
 |         (MarketTick, OHLCV, Trades, Snapshots, Deltas)  |
 +----------------------------+----------------------------+
                              | Canonical Events
                              v
 +---------------------------------------------------------+
 |             Event Reliability & Recovery Engine         |
 |         - Sliding window deduplication                  |
 |         - Sequence gap detection & resync tracking       |
 +----------------------------+----------------------------+
                              | Validated Streams
                              v
 +---------------------------------------------------------+
 |          Limit Order Book Reconstruction Engine         |
 |         - In-memory price ladder (Bids desc / Asks asc) |
 |         - Incremental delta application (Insert/Upd/Del)|
 +----------------------------+----------------------------+
                              |
               +--------------+--------------+
               |                             |
               v                             v
   [Async Database Persistence]    [Async In-Process Event Bus]
               |                             |
               | (M01 Health Sink)           v
               +-------------------> (M03 / M05 / M13 Downstream)
```
