"""
Comprehensive Test Suite for Module 01: Feed Registry & Configuration.
Covers all 8 milestones:
1. Feed Registration & Validation
2. Duplicate feed_code rejection
3. SecretReference format validation (zero plaintext secrets)
4. Immutable versioning & diffing
5. Immutable rollback
6. Desired state transitions & transactional outbox command enqueuing
7. Scheduling & timezone validation
8. Failover groups & priority ranking
9. Health event ingestion & summary aggregation
10. RBAC permissions (Admin vs Operator vs ReadOnly)
"""
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.config import settings
from backend.app.core.database import init_db
from backend.app.main import app

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def setup_test_db():
    import asyncio
    asyncio.run(init_db())
    yield


@pytest.fixture
def admin_headers():
    return {"X-API-Key": settings.API_KEY_ADMIN}


@pytest.fixture
def operator_headers():
    return {"X-API-Key": settings.API_KEY_OPERATOR}


@pytest.fixture
def read_only_headers():
    return {"X-API-Key": settings.API_KEY_READ_ONLY}


async def test_root_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert "M01" in data["module"]


async def test_feed_registration_and_rbac(operator_headers, read_only_headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        feed_code = f"NSE_EQ_{uuid.uuid4().hex[:6].upper()}"
        payload = {
            "feed_code": feed_code,
            "feed_name": "NSE Level 2 Equity Direct",
            "description": "NSE Primary L2 Multicast/TCP feed",
            "category": "DIRECT_EXCHANGE",
            "asset_class": "EQUITIES",
            "transport_protocol": "WEBSOCKET",
            "capabilities": {
                "depth": 5,
                "tick_by_tick": True,
                "snapshots": True,
            },
            "is_primary_eligible": True,
            "is_backup_eligible": True,
            "metadata_json": {"vendor": "NSE_COLOCATION"},
        }

        # 1. READ_ONLY role cannot create feed
        res_fail = await ac.post("/api/v1/feeds", json=payload, headers=read_only_headers)
        assert res_fail.status_code == 403

        # 2. OPERATOR role can create feed
        res_ok = await ac.post("/api/v1/feeds", json=payload, headers=operator_headers)
        assert res_ok.status_code == 201
        created = res_ok.json()
        assert created["feed_code"] == feed_code
        assert created["desired_state"] == "INACTIVE"
        assert created["current_version"] == 0

        # 3. Duplicate feed_code is rejected with 409
        res_dup = await ac.post("/api/v1/feeds", json=payload, headers=operator_headers)
        assert res_dup.status_code == 409


async def test_secret_reference_validation(operator_headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create feed
        feed_code = f"SECRET_TEST_{uuid.uuid4().hex[:6].upper()}"
        reg_res = await ac.post(
            "/api/v1/feeds",
            json={
                "feed_code": feed_code,
                "feed_name": "Secret Test Feed",
                "category": "VENDOR_CONSOLIDATED",
                "transport_protocol": "WEBSOCKET",
            },
            headers=operator_headers,
        )
        feed_id = reg_res.json()["id"]

        # 1. Plaintext credential must be REJECTED (Unprocessable Entity)
        bad_config = {
            "schema_version": "1.0.0",
            "change_reason": "Testing plaintext leak prevention",
            "config_payload": {
                "endpoint_url": "wss://feed.marketdata.com/live",
                "auth_credentials_ref": "my_plaintext_password_123",  # NOT a secret:// URI
            },
        }
        res_bad = await ac.post(
            f"/api/v1/feeds/{feed_id}/configurations",
            json=bad_config,
            headers=operator_headers,
        )
        assert res_bad.status_code == 422
        assert "secret://" in res_bad.json()["detail"]

        # 2. Valid SecretReference URI succeeds
        good_config = {
            "schema_version": "1.0.0",
            "change_reason": "Adding secured configuration with secret URI",
            "config_payload": {
                "endpoint_url": "wss://feed.marketdata.com/live",
                "auth_credentials_ref": "secret://production/zerodha_api_key",
                "heartbeat_interval_seconds": 10,
                "subscription_symbols": ["RELIANCE", "TCS", "INFY"],
            },
        }
        res_good = await ac.post(
            f"/api/v1/feeds/{feed_id}/configurations",
            json=good_config,
            headers=operator_headers,
        )
        assert res_good.status_code == 201
        cfg = res_good.json()
        assert cfg["version_number"] == 1
        assert cfg["config_payload"]["auth_credentials_ref"] == "secret://production/zerodha_api_key"


async def test_immutable_versioning_and_rollback(operator_headers, admin_headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        feed_code = f"VERSION_TEST_{uuid.uuid4().hex[:6].upper()}"
        reg_res = await ac.post(
            "/api/v1/feeds",
            json={
                "feed_code": feed_code,
                "feed_name": "Versioning Test Feed",
                "category": "DIRECT_EXCHANGE",
                "transport_protocol": "WEBSOCKET",
            },
            headers=operator_headers,
        )
        feed_id = reg_res.json()["id"]

        # Publish Version 1
        v1_payload = {
            "schema_version": "1.0.0",
            "change_reason": "Initial config",
            "config_payload": {
                "endpoint_url": "wss://feed1.nse.com",
                "heartbeat_interval_seconds": 15,
                "subscription_symbols": ["TCS"],
            },
        }
        res_v1 = await ac.post(f"/api/v1/feeds/{feed_id}/configurations", json=v1_payload, headers=operator_headers)
        assert res_v1.status_code == 201
        assert res_v1.json()["version_number"] == 1

        # Publish Version 2
        v2_payload = {
            "schema_version": "1.0.0",
            "change_reason": "Add RELIANCE and decrease heartbeat",
            "config_payload": {
                "endpoint_url": "wss://feed1.nse.com",
                "heartbeat_interval_seconds": 5,
                "subscription_symbols": ["TCS", "RELIANCE"],
            },
        }
        res_v2 = await ac.post(f"/api/v1/feeds/{feed_id}/configurations", json=v2_payload, headers=operator_headers)
        assert res_v2.status_code == 201
        assert res_v2.json()["version_number"] == 2

        # Diff v1 and v2
        diff_res = await ac.get(f"/api/v1/feeds/{feed_id}/configurations/diff/1/2", headers=operator_headers)
        assert diff_res.status_code == 200
        diff = diff_res.json()
        assert "heartbeat_interval_seconds" in diff["modified"]
        assert diff["modified"]["heartbeat_interval_seconds"]["from"] == 15
        assert diff["modified"]["heartbeat_interval_seconds"]["to"] == 5

        # Rollback to Version 1 (requires ADMIN role)
        rollback_res = await ac.post(
            f"/api/v1/feeds/{feed_id}/configurations/rollback",
            json={"target_version": 1, "change_reason": "Emergency revert to v1"},
            headers=admin_headers,
        )
        assert rollback_res.status_code == 200
        rb_data = rollback_res.json()
        # Immutable: rollback creates version 3!
        assert rb_data["version_number"] == 3
        assert rb_data["config_payload"]["heartbeat_interval_seconds"] == 15


async def test_lifecycle_and_transactional_outbox(operator_headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        feed_code = f"OUTBOX_TEST_{uuid.uuid4().hex[:6].upper()}"
        reg_res = await ac.post(
            "/api/v1/feeds",
            json={
                "feed_code": feed_code,
                "feed_name": "Outbox Test Feed",
                "category": "DIRECT_EXCHANGE",
                "transport_protocol": "WEBSOCKET",
            },
            headers=operator_headers,
        )
        feed_id = reg_res.json()["id"]

        # Request state transition to ACTIVE
        res = await ac.post(
            f"/api/v1/feeds/{feed_id}/state",
            json={"target_state": "ACTIVE", "reason": "Market open, starting feed"},
            headers=operator_headers,
        )
        assert res.status_code == 200
        cmd = res.json()
        assert cmd["command_type"] == "START"
        assert cmd["status"] == "PENDING"
        assert cmd["idempotency_key"] is not None

        # Verify feed desired_state is now ACTIVE
        feed_check = await ac.get(f"/api/v1/feeds/{feed_id}", headers=operator_headers)
        assert feed_check.json()["desired_state"] == "ACTIVE"


async def test_schedule_and_timezone(operator_headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        feed_code = f"SCHED_TEST_{uuid.uuid4().hex[:6].upper()}"
        reg_res = await ac.post(
            "/api/v1/feeds",
            json={
                "feed_code": feed_code,
                "feed_name": "Schedule Test Feed",
                "category": "DIRECT_EXCHANGE",
                "transport_protocol": "WEBSOCKET",
            },
            headers=operator_headers,
        )
        feed_id = reg_res.json()["id"]

        sched_payload = {
            "timezone": "Asia/Kolkata",
            "auto_start_stop_enabled": True,
            "sessions": [
                {"name": "Pre-Open", "start_time": "09:00:00", "end_time": "09:08:00"},
                {"name": "Regular", "start_time": "09:15:00", "end_time": "15:30:00"},
            ],
            "polling_interval_ms": 500,
            "active_days": [0, 1, 2, 3, 4],
        }

        res = await ac.post(f"/api/v1/feeds/{feed_id}/schedule", json=sched_payload, headers=operator_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["timezone"] == "Asia/Kolkata"
        assert len(data["sessions"]) == 2


async def test_failover_group_and_health_sink(operator_headers, admin_headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        feed_code_1 = f"FO_1_{uuid.uuid4().hex[:6].upper()}"
        feed_code_2 = f"FO_2_{uuid.uuid4().hex[:6].upper()}"

        f1 = (await ac.post(
            "/api/v1/feeds",
            json={"feed_code": feed_code_1, "feed_name": "Feed 1", "category": "DIRECT_EXCHANGE", "transport_protocol": "WEBSOCKET"},
            headers=operator_headers,
        )).json()

        f2 = (await ac.post(
            "/api/v1/feeds",
            json={"feed_code": feed_code_2, "feed_name": "Feed 2", "category": "DIRECT_EXCHANGE", "transport_protocol": "WEBSOCKET"},
            headers=operator_headers,
        )).json()

        group_name = f"NSE_EQUITIES_GROUP_{uuid.uuid4().hex[:4].upper()}"
        group_payload = {
            "group_name": group_name,
            "description": "NSE Equities Failover Cluster",
            "failover_latency_threshold_ms": 300.0,
            "consecutive_error_threshold": 3,
            "members": [
                {"feed_id": f1["id"], "priority_rank": 1, "is_active_in_group": True, "custom_weight": 1.0},
                {"feed_id": f2["id"], "priority_rank": 2, "is_active_in_group": True, "custom_weight": 1.0},
            ],
        }

        # Create failover group (requires ADMIN)
        res_group = await ac.post("/api/v1/feeds/failover-groups", json=group_payload, headers=admin_headers)
        assert res_group.status_code == 201
        grp = res_group.json()
        assert len(grp["priority_members"]) == 2

        # Report health from M02
        health_payload = {
            "runtime_state": "CONNECTED",
            "latency_ms": 12.5,
            "messages_received_delta": 15000,
            "bytes_received_delta": 450000,
            "error_count_delta": 0,
        }
        res_health = await ac.post(f"/api/v1/feeds/{f1['id']}/health", json=health_payload, headers=operator_headers)
        assert res_health.status_code == 201

        # Check health summary
        summary_res = await ac.get(f"/api/v1/feeds/{f1['id']}/health/summary", headers=operator_headers)
        assert summary_res.status_code == 200
        summary = summary_res.json()
        assert summary["latest_runtime_state"] == "CONNECTED"
        assert summary["current_latency_ms"] == 12.5
        assert summary["is_healthy"] is True


async def test_audit_log_recording(admin_headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/feeds/audit/logs", headers=admin_headers)
        assert res.status_code == 200
        logs = res.json()
        assert len(logs) > 0
        operations = [log["operation"] for log in logs]
        assert any("REGISTER_FEED" in op for op in operations)
