# M05.07 — Portfolio History Architecture

## 1. Overview and Core Purpose
The **M05.07 Portfolio History** engine provides institutional bitemporal portfolio state retention, historical point-in-time reconstruction, chronological change tracking, and reproducible risk run input manifest generation for the Institutional Portfolio Risk Dashboard.

It solves the fundamental temporal accounting problem in institutional finance:
- **Economic Time (`effective_at` / `effective_as_of`)**: When an economic event took place or the business date of a holding state.
- **Knowledge Time (`recorded_at` / `knowledge_as_of`)**: When the platform ingested or recorded that fact.

## 2. Bitemporal Query Dualism

### Query A (Effective-Time Historical State)
- Evaluates what the portfolio's book was at economic date $T$ using the **best/latest knowledge available today**.
- Includes post-facto adjustments, backdated corporate action corrections, and trade break resolutions recorded after $T$.
- Used for retrospective performance attribution and revised official accounting.

### Query B (Knowledge-Time Historical State)
- Evaluates what the firm's systems **knew** at knowledge cutoff $K$ about economic date $T$.
- Strictly ignores any adjustments or trade breaks recorded after $K$.
- Used for regulatory audit defense, compliance trade checks, and risk model backtesting.

## 3. Data Model Design

```
+-------------------------------------------------------+
|              PortfolioBookSnapshot                    |
|-------------------------------------------------------|
| snapshot_id (PK)                                      |
| portfolio_id, snapshot_type (EOD/INTRADAY/RESTATED)   |
| effective_as_of, knowledge_as_of                      |
| snapshot_version, is_restated, superseded_snapshot_id |
| total_nav_base, snapshot_hash                         |
+-------------------------------------------------------+
         |                       |                |
         v                       v                v
+------------------+   +------------------+   +----------------------+
| HistoricalPos    |   | HistoricalCash   |   | SnapshotSource       |
| Snapshot         |   | Snapshot         |   | Manifest             |
+------------------+   +------------------+   +----------------------+

+-------------------------------------------------------+
|             PortfolioChangeRecord                     |
|-------------------------------------------------------|
| change_record_id (PK)                                 |
| portfolio_id, sequence_number                         |
| event_category (TRADE, DIVIDEND, RESTATED, etc.)      |
| effective_at, recorded_at                             |
| instrument_id, account_id, quantity_delta, cash_delta |
| change_description, change_details                    |
+-------------------------------------------------------+

+-------------------------------------------------------+
|             RiskRunInputManifest                      |
|-------------------------------------------------------|
| manifest_id (PK), portfolio_id, risk_run_id           |
| snapshot_id, effective_as_of, knowledge_as_of         |
| market_data_partition_id, pricing_policy_version      |
| fx_rate_table_version, corporate_action_version       |
| positions_count, total_nav_base, manifest_hash        |
+-------------------------------------------------------+
```

## 4. Immutability & Reproducibility Guarantees
- Snapshots are never mutated in place. When a late-arriving trade break or backdated correction occurs, a new restated snapshot record (e.g. `v2`) is captured, explicitly pointing to `superseded_snapshot_id`.
- Every snapshot and risk run manifest is cryptographically fingerprinted using deterministic canonical JSON hashing (`SHA-256`).
- Downstream risk runs reference immutable `RiskRunInputManifest` identifiers, guaranteeing 100% reproducible historical simulations.

