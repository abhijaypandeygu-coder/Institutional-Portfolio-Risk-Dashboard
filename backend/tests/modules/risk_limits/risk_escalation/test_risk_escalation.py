"""
Pytest integration and verification test suite for M11.08 Risk Escalation.
"""

import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.modules.risk_limits.risk_escalation.calculations.risk_escalation_math import (
    calculate_acknowledgement_time,
    calculate_mitigation_time,
    calculate_resolution_time,
    calculate_sla_compliance_rate,
    calculate_reopening_rate,
    calculate_escalation_frequency,
    is_sla_breached,
)
from backend.app.modules.risk_limits.risk_escalation.services.risk_escalation_service import RiskEscalationService
from backend.app.modules.risk_limits.risk_escalation.schemas.risk_escalation_schemas import (
    RiskWorkflowCreateInput,
    BreachAcknowledgeInput,
    BreachAssignInput,
    ManualEscalateInput,
    ResolutionPlanCreateInput,
    ResolutionActionCreateInput,
    ResolutionActionProgressInput,
    MitigationEvidenceInput,
    ClosureRequestInput,
    ClosureApproveInput,
    BreachReopenInput,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await init_db()
    yield


@pytest.mark.asyncio
async def test_escalation_math():
    now = datetime.utcnow()
    sla_start = now - timedelta(minutes=30)
    ack_time = calculate_acknowledgement_time(sla_start, now)
    assert 1790 <= ack_time <= 1810

    compliance = calculate_sla_compliance_rate(8, 10)
    assert compliance == Decimal("80.00")

    reopen_rate = calculate_reopening_rate(1, 10)
    assert reopen_rate == Decimal("10.00")

    esc_freq = calculate_escalation_frequency(5, 10)
    assert esc_freq == Decimal("0.50")

    deadline = now - timedelta(minutes=5)
    assert is_sla_breached(deadline, now) is True

    deadline_future = now + timedelta(minutes=15)
    assert is_sla_breached(deadline_future, now) is False


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/risk-escalation/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "breach_acknowledgement" in data["capabilities"]


@pytest.mark.asyncio
async def test_workflow_lifecycle_ack_assign_escalate():
    async with AsyncSessionLocal() as session:
        svc = RiskEscalationService(session)

        # 1. Create Workflow from incoming breach
        breach_evt_id = f"EVT_{uuid.uuid4().hex[:8]}"
        payload = RiskWorkflowCreateInput(
            breach_event_id=breach_evt_id,
            breach_episode_id="EP_001",
            portfolio_id="PORT_ALPHA",
            risk_limit_id="LIM_VAR_99",
            severity="CRITICAL",
            initial_owner_user_id="user_analyst_1",
            initial_owner_team_id="team_quant_risk",
        )
        wf = await svc.get_or_create_workflow(payload)
        assert wf.current_lifecycle_state == "OPEN"
        assert wf.severity == "CRITICAL"
        assert wf.current_escalation_level_name == "LEVEL_2"
        assert wf.current_assignment_status == "ASSIGNED"
        assert len(wf.sla_instances) == 2

        # 2. Acknowledge breach
        ack_in = BreachAcknowledgeInput(
            acknowledged_by_user_id="user_analyst_1",
            user_role="RISK_ANALYST",
            review_notes="Under active review with desk",
        )
        wf_ack = await svc.acknowledge_breach(wf.id, ack_in)
        assert wf_ack.current_lifecycle_state == "ACKNOWLEDGED"
        assert wf_ack.acknowledgement_status == "ACKNOWLEDGED"
        assert wf_ack.acknowledged_at is not None

        # 3. Reassign breach
        assign_in = BreachAssignInput(
            assigned_user_id="user_manager_2",
            assigned_team_id="team_quant_risk",
            responsibility_level="LEVEL_2",
            assignment_type="REASSIGNMENT",
            reassignment_reason="Specialist reallocation",
            assigned_by_user_id="user_analyst_1",
        )
        wf_asn = await svc.assign_breach(wf.id, assign_in)
        assert wf_asn.current_owner_user_id == "user_manager_2"

        # 4. Manual escalation
        wf_esc = await svc.escalate_breach(
            workflow_id=wf.id,
            target_level_name="LEVEL_3",
            escalation_reason="Breach persists with high market volatility",
            initiated_by_user_id="user_manager_2",
            trigger_type="MANUAL_ESCALATION",
        )
        assert wf_esc.current_escalation_level_name == "LEVEL_3"
        assert wf_esc.escalation_count == 1


@pytest.mark.asyncio
async def test_resolution_plan_mitigation_and_closure():
    async with AsyncSessionLocal() as session:
        svc = RiskEscalationService(session)

        breach_evt_id = f"EVT_{uuid.uuid4().hex[:8]}"
        wf = await svc.get_or_create_workflow(RiskWorkflowCreateInput(
            breach_event_id=breach_evt_id,
            portfolio_id="PORT_BETA",
            risk_limit_id="LIM_CONC_SECTOR",
            severity="WARNING",
            initial_owner_user_id="trader_john",
        ))

        # 1. Acknowledge
        await svc.acknowledge_breach(wf.id, BreachAcknowledgeInput(
            acknowledged_by_user_id="trader_john",
            user_role="TRADER",
        ))

        # 2. Create Resolution Plan
        now = datetime.utcnow()
        plan_in = ResolutionPlanCreateInput(
            title="Sector De-risking Plan",
            description="Sell over-concentrated tech positions",
            proposed_actions_summary="Execute sell orders across 3 symbols",
            owner_user_id="trader_john",
            priority="HIGH",
            due_at=now + timedelta(hours=4),
            created_by="trader_john",
            actions=[
                ResolutionActionCreateInput(
                    action_title="Hedge NASDAQ exposure",
                    description="Short QQQ ETF to offset sector beta",
                    assigned_to_user_id="trader_john",
                    due_at=now + timedelta(hours=2),
                )
            ]
        )
        plan = await svc.create_resolution_plan(wf.id, plan_in)
        assert plan.plan_status == "ACTIVE"
        assert len(plan.actions) == 1
        action_id = plan.actions[0].id

        # 3. Update action progress
        prog_in = ResolutionActionProgressInput(
            action_status="COMPLETED",
            progress_percentage=Decimal("100.00"),
            notes="Hedge executed at 14:00 UTC",
            updated_by_user_id="trader_john",
        )
        act = await svc.update_action_progress(action_id, prog_in)
        assert act.action_status == "COMPLETED"
        assert act.progress_percentage == Decimal("100.00")

        # 4. Submit verified mitigation evidence
        ev_in = MitigationEvidenceInput(
            evidence_type="HEDGE_ORDER",
            document_reference="ORD_19827391",
            description="Order filled and verified",
            verified_risk_reduction=True,
            submitted_by_user_id="trader_john",
        )
        ev = await svc.submit_mitigation_evidence(wf.id, ev_in)
        assert ev.verified_risk_reduction is True

        wf_refresh = await svc.repo.get_workflow_by_id(wf.id)
        assert wf_refresh.current_lifecycle_state == "MITIGATED"

        # 5. Request Closure
        req_in = ClosureRequestInput(
            closure_reason="EXPOSURE_REMOVED",
            closure_description="Tech sector weight restored to 18%",
            requested_by_user_id="trader_john",
        )
        req = await svc.request_closure(wf.id, req_in)
        assert req.request_status == "PENDING_APPROVAL"

        # 6. Maker-checker: Requester cannot approve their own closure
        with pytest.raises(Exception):
            await svc.approve_closure(wf.id, ClosureApproveInput(
                approved_by_user_id="trader_john"
            ))

        # Independent Risk Manager approves closure
        wf_closed = await svc.approve_closure(wf.id, ClosureApproveInput(
            approved_by_user_id="risk_manager_sarah"
        ))
        assert wf_closed.current_lifecycle_state == "CLOSED"
        assert wf_closed.closure_status == "APPROVED"
        assert wf_closed.closed_at is not None

        # 7. Reopening
        wf_reopened = await svc.reopen_breach(wf.id, BreachReopenInput(
            reopen_trigger="RECURRENCE_DETECTED",
            reopen_reason="Tech concentration spiked above limit again post-market",
            reopened_by_user_id="system_monitor",
        ))
        assert wf_reopened.current_lifecycle_state == "REOPENED"
        assert wf_reopened.acknowledgement_status == "PENDING_ACKNOWLEDGEMENT"


@pytest.mark.asyncio
async def test_dashboard_and_analytics_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/risk-escalation/dashboard")
        assert resp.status_code == 200
        summary = resp.json()
        assert "total_active_breaches" in summary
        assert "severity_breakdown" in summary
        assert "sla_compliance_rate" in summary
