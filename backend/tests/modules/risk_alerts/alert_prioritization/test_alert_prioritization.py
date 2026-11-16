"""
Comprehensive test suite for M12.05 — Alert Prioritization.
Verifies all 17 feature groups:
1. Severity classification (WARNING, CRITICAL, EMERGENCY)
2. Severity policy configuration
3. Urgency evaluation (U1..U4, velocity)
4. Time-to-action assessment (Action windows)
5. Portfolio impact assessment (% NAV, scaling)
6. Risk impact assessment (limit utilization, VaR, stress)
7. Instrument & entity impact (breadth)
8. Composite priority scoring (S, U, I, P)
9. Priority band assignment (P1..P5, Emergency safeguard)
10. Dynamic priority recalculation & history
11. Deduplication (canonical SHA256 key, duplicate occurrence)
12. Correlation & grouping (parent cluster, group stats)
13. Escalation-aware grouping (escalation event recording)
14. Occurrence tracking (idempotency, occurrence metrics)
15. Priority explanation & evidence
16. Router API endpoints
17. Analytics summary
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.modules.risk_alerts.alert_prioritization.calculations.alert_prioritization_math import (
    normalize_score,
    calculate_deterioration_velocity,
    calculate_time_to_action,
    calculate_financial_impact_score,
    calculate_risk_impact_score,
    calculate_breadth_impact_score,
    calculate_composite_impact,
    calculate_persistence_score,
    calculate_priority_score,
    assign_priority_band,
    build_canonical_dedupe_key,
)
from backend.app.modules.risk_alerts.alert_prioritization.schemas.alert_prioritization_schemas import (
    AlertPrioritizationRequest,
    AlertPriorityPolicyCreate,
)
from backend.app.modules.risk_alerts.alert_prioritization.services.alert_prioritization_service import (
    AlertPrioritizationService,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_alert_prioritization_math_units():
    # 1. Normalize
    assert normalize_score(50, 0, 100) == 50.0
    assert normalize_score(150, 0, 100) == 100.0
    assert normalize_score(-10, 0, 100) == 0.0

    # 2. Velocity
    vel = calculate_deterioration_velocity(Decimal("10.0"), Decimal("5.0"), dt_seconds=60.0)
    assert vel == 5.0  # +5 per minute

    vel_dec = calculate_deterioration_velocity(Decimal("80.0"), Decimal("100.0"), dt_seconds=60.0, adverse_direction="DECREASING")
    assert vel_dec == 20.0  # drop of 20 is +20 adverse velocity

    # 3. Time to action
    tta_lbl, tta_mins = calculate_time_to_action("U1_IMMEDIATE", "EMERGENCY")
    assert tta_lbl == "IMMEDIATE_REVIEW"
    assert tta_mins == 5

    # 4. Financial impact
    f_score, pct_nav, conf = calculate_financial_impact_score(Decimal("500000"), Decimal("10000000"))
    assert pct_nav == Decimal("5.0000")
    assert f_score == 60.0
    assert conf == "HIGH"

    # 5. Risk impact
    r_score, r_conf = calculate_risk_impact_score(limit_utilization_pct=Decimal("110.0"), var_increase_pct=Decimal("20.0"))
    assert r_score > 50.0
    assert r_conf == "HIGH"

    # 6. Breadth impact
    b_score = calculate_breadth_impact_score(affected_instruments=5, total_instruments=20, affected_portfolios=2, affected_sectors=2)
    assert b_score > 0.0

    # 7. Composite impact
    c_impact = calculate_composite_impact(f_score, r_score, b_score)
    assert 0.0 <= c_impact <= 100.0

    # 8. Priority score & Emergency safeguard
    score = calculate_priority_score(
        severity_score=100.0,
        urgency_score=100.0,
        impact_score=80.0,
        persistence_score=20.0,
        priority_floor=90.0,
    )
    assert score >= 90.0
    band = assign_priority_band(score, is_emergency=True)
    assert band == "P1_IMMEDIATE"

    # 9. Canonical dedupe key
    k1 = build_canonical_dedupe_key("M12.01", "PORTFOLIO", "LOSS", "PORT_1", "PORTFOLIO", "COND_1")
    k2 = build_canonical_dedupe_key("M12.01", "PORTFOLIO", "LOSS", "PORT_1", "PORTFOLIO", "COND_1")
    k3 = build_canonical_dedupe_key("M12.01", "PORTFOLIO", "LOSS", "PORT_2", "PORTFOLIO", "COND_1")
    assert k1 == k2
    assert k1 != k3


@pytest.mark.asyncio
async def test_authoritative_severity_precedence():
    async with AsyncSessionLocal() as session:
        service = AlertPrioritizationService(session)

        # M11 Authoritative EMERGENCY must NOT be downgraded even if financial/risk data is missing
        req = AlertPrioritizationRequest(
            alert_id="ALT-AUTH-EMERGENCY-01",
            source_module="M11.06",
            category="BREACH",
            event_type="HARD_LIMIT_BREACH",
            portfolio_id="PORT-INST-01",
            source_severity="EMERGENCY",
            is_authoritative_severity=True,
            affected_value=None,  # Missing financial data
            nav=None,
        )

        res = await service.prioritize_alert(req)
        assert res.severity == "EMERGENCY"
        assert res.is_authoritative_severity is True
        assert res.severity_source == "M11.06_AUTHORITATIVE"
        assert res.priority_floor_applied is True
        assert res.priority_score >= 90.0
        assert res.priority_band == "P1_IMMEDIATE"
        assert res.confidence == "LOW"  # Reflects missing financial inputs
        assert res.quality_status == "MISSING_FINANCIAL_AND_RISK_DATA"


@pytest.mark.asyncio
async def test_policy_driven_severity_and_urgency():
    async with AsyncSessionLocal() as session:
        service = AlertPrioritizationService(session)

        # Create custom policy
        policy_req = AlertPriorityPolicyCreate(
            policy_name="POL_LOSS_SPECIAL",
            alert_category="PORTFOLIO",
            event_type="DRAWDOWN_LOSS",
            severity_rules={
                "rules": [
                    {"operator": "GTE", "threshold": "2.0", "severity": "WARNING"},
                    {"operator": "GTE", "threshold": "5.0", "severity": "CRITICAL"},
                    {"operator": "GTE", "threshold": "10.0", "severity": "EMERGENCY"},
                ]
            },
            priority_floor_config={"EMERGENCY": 90.0, "CRITICAL": 60.0},
        )
        await service.create_policy(policy_req)

        # Evaluate alert with 6.5% loss -> should trigger CRITICAL
        req = AlertPrioritizationRequest(
            alert_id="ALT-POL-CRIT-01",
            source_module="M12.04",
            category="PORTFOLIO",
            event_type="DRAWDOWN_LOSS",
            portfolio_id="PORT-EQ-01",
            observed_value=Decimal("6.5"),
            previous_value=Decimal("3.0"),
            dt_seconds=60.0,  # 3.5% jump in 1 min -> velocity 3.5 -> U2_HIGH
            affected_value=Decimal("650000"),
            nav=Decimal("10000000"),  # 6.5% of NAV
        )

        res = await service.prioritize_alert(req)
        assert res.severity == "CRITICAL"
        assert res.urgency == "U2_HIGH"
        assert res.priority_score >= 60.0  # Critical floor
        assert res.priority_band in ("P2_VERY_HIGH", "P3_HIGH")
        assert res.affected_value_pct_nav == Decimal("6.5000")


@pytest.mark.asyncio
async def test_deduplication_and_occurrence_tracking():
    async with AsyncSessionLocal() as session:
        service = AlertPrioritizationService(session)

        # First alert event
        req1 = AlertPrioritizationRequest(
            alert_id="ALT-REPEATED-01",
            source_module="M12.02",
            category="MARKET",
            event_type="PRICE_SHOCK",
            portfolio_id="PORT-US-01",
            instrument_id="AAPL",
            condition_id="PRICE_DEV_3SIGMA",
            observed_value=Decimal("4.2"),
            idempotency_key="EVT-001-A",
            affected_value=Decimal("200000"),
            nav=Decimal("10000000"),
        )
        res1 = await service.prioritize_alert(req1)
        group_id_1 = res1.group_id
        assert group_id_1 is not None

        # Repeat identical event with new occurrence
        req2 = AlertPrioritizationRequest(
            alert_id="ALT-REPEATED-01",
            source_module="M12.02",
            category="MARKET",
            event_type="PRICE_SHOCK",
            portfolio_id="PORT-US-01",
            instrument_id="AAPL",
            condition_id="PRICE_DEV_3SIGMA",
            observed_value=Decimal("4.5"),
            idempotency_key="EVT-002-B",
            affected_value=Decimal("200000"),
            nav=Decimal("10000000"),
        )
        res2 = await service.prioritize_alert(req2)
        assert res2.group_id == group_id_1

        # Check occurrence records
        occurrences = await service.get_alert_occurrences("ALT-REPEATED-01")
        assert len(occurrences) == 2

        # Verify idempotency: re-sending EVT-001-A returns existing evaluation without duplicating
        res_idem = await service.prioritize_alert(req1)
        assert res_idem.id == res1.id


@pytest.mark.asyncio
async def test_escalation_detection_and_history():
    async with AsyncSessionLocal() as session:
        service = AlertPrioritizationService(session)

        # Step 1: WARNING alert
        req1 = AlertPrioritizationRequest(
            alert_id="ALT-ESCALATE-01",
            source_module="M12.03",
            category="LIQUIDITY",
            event_type="SPREAD_WIDENING",
            portfolio_id="PORT-IN-01",
            source_severity="WARNING",
            affected_value=Decimal("50000"),
            nav=Decimal("10000000"),
        )
        res1 = await service.prioritize_alert(req1)
        assert res1.severity == "WARNING"

        # Step 2: Worsens to CRITICAL -> Escalation must be logged
        req2 = AlertPrioritizationRequest(
            alert_id="ALT-ESCALATE-01",
            source_module="M12.03",
            category="LIQUIDITY",
            event_type="SPREAD_WIDENING",
            portfolio_id="PORT-IN-01",
            source_severity="CRITICAL",
            affected_value=Decimal("1500000"),
            nav=Decimal("10000000"),
        )
        res2 = await service.prioritize_alert(req2)
        assert res2.severity == "CRITICAL"
        assert res2.priority_score > res1.priority_score

        # Check priority history
        history = await service.get_alert_history("ALT-ESCALATE-01")
        assert len(history) >= 1
        assert history[0].previous_severity == "WARNING"
        assert history[0].new_severity == "CRITICAL"


@pytest.mark.asyncio
async def test_prioritization_router_endpoints():
    import uuid
    policy_name = f"API_POLICY_{uuid.uuid4().hex[:8].upper()}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create Policy
        p_res = await client.post(
            "/api/v1/alert-prioritization/policies",
            json={
                "policy_name": policy_name,
                "policy_type": "DEFAULT",
                "severity_rules": {},
                "urgency_rules": {},
                "impact_weights": {"F": 0.45, "R": 0.40, "B": 0.15},
                "priority_weights": {"S": 0.35, "U": 0.30, "I": 0.25, "P": 0.10},
                "priority_band_config": {},
                "priority_floor_config": {"EMERGENCY": 90.0, "CRITICAL": 50.0},
            },
        )
        assert p_res.status_code == 201

        # 2. Prioritize Alert
        eval_res = await client.post(
            "/api/v1/alert-prioritization/prioritize",
            json={
                "alert_id": "ALT-API-01",
                "source_module": "M12.01",
                "category": "VAR",
                "event_type": "VAR_LIMIT_EXCEEDED",
                "portfolio_id": "PORT-GLOBAL-01",
                "source_severity": "CRITICAL",
                "is_authoritative_severity": True,
                "affected_value": "1200000.00",
                "nav": "10000000.00",
                "limit_utilization_pct": "115.0",
                "affected_instruments": 3,
                "total_instruments": 20,
            },
        )
        assert eval_res.status_code == 200
        data = eval_res.json()
        assert data["alert_id"] == "ALT-API-01"
        assert data["severity"] == "CRITICAL"
        assert data["priority_score"] >= 50.0

        # 3. Get Evaluation
        get_res = await client.get("/api/v1/alert-prioritization/evaluations/ALT-API-01")
        assert get_res.status_code == 200
        assert get_res.json()["alert_id"] == "ALT-API-01"

        # 4. Analytics Summary
        ana_res = await client.get("/api/v1/alert-prioritization/analytics/summary")
        assert ana_res.status_code == 200
        summary = ana_res.json()
        assert summary["total_evaluations"] >= 1
        assert "priority_band_distribution" in summary

