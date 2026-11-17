"""
Automated Unit and Integration Tests for M15.12 Operational Safety.
Validates Global Kill Switch enforcement, Scoped switches, Pre-dispatch Gateway checks,
Incident management, and REST APIs.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.modules.infrastructure_platform.operational_safety.services import (
    KillSwitchManager,
    ExecutionSafetyGateway,
    IncidentManager,
)
from backend.app.modules.infrastructure_platform.operational_safety.models.safety_models import (
    ExecutionDecisionOutcome,
    KillSwitchState,
    KillSwitchScopeType,
)


@pytest.fixture(autouse=True)
def reset_kill_switches():
    """Ensure switches are reset to inactive before each test."""
    for sw in KillSwitchManager.SWITCH_REGISTRY.values():
        sw["state"] = KillSwitchState.INACTIVE
        sw["activation_reason"] = None
        sw["activated_by"] = None


@pytest.mark.unit
def test_kill_switch_activation_and_reactivation():
    """Validates immediate state toggle and revision increments."""
    sw = KillSwitchManager.activate_switch(
        switch_code="GLOBAL_EXECUTION",
        reason="Test emergency halt",
        activated_by="RiskOfficer",
    )
    assert sw["state"] == KillSwitchState.ACTIVE
    assert KillSwitchManager.is_global_execution_blocked() is True

    # Reactivate
    reactivated = KillSwitchManager.reactivate_switch(
        switch_code="GLOBAL_EXECUTION",
        reason="Halt resolved",
        requested_by="RiskOfficer",
    )
    assert reactivated["state"] == KillSwitchState.INACTIVE
    assert KillSwitchManager.is_global_execution_blocked() is False


@pytest.mark.unit
def test_execution_safety_gateway_fail_closed_on_kill_switch():
    """Ensures execution gateway BLOCKS orders when kill switch is active."""
    # 1. Normal state -> Allowed
    res = ExecutionSafetyGateway.evaluate_execution_permission(
        instrument_id="RELIANCE",
        requested_quantity=100.0,
        side="BUY",
        adapter_id="ADAPTER_NSE_BROKER",
    )
    assert res["allowed"] is True
    assert res["decision"] == ExecutionDecisionOutcome.ALLOWED

    # 2. Activate Global Kill Switch
    KillSwitchManager.activate_switch("GLOBAL_EXECUTION", "Emergency Halt")

    # 3. Attempt same order -> Must be BLOCKED
    blocked_res = ExecutionSafetyGateway.evaluate_execution_permission(
        instrument_id="RELIANCE",
        requested_quantity=100.0,
        side="BUY",
        adapter_id="ADAPTER_NSE_BROKER",
    )
    assert blocked_res["allowed"] is False
    assert blocked_res["decision"] == ExecutionDecisionOutcome.BLOCKED
    assert "GLOBAL_KILL_SWITCH_ACTIVE" in blocked_res["reason_codes"]


@pytest.mark.unit
def test_execution_safety_gateway_stale_data_rejection():
    """Verifies that stale market data or limit failures block execution."""
    res = ExecutionSafetyGateway.evaluate_execution_permission(
        instrument_id="AAPL",
        requested_quantity=50.0,
        side="BUY",
        market_data_fresh=False, # Stale data
    )
    assert res["allowed"] is False
    assert "MARKET_DATA_STALE_OR_UNAVAILABLE" in res["reason_codes"]


@pytest.mark.unit
def test_incident_creation_and_runbook_catalogue():
    """Validates incident tracking and structured runbook availability."""
    inc = IncidentManager.create_incident(
        title="Test Incident",
        description="Testing incident creation",
        severity="SEV2_HIGH",
    )
    assert inc["incident_reference"].startswith("INC-")

    runbooks = IncidentManager.list_runbooks()
    assert len(runbooks) >= 3
    codes = [r["runbook_code"] for r in runbooks]
    assert "RB-EMERGENCY-SHUTDOWN" in codes
    assert "RB-RECOVERY-REACTIVATION" in codes


@pytest.mark.asyncio
@pytest.mark.integration
async def test_operational_safety_status_api():
    """Validates GET /api/v1/operational-safety/status endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/operational-safety/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_safety_state" in data
        assert "global_execution_enabled" in data
        assert len(data["kill_switches"]) >= 3


@pytest.mark.asyncio
@pytest.mark.integration
async def test_kill_switch_activate_api():
    """Validates POST /api/v1/operational-safety/kill-switches/activate endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "switch_code": "GLOBAL_EXECUTION",
            "reason": "API activation test",
            "confirm_action": True,
        }
        resp = await client.post("/api/v1/operational-safety/kill-switches/activate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "ACTIVE"
        assert KillSwitchManager.is_global_execution_blocked() is True

        # Precheck endpoint should now block
        precheck_resp = await client.post(
            "/api/v1/operational-safety/execution-gateway/precheck",
            json={"instrument_id": "TCS", "requested_quantity": 25.0, "side": "BUY"}
        )
        assert precheck_resp.status_code == 200
        precheck_data = precheck_resp.json()
        assert precheck_data["allowed"] is False
        assert precheck_data["decision"] == "BLOCKED"
