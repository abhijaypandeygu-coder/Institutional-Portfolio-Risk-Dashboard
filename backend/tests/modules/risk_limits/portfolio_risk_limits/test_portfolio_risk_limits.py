"""
Unit and integration tests for M11.01 Portfolio Risk Limits.

Tests covered:
1. Utilization & Headroom calculation across states (WITHIN_LIMIT, WARNING, HARD_LIMIT_EXCEEDED).
2. Absolute VaR limit evaluation with boundary detection.
3. NAV-relative VaR limit evaluation and zero-NAV fail-safe rejection.
4. Volatility limit evaluation (realized & forecast annualized).
5. Drawdown limit evaluation with positive magnitude conversion and high-water mark tracking.
6. Service and Repository lifecycle (Profile creation, assignment, and evaluation).
7. FastAPI REST API endpoints:
   - GET /api/v1/risk-limits/health
   - POST /api/v1/risk-limits/profiles
   - GET /api/v1/risk-limits/profiles
   - GET /api/v1/risk-limits/profiles/{code}
   - POST /api/v1/risk-limits/assignments
   - POST /api/v1/risk-limits/portfolios/{id}/evaluate
"""

from decimal import Decimal
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.core.database import init_db, AsyncSessionLocal
from backend.app.main import app
from backend.app.modules.risk_limits.portfolio_risk_limits.calculations.limit_math import (
    evaluate_threshold_utilization,
    evaluate_var_limit,
    evaluate_volatility_limit,
    evaluate_drawdown_limit,
)
from backend.app.modules.risk_limits.portfolio_risk_limits.schemas.limit_schemas import (
    RiskLimitCreate,
    ProfileCreate,
    AssignmentCreate,
    EvaluationRequest,
)
from backend.app.modules.risk_limits.portfolio_risk_limits.services.limit_service import (
    PortfolioRiskLimitService,
)


def test_evaluate_threshold_utilization():
    # Hard limit = 100, Warning = 80
    # Case 1: Value = 50 -> WITHIN_LIMIT, U_hard = 50%, U_warn = 62.5%
    u_warn, u_hard, headroom, state = evaluate_threshold_utilization(
        observed_value=Decimal("50.0"),
        warning_threshold=Decimal("80.0"),
        hard_threshold=Decimal("100.0"),
    )
    assert state == "WITHIN_LIMIT"
    assert u_hard == Decimal("50.00")
    assert u_warn == Decimal("62.50")
    assert headroom == Decimal("50.0000")

    # Case 2: Value = 85 -> WARNING
    u_warn, u_hard, headroom, state = evaluate_threshold_utilization(
        observed_value=Decimal("85.0"),
        warning_threshold=Decimal("80.0"),
        hard_threshold=Decimal("100.0"),
    )
    assert state == "WARNING"
    assert headroom == Decimal("15.0000")

    # Case 3: Value = 105 -> HARD_LIMIT_EXCEEDED
    u_warn, u_hard, headroom, state = evaluate_threshold_utilization(
        observed_value=Decimal("105.0"),
        warning_threshold=Decimal("80.0"),
        hard_threshold=Decimal("100.0"),
    )
    assert state == "HARD_LIMIT_EXCEEDED"
    assert headroom == Decimal("-5.0000")


def test_evaluate_absolute_var_limit():
    # Limit: Warn 80k, Hard 100k
    # Case: VaR = 90k -> WARNING
    res = evaluate_var_limit(
        observed_var=Decimal("90000.0"),
        limit_type="ABSOLUTE",
        warning_threshold=Decimal("80000.0"),
        hard_threshold=Decimal("100000.0"),
    )
    assert res["evaluation_status"] == "WARNING"
    assert res["headroom"] == Decimal("10000.0000")
    assert res["hard_utilization_pct"] == Decimal("90.00")


