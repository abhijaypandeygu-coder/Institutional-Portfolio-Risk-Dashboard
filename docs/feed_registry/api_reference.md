# Module 01: API Reference

All routes are mounted under `/api/v1/feeds`.

### Authentication
Authentication requires the header `X-API-Key`.
- `ADMIN`: Full access (create failover groups, trigger configuration rollbacks, view audit logs).
- `OPERATOR`: Operational access (register feeds, publish configuration versions, trigger lifecycle transitions, report health).
- `READ_ONLY`: Read-only queries (view feeds, diff configurations, inspect schedules and health summaries).

---

### Feed Registry Endpoints
- `POST /api/v1/feeds`: Register a new feed.
- `GET /api/v1/feeds`: Query feeds by category, state, and status.
- `GET /api/v1/feeds/{feed_id}`: Get feed details by UUID.
- `PATCH /api/v1/feeds/{feed_id}`: Update mutable feed metadata and capabilities.

### Configuration Versioning Endpoints
- `POST /api/v1/feeds/{feed_id}/configurations`: Publish a new version (enforces URI format for secrets).
- `GET /api/v1/feeds/{feed_id}/configurations`: List configuration version history.
- `GET /api/v1/feeds/{feed_id}/configurations/latest`: Fetch active configuration.
- `GET /api/v1/feeds/{feed_id}/configurations/{version}`: Fetch specific historical version.
- `GET /api/v1/feeds/{feed_id}/configurations/diff/{v1}/{v2}`: Semantic diff between two versions.
- `POST /api/v1/feeds/{feed_id}/configurations/rollback`: Perform immutable rollback.

### Lifecycle & Outbox Endpoints
- `POST /api/v1/feeds/{feed_id}/state`: Request state transition (`ACTIVE`, `INACTIVE`, `PAUSED`, `DRAINING`) and enqueues command for M02.

### Scheduling Endpoints
- `POST /api/v1/feeds/{feed_id}/schedule`: Configure active trading sessions and timezone.
- `GET /api/v1/feeds/{feed_id}/schedule`: Retrieve feed scheduling windows.

### Priority & Failover Endpoints
- `POST /api/v1/feeds/failover-groups`: Create group with prioritized feed ranks.
- `GET /api/v1/feeds/failover-groups`: List all failover clusters.

### Monitoring & Telemetry Endpoints
- `POST /api/v1/feeds/{feed_id}/health`: Sink for M02 ingestion telemetry.
- `GET /api/v1/feeds/{feed_id}/health/summary`: Aggregated health and latency status.

### Auditing Endpoints
- `GET /api/v1/feeds/audit/logs`: Query immutable audit logs.

