# M11.06 — Breach Detection: API Reference

All endpoints are hosted under prefix: `/api/v1/breach-detection`

---

## 1. System Health Check
- **Endpoint:** `GET /health`
- **Description:** Verifies that the Breach Detection evaluation engine and deduplication pipelines are operational.
- **Response:**
  ```json
  {
    "module": "M11.06 — Breach Detection",
    "status": "healthy",
    "features": [
      "Active Limit Resolution",
      "Warning & Hard Boundary Detection",
      "Stateful Breach Episodes & Deduplication",
      "Persistence & Recovery Hysteresis",
      "Stale & Invalid Input Rejection",
      "Immutable Cryptographic Evidence"
    ]
  }
  ```

---

## 2. Breach Evaluation

### `POST /evaluate`
Evaluate an incoming risk metric against applicable warning and hard boundaries.
- **Query Parameters:**
  - `hard_threshold` (Decimal, optional): Hard limit boundary.
  - `warning_threshold` (Decimal, optional): Warning limit boundary.
  - `limit_nature` (string, default: `"CAP"`): `"CAP"` (max limit) or `"FLOOR"` (min requirement).
  - `comparison_operator` (string, default: `"GREATER_THAN"`).
  - `active_limit_id` (string, optional): ID of base limit (M11.01/M11.04).
  - `effective_limit_snapshot_id` (string, optional): ID of dynamic limit snapshot (M11.05).
- **Request Body:**
  ```json
  {
    "portfolio_id": "PF_INST_001",
    "target_entity_type": "PORTFOLIO",
    "target_entity_id": "PF_INST_001",
    "metric_code": "PORTFOLIO_VAR",
    "metric_source_module": "M07_MARKET_RISK",
    "metric_value": 12.5,
    "metric_unit": "PERCENT",
    "metric_timestamp": "2026-11-16T10:30:00Z",
    "input_quality_status": "VALID"
  }
  ```
- **Response:**
  ```json
  {
    "id": "evl_3f8a12",
    "evaluation_reference": "EVAL-PORTFOLIO_VAR-20261116103000-AB12",
    "portfolio_id": "PF_INST_001",
    "target_entity_type": "PORTFOLIO",
    "target_entity_id": "PF_INST_001",
    "metric_code": "PORTFOLIO_VAR",
    "metric_value": "12.5000",
    "evaluation_status": "HARD_BREACH",
    "severity": "HIGH",
    "breach_magnitude": "2.5000",
    "utilization": "1.2500",
    "applied_threshold": "10.0000"
  }
  ```
- **Status:** `201 Created`

### `POST /evaluate/batch`
Batch evaluate multiple metrics across portfolios or entities.
- **Status:** `200 OK`

### `GET /evaluations/{evaluation_id}`
Retrieve a specific evaluation log with its observations and event links.

### `GET /evaluations`
Query evaluations with optional filters: `portfolio_id`, `metric_code`, `status`, `limit`.

---

## 3. Breach Events & Episodes

### `GET /events`
Query immutable breach events with filters: `portfolio_id`, `severity`, `event_type`, `limit`.

### `GET /events/{event_id}`
Retrieve a single breach event with exact financial and threshold evidence.

### `GET /episodes`
List active or historical breach episodes with filters: `portfolio_id`, `status` (`ACTIVE_WARNING`, `ACTIVE_HARD_BREACH`, `PERSISTENT_BREACH`, `RECOVERED`).

### `GET /episodes/{episode_id}`
Retrieve details of a breach episode including peak magnitude, lifecycle timestamps, and current state.

### `GET /episodes/{episode_id}/observations`
Retrieve chronological time-series observations recorded during an ongoing breach episode.

---

## 4. Detection Rules

### `POST /rules`
Configure a governed breach detection rule for a specific metric.
- **Request Body:**
  ```json
  {
    "rule_code": "RULE_VAR_PERSISTENCE",
    "rule_name": "Portfolio VaR Duration Persistence Rule",
    "metric_code": "PORTFOLIO_VAR",
    "applicable_scope": "ALL",
    "persistence_mode": "DURATION",
    "required_duration_seconds": 300,
    "recovery_duration_seconds": 180,
    "immediate_breach": false,
    "hysteresis_config": {
      "recovery_threshold": 9.5
    }
  }
  ```
- **Status:** `201 Created`

### `GET /rules`
List all active and configured detection rules.

---

## 5. Monitoring & Audit

### `GET /monitoring/overview`
Get aggregate breach health metrics across active warnings, hard breaches, persistent breaches, and stale input counts.
- **Response:**
  ```json
  {
    "total_active_warnings": 2,
    "total_active_hard_breaches": 1,
    "total_persistent_breaches": 1,
    "total_transient_breaches": 1,
    "total_recovering_breaches": 0,
    "total_stale_inputs": 0,
    "total_invalid_inputs": 0,
    "total_episodes_active": 4
  }
  ```

### `GET /audit`
Retrieve the immutable audit log for detection rules and episode state transitions.