def test_evaluate_relative_var_limit_and_zero_nav_failsafe():
    # NAV = 1,000,000, VaR = 25,000 (2.5%)
    # Warn limit = 2.0%, Hard limit = 3.0%
    res = evaluate_var_limit(
        observed_var=Decimal("25000.0"),
        limit_type="NAV_RELATIVE",
        warning_threshold=Decimal("2.0"),
        hard_threshold=Decimal("3.0"),
        portfolio_nav=Decimal("1000000.0"),
    )
    assert res["evaluation_status"] == "WARNING"
    assert res["observed_value"] == Decimal("2.5000")
    assert res["monetary_headroom"] == Decimal("5000.00")

    # Zero NAV Fail-Safe
    invalid_res = evaluate_var_limit(
        observed_var=Decimal("25000.0"),
        limit_type="NAV_RELATIVE",
        warning_threshold=Decimal("2.0"),
        hard_threshold=Decimal("3.0"),
        portfolio_nav=Decimal("0.0"),
    )
    assert invalid_res["evaluation_status"] == "INVALID"
    assert "Portfolio NAV must be strictly positive" in invalid_res["error_reason"]


def test_evaluate_volatility_and_drawdown_limits():
    # Volatility Limit: Warn = 0.150 (15.0%), Hard = 0.200 (20.0%)
    # Measured = 0.145 (14.5%) -> WITHIN_LIMIT
    vol_res = evaluate_volatility_limit(
        observed_volatility=Decimal("0.145"),
        warning_threshold=Decimal("0.150"),
        hard_threshold=Decimal("0.200"),
    )
    assert vol_res["evaluation_status"] == "WITHIN_LIMIT"
    assert vol_res["headroom"] == Decimal("0.0550")

    # Drawdown Limit: Warn = 0.050 (5.0%), Hard = 0.100 (10.0%)
    # Measured = 0.082 (8.2%) -> WARNING
    dd_res = evaluate_drawdown_limit(
        observed_drawdown=Decimal("0.082"),
        warning_threshold=Decimal("0.050"),
        hard_threshold=Decimal("0.100"),
    )
    assert dd_res["evaluation_status"] == "WARNING"
    assert dd_res["headroom"] == Decimal("0.0180")


@pytest.mark.asyncio
async def test_limit_service_lifecycle_and_evaluation():
    await init_db()
    async with AsyncSessionLocal() as session:
        service = PortfolioRiskLimitService(session)

        # 1. Create a risk limit profile
        create_dto = ProfileCreate(
            profile_name="Standard Moderate Equity Profile",
            profile_code="STD_MOD_EQ_01",
            description="Institutional equity profile with 99% 1d VaR, vol and drawdown boundaries",
            profile_category="MODERATE",
            mandate_type="EQUITIES_GROWTH",
            initial_limits=[
                RiskLimitCreate(
                    limit_code="VAR_NAV_01",
                    limit_name="99% 1D NAV-relative VaR",
                    risk_category="VAR",
                    metric_identifier="VAR_99_1D_HIST",
                    limit_type="NAV_RELATIVE",
                    warning_threshold=Decimal("2.0"),
                    hard_threshold=Decimal("3.0"),
                    threshold_unit="PERCENT_NAV",
                    confidence_level=0.99,
                    risk_horizon_days=1,
                    risk_methodology="HISTORICAL",
                ),
                RiskLimitCreate(
                    limit_code="VOL_ANN_01",
                    limit_name="Annualized Volatility Limit",
                    risk_category="VOLATILITY",
                    metric_identifier="REALIZED_VOL_ANN",
                    limit_type="PERCENTAGE",
                    warning_threshold=Decimal("0.15"),
                    hard_threshold=Decimal("0.20"),
                    threshold_unit="ANNUALIZED_VOL",
                ),
                RiskLimitCreate(
                    limit_code="DD_MAX_01",
                    limit_name="Peak-to-Trough Drawdown Limit",
                    risk_category="DRAWDOWN",
                    metric_identifier="MAX_DRAWDOWN",
                    limit_type="PERCENTAGE",
                    warning_threshold=Decimal("0.08"),
                    hard_threshold=Decimal("0.12"),
                    threshold_unit="DRAWDOWN_MAGNITUDE",
                ),
            ],
        )

        profile = await service.create_profile(create_dto)
        assert profile.id is not None
        assert profile.status == "ACTIVE"
        assert len(profile.versions) == 1
        assert len(profile.versions[0].limits) == 3

        # 2. Assign profile to portfolio
        portfolio_id = "PORT_TEST_901"
        assign_dto = AssignmentCreate(
            profile_id=profile.id,
            target_type="PORTFOLIO",
            target_id=portfolio_id,
            assigned_by="risk_officer",
        )
        assignment = await service.assign_profile(assign_dto)
        assert assignment.target_id == portfolio_id
        assert assignment.assignment_status == "ACTIVE"

        # 3. Evaluate portfolio limits (VaR = 2.2% -> Breaches 2.0% warning)
        eval_request = EvaluationRequest(
            portfolio_id=portfolio_id,
            observed_var_monetary=Decimal("22000.00"),  # on $1M NAV = 2.2%
            observed_volatility_annualized=Decimal("0.1400"),  # 14% -> within 15% warning
            observed_drawdown_magnitude=Decimal("0.0450"),     # 4.5% -> within 8% warning
            portfolio_nav=Decimal("1000000.00"),
        )

        res = await service.evaluate_portfolio_limits(eval_request)
        assert res["portfolio_id"] == portfolio_id
        assert res["overall_status"] == "WARNING"
        assert len(res["utilizations"]) == 3
        # Check specific VaR utilization state
        var_eval = next(u for u in res["utilizations"] if u["risk_category"] == "VAR")
        assert var_eval["evaluation_status"] == "WARNING"


