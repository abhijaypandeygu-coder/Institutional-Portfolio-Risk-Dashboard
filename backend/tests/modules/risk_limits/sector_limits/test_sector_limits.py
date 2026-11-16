"""
Comprehensive unit and integration tests for M11.03 — Sector Limits.

Tests covered:
1. Sector cap calculation within limit (NAV ₹10 Cr, Gross ₹2 Cr, Limit 25% -> 80% util, WARNING / WITHIN_LIMIT).
2. Sector cap breach (NAV ₹10 Cr, Gross ₹3 Cr, Limit 25% -> 120% util, 5% breach, HARD_LIMIT_EXCEEDED).
3. Industry cap calculation (NAV ₹10 Cr, Gross ₹1.5 Cr, Limit 12% -> 125% util, 3% breach).
4. Gross vs. Net sector exposure calculations (Long ₹2 Cr, Short ₹1 Cr -> Gross ₹3 Cr, Net ₹1 Cr).
5. Benchmark-relative overweight limit (PW 30%, BW 22%, Limit +5% -> Active +8%, 3% breach).
6. Benchmark-relative underweight limit (PW 10%, BW 20%, Lower Limit -5% -> Active -10%, 5% breach).
7. Industry hierarchy consistency (Technology 30% on 35% cap [OK], Software 14% on 12% cap [BREACH]).
8. Unclassified exposure and coverage tracking (₹9 Cr classified, ₹1 Cr unmapped -> 90% coverage).
9. Service and Repository lifecycle (Configurations, Profiles, Assignments, Portfolio evaluation).
10. FastAPI REST API endpoints:
    - GET /api/v1/risk-limits/sector-limits/health
    - POST /api/v1/risk-limits/sector-limits
    - GET /api/v1/risk-limits/sector-limits
    - POST /api/v1/risk-limits/sector-limit-profiles
    - GET /api/v1/risk-limits/sector-limit-profiles
    - POST /api/v1/risk-limits/sector-limit-assignments
    - POST /api/v1/risk-limits/sector-limits/evaluate
    - GET /api/v1/risk-limits/sector-limits/breaches
"""

import uuid
from decimal import Decimal
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.core.database import init_db, AsyncSessionLocal
from backend.app.main import app
from backend.app.modules.risk_limits.sector_limits.calculations.sector_limit_math import (
    calculate_sector_utilization,
    evaluate_active_weight_limit,
    aggregate_sector_and_industry_exposures,
)
from backend.app.modules.risk_limits.sector_limits.schemas.sector_limit_schemas import (
    SectorLimitConfigCreate,
    SectorProfileCreate,
    SectorAssignmentCreate,
    SectorPositionInput,
    SectorEvaluationRequest,
)
from backend.app.modules.risk_limits.sector_limits.services.sector_limit_service import (
    SectorLimitService,
)


def test_sector_cap_within_limit_math():
    """
    Test 1: Sector cap within limit.
    NAV: ₹10 Cr (100,000,000), Sector Gross MV: ₹2 Cr (20,000,000).
    Sector Weight: 20%. Warning Limit: 20%, Hard Limit: 25%.
    Utilization against Hard Limit: 20 / 25 * 100 = 80.00%.
    Status: WARNING (since weight >= warning 20%).
    Remaining capacity to hard limit: 5%.
    """
    nav = Decimal("100000000.00")
    gross_mv = Decimal("20000000.00")
    current_weight = (gross_mv / nav) * Decimal("100.0")  # 20%
    warning_limit = Decimal("20.0000")
    hard_limit = Decimal("25.0000")

    res = calculate_sector_utilization(
        actual_exposure=current_weight,
        warning_threshold=warning_limit,
        hard_threshold=hard_limit,
    )

    assert res["evaluation_status"] == "WARNING"
    assert res["hard_utilization_pct"] == Decimal("80.00")
    assert res["breach_amount"] == Decimal("0.0000")
    assert res["remaining_capacity"] == Decimal("5.0000")


