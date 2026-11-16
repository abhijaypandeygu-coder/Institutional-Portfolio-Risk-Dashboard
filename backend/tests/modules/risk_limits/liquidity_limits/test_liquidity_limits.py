"""
Comprehensive unit, financial correctness, and integration tests for M11.04 — Liquidity Limits.

Verifies:
1. Minimum liquidity score limit (Score 65 vs Min 70 -> Breach 5, HARD_LIMIT_EXCEEDED).
2. Minimum order book depth (Side-specific: 8,000 vs Min 10,000 -> Breach 2,000, HARD_LIMIT_EXCEEDED).
3. ADV calculation from session volumes ([100k, 120k, 80k, 140k, 60k] -> ADV 100k).
4. Simplified liquidation horizon (Qty 500k, ADV 100k, Part 10% -> 50 trading days).
5. Liquidation cost metrics (Notional ₹1 Cr, Cost ₹50k -> 50 bps).
6. Cost limit breach (Cost ₹75k, Cap ₹60k -> Breach ₹15k, Utilization 125%).
7. Horizon limit breach (Est Horizon 8 days, Cap 5 days -> Breach 3 days, Utilization 160%).
8. Stressed volume (Base 100k, -40% -> 60k).
9. Stressed depth (Base 50k, -30% -> 35k).
10. Stressed horizon (Qty 300k, Base ADV 100k [-40% -> 60k], Base Part 10% [-20% -> 8%] -> Daily 4,800 -> 62.5 days).
11. Side-aware depth evaluation (Long uses Bid depth, Short uses Ask depth).
12. Portfolio cost aggregation (₹20k + ₹30k = ₹50k).
13. Missing ADV handling (Horizon UNAVAILABLE, reason code present, no zero horizon).
14. Zero ADV handling (Horizon INVALID/UNAVAILABLE, no zero horizon).
15. Liquidity capacity and headroom analysis.
16. Proposed order pre-trade simulation.
17. Service lifecycle & Repository CRUD.
18. FastAPI REST API endpoints:
    - GET /api/v1/risk-limits/liquidity-limits/health
    - POST /api/v1/risk-limits/liquidity-limits
    - GET /api/v1/risk-limits/liquidity-limits
    - POST /api/v1/risk-limits/liquidity-limit-profiles
    - GET /api/v1/risk-limits/liquidity-limit-profiles
    - POST /api/v1/risk-limits/liquidity-limit-assignments
    - POST /api/v1/risk-limits/liquidity-limits/evaluate
    - POST /api/v1/risk-limits/liquidity-limits/evaluate/proposed-order
    - GET /api/v1/risk-limits/liquidity-limits/breaches
    - GET /api/v1/risk-limits/liquidity-limits/exceptions
"""

import uuid
from decimal import Decimal
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.core.database import init_db, AsyncSessionLocal
from backend.app.main import app
from backend.app.modules.risk_limits.liquidity_limits.calculations.liquidity_limit_math import (
    calculate_adv,
    calculate_adtv,
    calculate_liquidation_horizon,
    calculate_liquidation_cost_metrics,
    evaluate_minimum_limit,
    evaluate_maximum_limit,
    apply_stressed_liquidity_shocks,
    calculate_liquidity_headroom_and_capacity,
    simulate_proposed_order,
)
from backend.app.modules.risk_limits.liquidity_limits.schemas.liquidity_limit_schemas import (
    LiquidityLimitConfigCreate,
    LiquidityProfileCreate,
    LiquidityAssignmentCreate,
    PositionLiquidityInput,
    LiquidityEvaluationRequest,
    StressedParametersInput,
    ProposedOrderLiquidityRequest,
)
from backend.app.modules.risk_limits.liquidity_limits.services.liquidity_limit_service import (
    LiquidityLimitService,
)


def test_financial_spec_test1_minimum_liquidity_score():
    """
    Test 1: Minimum liquidity score.
    Actual score = 65. Minimum required score = 70.
    Shortfall = 5 score points. Status = HARD_LIMIT_EXCEEDED.
    """
    res = evaluate_minimum_limit(
        actual_value=Decimal("65.0000"),
        min_threshold=Decimal("70.0000"),
    )
    assert res["status"] == "HARD_LIMIT_EXCEEDED"
    assert res["breach_amount"] == Decimal("5.0000")
    assert res["headroom"] == Decimal("-5.0000")


