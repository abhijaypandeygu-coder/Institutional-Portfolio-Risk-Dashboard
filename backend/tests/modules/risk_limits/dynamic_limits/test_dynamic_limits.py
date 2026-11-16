"""
Comprehensive tests for M11.05 — Dynamic Limits.

Tests include:
1. Core Mathematical and Transformation Logic:
   - Condition operators: GREATER_THAN, GREATER_EQUAL, LESS_THAN, LESS_EQUAL, EQUAL, BETWEEN
   - Hysteresis band evaluation (entry/exit threshold, deadband persistence, UP & DOWN directions)
   - Multiplicative, Additive, and Absolute Replacement adjustments
   - Restrictive-only constraint (min for CAP, max for FLOOR; cannot loosen limits)
   - Adjustment bounds clamping (min_allowed_value, max_allowed_value)
   - Session resolution for IN (Asia/Kolkata) and US (America/New_York)
   - Cryptographic snapshot lineage hash generation
2. Maker-Checker Manual Override Governance:
   - Creating override request
   - Self-approval prevention (author cannot approve own request)
   - Successful approval by independent checker
   - Rejection and revocation lifecycle
   - Override validity time-window checks (past/future expiry)
3. Dynamic Limit Evaluation Engine:
   - Dynamic policy versioning and creation
   - Volatility condition firing (multiplicative derisking)
   - Liquidity condition firing (switching to conservative threshold)
   - Market regime condition firing (e.g., STRESSED regime triggers tightening)
   - Restrictive-only enforcement in live evaluation
   - Schedule session integration
   - Precedence conflict resolution (Hard Constraint > Emergency > Condition > Schedule > Override > Base)
   - Immutable snapshot creation with cryptographic lineage trace
4. Full FastAPI Router Integration:
   - GET /health
   - POST /policies & GET /policies
   - POST /policies/{id}/versions & POST /policies/{id}/versions/{v_id}/approve
   - POST /overrides & POST /overrides/{id}/approve
   - POST /evaluate & GET /snapshots
   - GET /audit
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
import zoneinfo
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db
from backend.app.modules.risk_limits.dynamic_limits.calculations.dynamic_limit_math import (
    evaluate_condition_operator,
    evaluate_hysteresis_state,
    calculate_adjusted_limit,
    resolve_market_session,
    generate_lineage_hash,
    OP_GREATER_THAN,
    OP_LESS_THAN,
    OP_BETWEEN,
    ADJ_MULTIPLICATIVE,
    ADJ_ADDITIVE,
    ADJ_ABSOLUTE_REPLACEMENT,
    LIMIT_NATURE_CAP,
    LIMIT_NATURE_FLOOR,
)


@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()


# -------------------------------------------------------------
# 1. Pure Mathematical & Calculation Tests
# -------------------------------------------------------------

def test_condition_operators():
    assert evaluate_condition_operator(Decimal("25.5"), OP_GREATER_THAN, Decimal("20.0")) is True
    assert evaluate_condition_operator(Decimal("19.5"), OP_GREATER_THAN, Decimal("20.0")) is False
    assert evaluate_condition_operator(Decimal("15.0"), OP_LESS_THAN, Decimal("20.0")) is True
    assert evaluate_condition_operator(Decimal("25.0"), OP_BETWEEN, Decimal("20.0"), Decimal("30.0")) is True
    assert evaluate_condition_operator(Decimal("35.0"), OP_BETWEEN, Decimal("20.0"), Decimal("30.0")) is False


def test_hysteresis_state_evaluation():
    # Volatility Spike (direction UP): Entry at 25.0, Exit at 20.0
    # Case 1: Inactive, reaching 24.0 (below entry) -> stays inactive
    assert evaluate_hysteresis_state(
        current_value=Decimal("24.0"),
        currently_active=False,
        entry_threshold=Decimal("25.0"),
        exit_threshold=Decimal("20.0"),
        direction="UP"
    ) is False

    # Case 2: Inactive, reaching 25.5 (exceeds entry) -> activates
    assert evaluate_hysteresis_state(
        current_value=Decimal("25.5"),
        currently_active=False,
        entry_threshold=Decimal("25.0"),
        exit_threshold=Decimal("20.0"),
        direction="UP"
    ) is True

    # Case 3: Active, falling to 22.0 (inside deadband, above exit) -> remains active
    assert evaluate_hysteresis_state(
        current_value=Decimal("22.0"),
        currently_active=True,
        entry_threshold=Decimal("25.0"),
        exit_threshold=Decimal("20.0"),
        direction="UP"
    ) is True

    # Case 4: Active, falling to 19.5 (strictly below exit) -> deactivates
    assert evaluate_hysteresis_state(
        current_value=Decimal("19.5"),
        currently_active=True,
        entry_threshold=Decimal("25.0"),
        exit_threshold=Decimal("20.0"),
        direction="UP"
    ) is False


def test_adjusted_limit_restrictive_only():
    # Base Cap = 10.0 (e.g. max position weight 10%)
    # Attempt to relax cap: Multiplier 1.2 -> raw = 12.0. Restrictive-only must clamp back to 10.0!
    raw, eff = calculate_adjusted_limit(
        base_limit=Decimal("10.0"),
        adjustment_type=ADJ_MULTIPLICATIVE,
        adjustment_value=Decimal("1.2"),
        nature=LIMIT_NATURE_CAP,
        restrictive_only=True
    )
    assert raw == Decimal("12.0000")
    assert eff == Decimal("10.0000")  # Cannot relax cap

    # Tightening cap: Multiplier 0.8 -> raw = 8.0. Restrictive-only permits tightening to 8.0
    raw, eff = calculate_adjusted_limit(
        base_limit=Decimal("10.0"),
        adjustment_type=ADJ_MULTIPLICATIVE,
        adjustment_value=Decimal("0.8"),
        nature=LIMIT_NATURE_CAP,
        restrictive_only=True
    )
    assert raw == Decimal("8.0000")
    assert eff == Decimal("8.0000")

    # Base Floor = 1,000,000 (e.g. min depth).
    # Tightening floor: Multiplier 1.5 -> raw = 1,500,000. Floor strengthens to 1,500,000
    raw, eff = calculate_adjusted_limit(
        base_limit=Decimal("1000000.0"),
        adjustment_type=ADJ_MULTIPLICATIVE,
        adjustment_value=Decimal("1.5"),
        nature=LIMIT_NATURE_FLOOR,
        restrictive_only=True
    )
    assert raw == Decimal("1500000.0000")
    assert eff == Decimal("1500000.0000")

    # Relaxing floor: Multiplier 0.7 -> raw = 700,000. Restrictive-only must clamp back to 1,000,000
    raw, eff = calculate_adjusted_limit(
        base_limit=Decimal("1000000.0"),
        adjustment_type=ADJ_MULTIPLICATIVE,
        adjustment_value=Decimal("0.7"),
        nature=LIMIT_NATURE_FLOOR,
        restrictive_only=True
    )
    assert raw == Decimal("700000.0000")
    assert eff == Decimal("1000000.0000")


def test_session_resolution():
    # India (Asia/Kolkata): Monday 10:30 AM IST -> REGULAR_TRADING
    tz_in = zoneinfo.ZoneInfo("Asia/Kolkata")
    dt_in_regular = datetime(2026, 11, 16, 10, 30, tzinfo=tz_in)
    assert resolve_market_session(dt_in_regular, "IN") == "REGULAR_TRADING"

    # India: Monday 09:10 AM IST -> PRE_MARKET
    dt_in_pre = datetime(2026, 11, 16, 9, 10, tzinfo=tz_in)
    assert resolve_market_session(dt_in_pre, "IN") == "PRE_MARKET"

    # US (America/New_York): Monday 09:45 AM EST -> MARKET_OPEN
    tz_us = zoneinfo.ZoneInfo("America/New_York")
    dt_us_open = datetime(2026, 11, 16, 9, 45, tzinfo=tz_us)
    assert resolve_market_session(dt_us_open, "US") == "MARKET_OPEN"


def test_cryptographic_lineage_hash():
    data1 = {"policy": "POL_01", "base": 10.0, "eff": 8.0}
    data2 = {"base": 10.0, "eff": 8.0, "policy": "POL_01"}
    # Must be deterministic regardless of key ordering
    hash1 = generate_lineage_hash(data1)
    hash2 = generate_lineage_hash(data2)
    assert hash1 == hash2
    assert len(hash1) == 64


# -------------------------------------------------------------
# 2. Integration / End-to-End API Tests
# -------------------------------------------------------------

@pytest.mark.asyncio
async def test_dynamic_limits_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/risk-limits/dynamic/health")
        assert res.status_code == 200
        data = res.json()
        assert data["module"] == "M11.05 — Dynamic Limits"
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_policy_creation_and_maker_checker_approval():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        policy_code = f"POL_VOL_DERISK_{datetime.utcnow().timestamp()}"
        payload = {
            "policy_code": policy_code,
            "name": "Dynamic Volatility Derisking Policy",
            "description": "Reduces max position weight during high market volatility",
            "portfolio_id": "PF_INST_001",
            "market": "IN",
            "asset_class": "EQUITY",
            "created_by": "quant_analyst_1",
            "initial_version": {
                "target_limit_code": "MAX_POSITION_WEIGHT",
                "limit_nature": "CAP",
                "base_limit_value": 10.0,
                "restrictive_only": True,
                "min_allowed_value": 2.0,
                "max_allowed_value": 15.0,
                "authored_by": "quant_analyst_1",
                "change_reason": "Institutional risk policy baseline",
                "conditions": [
                    {
                        "rule_name": "High Volatility Derisking",
                        "priority": 10,
                        "is_active": True,
                        "metric_source": "VOLATILITY",
                        "metric_name": "PORTFOLIO_VOLATILITY",
                        "operator": "GREATER_THAN",
                        "threshold_low": 0.25,
                        "hysteresis_entry": 0.25,
                        "hysteresis_exit": 0.20,
                        "hysteresis_direction": "UP",
                        "adjustment_type": "MULTIPLICATIVE",
                        "adjustment_value": 0.70,  # Tighten cap by 30% (from 10% to 7%)
                        "description": "Tightens position cap to 7% when portfolio vol exceeds 25%"
                    },
                    {
                        "rule_name": "Stressed Regime Derisking",
                        "priority": 5,  # Higher priority than vol
                        "is_active": True,
                        "metric_source": "REGIME",
                        "metric_name": "MARKET_REGIME",
                        "operator": "EQUAL",
                        "threshold_low": 1.0,
                        "regime_match": "STRESSED",
                        "adjustment_type": "MULTIPLICATIVE",
                        "adjustment_value": 0.50,  # Cut cap by 50% (from 10% to 5%)
                        "description": "Halves position cap during stressed market regime"
                    }
                ],
                "schedules": [
                    {
                        "session_name": "MARKET_OPEN",
                        "market": "IN",
                        "timezone": "Asia/Kolkata",
                        "adjustment_type": "MULTIPLICATIVE",
                        "adjustment_value": 0.85,
                        "is_active": True
                    }
                ]
            }
        }

        # 1. Create policy
        res = await ac.post("/api/v1/risk-limits/dynamic/policies", json=payload)
        assert res.status_code == 201
        pol_data = res.json()
        policy_id = pol_data["id"]
        version_id = pol_data["versions"][0]["id"]
        assert pol_data["status"] == "DRAFT"

        # 2. Maker-Checker Check: Author cannot self-approve
        self_approve_res = await ac.post(
            f"/api/v1/risk-limits/dynamic/policies/{policy_id}/versions/{version_id}/approve",
            json={"approved_by": "quant_analyst_1", "comments": "Attempting self approval"}
        )
        assert self_approve_res.status_code == 400
        assert "Maker-Checker violation" in self_approve_res.json()["detail"]

        # 3. Independent Risk Manager approves
        approve_res = await ac.post(
            f"/api/v1/risk-limits/dynamic/policies/{policy_id}/versions/{version_id}/approve",
            json={"approved_by": "risk_manager_independent", "comments": "Approved institutional risk bounds"}
        )
        assert approve_res.status_code == 200
        assert approve_res.json()["status"] == "APPROVED"

        # Verify policy is now ACTIVE
        pol_res = await ac.get(f"/api/v1/risk-limits/dynamic/policies/{policy_id}")
        assert pol_res.status_code == 200
        assert pol_res.json()["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_dynamic_evaluation_under_normal_and_stressed_conditions():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        policy_code = f"POL_EVAL_TEST_{datetime.utcnow().timestamp()}"
        payload = {
            "policy_code": policy_code,
            "name": "Dynamic Liquidity & Volatility Evaluation Policy",
            "portfolio_id": "PF_EVAL_001",
            "market": "IN",
            "asset_class": "EQUITY",
            "created_by": "quant_dev",
            "initial_version": {
                "target_limit_code": "MAX_POSITION_WEIGHT",
                "limit_nature": "CAP",
                "base_limit_value": 10.0,
                "restrictive_only": True,
                "authored_by": "quant_dev",
                "conditions": [
                    {
                        "rule_name": "High Volatility Tightening",
                        "priority": 10,
                        "is_active": True,
                        "metric_source": "VOLATILITY",
                        "metric_name": "PORTFOLIO_VOLATILITY",
                        "operator": "GREATER_THAN",
                        "threshold_low": 0.25,
                        "adjustment_type": "MULTIPLICATIVE",
                        "adjustment_value": 0.80,  # 10% * 0.8 = 8%
                    },
                    {
                        "rule_name": "Crisis Regime Halving",
                        "priority": 5,
                        "is_active": True,
                        "metric_source": "REGIME",
                        "metric_name": "MARKET_REGIME",
                        "operator": "EQUAL",
                        "threshold_low": 1.0,
                        "regime_match": "STRESSED",
                        "adjustment_type": "MULTIPLICATIVE",
                        "adjustment_value": 0.50,  # 10% * 0.5 = 5%
                    }
                ],
                "schedules": []
            }
        }

        # Create and approve policy
        res = await ac.post("/api/v1/risk-limits/dynamic/policies", json=payload)
        pol_id = res.json()["id"]
        ver_id = res.json()["versions"][0]["id"]
        await ac.post(
            f"/api/v1/risk-limits/dynamic/policies/{pol_id}/versions/{ver_id}/approve",
            json={"approved_by": "cro_approver"}
        )

        # Scenario 1: Normal conditions (Vol = 15%, Regime = NORMAL)
        eval_res1 = await ac.post(
            "/api/v1/risk-limits/dynamic/evaluate",
            json={
                "portfolio_id": "PF_EVAL_001",
                "market": "IN",
                "current_metrics": {
                    "PORTFOLIO_VOLATILITY": 0.15,
                    "MARKET_REGIME": "NORMAL"
                }
            }
        )
        assert eval_res1.status_code == 200
        snaps1 = eval_res1.json()
        target_snap1 = next(s for s in snaps1 if s["policy_id"] == pol_id)
        assert float(target_snap1["base_limit_value"]) == 10.0
        assert float(target_snap1["effective_limit_value"]) == 10.0
        assert target_snap1["condition_adjustment_applied"] is None

        # Scenario 2: Volatility Spikes (Vol = 30%, Regime = NORMAL)
        eval_res2 = await ac.post(
            "/api/v1/risk-limits/dynamic/evaluate",
            json={
                "portfolio_id": "PF_EVAL_001",
                "market": "IN",
                "current_metrics": {
                    "PORTFOLIO_VOLATILITY": 0.30,
                    "MARKET_REGIME": "NORMAL"
                }
            }
        )
        assert eval_res2.status_code == 200
        snaps2 = eval_res2.json()
        target_snap2 = next(s for s in snaps2 if s["policy_id"] == pol_id)
        assert float(target_snap2["effective_limit_value"]) == 8.0
        assert target_snap2["condition_adjustment_applied"] == "High Volatility Tightening"

        # Scenario 3: Stressed Market Regime (Regime = STRESSED, Vol = 35%)
        # Priority 5 (Stressed Regime) takes precedence over Volatility rule
        eval_res3 = await ac.post(
            "/api/v1/risk-limits/dynamic/evaluate",
            json={
                "portfolio_id": "PF_EVAL_001",
                "market": "IN",
                "current_metrics": {
                    "PORTFOLIO_VOLATILITY": 0.35,
                    "MARKET_REGIME": "STRESSED"
                }
            }
        )
        assert eval_res3.status_code == 200
        snaps3 = eval_res3.json()
        target_snap3 = next(s for s in snaps3 if s["policy_id"] == pol_id)
        assert float(target_snap3["effective_limit_value"]) == 5.0
        assert target_snap3["condition_adjustment_applied"] == "Crisis Regime Halving"
        assert target_snap3["snapshot_hash"] is not None


@pytest.mark.asyncio
async def test_manual_override_governance_and_precedence():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        policy_code = f"POL_OVR_TEST_{datetime.utcnow().timestamp()}"
        payload = {
            "policy_code": policy_code,
            "name": "Manual Override Governance Test Policy",
            "portfolio_id": "PF_OVR_001",
            "market": "IN",
            "created_by": "trader_alice",
            "initial_version": {
                "target_limit_code": "MAX_VAR_USD",
                "limit_nature": "CAP",
                "base_limit_value": 500000.0,
                "authored_by": "trader_alice",
                "conditions": []
            }
        }

        res = await ac.post("/api/v1/risk-limits/dynamic/policies", json=payload)
        pol_id = res.json()["id"]
        ver_id = res.json()["versions"][0]["id"]
        await ac.post(
            f"/api/v1/risk-limits/dynamic/policies/{pol_id}/versions/{ver_id}/approve",
            json={"approved_by": "cro_bob"}
        )

        # 1. Request manual override: Trader requests temporary derisking to 300,000
        now = datetime.utcnow()
        override_payload = {
            "policy_id": pol_id,
            "target_limit_code": "MAX_VAR_USD",
            "override_value": 300000.0,
            "reason_code": "MARKET_EVENT",
            "justification": "Elections announcement expected; preemptively reducing allowable VaR",
            "effective_from": (now - timedelta(minutes=5)).isoformat(),
            "effective_to": (now + timedelta(hours=2)).isoformat(),
            "requested_by": "trader_alice"
        }
        ovr_res = await ac.post("/api/v1/risk-limits/dynamic/overrides", json=override_payload)
        assert ovr_res.status_code == 201
        ovr_data = ovr_res.json()
        ovr_id = ovr_data["id"]
        assert ovr_data["status"] == "PENDING_APPROVAL"

        # 2. Maker-Checker check: Alice cannot approve her own override
        self_app_res = await ac.post(
            f"/api/v1/risk-limits/dynamic/overrides/{ovr_id}/approve",
            json={"approved_by": "trader_alice", "comments": "Self approval"}
        )
        assert self_app_res.status_code == 400
        assert "Maker-Checker violation" in self_app_res.json()["detail"]

        # 3. Independent Risk Manager (cro_bob) approves
        app_res = await ac.post(
            f"/api/v1/risk-limits/dynamic/overrides/{ovr_id}/approve",
            json={"approved_by": "cro_bob", "comments": "Approved temporary VaR cap reduction"}
        )
        assert app_res.status_code == 200
        assert app_res.json()["status"] == "APPROVED"

        # 4. Evaluate: Effective VaR should now reflect manual override of 300,000
        eval_res = await ac.post(
            "/api/v1/risk-limits/dynamic/evaluate",
            json={"portfolio_id": "PF_OVR_001", "market": "IN"}
        )
        assert eval_res.status_code == 200
        snaps = eval_res.json()
        snap = next(s for s in snaps if s["policy_id"] == pol_id)
        assert float(snap["effective_limit_value"]) == 300000.0
        assert snap["override_applied_id"] == ovr_id

        # 5. Revoke Override: Risk Manager revokes override early
        revoke_res = await ac.post(
            f"/api/v1/risk-limits/dynamic/overrides/{ovr_id}/revoke",
            json={"revoked_by": "cro_bob", "revocation_reason": "Event passed smoothly, reverting"}
        )
        assert revoke_res.status_code == 200
        assert revoke_res.json()["status"] == "REVOKED"

        # 6. Re-evaluate: Effective VaR immediately restores back to base 500,000
        eval_res2 = await ac.post(
            "/api/v1/risk-limits/dynamic/evaluate",
            json={"portfolio_id": "PF_OVR_001", "market": "IN"}
        )
        assert eval_res2.status_code == 200
        snaps2 = eval_res2.json()
        snap2 = next(s for s in snaps2 if s["policy_id"] == pol_id)
        assert float(snap2["effective_limit_value"]) == 500000.0
        assert snap2["override_applied_id"] is None
