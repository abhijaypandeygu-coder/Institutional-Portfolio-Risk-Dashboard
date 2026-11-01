# M05.07 — Portfolio History API Reference

All endpoints are mounted under `/api/v1/portfolios/{portfolio_id}/history`.

## 1. Snapshots

### Capture Snapshot
- **URL:** `POST /api/v1/portfolios/{portfolio_id}/history/snapshots`
- **Status:** `201 Created`
- **Description:** Captures an authoritative EOD, Intraday, or Restated snapshot of holdings, cash balances, and valuations.
- **Request Body:**
```json
{
  "portfolio_id": "PORT-001",
  "snapshot_type": "EOD",
  "effective_as_of": "2026-10-01T16:00:00",
  "knowledge_as_of": "2026-10-01T17:00:00",
  "base_currency": "USD",
  "positions": [...],
  "cash_balances": [...],
  "valuations": [...],
  "source_manifests": [...]
}
```

### List Snapshots
- **URL:** `GET /api/v1/portfolios/{portfolio_id}/history/snapshots?limit=50`
- **Status:** `200 OK`
- **Description:** Lists snapshots ordered by effective date and knowledge date descending.

## 2. Bitemporal Point-in-Time Query

### Query As-Of
- **URL:** `POST /api/v1/portfolios/{portfolio_id}/history/query-as-of`
- **Status:** `200 OK`
- **Description:** Evaluates bitemporal portfolio state.
  - Omit `knowledge_as_of` for **Query A** (Effective-time state using latest knowledge).
  - Provide `knowledge_as_of` for **Query B** (Knowledge-time point-in-time state).
- **Request Body:**
```json
{
  "portfolio_id": "PORT-001",
  "effective_as_of": "2026-10-01T16:00:00",
  "knowledge_as_of": "2026-10-01T17:00:00"
}
```

## 3. Change Timeline

### Record Change Event
- **URL:** `POST /api/v1/portfolios/{portfolio_id}/history/timeline`
- **Status:** `201 Created`
- **Description:** Ingests an atomic portfolio change event with strict monotonic sequence numbering.

### Get Change Timeline
- **URL:** `GET /api/v1/portfolios/{portfolio_id}/history/timeline`
- **Params:** `start_time`, `end_time`, `knowledge_cutoff`, `instrument_id`
- **Status:** `200 OK`
- **Description:** Returns the chronological audit trail of portfolio modifications.

## 4. Risk Run Reproducibility Manifests

### Create Risk Run Manifest
- **URL:** `POST /api/v1/portfolios/{portfolio_id}/history/risk-manifests`
- **Status:** `201 Created`
- **Description:** Produces an immutable SHA-256 fingerprinted input package binding exact snapshot IDs, market data partitions, pricing policies, and corporate action versions.

### Get Risk Run Manifest
- **URL:** `GET /api/v1/portfolios/{portfolio_id}/history/risk-manifests/{manifest_id}`
- **Status:** `200 OK`
- **Description:** Retrieves the exact manifest payload and hash for historical verification.