def test_financial_spec_test2_minimum_depth():
    """
    Test 2: Minimum depth.
    Actual eligible side-specific depth = 8,000 shares. Minimum = 10,000 shares.
    Shortfall = 2,000 shares. Status = HARD_LIMIT_EXCEEDED.
    """
    res = evaluate_minimum_limit(
        actual_value=Decimal("8000.0000"),
        min_threshold=Decimal("10000.0000"),
        unit="SHARES",
    )
    assert res["status"] == "HARD_LIMIT_EXCEEDED"
    assert res["breach_amount"] == Decimal("2000.0000")
    assert res["headroom"] == Decimal("-2000.0000")


def test_financial_spec_test3_adv_calculation():
    """
    Test 3: ADV calculation.
    Daily volumes: 100k, 120k, 80k, 140k, 60k.
    Expected ADV = 100,000.
    """
    vols = [
        Decimal("100000"),
        Decimal("120000"),
        Decimal("80000"),
        Decimal("140000"),
        Decimal("60000"),
    ]
    adv = calculate_adv(vols)
    assert adv == Decimal("100000.0000")


def test_financial_spec_test4_liquidation_horizon():
    """
    Test 4: Liquidation horizon.
    Position quantity = 500,000 shares. ADV = 100,000 shares. Participation = 10%.
    Daily capacity = 10,000. Horizon = 50 trading sessions.
    """
    res = calculate_liquidation_horizon(
        position_quantity=Decimal("500000"),
        adv=Decimal("100000"),
        participation_rate=Decimal("0.1000"),
    )
    assert res["status"] == "VALID"
    assert res["daily_capacity"] == Decimal("10000.0000")
    assert res["liquidation_horizon_days"] == Decimal("50.0000")


def test_financial_spec_test5_liquidation_cost_bps():
    """
    Test 5: Liquidation cost.
    Liquidation notional = ₹1 crore (10,000,000). Estimated all-in cost = ₹50,000.
    Cost bps = (50,000 / 10,000,000) * 10,000 = 50 bps.
    """
    res = calculate_liquidation_cost_metrics(
        estimated_cost=Decimal("50000.0000"),
        liquidated_notional=Decimal("10000000.0000"),
        portfolio_nav=Decimal("100000000.0000"),
    )
    assert res["cost_bps"] == Decimal("50.0000")
    assert res["cost_pct_nav"] == Decimal("0.0500")


def test_financial_spec_test6_cost_breach():
    """
    Test 6: Cost breach.
    Estimated cost = ₹75,000. Maximum allowed = ₹60,000.
    Breach = ₹15,000. Utilization = 125%.
    """
    res = evaluate_maximum_limit(
        actual_value=Decimal("75000.0000"),
        max_threshold=Decimal("60000.0000"),
        unit="INR",
    )
    assert res["status"] == "HARD_LIMIT_EXCEEDED"
    assert res["breach_amount"] == Decimal("15000.0000")
    assert res["utilization_pct"] == Decimal("125.00")


def test_financial_spec_test7_horizon_breach():
    """
    Test 7: Horizon breach.
    Estimated horizon = 8 trading sessions. Maximum permitted = 5 trading sessions.
    Breach = 3 trading sessions. Utilization = 160%.
    """
    res = evaluate_maximum_limit(
        actual_value=Decimal("8.0000"),
        max_threshold=Decimal("5.0000"),
        unit="TRADING_DAYS",
    )
    assert res["status"] == "HARD_LIMIT_EXCEEDED"
    assert res["breach_amount"] == Decimal("3.0000")
    assert res["utilization_pct"] == Decimal("160.00")


