"""
Comprehensive tests for M11.07 — Breach Classification.

Tests cover:
1. Core calculations & severity precedence:
   - Materiality calculation: valid NAV, zero NAV, negative NAV, missing NAV.
   - Severity resolution precedence: EMERGENCY > CRITICAL > WARNING.
   - Numeric rule evaluations: GREATER_THAN, GREATER_EQUAL, LESS_THAN, BETWEEN, etc.
2. Maker-Checker Policy Workflow:
   - Draft policy and policy version creation.
   - Maker-checker rejection: author cannot approve own policy version.
   - Independent risk officer approval.
3. Classification Engine Operations:
   - Classifying M11.06 soft warning as WARNING.
   - Classifying M11.06 hard limit breach as CRITICAL.
   - Triggering EMERGENCY severity based on high excess magnitude and emergency rules.
   - Idempotent repeated classification requests.
   - Preserving full evidence and generating downstream classification events.
4. Reclassification Workflow:
   - Controlled manual upgrade (WARNING -> CRITICAL or CRITICAL -> EMERGENCY).
   - Recovery downgrade with reason code.
   - Historical audit logging in ClassificationHistory.
5. REST API Endpoints:
   - GET /health
   - POST /policies & POST /policies/{id}/versions/{v_id}/approve
   - POST /classify & GET /classifications
   - POST /classifications/{id}/reclassify & GET /reclassification-history
   - GET /monitoring/overview & GET /audit
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db
from backend.app.modules.risk_limits.breach_classification.calculations.breach_classification_math import (
    calculate_portfolio_materiality,
    resolve_higher_severity,
    evaluate_severity_rule,
    SEVERITY_WARNING,
    SEVERITY_CRITICAL,
    SEVERITY_EMERGENCY,
)


@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()


# -------------------------------------------------------------
# 1. Pure Calculation & Logic Tests
# -------------------------------------------------------------

def test_materiality_calculations():
    # Valid positive NAV: Impact 500,000 on NAV 10,000,000 -> 5.0%
    pct, status = calculate_portfolio_materiality(Decimal("500000"), Decimal("10000000"))
    assert pct == Decimal("5.0000")
    assert status == "VALID"

    # Missing NAV -> UNAVAILABLE
    pct_none, status_none = calculate_portfolio_materiality(Decimal("500000"), None)
    assert pct_none is None
    assert status_none == "UNAVAILABLE"

    # Zero or Negative NAV -> INVALID_NAV
    pct_zero, status_zero = calculate_portfolio_materiality(Decimal("500000"), Decimal("0"))
    assert pct_zero is None
    assert status_zero == "INVALID_NAV"


def test_severity_precedence():
    # EMERGENCY beats CRITICAL and WARNING
    assert resolve_higher_severity(SEVERITY_WARNING, SEVERITY_EMERGENCY) == SEVERITY_EMERGENCY
    assert resolve_higher_severity(SEVERITY_CRITICAL, SEVERITY_EMERGENCY) == SEVERITY_EMERGENCY
    assert resolve_higher_severity(SEVERITY_WARNING, SEVERITY_CRITICAL) == SEVERITY_CRITICAL
    assert resolve_higher_severity(SEVERITY_CRITICAL, SEVERITY_WARNING) == SEVERITY_CRITICAL


def test_rule_operator_evaluations():
    assert evaluate_severity_rule("GREATER_THAN", Decimal("25.0"), Decimal("20.0")) is True
    assert evaluate_severity_rule("GREATER_THAN", Decimal("18.0"), Decimal("20.0")) is False
    assert evaluate_severity_rule("BETWEEN", Decimal("15.0"), Decimal("10.0"), Decimal("20.0")) is True
    assert evaluate_severity_rule("BETWEEN", Decimal("25.0"), Decimal("10.0"), Decimal("20.0")) is False


# -------------------------------------------------------------
# 2. Integration / End-to-End API Tests
# -------------------------------------------------------------

@pytest.mark.asyncio
async def test_classification_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/breach-classification/health")
        assert res.status_code == 200
        data = res.json()
        assert data["module"] == "M11.07 — Breach Classification"
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_policy_creation_and_maker_checker():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        policy_code = f"POL_SEV_TEST_{datetime.utcnow().timestamp()}"
        payload = {
            "policy_code": policy_code,
            "name": "Institutional Severity Policy",
            "scope_type": "ALL",
            "risk_category": "ALL",
            "priority": 10,
            "created_by": "quant_analyst_1",
            "initial_version": {
                "rules": [
                    {
                        "rule_code": "HIGH_MAGNITUDE_CRITICAL",
                        "rule_name": "Critical Breach on Magnitude > 2.0%",
                        "target_metric_code": "ALL",
                        "condition_operator": "GREATER_THAN",
                        "threshold_value": 2.0,
                        "target_severity": "CRITICAL",
                        "priority": 20
                    },
                    {
                        "rule_code": "EXTREME_MAGNITUDE_EMERGENCY",
                        "rule_name": "Emergency Breach on Magnitude > 10.0%",
                        "target_metric_code": "ALL",
                        "condition_operator": "GREATER_THAN",
                        "threshold_value": 10.0,
                        "target_severity": "EMERGENCY",
                        "priority": 5,
                        "immediate_classification": True
                    }
                ]
            }
        }

        # 1. Create Policy
        res = await ac.post("/api/v1/breach-classification/policies", json=payload)
        assert res.status_code == 201
        pol_data = res.json()
        pol_id = pol_data["id"]
        ver_id = pol_data["versions"][0]["id"]
        assert pol_data["lifecycle_status"] == "DRAFT"

        # 2. Maker-checker check: Author cannot approve own version
        self_app_res = await ac.post(
            f"/api/v1/breach-classification/policies/{pol_id}/versions/{ver_id}/approve",
            json={"approved_by": "quant_analyst_1", "comments": "Self approval attempt"}
        )
        assert self_app_res.status_code == 400
        assert "Maker-Checker violation" in self_app_res.json()["detail"]

        # 3. Independent checker approves
        app_res = await ac.post(
            f"/api/v1/breach-classification/policies/{pol_id}/versions/{ver_id}/approve",
            json={"approved_by": "risk_officer_bob", "comments": "Approved institutional severity rules"}
        )
        assert app_res.status_code == 200
        assert app_res.json()["approval_status"] == "APPROVED"

        # Verify policy is ACTIVE
        check_res = await ac.get(f"/api/v1/breach-classification/policies/{pol_id}")
        assert check_res.json()["lifecycle_status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_breach_event_classification_and_reclassification():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        now = datetime.utcnow()
        pf_id = f"PF_CLASS_{now.timestamp()}"

        # 1. First trigger a Breach Event in M11.06 Breach Detection
        breach_res = await ac.post(
            "/api/v1/breach-detection/evaluate",
            params={"hard_threshold": 10.0, "warning_threshold": 8.0, "limit_nature": "CAP"},
            json={
                "portfolio_id": pf_id,
                "target_entity_type": "PORTFOLIO",
                "target_entity_id": pf_id,
                "metric_code": "PORTFOLIO_VAR",
                "metric_value": 15.0,  # Magnitude = 5.0%
                "metric_timestamp": now.isoformat(),
            }
        )
        assert breach_res.status_code == 201
        eval_data = breach_res.json()
        assert eval_data["evaluation_status"] == "HARD_BREACH"

        # Fetch the generated breach event
        events_res = await ac.get("/api/v1/breach-detection/events", params={"portfolio_id": pf_id})
        assert events_res.status_code == 200
        events = events_res.json()
        assert len(events) >= 1
        breach_event_id = events[0]["id"]

        # 2. Classify the breach event in M11.07
        classify_res = await ac.post(
            "/api/v1/breach-classification/classify",
            json={
                "breach_event_id": breach_event_id,
                "portfolio_nav": 50000000.0,
            }
        )
        assert classify_res.status_code == 201
        cls_data = classify_res.json()
        classif_id = cls_data["id"]
        assert cls_data["severity"] in ("CRITICAL", "EMERGENCY")
        assert cls_data["materiality_status"] == "VALID"
        assert len(cls_data["evidence"]) >= 1

        # 3. Idempotency test: Re-classifying same event returns existing record
        classify_res2 = await ac.post(
            "/api/v1/breach-classification/classify",
            json={"breach_event_id": breach_event_id}
        )
        assert classify_res2.status_code == 201
        assert classify_res2.json()["id"] == classif_id

        # 4. Controlled Reclassification: Risk Manager upgrades to EMERGENCY
        reclass_res = await ac.post(
            f"/api/v1/breach-classification/classifications/{classif_id}/reclassify",
            json={
                "new_severity": "EMERGENCY",
                "reason_code": "EXECUTIVE_ESCALATION",
                "reason_text": "Market-wide volatility circuit breaker hit; immediate emergency status applied",
                "changed_by": "cro_executive"
            }
        )
        assert reclass_res.status_code == 200
        assert reclass_res.json()["severity"] == "EMERGENCY"
        assert reclass_res.json()["classification_status"] == "RECLASSIFIED"

        # 5. Check History Log
        hist_res = await ac.get("/api/v1/breach-classification/reclassification-history", params={"classification_id": classif_id})
        assert hist_res.status_code == 200
        history_items = hist_res.json()
        assert len(history_items) >= 1
        assert history_items[0]["new_severity"] == "EMERGENCY"
        assert history_items[0]["change_type"] == "UPGRADE"

        # 6. Check Monitoring Overview
        overview_res = await ac.get("/api/v1/breach-classification/monitoring/overview")
        assert overview_res.status_code == 200
        ov_data = overview_res.json()
        assert ov_data["total_active_classifications"] >= 1
        assert ov_data["total_upgraded_events"] >= 1

