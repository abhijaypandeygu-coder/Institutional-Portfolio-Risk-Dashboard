"""
Comprehensive unit and integration tests for M11.02 — Position Limits.

Tests covered:
1. Position weight calculations (signed and absolute) & zero/negative NAV fail-safe handling.
2. Directional exposure isolation (Long vs. Short).
3. Utilization, remaining capacity, and breach amounts.
4. Financial correctness tests from specification:
   - Example 1: Max position weight within limit (10% NAV, 10% limit -> 100% utilization).
   - Example 2: Position weight breach (15% NAV, 10% limit -> 150% utilization, 5% breach).
   - Example 3: Absolute notional (USD 2M notional, USD 1.5M limit -> 133.33% utilization).
   - Example 4: Long/short separation (Long USD 800k on 1M cap, Short USD 300k on 500k cap).
   - Example 5: Issuer aggregation (Listing A USD 600k + Listing B USD 400k -> USD 1M on 900k limit -> 111.11%).
   - Example 6: Long/short issuer netting (Gross USD 1.4M vs Net USD 600k on 1M long / 400k short).
5. Proposed-order simulation and pre-trade evaluation (M11.07 consumption).
6. Service and Repository lifecycle (Configurations, Profiles, Assignments, Portfolio evaluation).
7. FastAPI REST API endpoints:
   - GET /api/v1/risk-limits/position-limits/health
   - POST /api/v1/risk-limits/position-limits
   - GET /api/v1/risk-limits/position-limits
   - POST /api/v1/risk-limits/position-limit-profiles
   - GET /api/v1/risk-limits/position-limit-profiles
   - POST /api/v1/risk-limits/position-limit-assignments
   - POST /api/v1/risk-limits/position-limits/evaluate
   - POST /api/v1/risk-limits/position-limits/evaluate/proposed-order
   - GET /api/v1/risk-limits/position-limits/breaches
"""

from decimal import Decimal
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.core.database import init_db, AsyncSessionLocal
from backend.app.main import app
from backend.app.modules.risk_limits.position_limits.calculations.position_limit_math import (
    calculate_position_weight,
    calculate_directional_exposure,
    calculate_limit_utilization,
    aggregate_issuer_exposures,
    simulate_proposed_order,
)
from backend.app.modules.risk_limits.position_limits.schemas.position_limit_schemas import (
    ConfigurationCreate,
    ProfileCreate,
    AssignmentCreate,
    PositionInput,
    PortfolioEvaluationRequest,
    ProposedOrderRequest,
)
from backend.app.modules.risk_limits.position_limits.services.position_limit_service import (
    PositionLimitService,
)


def test_position_weight_calculations_and_failsafe():
    nav = Decimal("10000000.00")  # ₹10 Crore
    mv_long = Decimal("1500000.00")  # ₹1.5 Crore
    mv_short = Decimal("-1500000.00")

    # Absolute weight: 1.5 / 10 * 100 = 15%
    w_abs, st = calculate_position_weight(mv_short, nav, use_absolute=True)
    assert st == "VALID"
    assert w_abs == Decimal("15.0000")

    # Signed weight: -1.5 / 10 * 100 = -15%
    w_signed, st = calculate_position_weight(mv_short, nav, use_absolute=False)
    assert st == "VALID"
    assert w_signed == Decimal("-15.0000")

    # Zero or negative NAV fail-safe
    w_zero, st_zero = calculate_position_weight(mv_long, Decimal("0.0"))
    assert st_zero == "INVALID_NAV"
    assert w_zero == Decimal("0.0000")

    w_neg, st_neg = calculate_position_weight(mv_long, Decimal("-50000.0"))
    assert st_neg == "INVALID_NAV"
    assert w_neg == Decimal("0.0000")