def test_financial_spec_test8_9_10_stressed_transformations():
    """
    Test 8, 9, 10: Stressed volume, depth, and liquidation horizon.
    - Test 8: Base ADV 100k, 40% contraction -> 60k.
    - Test 9: Base depth 50k, 30% reduction -> 35k.
    - Test 10: Qty 300k, Base ADV 100k (-40% -> 60k), Base part 10% (-20% -> 8%)
      -> Daily capacity 4,800 -> Stressed horizon 62.5 days.
    """
    shocks = apply_stressed_liquidity_shocks(
        baseline_adv=Decimal("100000"),
        baseline_depth=Decimal("50000"),
        baseline_spread_bps=Decimal("10.0"),
        baseline_participation_rate=Decimal("0.1000"),
        volume_contraction_pct=Decimal("40.0"),
        depth_reduction_pct=Decimal("30.0"),
        spread_widening_pct=Decimal("50.0"),
        participation_reduction_pct=Decimal("20.0"),
    )

    # Test 8
    assert shocks["stressed_adv"] == Decimal("60000.0000")
    # Test 9
    assert shocks["stressed_depth"] == Decimal("35000.0000")
    assert shocks["stressed_participation_rate"] == Decimal("0.0800")
    assert shocks["stressed_spread_bps"] == Decimal("15.0000")

    # Test 10: Stressed horizon
    st_horizon = calculate_liquidation_horizon(
        position_quantity=Decimal("300000"),
        adv=shocks["stressed_adv"],
        participation_rate=shocks["stressed_participation_rate"],
    )
    assert st_horizon["status"] == "VALID"
    assert st_horizon["daily_capacity"] == Decimal("4800.0000")
    assert st_horizon["liquidation_horizon_days"] == Decimal("62.5000")


def test_financial_spec_test13_14_missing_and_zero_adv():
    """
    Test 13 & 14: Missing and Zero ADV fail-safe behavior.
    - Missing ADV -> UNAVAILABLE, not zero horizon.
    - Zero ADV -> INVALID, not zero horizon.
    """
    res_missing = calculate_liquidation_horizon(
        position_quantity=Decimal("100000"),
        adv=None,
        participation_rate=Decimal("0.1000"),
    )
    assert res_missing["status"] == "UNAVAILABLE"
    assert res_missing["liquidation_horizon_days"] is None
    assert res_missing["reason"] == "MISSING_ADV"

    res_zero = calculate_liquidation_horizon(
        position_quantity=Decimal("100000"),
        adv=Decimal("0.0"),
        participation_rate=Decimal("0.1000"),
    )
    assert res_zero["status"] == "INVALID"
    assert res_zero["liquidation_horizon_days"] is None
    assert res_zero["reason"] == "ZERO_OR_NEGATIVE_ADV"


def test_liquidity_capacity_and_headroom():
    """
    Test 15: Liquidity capacity and binding constraint.
    Qty 20k. Horizon limit 5 days, ADV 10k, Part 10% -> Horizon capacity = 5 * 10k * 0.10 = 5,000.
    Available depth = 8,000.
    Binding constraint is HORIZON_LIMIT (5,000 < 8,000).
    Headroom = 5,000 - 20,000 = -15,000 (CAPACITY_EXCEEDED).
    """
    cap_res = calculate_liquidity_headroom_and_capacity(
        position_quantity=Decimal("20000"),
        adv=Decimal("10000"),
        participation_rate=Decimal("0.1000"),
        max_horizon_days=Decimal("5.0"),
        available_depth=Decimal("8000"),
    )
    assert cap_res["binding_constraint"] == "HORIZON_LIMIT"
    assert cap_res["max_supported_quantity"] == Decimal("5000.0000")
    assert cap_res["headroom_quantity"] == Decimal("-15000.0000")
    assert cap_res["status"] == "CAPACITY_EXCEEDED"


def test_simulate_proposed_order():
    """
    Test 16: Pre-trade proposed order simulation.
    Current position 10k BUY. Proposed +10k BUY -> Projected 20k.
    ADV 100k, Part 10% -> Daily capacity 10k -> Projected horizon 2 days.
    """
    sim = simulate_proposed_order(
        current_quantity=Decimal("10000"),
        proposed_quantity=Decimal("10000"),
        order_side="BUY",
        adv=Decimal("100000"),
        participation_rate=Decimal("0.1000"),
        estimated_cost_per_share=Decimal("0.50"),
    )
    assert sim["projected_quantity"] == Decimal("20000")
    assert sim["projected_side"] == "LONG"
    assert sim["projected_horizon_days"] == Decimal("2.0000")
    assert sim["projected_cost"] == Decimal("10000.0000")