def test_sector_cap_breach_math():
    """
    Test 2: Sector cap breach.
    NAV: ₹10 Cr, Gross MV: ₹3 Cr.
    Sector Weight: 30%. Hard Limit: 25%. Warning Limit: 20%.
    Utilization: 30 / 25 * 100 = 120.00%.
    Breach: 5%.
    Status: HARD_LIMIT_EXCEEDED.
    """
    nav = Decimal("100000000.00")
    gross_mv = Decimal("30000000.00")
    current_weight = (gross_mv / nav) * Decimal("100.0")  # 30%
    warning_limit = Decimal("20.0000")
    hard_limit = Decimal("25.0000")

    res = calculate_sector_utilization(
        actual_exposure=current_weight,
        warning_threshold=warning_limit,
        hard_threshold=hard_limit,
    )

    assert res["evaluation_status"] == "HARD_LIMIT_EXCEEDED"
    assert res["hard_utilization_pct"] == Decimal("120.00")
    assert res["breach_amount"] == Decimal("5.0000")
    assert res["remaining_capacity"] == Decimal("-5.0000")


def test_industry_cap_math():
    """
    Test 3: Industry cap.
    NAV: ₹10 Cr, Industry Gross MV: ₹1.5 Cr (15%).
    Industry Cap (Hard): 12%. Warning: 10%.
    Utilization: 15 / 12 * 100 = 125.00%. Breach: 3%.
    """
    current_weight = Decimal("15.0000")
    warning_limit = Decimal("10.0000")
    hard_limit = Decimal("12.0000")

    res = calculate_sector_utilization(
        actual_exposure=current_weight,
        warning_threshold=warning_limit,
        hard_threshold=hard_limit,
    )

    assert res["evaluation_status"] == "HARD_LIMIT_EXCEEDED"
    assert res["hard_utilization_pct"] == Decimal("125.00")
    assert res["breach_amount"] == Decimal("3.0000")


def test_gross_vs_net_sector_exposure_math():
    """
    Test 4: Gross vs Net sector exposure.
    Long ₹2 Cr, Short ₹1 Cr.
    Gross = |2| + |-1| = ₹3 Cr. Net = 2 - 1 = ₹1 Cr.
    """
    positions = [
        {"security_id": "SEC_1", "sector_id": "FINANCIALS", "industry_id": "BANKS", "market_value": Decimal("20000000.00")},
        {"security_id": "SEC_2", "sector_id": "FINANCIALS", "industry_id": "BANKS", "market_value": Decimal("-10000000.00")},
    ]
    nav = Decimal("100000000.00")

    res = aggregate_sector_and_industry_exposures(positions, nav)
    sec_data = next(s for s in res["sectors"] if s["sector_id"] == "FINANCIALS")

    assert sec_data["gross_exposure"] == Decimal("30000000.00")
    assert sec_data["net_exposure"] == Decimal("10000000.00")
    assert sec_data["long_exposure"] == Decimal("20000000.00")
    assert sec_data["short_exposure"] == Decimal("10000000.00")
    assert sec_data["gross_weight_pct"] == Decimal("30.0000")
    assert sec_data["net_weight_pct"] == Decimal("10.0000")


def test_benchmark_relative_limits_math():
    """
    Test 5 & 6: Benchmark relative active limits (overweight & underweight).
    """
    # Test 5: Overweight breach
    # Portfolio Weight: 30%, Benchmark Weight: 22%, Active: +8%.
    # Max Overweight: +5%. Breach: 3%.
    res_over = evaluate_active_weight_limit(
        portfolio_weight_pct=Decimal("30.0000"),
        benchmark_weight_pct=Decimal("22.0000"),
        upper_overweight_limit_pct=Decimal("5.0000"),
        lower_underweight_limit_pct=Decimal("-5.0000"),
    )
    assert res_over["active_weight_pct"] == Decimal("8.0000")
    assert res_over["evaluation_status"] == "HARD_LIMIT_EXCEEDED"
    assert res_over["breach_amount"] == Decimal("3.0000")
    assert res_over["breach_type"] == "OVERWEIGHT"

    # Test 6: Underweight breach
    # Portfolio Weight: 10%, Benchmark Weight: 20%, Active: -10%.
    # Max Underweight: -5%. Breach: 5%.
    res_under = evaluate_active_weight_limit(
        portfolio_weight_pct=Decimal("10.0000"),
        benchmark_weight_pct=Decimal("20.0000"),
        upper_overweight_limit_pct=Decimal("5.0000"),
        lower_underweight_limit_pct=Decimal("-5.0000"),
    )
    assert res_under["active_weight_pct"] == Decimal("-10.0000")
    assert res_under["evaluation_status"] == "HARD_LIMIT_EXCEEDED"
    assert res_under["breach_amount"] == Decimal("5.0000")
    assert res_under["breach_type"] == "UNDERWEIGHT"


