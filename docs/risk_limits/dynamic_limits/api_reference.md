# M11.05 — Dynamic Limits: API Reference

All endpoints are hosted under prefix: `/api/v1/risk-limits/dynamic`

---

## 1. Engine Health Check
- **Endpoint:** `GET /health`
- **Description:** Verifies that the Dynamic Limits calculation engine and rule evaluators are active.
- **Response:**
  ```json
  {
    "module": "M11.05 — Dynamic Limits",
    "status": "healthy",
    "features": [
      "Condition-Based Adjustments",
      "Session Time-Based Profiles",
      "Maker-Checker Manual Overrides",
      "Immutable Effective Snapshots",
      "Conflict Resolution Precedence"
    ]
  }
  ```

---

## 2. Policy Management

### `POST /policies`
Create a new dynamic risk limit policy. Optionally takes an initial version containing conditions and schedules.
- **Request Body:**
  ```json
  {
    "policy_code": "POL_VOL_DERISK_2026",
    "name": "Volatility Adaptive Derisking Policy",
    "description": "Reduces max position weight when portfolio volatility spikes",
    "portfolio_id": "PF_INST_001",
    "market": "IN",
    "asset_class": "EQUITY",
    "created_by": "quant_developer_1",
    "initial_version": {
      "target_limit_code": "MAX_POSITION_WEIGHT",
      "limit_nature": "CAP",
      "base_limit_value": 10.0,
      "restrictive_only": true,
      "min_allowed_value": 2.0,
      "max_allowed_value": 15.0,
      "authored_by": "quant_developer_1",
      "change_reason": "Baseline policy initialization",
      "conditions": [
        {
          "rule_name": "High Volatility Tightening",
          "priority": 10,
          "is_active": true,
          "metric_source": "VOLATILITY",
          "metric_name": "PORTFOLIO_VOLATILITY",
          "operator": "GREATER_THAN",
          "threshold_low": 0.25,
          "hysteresis_entry": 0.25,
          "hysteresis_exit": 0.20,
          "hysteresis_direction": "UP",
          "adjustment_type": "MULTIPLICATIVE",
          "adjustment_value": 0.70
        }
      ],
      "schedules": [
        {
          "session_name": "MARKET_OPEN",
          "market": "IN",
          "timezone": "Asia/Kolkata",
          "adjustment_type": "MULTIPLICATIVE",
          "adjustment_value": 0.85,
          "is_active": true
        }
      ]
    }
  }
  ```
- **Status:** `201 Created`

### `GET /policies`
Query existing policies with optional query filters: `portfolio_id`, `market`, `status`.

### `GET /policies/{policy_id}`
Retrieve a specific policy with all versions, conditions, schedules, and active overrides.

### `POST /policies/{policy_id}/versions`
Draft a new version for an existing policy.
- **Status:** `201 Created`

### `POST /policies/{policy_id}/versions/{version_id}/approve`
Maker-Checker approval of a draft policy version. Rejects self-approval attempts.
- **Request Body:**
  ```json
  {
    "approved_by": "independent_risk_officer",
    "comments": "Approved after reviewing volatility backtest metrics"
  }
  ```
- **Status:** `200 OK`

---

## 3. Maker-Checker Manual Overrides

### `POST /overrides`
Request a time-bounded manual override.
- **Request Body:**
  ```json
  {
    "policy_id": "pol_12345",
    "target_limit_code": "MAX_POSITION_WEIGHT",
    "override_value": 5.0,
    "reason_code": "MARKET_EVENT",
    "justification": "Elections announcement expected; temporarily cutting cap to 5%",
    "effective_from": "2026-11-16T09:00:00Z",
    "effective_to": "2026-11-16T15:30:00Z",
    "requested_by": "trader_alice"
  }
  ```
- **Status:** `201 Created`

### `POST /overrides/{override_id}/approve`
Maker-Checker approval of an override request. Rejects self-approvals (`requested_by == approved_by`).

### `POST /overrides/{override_id}/reject`
Reject a pending override with justification.

### `POST /overrides/{override_id}/revoke`
Revoke an approved override prior to its scheduled expiry.

---

## 4. Limit Evaluation & Effective Snapshots

### `POST /evaluate`
Evaluate dynamic limits for a portfolio and market under live metrics.
- **Request Body:**
  ```json
  {
    "portfolio_id": "PF_INST_001",
    "market": "IN",
    "as_of_time": "2026-11-16T10:30:00Z",
    "current_metrics": {
      "PORTFOLIO_VOLATILITY": 0.28,
      "MARKET_REGIME": "NORMAL"
    }
  }
  ```
- **Response:**
  ```json
  [
    {
      "id": "snp_9a8b7c",
      "policy_id": "pol_12345",
      "policy_version_id": "ver_67890",
      "portfolio_id": "PF_INST_001",
      "target_limit_code": "MAX_POSITION_WEIGHT",
      "base_limit_value": "10.0000",
      "effective_limit_value": "7.0000",
      "limit_nature": "CAP",
      "active_regime": "NORMAL",
      "active_session": "REGULAR_TRADING",
      "condition_adjustment_applied": "High Volatility Tightening",
      "override_applied_id": null,
      "as_of_time": "2026-11-16T10:30:00",
      "snapshot_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "lineage_metadata": { ... }
    }
  ]
  ```

### `GET /snapshots`
List persisted effective limit snapshots with optional query filters: `portfolio_id`, `target_limit_code`, `limit`.

---

## 5. Audit Events

### `GET /audit`
Retrieve the immutable audit trail log with optional `entity_id` filter.