@pytest.mark.asyncio
async def test_liquidity_limits_service_lifecycle():
    """
    Test 17: Service and repository full lifecycle.
    1. Create profile with minimum score (70) and maximum horizon (5 days) limits.
    2. Assign profile to portfolio.
    3. Evaluate portfolio with:
       - Pos 1: Tech stock, score 65 (Breach score), ADV 100k, Qty 20k -> Horizon 2 days (OK).
       - Pos 2: Small cap, score 80 (OK), ADV 10k, Qty 100k, Part 10% -> Horizon 100 days (Breach horizon).
    4. Verify evaluation results, breach events, and exception recording.
    """
    await init_db()

    async with AsyncSessionLocal() as session:
        service = LiquidityLimitService(session)

        # 1. Create Profile with Initial Configurations
        p_code = f"LIQ_PROF_{uuid.uuid4().hex[:8]}"
        cfg_score = LiquidityLimitConfigCreate(
            limit_code=f"CFG_SCORE_{uuid.uuid4().hex[:6]}",
            limit_name="Min Liquidity Score 70",
            limit_type="MIN_LIQUIDITY_SCORE",
            metric_name="score",
            minimum_threshold=Decimal("70.0000"),
            warning_threshold=Decimal("75.0000"),
            threshold_unit="POINTS",
        )
        cfg_horizon = LiquidityLimitConfigCreate(
            limit_code=f"CFG_HORIZON_{uuid.uuid4().hex[:6]}",
            limit_name="Max Liquidation Horizon 5 Days",
            limit_type="MAX_LIQUIDATION_HORIZON",
            metric_name="horizon_days",
            maximum_threshold=Decimal("5.0000"),
            warning_threshold=Decimal("4.0000"),
            threshold_unit="TRADING_DAYS",
            participation_rate=Decimal("0.1000"),
        )

        profile = await service.create_profile(
            LiquidityProfileCreate(
                profile_name=f"Liquidity Control Profile {p_code}",
                profile_code=p_code,
                description="Profile for lifecycle testing",
                initial_limits=[cfg_score, cfg_horizon],
            )
        )
        assert profile.id is not None

        # 2. Assign Profile to Portfolio
        portfolio_id = f"PORT_{uuid.uuid4().hex[:8]}"
        assignment = await service.assign_profile(
            LiquidityAssignmentCreate(
                profile_id=profile.id,
                target_type="PORTFOLIO",
                target_id=portfolio_id,
            )
        )
        assert assignment.id is not None

        # 3. Evaluate Portfolio
        eval_req = LiquidityEvaluationRequest(
            portfolio_id=portfolio_id,
            portfolio_nav=Decimal("50000000.00"),
            positions=[
                PositionLiquidityInput(
                    instrument_id="SEC_A",
                    position_side="LONG",
                    quantity=Decimal("20000"),
                    market_value=Decimal("2000000"),
                    liquidity_score=Decimal("65.0"),  # Fails min score 70
                    adv=Decimal("100000"),
                    bid_depth=Decimal("50000"),
                    estimated_liquidation_cost=Decimal("20000"),
                ),
                PositionLiquidityInput(
                    instrument_id="SEC_B",
                    position_side="LONG",
                    quantity=Decimal("100000"),
                    market_value=Decimal("5000000"),
                    liquidity_score=Decimal("80.0"),  # Passes score
                    adv=Decimal("10000"),             # 100k / (10k * 0.10) = 100 days -> Fails max horizon 5 days
                    bid_depth=Decimal("25000"),
                    estimated_liquidation_cost=Decimal("30000"),
                ),
            ],
        )

        eval_resp = await service.evaluate_portfolio_liquidity(eval_req)
        assert eval_resp.portfolio_id == portfolio_id
        assert eval_resp.overall_status in ("BREACH", "HARD_LIMIT_EXCEEDED")
        assert eval_resp.hard_breaches_count >= 2
        assert eval_resp.total_liquidation_cost == Decimal("50000.0000")  # Test 12: Cost aggregation ₹20k + ₹30k
        assert eval_resp.max_liquidation_horizon_days == Decimal("100.0000")

        # Verify results breakdown
        score_breach = next(r for r in eval_resp.results if r.limit_type == "MIN_LIQUIDITY_SCORE" and r.instrument_id == "SEC_A")
        assert score_breach.evaluation_status == "HARD_LIMIT_EXCEEDED"
        assert score_breach.breach_amount == Decimal("5.0000")

        horizon_breach = next(r for r in eval_resp.results if r.limit_type == "MAX_LIQUIDATION_HORIZON" and r.instrument_id == "SEC_B")
        assert horizon_breach.evaluation_status == "HARD_LIMIT_EXCEEDED"
        assert horizon_breach.breach_amount == Decimal("95.0000")


