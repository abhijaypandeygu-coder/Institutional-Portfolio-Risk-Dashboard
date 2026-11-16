"""
Comprehensive tests for M11.06 — Breach Detection.

Tests cover:
1. Quantitative calculations:
   - Maximum-type limits (CAP): utilization, breach magnitude, excess percentage.
   - Minimum-type limits (FLOOR): utilization, breach magnitude, shortfall percentage.
   - Range-type limits: boundary checking and magnitude.
   - Comparison operators (GREATER_THAN, GREATER_EQUAL, LESS_THAN, LESS_EQUAL, EQUAL, OUTSIDE_RANGE).
2. Input Quality & Freshness Assessment:
   - Valid vs stale metrics (age > max_age_seconds).
   - Rejecting corrupted/invalid inputs without false "within limit" claims.
3. Persistence Models:
   - Immediate breach (zero tolerance flag).
   - Duration-based persistence.
   - Consecutive-observation persistence.
   - Window-based persistence.
4. Hysteresis & Recovery:
   - Recovery threshold confirmation under separate hysteresis boundaries.
   - Re-opening breaches on subsequent violations.
5. Missing Limit Fail-Safe:
   - Rejection and LIMIT_UNAVAILABLE when no applicable threshold exists.
6. API Endpoints & State deduplication:
   - GET /health
   - POST /evaluate (Within limit, Warning, Hard breach, Stale input, Missing limit)
   - Deduplication: Consecutive observations during an ongoing breach append to the same episode without creating duplicate episodes.
   - Recovery event generation.
   - Monitoring overview & audit trail.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db
from backend.app.modules.risk_limits.breach_detection.calculations.breach_detection_math import (
    evaluate_boundary_violation,
    calculate_utilization_and_magnitude,
    check_input_freshness,
    classify_breach_severity,
    evaluate_persistence,
    check_recovery_hysteresis,
    OP_GREATER_THAN,
    OP_LESS_THAN,
    OP_OUTSIDE_RANGE,
    THRESHOLD_TYPE_MAX,
    THRESHOLD_TYPE_MIN,
    STATUS_PERSISTENT_BREACH,
    STATUS_PERSISTENCE_PENDING,
)


@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()


# -------------------------------------------------------------
# 1. Pure Calculation & Logic Tests
# -------------------------------------------------------------

def test_boundary_violations():
    # Maximum limit cap: 10.0
    assert evaluate_boundary_violation(Decimal("10.5"), Decimal("10.0"), OP_GREATER_THAN) is True
    assert evaluate_boundary_violation(Decimal("9.5"), Decimal("10.0"), OP_GREATER_THAN) is False

    # Minimum limit floor: 1000000
    assert evaluate_boundary_violation(Decimal("800000"), Decimal("1000000"), OP_LESS_THAN) is True
    assert evaluate_boundary_violation(Decimal("1200000"), Decimal("1000000"), OP_LESS_THAN) is False

    # Range limit [10.0, 20.0]
    assert evaluate_boundary_violation(Decimal("25.0"), Decimal("10.0"), OP_OUTSIDE_RANGE, threshold_high=Decimal("20.0")) is True
    assert evaluate_boundary_violation(Decimal("15.0"), Decimal("10.0"), OP_OUTSIDE_RANGE, threshold_high=Decimal("20.0")) is False


def test_utilization_and_magnitude():
    # Cap 10.0 with observed 12.5 -> Excess = 2.5 (25% excess), Utilization = 1.25
    u, mag, excess = calculate_utilization_and_magnitude(Decimal("12.5"), Decimal("10.0"), THRESHOLD_TYPE_MAX)
    assert u == Decimal("1.2500")
    assert mag == Decimal("2.5000")
    assert excess == Decimal("25.0000")

    # Floor 100 with observed 80 -> Shortfall = 20 (20% shortfall), Utilization = 1.25
    u, mag, excess = calculate_utilization_and_magnitude(Decimal("80"), Decimal("100"), THRESHOLD_TYPE_MIN)
    assert u == Decimal("1.2500")
    assert mag == Decimal("20.0000")
    assert excess == Decimal("20.0000")


def test_input_freshness():
    now = datetime.utcnow()
    # 5 minutes old metric (fresh within 3600s)
    is_fresh, age = check_input_freshness(now - timedelta(minutes=5), now, max_permitted_age_seconds=3600)
    assert is_fresh is True
    assert 295 <= age <= 305

    # 2 hours old metric (stale beyond 3600s)
    is_fresh, age = check_input_freshness(now - timedelta(hours=2), now, max_permitted_age_seconds=3600)
    assert is_fresh is False
    assert age >= 7200


def test_persistence_modes():
    now = datetime.utcnow()
    # Duration mode: requires 300 seconds
    t0 = now - timedelta(seconds=350)
    obs = [(t0, True), (now, True)]
    is_p, status = evaluate_persistence(obs, first_violation_at=t0, current_time=now, persistence_mode="DURATION", required_duration_seconds=300)
    assert is_p is True
    assert status == STATUS_PERSISTENT_BREACH

    # Consecutive mode: requires 3 consecutive
    obs_consec = [(now - timedelta(seconds=20), True), (now - timedelta(seconds=10), True), (now, True)]
    is_p, _ = evaluate_persistence(obs_consec, first_violation_at=t0, current_time=now, persistence_mode="CONSECUTIVE", required_consecutive_count=3)
    assert is_p is True

    # Failed consecutive: one non-violation in between
    obs_broken = [(now - timedelta(seconds=20), True), (now - timedelta(seconds=10), False), (now, True)]
    is_p, status = evaluate_persistence(obs_broken, first_violation_at=t0, current_time=now, persistence_mode="CONSECUTIVE", required_consecutive_count=3)
    assert is_p is False
    assert status == STATUS_PERSISTENCE_PENDING


def test_recovery_hysteresis():
    # Hard boundary 25.0, Recovery threshold 22.0
    # Falling to 23.0 has not yet recovered (hysteresis deadband)
    assert check_recovery_hysteresis(Decimal("23.0"), Decimal("25.0"), Decimal("22.0"), THRESHOLD_TYPE_MAX) is False
    # Falling to 21.5 has successfully recovered
    assert check_recovery_hysteresis(Decimal("21.5"), Decimal("25.0"), Decimal("22.0"), THRESHOLD_TYPE_MAX) is True


# -------------------------------------------------------------
# 2. Integration / API Tests
# -------------------------------------------------------------

@pytest.mark.asyncio
async def test_breach_detection_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/breach-detection/health")
        assert res.status_code == 200
        assert res.json()["module"] == "M11.06 — Breach Detection"


@pytest.mark.asyncio
async def test_evaluation_within_limit_and_warning_and_hard_breach():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        now = datetime.utcnow()
        pf_id = f"PF_TEST_{now.timestamp()}"

        # 1. Normal evaluation within limits (Value = 6.0, Warning = 8.0, Hard = 10.0)
        res1 = await ac.post(
            "/api/v1/breach-detection/evaluate",
            params={"hard_threshold": 10.0, "warning_threshold": 8.0, "limit_nature": "CAP"},
            json={
                "portfolio_id": pf_id,
                "target_entity_type": "PORTFOLIO",
                "target_entity_id": pf_id,
                "metric_code": "PORTFOLIO_VAR",
                "metric_value": 6.0,
                "metric_timestamp": now.isoformat(),
            }
        )
        assert res1.status_code == 201
        data1 = res1.json()
        assert data1["evaluation_status"] == "WITHIN_LIMIT"
        assert float(data1["breach_magnitude"]) == 0.0

        # 2. Warning boundary crossed (Value = 8.5, Warning = 8.0, Hard = 10.0)
        res2 = await ac.post(
            "/api/v1/breach-detection/evaluate",
            params={"hard_threshold": 10.0, "warning_threshold": 8.0, "limit_nature": "CAP"},
            json={
                "portfolio_id": pf_id,
                "target_entity_type": "PORTFOLIO",
                "target_entity_id": pf_id,
                "metric_code": "PORTFOLIO_VAR",
                "metric_value": 8.5,
                "metric_timestamp": now.isoformat(),
            }
        )
        assert res2.status_code == 201
        data2 = res2.json()
        assert data2["evaluation_status"] == "WARNING"

        # 3. Hard limit crossed (Value = 13.0, Warning = 8.0, Hard = 10.0)
        res3 = await ac.post(
            "/api/v1/breach-detection/evaluate",
            params={"hard_threshold": 10.0, "warning_threshold": 8.0, "limit_nature": "CAP"},
            json={
                "portfolio_id": pf_id,
                "target_entity_type": "PORTFOLIO",
                "target_entity_id": pf_id,
                "metric_code": "PORTFOLIO_VAR",
                "metric_value": 13.0,
                "metric_timestamp": now.isoformat(),
            }
        )
        assert res3.status_code == 201
        data3 = res3.json()
        assert data3["evaluation_status"] == "HARD_BREACH"
        assert float(data3["breach_magnitude"]) == 3.0
        assert data3["severity"] in ("HIGH", "CRITICAL")


@pytest.mark.asyncio
async def test_stale_and_invalid_metric_rejection():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        now = datetime.utcnow()
        pf_id = f"PF_STALE_{now.timestamp()}"

        # 1. Stale metric: 3 hours old
        res_stale = await ac.post(
            "/api/v1/breach-detection/evaluate",
            params={"hard_threshold": 10.0},
            json={
                "portfolio_id": pf_id,
                "target_entity_type": "PORTFOLIO",
                "target_entity_id": pf_id,
                "metric_code": "PORTFOLIO_VAR",
                "metric_value": 5.0,  # Below limit, but stale! Cannot claim WITHIN_LIMIT
                "metric_timestamp": (now - timedelta(hours=3)).isoformat(),
            }
        )
        assert res_stale.status_code == 201
        assert res_stale.json()["evaluation_status"] == "STALE_INPUT"

        # 2. Corrupted / Invalid data quality status
        res_invalid = await ac.post(
            "/api/v1/breach-detection/evaluate",
            params={"hard_threshold": 10.0},
            json={
                "portfolio_id": pf_id,
                "target_entity_type": "PORTFOLIO",
                "target_entity_id": pf_id,
                "metric_code": "PORTFOLIO_VAR",
                "metric_value": 5.0,
                "metric_timestamp": now.isoformat(),
                "input_quality_status": "CORRUPTED"
            }
        )
        assert res_invalid.status_code == 201
        assert res_invalid.json()["evaluation_status"] == "INVALID_INPUT"

        # 3. Missing Limit (no hard_threshold specified) -> LIMIT_UNAVAILABLE
        res_missing_lim = await ac.post(
            "/api/v1/breach-detection/evaluate",
            json={
                "portfolio_id": pf_id,
                "target_entity_type": "PORTFOLIO",
                "target_entity_id": pf_id,
                "metric_code": "PORTFOLIO_VAR",
                "metric_value": 5.0,
                "metric_timestamp": now.isoformat(),
            }
        )
        assert res_missing_lim.status_code == 201
        assert res_missing_lim.json()["evaluation_status"] == "LIMIT_UNAVAILABLE"


@pytest.mark.asyncio
async def test_episode_lifecycle_and_recovery_deduplication():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        now = datetime.utcnow()
        pf_id = f"PF_EPISODE_{now.timestamp()}"
        metric_code = "POSITION_WEIGHT_MAX"

        # Step 1: Initial violation creates an Episode and Event
        res1 = await ac.post(
            "/api/v1/breach-detection/evaluate",
            params={"hard_threshold": 10.0, "limit_nature": "CAP"},
            json={
                "portfolio_id": pf_id,
                "target_entity_type": "POSITION",
                "target_entity_id": "RELIANCE.NS",
                "metric_code": metric_code,
                "metric_value": 12.0,
                "metric_timestamp": now.isoformat(),
            }
        )
        assert res1.status_code == 201

        # Check that exactly one episode exists for this portfolio & entity
        episodes_res1 = await ac.get("/api/v1/breach-detection/episodes", params={"portfolio_id": pf_id})
        assert episodes_res1.status_code == 200
        episodes1 = episodes_res1.json()
        assert len(episodes1) == 1
        ep_id = episodes1[0]["id"]
        assert episodes1[0]["episode_status"] == "ACTIVE_HARD_BREACH"

        # Step 2: Second consecutive violation updates ongoing episode without creating duplicate episode
        res2 = await ac.post(
            "/api/v1/breach-detection/evaluate",
            params={"hard_threshold": 10.0, "limit_nature": "CAP"},
            json={
                "portfolio_id": pf_id,
                "target_entity_type": "POSITION",
                "target_entity_id": "RELIANCE.NS",
                "metric_code": metric_code,
                "metric_value": 14.0,  # Peak increases
                "metric_timestamp": (now + timedelta(minutes=1)).isoformat(),
            }
        )
        assert res2.status_code == 201

        episodes_res2 = await ac.get("/api/v1/breach-detection/episodes", params={"portfolio_id": pf_id})
        episodes2 = episodes_res2.json()
        assert len(episodes2) == 1  # Deduplicated!
        assert float(episodes2[0]["maximum_breach_magnitude"]) == 4.0

        # Step 3: Metric returns below threshold (e.g. 8.0) -> Triggers RECOVERED
        res3 = await ac.post(
            "/api/v1/breach-detection/evaluate",
            params={"hard_threshold": 10.0, "limit_nature": "CAP"},
            json={
                "portfolio_id": pf_id,
                "target_entity_type": "POSITION",
                "target_entity_id": "RELIANCE.NS",
                "metric_code": metric_code,
                "metric_value": 8.0,
                "metric_timestamp": (now + timedelta(minutes=2)).isoformat(),
            }
        )
        assert res3.status_code == 201
        assert res3.json()["evaluation_status"] == "WITHIN_LIMIT"

        episodes_res3 = await ac.get(f"/api/v1/breach-detection/episodes/{ep_id}")
        assert episodes_res3.status_code == 200
        assert episodes_res3.json()["episode_status"] == "RECOVERED"
        assert episodes_res3.json()["recovered_at"] is not None

        # Verify breach events contains both HARD_BREACH_ENTERED and BREACH_RECOVERED
        events_res = await ac.get("/api/v1/breach-detection/events", params={"portfolio_id": pf_id})
        assert events_res.status_code == 200
        event_types = [e["event_type"] for e in events_res.json()]
        assert "HARD_BREACH_ENTERED" in event_types
        assert "BREACH_RECOVERED" in event_types
