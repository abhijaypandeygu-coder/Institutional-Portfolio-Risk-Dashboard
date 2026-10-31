# Module 01: Feed Registry & Configuration — Architecture

## Overview
Module 01 (**Feed Registry & Configuration**) is the authoritative metadata and control-plane subsystem of the *Institutional Portfolio Risk Dashboard*.

### Key Design Principles
1. **Control Plane vs Data Plane Separation**: M01 strictly governs *desired states*, *metadata*, *schedules*, and *immutable configurations*. M02 (*Market Data Ingestion Engine*) owns network sockets, connections, and raw market data frames.
2. **Zero-Knowledge Secret Management**: No plaintext passwords, API keys, or broker tokens are stored in database records or exposed in responses. Sensitive credentials must use the `SecretReference` URI pattern (`secret://<scope>/<key>`).
3. **Immutable Versioning**: Configuration updates are append-only. A configuration rollback never destroys history; restoring Version 1 creates Version 3 with the contents of Version 1.
4. **Transactional Outbox for M02 Commands**: State transitions (`START`, `STOP`, `PAUSE`, `DRAIN`) update the desired state and record a command in `feed_lifecycle_commands` in the same atomic database transaction.
5. **Auditing & RBAC**: Every mutating action is protected by role-based access control (`ADMIN`, `OPERATOR`, `READ_ONLY`) and written to an append-only audit trail (`feed_audit_logs`).

```
 +---------------------------------------------------------+
 |             FastAPI Control Plane (M01)                |
 |  [Registry] -> [Versioning] -> [Schedules] -> [Audit]   |
 +----------------------------+----------------------------+
                              | Transactional Outbox
                              v
 +---------------------------------------------------------+
 |       M02 Market Data Ingestion & Session Manager       |
 |  [Transport Engine (C++20)] <-> [WebSocket / Multicast] |
 +----------------------------+----------------------------+
                              | Health Reporting Sink
                              v
 +---------------------------------------------------------+
 |             M01 Feed Health & Telemetry Sink            |
 +---------------------------------------------------------+
```