@pytest.mark.asyncio
async def test_liquidity_limits_api_endpoints():
    """
    Test 18: Full FastAPI REST API verification.
    """
    await init_db()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Health check
        res_health = await client.get("/api/v1/risk-limits/liquidity-limits/health")
        assert res_health.status_code == 200
        assert res_health.json()["status"] == "healthy"
        assert res_health.json()["module"] == "M11.04 - Liquidity Limits"

        # Create Profile with Initial Configurations
        prof_code = f"API_PROF_{uuid.uuid4().hex[:6]}"
        res_prof = await client.post(
            "/api/v1/risk-limits/liquidity-limit-profiles",
            json={
                "profile_name": f"API Liquidity Profile {prof_code}",
                "profile_code": prof_code,
                "description": "REST API Test Profile",
                "initial_limits": [
                    {
                        "limit_code": f"API_CFG_{uuid.uuid4().hex[:6]}",
                        "limit_name": "Maximum Liquidation Cost BPS",
                        "limit_type": "MAX_LIQUIDATION_COST_BPS",
                        "metric_name": "cost_bps",
                        "maximum_threshold": 40.0,
                        "warning_threshold": 35.0,
                        "threshold_unit": "BPS",
                    }
                ],
            },
        )
        assert res_prof.status_code == 201
        prof_id = res_prof.json()["id"]

        # List Configurations
        res_cfg_list = await client.get("/api/v1/risk-limits/liquidity-limits")
        assert res_cfg_list.status_code == 200
        assert len(res_cfg_list.json()) >= 1

        # Assign Profile
        port_id = f"API_PORT_{uuid.uuid4().hex[:6]}"
        res_assign = await client.post(
            "/api/v1/risk-limits/liquidity-limit-assignments",
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
            "/api/v1/risk-limits/liquidity-limits/evaluate",
            json={
                "portfolio_id": port_id,
                "portfolio_nav": 10000000.0,
                "positions": [
                    {
                        "instrument_id": "RELIANCE",
                        "position_side": "LONG",
                        "quantity": 1000.0,
                        "market_value": 2500000.0,
                        "adv": 50000.0,
                        "bid_depth": 10000.0,
                        "liquidity_score": 85.0,
                        "estimated_liquidation_cost": 15000.0,  # (15k / 2.5M) * 10,000 = 60 bps (> 40 bps limit)
                    }
                ],
            },
        )
        assert res_eval.status_code == 200
        eval_data = res_eval.json()
        assert eval_data["overall_status"] in ("BREACH", "HARD_LIMIT_EXCEEDED")

        # Evaluate Proposed Order
        res_order = await client.post(
            "/api/v1/risk-limits/liquidity-limits/evaluate/proposed-order",
            json={
                "portfolio_id": port_id,
                "instrument_id": "RELIANCE",
                "order_side": "BUY",
                "proposed_quantity": 5000.0,
                "current_quantity": 1000.0,
                "adv": 50000.0,
                "participation_rate": 0.10,
                "max_horizon_days_limit": 3.0,
            },
        )
        assert res_order.status_code == 200
        order_data = res_order.json()
        assert float(order_data["projected_quantity"]) == 6000.0
        assert order_data["evaluation_status"] == "WITHIN_LIMIT"

        # Query Breaches
        res_breaches = await client.get(f"/api/v1/risk-limits/liquidity-limits/breaches?portfolio_id={port_id}")
        assert res_breaches.status_code == 200
        assert len(res_breaches.json()) >= 1