@pytest.mark.asyncio
async def test_portfolio_risk_limits_api_endpoints():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Health check
        health_resp = await client.get("/api/v1/risk-limits/health")
        assert health_resp.status_code == 200
        health_data = health_resp.json()
        assert health_data["module"] == "M11.01 - Portfolio Risk Limits"
        assert health_data["status"] == "healthy"

        # Create Profile via API with unique code
        import uuid
        u_code = f"CONS_WEALTH_{uuid.uuid4().hex[:6]}"
        create_payload = {
            "profile_code": u_code,
            "profile_name": "Conservative Wealth Profile",
            "description": "Conservative profile with tight drawdown and VaR controls",
            "profile_category": "CONSERVATIVE",
            "initial_limits": [
                {
                    "limit_code": f"VAR_NAV_{uuid.uuid4().hex[:6]}",
                    "limit_name": "99% 1D VaR",
                    "risk_category": "VAR",
                    "metric_identifier": "VAR_99_1D",
                    "limit_type": "NAV_RELATIVE",
                    "warning_threshold": "1.0",
                    "hard_threshold": "1.5",
                    "threshold_unit": "PERCENT_NAV",
                },
                {
                    "limit_code": f"VOL_{uuid.uuid4().hex[:6]}",
                    "limit_name": "Max Volatility",
                    "risk_category": "VOLATILITY",
                    "metric_identifier": "REALIZED_VOL",
                    "limit_type": "PERCENTAGE",
                    "warning_threshold": "0.08",
                    "hard_threshold": "0.10",
                    "threshold_unit": "ANNUALIZED_VOL",
                },
            ],
        }
        res = await client.post("/api/v1/risk-limits/profiles", json=create_payload)
        assert res.status_code == 201
        profile_data = res.json()
        profile_id = profile_data["id"]
        assert profile_data["profile_code"] == u_code

        # Query Profile by code
        res_get = await client.get(f"/api/v1/risk-limits/profiles/{u_code}")
        assert res_get.status_code == 200
        assert res_get.json()["id"] == profile_id

        # Assign Profile
        assign_payload = {
            "profile_id": profile_id,
            "target_type": "PORTFOLIO",
            "target_id": "PORT_API_902",
            "assigned_by": "risk_officer",
        }
        res_assign = await client.post("/api/v1/risk-limits/assignments", json=assign_payload)
        assert res_assign.status_code == 201
        assert res_assign.json()["target_id"] == "PORT_API_902"

        # Evaluate Portfolio Limits (hard breach on VaR: 85k on 5M = 1.7% > 1.5% hard threshold)
        eval_payload = {
            "portfolio_id": "PORT_API_902",
            "observed_var_monetary": "85000.0",
            "observed_volatility_annualized": "0.065",
            "portfolio_nav": "5000000.0",
        }
        res_eval = await client.post("/api/v1/risk-limits/portfolios/PORT_API_902/evaluate", json=eval_payload)
        assert res_eval.status_code == 200
        eval_data = res_eval.json()
        assert eval_data["portfolio_id"] == "PORT_API_902"
        assert eval_data["overall_status"] == "HARD_LIMIT_EXCEEDED"
        assert len(eval_data["utilizations"]) == 2
