"""
Comprehensive unit and integration tests for M13.08 — Alerts Dashboard.

Verifies:
1. Feature M13.08.01: Active breaches summary counts, active breach listing with duration/utilization/SLA calculations, and breach detail retrieval.
2. Feature M13.08.02: Recent alerts summary counts, filterable chronological alert feed, alert detail with trigger condition and evidence payload, and immutable audit timeline history.
3. Feature M13.08.03: Operational workflow actions (Acknowledge, Assign, Close, Reopen, and Breach Acknowledgment forwarded to M11).
4. Feature M13.08.04: Dashboard view preferences, saved custom views, and audit logging.
5. REST API endpoints mounted under `/api/v1/dashboard/alerts/*`.
"""

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.core.database import AsyncSessionLocal
from backend.app.main import app

# Models
from backend.app.modules.portfolio_management.portfolio_creation.models import (
    Portfolio,
    PortfolioLifecycleStatus,
    PortfolioTypeEnum,
    CreationSourceEnum,
    MarketScopeEnum,
)
from backend.app.modules.instrument_reference_data.instrument_master.models import Instrument
from backend.app.modules.risk_limits.breach_detection.models.breach_detection_models import (
    BreachEvaluation,
    BreachEpisode,
    BreachObservation,
    BreachEvent,
)
from backend.app.modules.risk_limits.risk_escalation.models.risk_escalation_models import (
    RiskBreachWorkflow,
)
from backend.app.modules.risk_alerts.models.risk_alerts_models import (
    AlertRule,
    AlertEvent,
    AlertEvidence,
    AlertLifecycleEvent,
)
from backend.app.modules.dashboard_visualization.alerts_dashboard.services.alerts_dashboard_service import (
    AlertsDashboardService,
)
from backend.app.modules.dashboard_visualization.alerts_dashboard.schemas.alerts_dashboard_schemas import (
    AlertAcknowledgeActionRequest,
    AlertAssignActionRequest,
    AlertCloseActionRequest,
    AlertReopenActionRequest,
    BreachAcknowledgeActionRequest,
    AlertsPreferenceCreateRequest,
    AlertsSavedViewCreateRequest,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_alerts_dashboard_services_and_analytics():
    """Tests active breaches, recent alerts, action workflows, and history timeline."""
    suffix = uuid.uuid4().hex[:6]
    port_id = f"PORT_ALR_{suffix}"
    inst_id = f"INST_AAPL_{suffix}"
    rule_id = f"RULE_VAR_{suffix}"
    
    breach_id = f"BREACH_EVT_{suffix}"
    eval_id = f"EVAL_REF_{suffix}"
    ep_id = f"EPISODE_{suffix}"
    wf_id = f"WF_BREACH_{suffix}"
    
    alert_1_id = f"ALR_1_{suffix}"
    alert_2_id = f"ALR_2_{suffix}"
    now = utc_now()

    async with AsyncSessionLocal() as session:
        # 1. Setup Portfolio & Instrument
        port = Portfolio(
            portfolio_id=port_id,
            portfolio_code=port_id,
            portfolio_name=f"Macro Hedge Port {suffix}",
            short_name="Macro Hedge",
            base_currency="USD",
            lifecycle_status=PortfolioLifecycleStatus.ACTIVE,
            portfolio_type=PortfolioTypeEnum.DISCRETIONARY,
            creation_source=CreationSourceEnum.MANUAL_ADMINISTRATION,
            market_scope=MarketScopeEnum.UNITED_STATES,
            created_by="TEST_ADMIN",
        )
        inst = Instrument(
            instrument_id=inst_id,
            canonical_name="Apple Inc",
            short_name="AAPL",
            instrument_type="COMMON_STOCK",
            asset_class="EQUITY",
            issue_currency="USD",
        )
        session.add_all([port, inst])

        # 2. Setup M11 Breach Evaluation, Episode, Event & Workflow
        breach_eval = BreachEvaluation(
            id=eval_id,
            evaluation_reference=f"EVREF_{suffix}",
            portfolio_id=port_id,
            target_entity_type="PORTFOLIO",
            target_entity_id=port_id,
            metric_code="PORTFOLIO_VAR_95",
            metric_source_module="M07.02",
            metric_value=Decimal("450000.00"),
            hard_threshold=Decimal("400000.00"),
            applied_threshold=Decimal("400000.00"),
            evaluation_status="HARD_BREACH",
            severity="CRITICAL",
            breach_magnitude=Decimal("50000.00"),
            utilization=Decimal("112.50"),
            metric_timestamp=now - timedelta(hours=2),
        )
        episode = BreachEpisode(
            id=ep_id,
            portfolio_id=port_id,
            risk_limit_id=f"LIMIT_VAR_{suffix}",
            target_entity_type="PORTFOLIO",
            target_entity_id=port_id,
            metric_code="PORTFOLIO_VAR_95",
            episode_status="ACTIVE_HARD_BREACH",
            first_violation_at=now - timedelta(hours=2),
            breach_detected_at=now - timedelta(hours=2),
            maximum_breach_magnitude=Decimal("50000.00"),
            maximum_observed_value=Decimal("450000.00"),
            first_evaluation_id=eval_id,
            latest_evaluation_id=eval_id,
        )
        breach_event = BreachEvent(
            id=breach_id,
            event_reference=f"BEVT_{suffix}",
            breach_episode_id=ep_id,
            portfolio_id=port_id,
            target_entity_type="PORTFOLIO",
            target_entity_id=port_id,
            risk_limit_id=f"LIMIT_VAR_{suffix}",
            metric_code="PORTFOLIO_VAR_95",
            event_type="HARD_BREACH_ENTERED",
            severity="CRITICAL",
            observed_value=Decimal("450000.00"),
            threshold_value=Decimal("400000.00"),
            warning_threshold=Decimal("350000.00"),
            hard_threshold=Decimal("400000.00"),
            breach_magnitude=Decimal("50000.00"),
            utilization=Decimal("112.50"),
            metric_timestamp=now - timedelta(hours=2),
            detected_at=now - timedelta(hours=2),
            evaluation_id=eval_id,
            correlation_id=f"CORR_{suffix}",
        )
        wf = RiskBreachWorkflow(
            id=wf_id,
            workflow_reference=f"WRK-{suffix}",
            breach_event_id=breach_id,
            breach_episode_id=ep_id,
            portfolio_id=port_id,
            risk_limit_id=f"LIMIT_VAR_{suffix}",
            severity="CRITICAL",
            current_lifecycle_state="OPEN",
            current_assignment_status="UNASSIGNED",
            current_sla_status="ON_TRACK",
            acknowledgement_status="PENDING_ACKNOWLEDGEMENT",
            sla_start_at=now - timedelta(hours=2),
            acknowledgement_due_at=now + timedelta(minutes=15),
            resolution_due_at=now + timedelta(hours=2),
            created_at=now - timedelta(hours=2),
            updated_at=now - timedelta(hours=2),
        )
        session.add_all([breach_eval, episode, breach_event, wf])

        # 3. Setup M12 Alert Rule, Alert Events & Evidence
        alert_rule = AlertRule(
            id=rule_id,
            rule_code=f"RULE_VAR_{suffix}",
            name="VaR Limit Exceeded Alert",
            metric_category="VAR",
            metric_identifier="var_95",
            priority="CRITICAL",
            created_by="QUANT_RISK",
        )
        session.add(alert_rule)

        al1 = AlertEvent(
            id=alert_1_id,
            alert_type="THRESHOLD_ALERT",
            alert_category="VAR",
            source_module="M12.01",
            source_event_id=breach_id,  # Linked to M11 breach!
            portfolio_id=port_id,
            instrument_id=inst_id,
            rule_id=rule_id,
            title="Portfolio 95% VaR Limit Breached",
            description="Portfolio 1-day 95% VaR at $450,000 exceeds hard limit of $400,000.",
            priority="CRITICAL",
            status="OPEN",
            deduplication_key=f"DEDUP_VAR_{suffix}",
            first_seen_at=now - timedelta(hours=1),
            last_seen_at=now - timedelta(hours=1),
            created_at=now - timedelta(hours=1),
            updated_at=now - timedelta(hours=1),
        )
        ev1 = AlertEvidence(
            id=f"EV_1_{suffix}",
            alert_id=alert_1_id,
            metric_value=Decimal("450000.00"),
            threshold_value=Decimal("400000.00"),
            metric_unit="USD",
            currency="USD",
            evidence_payload={"limit_utilization_pct": 112.5, "var_model": "PARAMETRIC_STUDENT_T"},
        )
        lc1 = AlertLifecycleEvent(
            id=f"LC_1_{suffix}",
            alert_id=alert_1_id,
            previous_status="NONE",
            new_status="OPEN",
            action_type="CREATED",
            actor_id="SYSTEM",
            action_note="Triggered by M12 threshold monitoring rule",
            created_at=now - timedelta(hours=1),
        )

        al2 = AlertEvent(
            id=alert_2_id,
            alert_type="LIQUIDITY_ALERT",
            alert_category="LIQUIDITY",
            source_module="M12.03",
            portfolio_id=port_id,
            instrument_id=inst_id,
            title="Abnormal Bid-Ask Spread Widening",
            description="AAPL spread widened to 18.5 bps, exceeding 12 bps threshold.",
            priority="HIGH",
            status="OPEN",
            deduplication_key=f"DEDUP_LIQ_{suffix}",
            first_seen_at=now - timedelta(minutes=30),
            last_seen_at=now - timedelta(minutes=30),
            created_at=now - timedelta(minutes=30),
            updated_at=now - timedelta(minutes=30),
        )
        session.add_all([al1, ev1, lc1, al2])
        await session.commit()

    # --- Test Service Layer ---
    async with AsyncSessionLocal() as session:
        svc = AlertsDashboardService(session)

        # 1. Active Breaches Summary
        b_summary = await svc.get_active_breaches_summary(portfolio_id=port_id)
        assert b_summary.counts.total_active >= 1
        assert b_summary.counts.critical >= 1
        assert b_summary.counts.unacknowledged >= 1

        # 2. Active Breaches List
        b_list = await svc.list_active_breaches(portfolio_id=port_id, severity="CRITICAL")
        assert b_list.total >= 1
        top_breach = b_list.items[0]
        assert top_breach.breach_id == breach_id
        assert top_breach.severity == "CRITICAL"
        assert top_breach.utilization == Decimal("112.50")
        assert top_breach.status == "OPEN"
        assert top_breach.duration_minutes >= 115

        # 3. Breach Detail
        b_detail = await svc.get_breach_detail(breach_id)
        assert b_detail.breach.breach_id == breach_id
        assert len(b_detail.related_alerts) >= 1
        assert b_detail.related_alerts[0]["alert_id"] == alert_1_id

        # 4. Recent Alerts Summary
        a_summary = await svc.get_recent_alerts_summary(portfolio_id=port_id)
        assert a_summary.counts.total_alerts >= 2
        assert a_summary.counts.new_alerts >= 2
        assert a_summary.counts.unacknowledged >= 2

        # 5. Recent Alerts List
        a_list = await svc.list_recent_alerts(portfolio_id=port_id, time_preset="LAST_24_HOURS")
        assert a_list.total >= 2
        alert_ids = [a.alert_id for a in a_list.items]
        assert alert_1_id in alert_ids
        assert alert_2_id in alert_ids

        # 6. Alert Detail & Permitted Actions
        a_detail = await svc.get_alert_detail(alert_1_id)
        assert a_detail.alert.alert_id == alert_1_id
        assert a_detail.rule_code == f"RULE_VAR_{suffix}"
        assert a_detail.observed_value == Decimal("450000.00")
        assert "ACKNOWLEDGE" in a_detail.permitted_actions
        assert "ASSIGN" in a_detail.permitted_actions

        # 7. Operational Workflow Action: Acknowledge Alert (with unlinked breach safety check)
        ack_res = await svc.acknowledge_alert(
            alert_id=alert_1_id,
            user_id="risk_officer_1",
            req=AlertAcknowledgeActionRequest(comment="Under investigation by macro desk"),
        )
        assert ack_res.success is True
        assert ack_res.new_state == "ACKNOWLEDGED"
        assert ack_res.has_unresolved_linked_breach_warning is True
        assert "does not mitigate" in (ack_res.warning_message or "")

        # 8. Operational Workflow Action: Assign Alert
        assign_res = await svc.assign_alert(
            alert_id=alert_1_id,
            user_id="risk_officer_1",
            req=AlertAssignActionRequest(assigned_to_user_id="analyst_jane"),
        )
        assert assign_res.success is True
        assert assign_res.new_state == "ASSIGNED"

        # 9. Operational Workflow Action: Close Alert
        close_res = await svc.close_alert(
            alert_id=alert_1_id,
            user_id="risk_officer_1",
            req=AlertCloseActionRequest(
                resolution_category="INVESTIGATED",
                resolution_comment="Hedge ratio rebalanced, VaR expected to normalize",
            ),
        )
        assert close_res.success is True
        assert close_res.new_state == "CLOSED"
        assert close_res.has_unresolved_linked_breach_warning is True

        # 10. Operational Workflow Action: Reopen Alert
        reopen_res = await svc.reopen_alert(
            alert_id=alert_1_id,
            user_id="risk_officer_1",
            req=AlertReopenActionRequest(reopening_reason="VaR spiked again during market close"),
        )
        assert reopen_res.success is True
        assert reopen_res.new_state == "REOPENED"

        # 11. Timeline History Verification
        hist = await svc.get_alert_history(alert_1_id)
        assert hist.total_events >= 5
        types = [e.event_type for e in hist.events]
        assert "CREATED" in types
        assert "ACKNOWLEDGED" in types
        assert "ASSIGNED" in types
        assert "CLOSED" in types
        assert "REOPENED" in types

        # 12. Forward Breach Acknowledgment to M11.08
        breach_ack_res = await svc.acknowledge_breach(
            breach_id=breach_id,
            user_id="risk_officer_1",
            req=BreachAcknowledgeActionRequest(review_notes="Formal M11 breach review completed"),
        )
        assert breach_ack_res.success is True
        assert breach_ack_res.new_state == "ACKNOWLEDGED"


@pytest.mark.asyncio
async def test_alerts_dashboard_persistence_and_api():
    """Tests preferences, saved views, and REST API endpoints."""
    user_id = f"user_{uuid.uuid4().hex[:6]}"
    port_id = f"PORT_API_{uuid.uuid4().hex[:6]}"

    async with AsyncSessionLocal() as session:
        svc = AlertsDashboardService(session)

        # 1. Preferences persistence
        pref_req = AlertsPreferenceCreateRequest(
            dashboard_name="Daily Risk Watch",
            default_portfolio_id=port_id,
            default_severity_selection=["CRITICAL", "EMERGENCY"],
            default_alert_category_selection=["VAR", "LIQUIDITY"],
            default_time_range_preset="LAST_4_HOURS",
            breaches_page_size=20,
            alerts_page_size=40,
            sound_alerts_enabled=True,
        )
        pref = await svc.update_user_preferences(user_id=user_id, req=pref_req)
        assert pref.dashboard_name == "Daily Risk Watch"
        assert pref.sound_alerts_enabled is True
        assert pref.breaches_page_size == 20

        # 2. Saved Views persistence
        view_req = AlertsSavedViewCreateRequest(
            view_name="Critical Liquidity & VaR",
            description="Filters active emergency and critical alerts",
            portfolio_id=port_id,
            selected_severities=["CRITICAL", "EMERGENCY"],
            selected_categories=["VAR", "LIQUIDITY"],
            time_range_preset="LAST_1_HOUR",
            is_public=True,
        )
        saved_view = await svc.create_saved_view(user_id=user_id, req=view_req)
        assert saved_view.id.startswith("aview_")
        assert saved_view.view_name == "Critical Liquidity & VaR"

        views = await svc.list_saved_views(user_id=user_id)
        assert len(views) >= 1

    # 3. HTTP Endpoints via AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Breach summary
        r1 = await ac.get("/api/v1/dashboard/alerts/breaches/summary")
        assert r1.status_code == 200
        assert "counts" in r1.json()

        # Breaches listing
        r2 = await ac.get("/api/v1/dashboard/alerts/breaches?page=1&page_size=10")
        assert r2.status_code == 200
        assert "items" in r2.json()

        # Alert summary
        r3 = await ac.get("/api/v1/dashboard/alerts/summary?time_preset=LAST_24_HOURS")
        assert r3.status_code == 200
        assert "counts" in r3.json()

        # Alerts feed
        r4 = await ac.get("/api/v1/dashboard/alerts?page=1&page_size=10")
        assert r4.status_code == 200
        assert "items" in r4.json()

        # Preferences
        r5 = await ac.get(f"/api/v1/dashboard/alerts/preferences/me?user_id={user_id}")
        assert r5.status_code == 200
        assert r5.json()["dashboard_name"] == "Daily Risk Watch"

        # Saved views
        r6 = await ac.get(f"/api/v1/dashboard/alerts/saved-views?user_id={user_id}")
        assert r6.status_code == 200
        assert isinstance(r6.json(), list)