def test_unclassified_exposure_and_coverage_tracking():
    """
    Test 8: Unclassified exposure and coverage tracking.
    Total Gross: ₹10 Cr.
    Classified: ₹9 Cr (Tech ₹5 Cr, Health ₹4 Cr).
    Unclassified: ₹1 Cr.
    Coverage: 90.00%.
    """
    positions = [
        {"security_id": "SEC_1", "sector_id": "TECHNOLOGY", "industry_id": "SOFTWARE", "market_value": Decimal("50000000.00")},
        {"security_id": "SEC_2", "sector_id": "HEALTHCARE", "industry_id": "PHARMA", "market_value": Decimal("40000000.00")},
        {"security_id": "SEC_UNMAPPED", "sector_id": None, "industry_id": None, "market_value": Decimal("10000000.00")},
    ]
    nav = Decimal("100000000.00")

    res = aggregate_sector_and_industry_exposures(positions, nav)

    assert res["total_gross_exposure"] == Decimal("100000000.00")
    assert res["classified_gross_exposure"] == Decimal("90000000.00")
    assert res["unclassified_gross_exposure"] == Decimal("10000000.00")
    assert res["classification_coverage_pct"] == Decimal("90.00")
    assert len(res["unmapped_positions"]) == 1
    assert res["unmapped_positions"][0]["security_id"] == "SEC_UNMAPPED"


@pytest.mark.asyncio
async def test_sector_limits_service_lifecycle():
    """
    Test 9: Service and repository full lifecycle.
    1. Create profile.
    2. Add sector limit configuration (Tech max 35%, Software max 12%).
    3. Assign profile to portfolio.
    4. Evaluate portfolio with Tech 30% (OK) and Software 14% (Breach).
    5. Verify evaluation results and breach events recorded.
    """
    await init_db()

    async with AsyncSessionLocal() as session:
        service = SectorLimitService(session)

        # 1. Create Profile with Initial Configurations
        p_code = f"PROF_{uuid.uuid4().hex[:8]}"
        cfg_sector_in = SectorLimitConfigCreate(
            limit_code=f"CFG_SEC_{uuid.uuid4().hex[:6]}",
            limit_name="Tech Sector Max Weight",
            sector_id="Information Technology",
            sector_name="Information Technology",
            limit_type="MAX_SECTOR_WEIGHT",
            threshold_value=Decimal("35.0000"),
            warning_threshold=Decimal("30.0000"),
            threshold_unit="PERCENT_NAV",
        )
        cfg_industry_in = SectorLimitConfigCreate(
            limit_code=f"CFG_IND_{uuid.uuid4().hex[:6]}",
            limit_name="Software Industry Max Weight",
            industry_id="Software & Services",
            industry_name="Software & Services",
            limit_type="MAX_INDUSTRY_WEIGHT",
            threshold_value=Decimal("12.0000"),
            warning_threshold=Decimal("10.0000"),
            threshold_unit="PERCENT_NAV",
        )

        profile = await service.create_profile(
            SectorProfileCreate(
                profile_name=f"Tech Fund Profile {p_code}",
                profile_code=p_code,
                classification_system="GICS",
                description="Profile for sector limit tests",
                initial_limits=[cfg_sector_in, cfg_industry_in],
            )
        )
        assert profile.id is not None

        # 3. Assign Profile to Portfolio
        portfolio_id = f"PORT_{uuid.uuid4().hex[:8]}"
        assignment = await service.assign_profile(
            SectorAssignmentCreate(
                profile_id=profile.id,
                target_type="PORTFOLIO",
                target_id=portfolio_id,
            )
        )
        assert assignment.id is not None

        # 4. Evaluate Portfolio: NAV ₹10 Cr
        # Position 1: Hardware ₹1.6 Cr (16%) -> IT Sector total = 30% (<= 35% Hard, OK)
        # Position 2: Software ₹1.4 Cr (14%) -> Software Industry = 14% (> 12% Hard, BREACH)
        eval_req = SectorEvaluationRequest(
            portfolio_id=portfolio_id,
            portfolio_nav=Decimal("100000000.00"),
            benchmark_id="NIFTY50",
            positions=[
                SectorPositionInput(
                    instrument_id="TECH_HW",
                    quantity=Decimal("1000"),
                    market_value=Decimal("16000000.00"),
                    sector_id="Information Technology",
                    sector_name="Information Technology",
                    industry_id="Technology Hardware",
                    industry_name="Technology Hardware",
                ),
                SectorPositionInput(
                    instrument_id="TECH_SW",
                    quantity=Decimal("1000"),
                    market_value=Decimal("14000000.00"),
                    sector_id="Information Technology",
                    sector_name="Information Technology",
                    industry_id="Software & Services",
                    industry_name="Software & Services",
                ),
            ],
            benchmark_weights={
                "Information Technology": Decimal("25.0000"),
                "Software & Services": Decimal("10.0000"),
            },
        )

        eval_resp = await service.evaluate_portfolio_sectors(eval_req)
        assert eval_resp.portfolio_id == portfolio_id
        assert eval_resp.overall_status in ["BREACH", "HARD_LIMIT_EXCEEDED"]
        assert eval_resp.hard_breaches_count >= 1
        assert eval_resp.classification_coverage_pct == Decimal("100.00")

        # Verify results breakdown
        industry_res = next(r for r in eval_resp.results if r.industry_id == "Software & Services")
        assert industry_res.evaluation_status == "HARD_LIMIT_EXCEEDED"
        assert industry_res.breach_amount == Decimal("2.0000")

        sector_res = next(r for r in eval_resp.results if r.sector_id == "Information Technology")
        assert sector_res.evaluation_status == "WARNING"  # 30% reaches warning limit