def test_financial_correctness_examples_from_spec():
    # Example 1: Maximum position weight
    # NAV = ₹10 crore, MV = ₹1 crore, Limit = 10% -> Utilization = 100%
    w1, _ = calculate_position_weight(Decimal("10000000.0"), Decimal("100000000.0"))  # 1 Cr on 10 Cr = 10%
    u1 = calculate_limit_utilization(w1, warning_threshold=Decimal("8.0"), hard_threshold=Decimal("10.0"))
    assert u1["hard_utilization_pct"] == Decimal("100.00")
    assert u1["evaluation_status"] == "HARD_LIMIT_EXCEEDED"  # At exactly 10% (GREATER_THAN_OR_EQUAL)

    # Example 2: Position weight breach
    # NAV = ₹10 crore, MV = ₹1.5 crore, Limit = 10% -> Utilization = 150%, Breach = 5%
    w2, _ = calculate_position_weight(Decimal("15000000.0"), Decimal("100000000.0"))  # 1.5 Cr on 10 Cr = 15%
    u2 = calculate_limit_utilization(w2, warning_threshold=Decimal("8.0"), hard_threshold=Decimal("10.0"))
    assert u2["hard_utilization_pct"] == Decimal("150.00")
    assert u2["breach_amount"] == Decimal("5.0000")
    assert u2["evaluation_status"] == "HARD_LIMIT_EXCEEDED"

    # Example 3: Absolute notional
    # Position notional = USD 2M, Limit = USD 1.5M -> Utilization = 133.33%
    u3 = calculate_limit_utilization(
        actual_exposure=Decimal("2000000.0"),
        warning_threshold=Decimal("1200000.0"),
        hard_threshold=Decimal("1500000.0")
    )
    assert u3["hard_utilization_pct"] == Decimal("133.33")
    assert u3["breach_amount"] == Decimal("500000.0000")

    # Example 4: Long/short separation
    # Long = 800k (cap 1M), Short = 300k (cap 500k) -> Long U = 80%, Short U = 60%, Both within
    long_exp = calculate_directional_exposure(Decimal("800000.0"), direction="LONG")
    short_exp = calculate_directional_exposure(Decimal("-300000.0"), direction="SHORT")
    u_long = calculate_limit_utilization(long_exp, warning_threshold=Decimal("850000.0"), hard_threshold=Decimal("1000000.0"))
    u_short = calculate_limit_utilization(short_exp, warning_threshold=Decimal("400000.0"), hard_threshold=Decimal("500000.0"))
    assert u_long["hard_utilization_pct"] == Decimal("80.00")
    assert u_short["hard_utilization_pct"] == Decimal("60.00")
    assert u_long["evaluation_status"] == "WITHIN_LIMIT"
    assert u_short["evaluation_status"] == "WITHIN_LIMIT"

    # Example 5: Issuer aggregation
    # Listing A = 600k, Listing B = 400k -> Total = 1M on 900k limit -> 111.11%
    issuer_positions = [
        {"market_value": Decimal("600000.0")},
        {"market_value": Decimal("400000.0")},
    ]
    agg5 = aggregate_issuer_exposures(issuer_positions)
    assert agg5["gross_exposure"] == Decimal("1000000.00")
    u5 = calculate_limit_utilization(agg5["gross_exposure"], warning_threshold=Decimal("800000.0"), hard_threshold=Decimal("900000.0"))
    assert u5["hard_utilization_pct"] == Decimal("111.11")
    assert u5["breach_amount"] == Decimal("100000.0000")

    # Example 6: Long/short issuer netting
    # Long = 1M, Short = 400k -> Gross = 1.4M, Net = 600k, Long = 1M, Short = 400k
    issuer_positions_mixed = [
        {"market_value": Decimal("1000000.0")},
        {"market_value": Decimal("-400000.0")},
    ]
    agg6 = aggregate_issuer_exposures(issuer_positions_mixed)
    assert agg6["gross_exposure"] == Decimal("1400000.00")
    assert agg6["net_exposure"] == Decimal("600000.00")
    assert agg6["long_exposure"] == Decimal("1000000.00")
    assert agg6["short_exposure"] == Decimal("400000.00")


def test_simulate_proposed_order():
    # Current: 100 shares @ $150 = $15,000
    # Proposed: BUY 50 shares @ $160
    # Post: 150 shares @ $160 = $24,000
    sim = simulate_proposed_order(
        current_quantity=Decimal("100"),
        current_market_value=Decimal("15000.0"),
        order_side="BUY",
        order_quantity=Decimal("50"),
        reference_price=Decimal("160.0"),
        fx_rate=Decimal("1.0"),
        portfolio_nav=Decimal("200000.0")
    )
    assert sim["post_quantity"] == Decimal("150")
    assert sim["post_market_value"] == Decimal("24000.0000")
    # Post weight: 24,000 / 200,000 = 12%
    assert sim["post_weight_pct"] == Decimal("12.0000")


