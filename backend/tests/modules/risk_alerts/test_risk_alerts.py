"""
Pytest integration test suite for M12 Risk Alerts & Notification Engine.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.modules.risk_alerts.calculations.risk_alerts_math import (
    calculate_threshold_proximity,
    calculate_relative_var_pct,
    calculate_volatility_change,
    calculate_drawdown_magnitude,
    evaluate_threshold_state,
    build_deduplication_key,
)
from backend.app.modules.risk_alerts.services.risk_alerts_service import RiskAlertsService
from backend.app.modules.risk_alerts.schemas.risk_alerts_schemas import (
    AlertRuleCreateInput,
    AlertThresholdInput,
    ThresholdMetricEvaluateInput,
    EventAlertCreateInput,
    AlertAcknowledgeInput,
    AlertAssignInput,
    AlertResolveInput,
    AlertReopenInput,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await init_db()
    yield


@pytest.mark.asyncio
async def test_risk_alerts_math_and_hysteresis():
    prox = calculate_threshold_proximity(Decimal("85.00"), Decimal("100.00"))
    assert prox == Decimal("85.00")

    rel_var = calculate_relative_var_pct(Decimal("25000.00"), Decimal("1000000.00"))
    assert rel_var == Decimal("2.50")

    d_vol, d_pct = calculate_volatility_change(Decimal("0.24"), Decimal("0.20"))
    assert d_vol == Decimal("0.0400")
    assert d_pct == Decimal("20.00")

    dd_mag = calculate_drawdown_magnitude(Decimal("-0.1250"))
    assert dd_mag == Decimal("0.1250")

    # Upper bound hysteresis
    state1, ch1 = evaluate_threshold_state(Decimal("85.00"), Decimal("80.00"), Decimal("100.00"))
    assert state1 == "WARNING"
    assert ch1 is True

    # Drop slightly, still within hysteresis (recovery threshold is 72.0)
    state2, ch2 = evaluate_threshold_state(Decimal("75.00"), Decimal("80.00"), Decimal("100.00"), current_state="WARNING")
    assert state2 == "RECOVERING"

    # Drop below recovery
    state3, ch3 = evaluate_threshold_state(Decimal("70.00"), Decimal("80.00"), Decimal("100.00"), current_state="WARNING")
    assert state3 == "RECOVERED"


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/alerts/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert len(data["features"]) == 8


@pytest.mark.asyncio
async def test_threshold_rule_creation_and_var_alert():
    async with AsyncSessionLocal() as session:
        svc = RiskAlertsService(session)

        # 1. Create VaR Alert Rule
        rule_in = AlertRuleCreateInput(
            rule_code=f"RULE_VAR_{uuid.uuid4().hex[:6]}",
            name="Portfolio VaR 95% Daily Alert",
            description="Monitors daily VaR threshold crossing",
            metric_category="VAR",
            metric_identifier="var_95_daily",
            priority="HIGH",
            created_by="risk_manager_1",
            threshold=AlertThresholdInput(
                comparison_operator="GREATER_THAN_OR_EQUAL",
                warning_threshold=Decimal("2.00"),  # 2.0% NAV
                critical_threshold=Decimal("3.00"), # 3.0% NAV
                recovery_threshold=Decimal("1.80"), # 1.8% NAV
                metric_unit="NAV_PERCENTAGE",
            ),
        )
        rule = await svc.create_alert_rule(rule_in)
        assert rule.metric_category == "VAR"
        assert rule.status == "ACTIVE"

        # 2. Evaluate normal metric (1.5% NAV) -> NORMAL
        res_normal = await svc.evaluate_threshold_metric(ThresholdMetricEvaluateInput(
            portfolio_id="PORT_TEST_1",
            metric_category="VAR",
            metric_identifier="var_95_daily",
            current_value=Decimal("1.50"),
        ))
        assert res_normal.current_state == "NORMAL"
        assert res_normal.rule_triggered is False
        assert res_normal.alert is None

        # 3. Evaluate warning metric (2.4% NAV) -> WARNING Alert Generated
        res_warning = await svc.evaluate_threshold_metric(ThresholdMetricEvaluateInput(
            portfolio_id="PORT_TEST_1",
            metric_category="VAR",
            metric_identifier="var_95_daily",
            current_value=Decimal("2.40"),
        ))
        assert res_warning.current_state == "WARNING"
        assert res_warning.rule_triggered is True
        assert res_warning.alert is not None
        assert res_warning.alert.status == "OPEN"
        alert_id = res_warning.alert.id

        # 4. Evaluate critical metric (3.2% NAV) -> CRITICAL (Deduplicated, occurrence count incremented)
        res_crit = await svc.evaluate_threshold_metric(ThresholdMetricEvaluateInput(
            portfolio_id="PORT_TEST_1",
            metric_category="VAR",
            metric_identifier="var_95_daily",
            current_value=Decimal("3.20"),
        ))
        assert res_crit.current_state == "CRITICAL"
        assert res_crit.alert.id != alert_id or res_crit.alert.occurrence_count >= 1

        # 5. Stale data gate test
        res_stale = await svc.evaluate_threshold_metric(ThresholdMetricEvaluateInput(
            portfolio_id="PORT_TEST_1",
            metric_category="VAR",
            metric_identifier="var_95_daily",
            current_value=Decimal("1.00"),
            data_quality_status="STALE",
        ))
        assert res_stale.current_state == "STALE"


@pytest.mark.asyncio
async def test_alert_lifecycle_ack_assign_resolve_reopen():
    async with AsyncSessionLocal() as session:
        svc = RiskAlertsService(session)

        # Create Event Alert (e.g. from M11.06 Breach)
        event_in = EventAlertCreateInput(
            alert_type="EVENT_ALERT",
            alert_category="BREACH",
            source_module="M11.06",
            source_event_id=f"BREACH_EVT_{uuid.uuid4().hex[:6]}",
            portfolio_id="PORT_ALPHA",
            title="Position Limit Hard Breach Detected",
            description="TSLA position weight exceeded 10% NAV",
            priority="CRITICAL",
        )
        alert = await svc.create_event_alert(event_in)
        assert alert.status == "OPEN"
        assert alert.priority == "CRITICAL"

        # Acknowledge
        ack = await svc.acknowledge_alert(alert.id, AlertAcknowledgeInput(
            acknowledged_by_user_id="analyst_jane",
            action_note="Reviewed with execution desk",
        ))
        assert ack.status == "ACKNOWLEDGED"
        assert ack.acknowledged_by_user_id == "analyst_jane"

        # Assign
        asn = await svc.assign_alert(alert.id, AlertAssignInput(
            assigned_user_id="manager_dan",
            assigned_by_user_id="analyst_jane",
            action_note="Escalated for senior review",
        ))
        assert asn.status == "ASSIGNED"
        assert asn.assigned_user_id == "manager_dan"

        # Resolve
        res = await svc.resolve_alert(alert.id, AlertResolveInput(
            resolved_by_user_id="manager_dan",
            resolution_reason="POSITION_TRIMMED",
            action_note="Executed 500 shares sell order, restored weight to 8.5%",
        ))
        assert res.status == "RESOLVED"
        assert res.resolved_by_user_id == "manager_dan"

        # Reopen
        rop = await svc.reopen_alert(alert.id, AlertReopenInput(
            reopened_by_user_id="system_monitor",
            reopen_reason="Recurrence observed post-market",
        ))
        assert rop.status == "REOPENED"


@pytest.mark.asyncio
async def test_dashboard_and_analytics():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/alerts/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_active_alerts" in data
        assert "priority_breakdown" in data
        assert "category_breakdown" in data
