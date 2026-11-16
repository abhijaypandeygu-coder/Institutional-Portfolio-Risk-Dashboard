"""
Pytest integration and verification test suite for M11.09 Pre-trade Risk Checks.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.modules.risk_limits.pretrade_risk_checks.calculations.pretrade_risk_math import (
    calculate_projected_position,
    calculate_exposures,
    calculate_sector_exposure,
    calculate_parametric_var,
    calculate_participation_rate,
)
from backend.app.modules.risk_limits.pretrade_risk_checks.services.pretrade_risk_service import PretradeRiskService
from backend.app.modules.risk_limits.pretrade_risk_checks.schemas.pretrade_risk_schemas import ProposedOrderInput


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await init_db()
    yield


@pytest.mark.asyncio
async def test_pretrade_math_and_transitions():
    # Long increased
    q1, d1, t1 = calculate_projected_position(Decimal("100"), "BUY", Decimal("50"))
    assert q1 == Decimal("150")
    assert d1 == "LONG"
    assert t1 == "LONG_INCREASED"

    # Long closed
    q2, d2, t2 = calculate_projected_position(Decimal("100"), "SELL", Decimal("100"))
    assert q2 == Decimal("0")
    assert d2 == "FLAT"
    assert t2 == "LONG_CLOSED"

    # Long reversed to short
    q3, d3, t3 = calculate_projected_position(Decimal("50"), "SELL", Decimal("100"))
    assert q3 == Decimal("-50")
    assert d3 == "SHORT"
    assert t3 == "LONG_REVERSED_TO_SHORT"

    # Exposures
    pos_map = {"AAPL": Decimal("150000.00"), "MSFT": Decimal("-50000.00")}
    nav = Decimal("1000000.00")
    exp = calculate_exposures(pos_map, nav)
    assert exp["gross_exposure"] == Decimal("200000.00")
    assert exp["net_exposure"] == Decimal("100000.00")
    assert exp["gross_weight"] == Decimal("0.2000")
    assert exp["net_weight"] == Decimal("0.1000")

    # Sector
    sec_map = {"AAPL": "TECHNOLOGY", "MSFT": "TECHNOLOGY"}
    sec_exp = calculate_sector_exposure(pos_map, sec_map, nav)
    assert sec_exp["TECHNOLOGY"]["exposure"] == Decimal("100000.00")
    assert sec_exp["TECHNOLOGY"]["weight"] == Decimal("0.1000")

    # VaR
    var = calculate_parametric_var([0.15], [[0.04]], 1000000.0)
    assert var > 0.0

    # Participation
    rate = calculate_participation_rate(Decimal("1000"), Decimal("50000"))
    assert rate == Decimal("2.00")


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/pretrade/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "execution_authorization" in data["capabilities"]


@pytest.mark.asyncio
async def test_order_validation_syntax():
    async with AsyncSessionLocal() as session:
        svc = PretradeRiskService(session)

        # Invalid: Negative qty
        bad_qty = ProposedOrderInput(
            portfolio_id="PORT_1",
            instrument_id="AAPL",
            listing_id="LST_1",
            exchange="NASDAQ",
            side="BUY",
            quantity=Decimal("10"),  # Valid for pydantic, will test service logic
            order_type="UNSUPPORTED_TYPE",
            submitting_user_id="trader_1",
        )
        val_res = svc.validate_order_parameters(bad_qty)
        assert not val_res.is_valid
        assert any("Unsupported order type" in err for err in val_res.errors)


@pytest.mark.asyncio
async def test_order_evaluation_pass_and_authorization():
    async with AsyncSessionLocal() as session:
        svc = PretradeRiskService(session)

        order_in = ProposedOrderInput(
            portfolio_id="PORT_EQUITY_1",
            instrument_id="AAPL",
            listing_id="LST_AAPL_NASDAQ",
            exchange="NASDAQ",
            side="BUY",
            quantity=Decimal("100"),
            limit_price=Decimal("150.00"),
            order_type="LIMIT",
            time_in_force="DAY",
            submitting_user_id="algo_desk_1",
        )

        resp = await svc.evaluate_proposed_order(order_in)
        assert resp.decision == "PASS"
        assert resp.primary_reason_code == "ALL_CHECKS_PASSED"
        assert resp.authorization_id is not None
        assert resp.simulation is not None
        assert len(resp.check_results) == 7

        # Validate authorization
        auth_val = await svc.validate_authorization(resp.authorization_id)
        assert auth_val.is_valid is True
        assert auth_val.status == "ACTIVE"


@pytest.mark.asyncio
async def test_order_evaluation_reject_position_limit_exceeded():
    async with AsyncSessionLocal() as session:
        svc = PretradeRiskService(session)

        # Proposed order exceeds max position limit (10% NAV = $100k, order is 1000 * 150 = $150k)
        order_in = ProposedOrderInput(
            portfolio_id="PORT_EQUITY_2",
            instrument_id="TSLA",
            listing_id="LST_TSLA_NASDAQ",
            exchange="NASDAQ",
            side="BUY",
            quantity=Decimal("1000"),
            limit_price=Decimal("150.00"),
            order_type="LIMIT",
            time_in_force="DAY",
            submitting_user_id="trader_bob",
        )

        resp = await svc.evaluate_proposed_order(order_in)
        assert resp.decision == "REJECT"
        assert "POSITION_LIMIT_EXCEEDED" in resp.reason_summary
        assert resp.authorization_id is None


@pytest.mark.asyncio
async def test_order_evaluation_review_required_stale_data():
    async with AsyncSessionLocal() as session:
        svc = PretradeRiskService(session)

        order_in = ProposedOrderInput(
            portfolio_id="PORT_EQUITY_3",
            instrument_id="MSFT",
            listing_id="LST_MSFT_NASDAQ",
            exchange="NASDAQ",
            side="BUY",
            quantity=Decimal("50"),
            limit_price=Decimal("300.00"),
            order_type="LIMIT",
            submitting_user_id="trader_alice",
        )

        # Inject stale market data (> 60 seconds)
        mock_stale_state = {
            "nav": Decimal("1000000.00"),
            "cash": Decimal("250000.00"),
            "positions": {"MSFT": Decimal("10.00")},
            "position_values": {"MSFT": Decimal("3000.00")},
            "sectors": {"MSFT": "TECHNOLOGY"},
            "market_price": Decimal("300.00"),
            "expected_volume": Decimal("100000.00"),
            "cov_matrix": [[0.04]],
            "weights": [0.015],
            "data_freshness_sec": 120,  # 120s stale
        }

        resp = await svc.evaluate_proposed_order(order_in, mock_portfolio_state=mock_stale_state)
        assert resp.decision == "REVIEW_REQUIRED"
        assert resp.primary_reason_code == "MARKET_DATA_STALE"
        assert resp.authorization_id is None


@pytest.mark.asyncio
async def test_dashboard_and_analytics():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/pretrade/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_orders_evaluated" in data
        assert "pass_percentage" in data
        assert "rejection_reasons_breakdown" in data

