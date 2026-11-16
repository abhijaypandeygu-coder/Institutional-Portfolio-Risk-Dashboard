"""
Comprehensive test suite for M12.06 — Alert Management.
Verifies all core feature groups:
1. Alert Acknowledgement & Metadata Context (reviewer, timestamps, snapshots)
2. Alert Ownership Assignment (individual and role-based, assignment history)
3. Unassignment and reassignment history preservation
4. Investigation Workflow & Centralized State Machine transitions
5. Investigation Comments & Revision History
6. Investigation Evidence & Attachments
7. Disposition Management & Selected Actions
8. Resolution Assessment before closure
9. Formal Alert Closure with mandatory reason & snapshots
10. Alert Reopening with workflow cycle incrementation and previous closure preservation
11. Immutable Chronological Workflow Event History
12. Work Queue & Summary Analytics
"""

import pytest
import pytest_asyncio
import uuid
from datetime import datetime
from decimal import Decimal
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.modules.risk_alerts.models.risk_alerts_models import AlertEvent
from backend.app.modules.risk_alerts.alert_management.schemas.alert_management_schemas import (
    AlertAcknowledgeRequest,
    AlertAssignRequest,
    AlertWorkflowTransitionRequest,
    AlertCommentCreate,
    AlertCommentUpdate,
    AlertEvidenceCreate,
    AlertDispositionCreate,
    AlertResolutionAssessmentCreate,
    AlertCloseRequest,
    AlertReopenRequest,
)
from backend.app.modules.risk_alerts.alert_management.services.alert_management_service import (
    AlertManagementService,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await init_db()


async def create_test_master_alert(session, alert_id: str):
    """Helper to ensure a parent alert exists in alert_events for foreign keys."""
    evt = AlertEvent(
        id=alert_id,
        alert_type="PORTFOLIO_ALERT",
        alert_category="DRAWDOWN",
        source_module="M12.04",
        portfolio_id="PORT-EQ-TEST",
        title="Portfolio Drawdown Warning",
        description="Intraday portfolio drawdown exceeded 3%",
        priority="HIGH",
        status="OPEN",
        deduplication_key=f"DEDUP-{alert_id}",
    )
    session.add(evt)
    await session.flush()
    return evt


@pytest.mark.asyncio
async def test_alert_acknowledgement_and_metadata():
    alert_id = f"ALT-ACK-{uuid.uuid4().hex[:8].upper()}"
    async with AsyncSessionLocal() as session:
        await create_test_master_alert(session, alert_id)
        service = AlertManagementService(session)

        req = AlertAcknowledgeRequest(
            reviewer_user_id="USER-REV-01",
            reviewer_role_snapshot="SENIOR_RISK_MANAGER",
            acknowledgement_comment="Acknowledging drawdown alert for investigation",
            priority_snapshot="HIGH",
            severity_snapshot="CRITICAL",
            urgency_snapshot="U2_HIGH",
            request_id="REQ-ACK-101",
        )

        ack = await service.acknowledge_alert(alert_id, req)
        assert ack.alert_id == alert_id
        assert ack.reviewer_user_id == "USER-REV-01"
        assert ack.reviewer_role_snapshot == "SENIOR_RISK_MANAGER"
        assert ack.workflow_cycle == 1
        assert ack.acknowledged_at is not None

        # Verify state projection
        state = await service.get_workflow_state(alert_id)
        assert state.acknowledgement_state == "ACKNOWLEDGED"
        assert state.current_state == "ACKNOWLEDGED"

        # Verify idempotency
        ack_second = await service.acknowledge_alert(alert_id, req)
        assert ack_second.id == ack.id

        # Verify timeline event
        timeline = await service.get_workflow_timeline(alert_id)
        assert len(timeline) >= 1
        assert timeline[0].event_type == "ALERT_ACKNOWLEDGED"
        assert timeline[0].actor_user_id == "USER-REV-01"


@pytest.mark.asyncio
async def test_alert_assignment_and_history():
    alert_id = f"ALT-ASN-{uuid.uuid4().hex[:8].upper()}"
    async with AsyncSessionLocal() as session:
        await create_test_master_alert(session, alert_id)
        service = AlertManagementService(session)

        # 1. Individual assignment
        req1 = AlertAssignRequest(
            assignment_type="USER",
            assigned_user_id="ANALYST_ALICE",
            assigned_by_user_id="LEAD_BOB",
            assignment_reason="Initial assignment for equity investigation",
        )
        asn1 = await service.assign_alert(alert_id, req1)
        assert asn1.assigned_user_id == "ANALYST_ALICE"
        assert asn1.assignment_status == "ACTIVE"

        state1 = await service.get_workflow_state(alert_id)
        assert state1.current_owner_user_id == "ANALYST_ALICE"
        assert state1.current_state == "ASSIGNED"

        # 2. Reassignment to a role
        req2 = AlertAssignRequest(
            assignment_type="ROLE",
            assigned_role_id="ROLE_MARKET_RISK",
            assigned_by_user_id="LEAD_BOB",
            assignment_reason="Reassigned to Market Risk team desk",
        )
        asn2 = await service.assign_alert(alert_id, req2)
        assert asn2.assigned_role_id == "ROLE_MARKET_RISK"
        assert asn2.assignment_status == "ACTIVE"

        # Check previous assignment transitioned to REASSIGNED
        assignments = await service.repo.list_assignments(alert_id)
        assert len(assignments) == 2
        assert assignments[1].assignment_status == "REASSIGNED"  # Older assignment

        # 3. Unassignment
        unassigned = await service.unassign_alert(alert_id, unassigned_by_user_id="LEAD_BOB", reason="Work completed")
        assert unassigned is not None
        assert unassigned.assignment_status == "UNASSIGNED"

        state_unassigned = await service.get_workflow_state(alert_id)
        assert state_unassigned.current_owner_user_id is None
        assert state_unassigned.current_owner_role_id is None


@pytest.mark.asyncio
async def test_investigation_state_machine_and_validation():
    alert_id = f"ALT-STM-{uuid.uuid4().hex[:8].upper()}"
    async with AsyncSessionLocal() as session:
        await create_test_master_alert(session, alert_id)
        service = AlertManagementService(session)

        # Valid transition: OPEN -> INVESTIGATING
        req_inv = AlertWorkflowTransitionRequest(
            target_state="INVESTIGATING",
            actor_user_id="USER-ANALYST",
            reason="Starting deep-dive analysis",
        )
        st1 = await service.transition_state(alert_id, req_inv)
        assert st1.current_state == "INVESTIGATING"
        assert st1.investigation_started_at is not None

        # Invalid transition: INVESTIGATING -> CLOSED directly (must go to RESOLVED first)
        req_invalid = AlertWorkflowTransitionRequest(
            target_state="CLOSED",
            actor_user_id="USER-ANALYST",
            reason="Trying to close directly",
        )
        with pytest.raises(ValueError, match="Invalid state transition"):
            await service.transition_state(alert_id, req_invalid)

        # Valid transition: INVESTIGATING -> PENDING_INFORMATION -> INVESTIGATING
        await service.transition_state(
            alert_id,
            AlertWorkflowTransitionRequest(
                target_state="PENDING_INFORMATION",
                actor_user_id="USER-ANALYST",
                reason="Waiting for broker settlement file",
            ),
        )
        st2 = await service.get_workflow_state(alert_id)
        assert st2.current_state == "PENDING_INFORMATION"

        await service.transition_state(
            alert_id,
            AlertWorkflowTransitionRequest(
                target_state="INVESTIGATING",
                actor_user_id="USER-ANALYST",
                reason="Broker statement received",
            ),
        )
        st3 = await service.get_workflow_state(alert_id)
        assert st3.current_state == "INVESTIGATING"


@pytest.mark.asyncio
async def test_comments_and_revisions():
    alert_id = f"ALT-CMT-{uuid.uuid4().hex[:8].upper()}"
    async with AsyncSessionLocal() as session:
        await create_test_master_alert(session, alert_id)
        service = AlertManagementService(session)

        # Add comment
        req_c = AlertCommentCreate(
            author_user_id="USER_CHRIS",
            comment_category="FINANCIAL_ASSESSMENT",
            comment_content="Initial estimate of affected loss is $120k.",
        )
        cmt = await service.add_comment(alert_id, req_c)
        assert cmt.author_user_id == "USER_CHRIS"
        assert cmt.comment_content == "Initial estimate of affected loss is $120k."

        # Edit comment with revision tracking
        req_up = AlertCommentUpdate(
            revised_by_user_id="USER_CHRIS",
            revised_content="Revised estimate of affected loss is $145k after factoring fees.",
            revision_reason="Included clearing and brokerage fee schedule",
        )
        updated = await service.update_comment(cmt.id, req_up)
        assert updated.is_edited is True
        assert updated.comment_content == "Revised estimate of affected loss is $145k after factoring fees."

        # Verify revision history
        comments = await service.list_comments(alert_id)
        assert len(comments) == 1
        assert len(comments[0].revisions) == 1
        assert comments[0].revisions[0].previous_content == "Initial estimate of affected loss is $120k."


@pytest.mark.asyncio
async def test_evidence_and_disposition():
    alert_id = f"ALT-DSP-{uuid.uuid4().hex[:8].upper()}"
    async with AsyncSessionLocal() as session:
        await create_test_master_alert(session, alert_id)
        service = AlertManagementService(session)

        # Attach evidence
        req_ev = AlertEvidenceCreate(
            evidence_type="MARKET_SNAPSHOT",
            description="L2 order book snapshot showing 45 bps bid-ask spread",
            evidence_payload={"bid": "100.10", "ask": "100.55", "spread_bps": 45.0},
            uploaded_by_user_id="USER_EVIDENCE_UPLOADER",
        )
        ev = await service.add_evidence(alert_id, req_ev)
        assert ev.evidence_type == "MARKET_SNAPSHOT"

        # Record disposition
        req_disp = AlertDispositionCreate(
            disposition="CONFIRMED_ISSUE",
            disposition_reason="Transient liquidity withdrawal confirmed on NASDAQ open",
            selected_action="CONTINUE_MONITORING",
            selected_by_user_id="USER_SENIOR_ANALYST",
        )
        disp = await service.record_disposition(alert_id, req_disp)
        assert disp.disposition == "CONFIRMED_ISSUE"

        state = await service.get_workflow_state(alert_id)
        assert state.current_disposition == "CONFIRMED_ISSUE"


@pytest.mark.asyncio
async def test_full_resolution_closure_and_reopening_lifecycle():
    alert_id = f"ALT-CYCLE-{uuid.uuid4().hex[:8].upper()}"
    async with AsyncSessionLocal() as session:
        await create_test_master_alert(session, alert_id)
        service = AlertManagementService(session)

        # 1. Move to INVESTIGATING and record disposition
        await service.transition_state(
            alert_id,
            AlertWorkflowTransitionRequest(target_state="INVESTIGATING", actor_user_id="USER_A"),
        )
        await service.record_disposition(
            alert_id,
            AlertDispositionCreate(
                disposition="RESOLVED",
                disposition_reason="Bid-ask spread restored to 2.1 bps normal range",
                selected_action="NO_ACTION",
                selected_by_user_id="USER_A",
            ),
        )

        # 2. Assess resolution -> moves to RESOLVED
        await service.assess_resolution(
            alert_id,
            AlertResolutionAssessmentCreate(
                resolution_status="RESOLVED",
                resolution_reason="Liquidity indicators back within standard limits for 30 minutes",
                assessed_by_user_id="USER_A",
            ),
        )
        st_resolved = await service.get_workflow_state(alert_id)
        assert st_resolved.current_state == "RESOLVED"
        assert st_resolved.resolved_at is not None

        # 3. Formal Closure
        closure = await service.close_alert(
            alert_id,
            AlertCloseRequest(
                closed_by_user_id="RISK_LEAD_DAVE",
                closure_reason="ISSUE_RESOLVED",
                closure_notes="Sign-off provided after verifying market depth",
            ),
        )
        assert closure.closure_reason == "ISSUE_RESOLVED"
        st_closed = await service.get_workflow_state(alert_id)
        assert st_closed.current_state == "CLOSED"
        assert st_closed.closed_at is not None

        # 4. Reopening alert (condition recurs)
        reopen = await service.reopen_alert(
            alert_id,
            AlertReopenRequest(
                reopened_by_user_id="RISK_AUTOMATION",
                reopening_reason="Condition relapsed: Spread widened again to 55 bps",
            ),
        )
        assert reopen.previous_workflow_cycle == 1
        assert reopen.new_workflow_cycle == 2

        # Check state projection in cycle 2
        st_reopened = await service.get_workflow_state(alert_id)
        assert st_reopened.workflow_cycle == 2
        assert st_reopened.current_state == "REOPENED"
        assert st_reopened.acknowledgement_state == "UNACKNOWLEDGED"  # Requires new acknowledgement
        assert st_reopened.closed_at is None

        # Verify historical closure is preserved
        closures = await service.repo.list_closures(alert_id)
        assert len(closures) == 1
        assert closures[0].workflow_cycle == 1

        # Verify timeline records entire journey across cycles
        timeline = await service.get_workflow_timeline(alert_id)
        event_types = [e.event_type for e in timeline]
        assert "ALERT_INVESTIGATION_STARTED" in event_types
        assert "ALERT_RESOLVED" in event_types
        assert "ALERT_CLOSED" in event_types
        assert "ALERT_REOPENED" in event_types


@pytest.mark.asyncio
async def test_management_router_endpoints():
    alert_id = f"ALT-ROUTER-{uuid.uuid4().hex[:8].upper()}"
    async with AsyncSessionLocal() as session:
        await create_test_master_alert(session, alert_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Acknowledge endpoint
        ack_res = await client.post(
            f"/api/v1/alert-management/alerts/{alert_id}/acknowledge",
            json={
                "reviewer_user_id": "API_USER_1",
                "reviewer_role_snapshot": "RISK_DESK",
                "acknowledgement_comment": "API Acknowledge Test",
            },
        )
        assert ack_res.status_code == 200
        assert ack_res.json()["alert_id"] == alert_id

        # 2. Assign endpoint
        asn_res = await client.post(
            f"/api/v1/alert-management/alerts/{alert_id}/assign",
            json={
                "assignment_type": "USER",
                "assigned_user_id": "API_ANALYST",
                "assigned_by_user_id": "API_LEAD",
                "assignment_reason": "Routing via API",
            },
        )
        assert asn_res.status_code == 200
        assert asn_res.json()["assigned_user_id"] == "API_ANALYST"

        # 3. Add comment endpoint
        cmt_res = await client.post(
            f"/api/v1/alert-management/alerts/{alert_id}/comments",
            json={
                "author_user_id": "API_ANALYST",
                "comment_category": "TECHNICAL_FINDING",
                "comment_content": "Order routing feed lag observed",
            },
        )
        assert cmt_res.status_code == 201

        # 4. Get timeline endpoint
        tl_res = await client.get(f"/api/v1/alert-management/alerts/{alert_id}/workflow/timeline")
        assert tl_res.status_code == 200
        events = tl_res.json()
        assert len(events) >= 2

        # 5. Summary endpoint
        sum_res = await client.get("/api/v1/alert-management/summary")
        assert sum_res.status_code == 200
        assert sum_res.json()["total_alerts"] >= 1

