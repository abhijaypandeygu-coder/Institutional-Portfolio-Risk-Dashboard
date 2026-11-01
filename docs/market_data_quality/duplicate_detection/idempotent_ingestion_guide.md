# Idempotent Ingestion & Database Concurrency Guide

## 1. Concurrency & Race Conditions
In distributed market data ingestion pipelines, duplicate deliveries frequently arrive simultaneously across parallel workers (due to HTTP retries, redundant socket feeds, or replay streams).

A simple query-then-insert pattern:
```python
if not exists(idempotency_key):
    insert(event)
```
fails under concurrency because two workers querying concurrently will both see `not exists` and attempt insertion.

---

## 2. PostgreSQL & SQLite Enforcement
`M03.05` enforces idempotency directly at the database engine level:
1. `m03_event_identity_registry.idempotency_key` carries an authoritative `UNIQUE` constraint.
2. An atomic insert is attempted inside a database transaction.
3. If an `IntegrityError` (unique constraint violation) occurs due to a concurrent worker arriving a microsecond earlier, the session is cleanly rolled back and redirected to load the canonical identity.
4. The event is classified as `DUPLICATE_EVENT`, and the canonical ID from the winning worker is returned.

---

## 3. Guarantees
- **At-least-once message delivery** is tolerated over the network.
- **Exactly-once business record creation** is guaranteed in the database.
- Application restarts and worker reboots do not reset deduplication history because identity records are durably persisted.