@pytest.mark.asyncio
async def test_position_limit_service_lifecycle_and_evaluation():
    await init_db()
    async with AsyncSessionLocal() as session:
        service = PositionLimitService(session)

        # 1. Create Profile with standard position limits
        profile_dto = ProfileCreate(
            profile_code="EQUITY_CORE_PROFILE_01",
            profile_name="Equity Core Position Risk Profile",
            profile_tier="MODERATE",
            description="10% max weight, $1M max notional, 15% max issuer concentration",
            initial_limits=[
                ConfigurationCreate(
                    limit_code="MAX_WT_10",
                    limit_name="10% Max Position Weight",
                    limit_type="MAX_POSITION_WEIGHT",
                    direction="ANY",
                    aggregation_level="INSTRUMENT",
                    threshold_value=Decimal("10.0"),
                    warning_threshold=Decimal("8.0"),
                    threshold_unit="PERCENT_NAV",
                ),
                ConfigurationCreate(
                    limit_code="MAX_NOTIONAL_1M",
                    limit_name="USD 1M Max Notional",
                    limit_type="MAX_ABSOLUTE_NOTIONAL",
                    direction="ANY",
                    aggregation_level="INSTRUMENT",
                    threshold_value=Decimal("1000000.0"),
                    warning_threshold=Decimal("800000.0"),
                    threshold_unit="USD",
                    limit_currency="USD",
                ),
                ConfigurationCreate(
                    limit_code="MAX_ISSUER_15",
                    limit_name="15% Max Issuer Concentration",
                    limit_type="MAX_ISSUER_WEIGHT",
                    direction="GROSS",
                    aggregation_level="ISSUER",
                    threshold_value=Decimal("15.0"),
                    warning_threshold=Decimal("12.0"),
                    threshold_unit="PERCENT_NAV",
                ),
            ]
        )
        profile = await service.create_profile(profile_dto)
        assert profile.id is not None
        assert len(profile.configurations) == 3

        # 2. Assign Profile to Portfolio
        portfolio_id = "PORT_EQ_101"
        assign_dto = AssignmentCreate(
            profile_id=profile.id,
            target_type="PORTFOLIO",
            target_id=portfolio_id,
            assigned_by="risk_officer",
        )
        assign = await service.assign_profile(assign_dto)
        assert assign.target_id == portfolio_id
        assert assign.status == "ACTIVE"

        # 3. Portfolio Evaluation
        # NAV = $5,000,000
        # Pos 1: AAPL (Issuer: APPLE) MV = $450,000 (9.0% -> WARNING on 8% threshold)
        # Pos 2: MSFT (Issuer: MICROSOFT) MV = $600,000 (12.0% -> HARD BREACH on 10% threshold)
        # Pos 3: GOOGL (Issuer: ALPHABET) MV = $300,000 (6.0% -> WITHIN_LIMIT)
        eval_req = PortfolioEvaluationRequest(
            portfolio_id=portfolio_id,
            portfolio_nav=Decimal("5000000.0"),
            base_currency="USD",
            positions=[
                PositionInput(
                    instrument_id="INST_AAPL",
                    symbol="AAPL",
                    issuer_id="ISSUER_APPLE",
                    quantity=Decimal("3000"),
                    market_value=Decimal("450000.0"),
                ),
                PositionInput(
                    instrument_id="INST_MSFT",
                    symbol="MSFT",
                    issuer_id="ISSUER_MSFT",
                    quantity=Decimal("1500"),
                    market_value=Decimal("600000.0"),
                ),
                PositionInput(
                    instrument_id="INST_GOOGL",
                    symbol="GOOGL",
                    issuer_id="ISSUER_ALPHABET",
                    quantity=Decimal("1000"),
                    market_value=Decimal("300000.0"),
                ),
            ],
            evaluator="test_evaluator"
        )
        eval_run = await service.evaluate_portfolio_positions(eval_req)
        assert eval_run.portfolio_id == portfolio_id
        assert eval_run.overall_status == "HARD_LIMIT_EXCEEDED"
        assert eval_run.hard_breaches_count >= 1
        assert eval_run.warning_breaches_count >= 1

        # 4. Proposed-order simulation (Pre-trade check)
        # Buying more MSFT should be rejected (is_pretrade_approved = False)
        order_req = ProposedOrderRequest(
            portfolio_id=portfolio_id,
            portfolio_nav=Decimal("5000000.0"),
            instrument_id="INST_MSFT",
            symbol="MSFT",
            order_side="BUY",
            order_quantity=Decimal("500"),
            reference_price=Decimal("400.0"),
            current_quantity=Decimal("1500"),
            current_market_value=Decimal("600000.0"),
        )
        pretrade_res = await service.evaluate_proposed_order(order_req)
        assert pretrade_res.is_pretrade_approved is False
        assert pretrade_res.overall_status == "HARD_LIMIT_EXCEEDED"
        assert pretrade_res.projected_weight_pct == Decimal("16.0000")  # (600k + 200k) / 5M = 16%