@pytest.mark.asyncio
async def test_sector_limits_api_endpoints():
    """
    Test 10: Full FastAPI REST API verification.
    """
    await init_db()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Health check
        res_health = await client.get("/api/v1/risk-limits/sector-limits/health")
        assert res_health.status_code == 200
        assert res_health.json()["status"] == "healthy"
        assert res_health.json()["module"] == "M11.03 - Sector Limits"

        # Create Profile
        prof_code = f"API_PROF_{uuid.uuid4().hex[:6]}"
        res_prof = await client.post(
            "/api/v1/risk-limits/sector-limit-profiles",
            json={
                "profile_name": f"API Profile {prof_code}",
                "profile_code": prof_code,
                "classification_system": "GICS",
                "description": "REST API Test Profile",
            },
        )
        assert res_prof.status_code == 201
        prof_data = res_prof.json()
        prof_id = prof_data["id"]

        # Create Sector Limit Configuration
        res_cfg = await client.post(
            "/api/v1/risk-limits/sector-limits",
            json={
                "limit_code": f"API_CFG_{uuid.uuid4().hex[:6]}",
                "limit_name": "Financials Sector Cap",
                "sector_id": "Financials",
                "sector_name": "Financials",
                "limit_type": "MAX_SECTOR_WEIGHT",
                "direction": "GROSS",
                "threshold_value": 25.0,
                "warning_threshold": 20.0,
                "threshold_unit": "PERCENT_NAV",
            },
        )
        assert res_cfg.status_code == 201
        assert res_cfg.json()["sector_id"] == "Financials"

        # List Configurations
        res_cfg_list = await client.get("/api/v1/risk-limits/sector-limits")
        assert res_cfg_list.status_code == 200
        assert len(res_cfg_list.json()) >= 1

        # Assign Profile
        port_id = f"API_PORT_{uuid.uuid4().hex[:6]}"
        res_assign = await client.post(
            "/api/v1/risk-limits/sector-limit-assignments",
            json={
                "profile_id": prof_id,
                "target_type": "PORTFOLIO",
                "target_id": port_id,
            },
        )
        assert res_assign.status_code == 201
        assert res_assign.json()["target_id"] == port_id

        # Evaluate Portfolio
        res_eval = await client.post(
            "/api/v1/risk-limits/sector-limits/evaluate",
            json={
                "portfolio_id": port_id,
                "portfolio_nav": 10000000.0,
                "benchmark_id": "SPX",
                "positions": [
                    {
                        "instrument_id": "JPM",
                        "quantity": 1000.0,
                        "market_value": 2800000.0,  # 28% -> Exceeds 25% Hard Cap
                        "sector_id": "Financials",
                        "industry_id": "Banks",
                    }
                ],
                "benchmark_weights": {
                    "Financials": 20.0,
                },
            },
        )
        assert res_eval.status_code == 200
        eval_out = res_eval.json()
        assert eval_out["overall_status"] in ["BREACH", "HARD_LIMIT_EXCEEDED"]
        assert eval_out["hard_breaches_count"] >= 1

        # Query Breaches
        res_breaches = await client.get(f"/api/v1/risk-limits/sector-limits/breaches?portfolio_id={port_id}")
        assert res_breaches.status_code == 200
        breaches = res_breaches.json()
        assert len(breaches) >= 1