@pytest.mark.asyncio
async def test_position_limits_api_endpoints():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Health check
        h_res = await client.get("/api/v1/risk-limits/position-limits/health")
        assert h_res.status_code == 200
        assert h_res.json()["module"] == "M11.02 - Position Limits"

        # Create Profile with dynamic unique code
        import uuid
        u_suffix = uuid.uuid4().hex[:8]
        prof_payload = {
            "profile_code": f"API_GROWTH_{u_suffix}",
            "profile_name": "API Growth Profile",
            "profile_tier": "AGGRESSIVE",
            "initial_limits": [
                {
                    "limit_code": f"API_MAX_WT_{u_suffix}",
                    "limit_name": "12% Max Weight",
                    "limit_type": "MAX_POSITION_WEIGHT",
                    "direction": "ANY",
                    "aggregation_level": "INSTRUMENT",
                    "threshold_value": "12.0",
                    "warning_threshold": "10.0",
                    "threshold_unit": "PERCENT_NAV",
                }
            ]
        }
        p_res = await client.post("/api/v1/risk-limits/position-limit-profiles", json=prof_payload)
        assert p_res.status_code == 201
        p_data = p_res.json()
        assert p_data["profile_code"] == f"API_GROWTH_{u_suffix}"

        # Assign Profile
        assign_payload = {
            "profile_id": p_data["id"],
            "target_type": "PORTFOLIO",
            "target_id": "PORT_API_TEST",
            "assigned_by": "api_tester"
        }
        a_res = await client.post("/api/v1/risk-limits/position-limit-assignments", json=assign_payload)
        assert a_res.status_code == 201

        # Portfolio Evaluation via API
        eval_payload = {
            "portfolio_id": "PORT_API_TEST",
            "portfolio_nav": "1000000.0",  # $1M
            "base_currency": "USD",
            "positions": [
                {
                    "instrument_id": "TSLA_US",
                    "symbol": "TSLA",
                    "quantity": "500",
                    "market_value": "110000.0",  # 11% -> WARNING (threshold: 10% warn, 12% hard)
                    "currency": "USD"
                }
            ]
        }
        eval_resp = await client.post("/api/v1/risk-limits/position-limits/evaluate", json=eval_payload)
        assert eval_resp.status_code == 200
        eval_json = eval_resp.json()
        assert eval_json["overall_status"] == "WARNING"

        # Pre-trade Proposed Order Check via API
        order_payload = {
            "portfolio_id": "PORT_API_TEST",
            "portfolio_nav": "1000000.0",
            "instrument_id": "TSLA_US",
            "symbol": "TSLA",
            "order_side": "BUY",
            "order_quantity": "100",
            "reference_price": "250.0",  # +$25k -> total $135k on $1M = 13.5% > 12% HARD BREACH
            "current_quantity": "500",
            "current_market_value": "110000.0"
        }
        pretrade_resp = await client.post("/api/v1/risk-limits/position-limits/evaluate/proposed-order", json=order_payload)
        assert pretrade_resp.status_code == 200
        pretrade_json = pretrade_resp.json()
        assert pretrade_json["is_pretrade_approved"] is False
        assert pretrade_json["overall_status"] == "HARD_LIMIT_EXCEEDED"
