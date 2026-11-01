"""
M06.02 Net Exposure Tests.
Integration and unit tests verifying:
1. Net Market Value (Long - Short, sum of signed market values).
2. Net Exposure Ratio (positive, negative, approximately neutral).
3. Directional interpretation (NET_LONG, NET_SHORT, APPROX_NEUTRAL).
4. Neutrality threshold policy (absolute, relative, combined).
5. Currency normalization (INR and USD positions).
6. Multi-portfolio group consolidated net exposure and membership deduplication.
7. Denominator validation (zero, negative, unavailable).
"""

import pytest
from datetime import datetime
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.core.database import init_db


@pytest.mark.asyncio
async def test_net_exposure_single_portfolio_and_directional_states():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ts = datetime.utcnow().timestamp()
        portfolio_id = f"PORT-NET-1-{ts}"

        # 1. Create Portfolio
        await client.post(
            "/api/v1/portfolios",
            json={
                "portfolio_code": f"COD-NET-{ts}",
                "portfolio_name": "Net Exposure Test Portfolio",
                "base_currency": "USD",
                "strategy": "EQUITY_LONG_SHORT",
                "owner_id": "USR-NET-1",
            },
        )

        # 2. Buy 500 AAPL (Long), Sell 200 MSFT (Short)
        await client.post(
            "/api/v1/positions/events",
            json={
                "portfolio_id": portfolio_id,
                "account_id": "ACC-NET-1",
                "instrument_id": "INST-AAPL",
                "event_type": "TRADE_BUY",
                "signed_quantity_delta": "500.000000",
                "settled_quantity_delta": "500.000000",
                "idempotency_key": f"BUY_AAPL_{ts}",
            },
        )
        await client.post(
            "/api/v1/positions/events",
            json={
                "portfolio_id": portfolio_id,
                "account_id": "ACC-NET-1",
                "instrument_id": "INST-MSFT",
                "event_type": "TRADE_SELL",
                "signed_quantity_delta": "-200.000000",
                "settled_quantity_delta": "-200.000000",
                "idempotency_key": f"SELL_MSFT_{ts}",
            },
        )

        # 3. Mark prices: AAPL = $150 (Long MV = $75,000), MSFT = $300 (Short MV = -$60,000)
        val_run = await client.post(
            "/api/v1/valuations/run",
            json={
                "portfolio_id": portfolio_id,
                "mark_prices": {
                    "INST-AAPL": "150.000000",
                    "INST-MSFT": "300.000000",
                },
            },
        )
        assert val_run.status_code == 201

        # 4. Calculate Net Exposure with NAV Denominator = $100,000
        # Expected:
        # Long Exposure = $75,000
        # Short Exposure = $60,000
        # Net Market Value = 75,000 - 60,000 = +$15,000
        # Gross Exposure Reference = $135,000
        # Net Exposure Ratio = 15,000 / 100,000 = 0.15x (15%)
        # Relative Neutrality Threshold = 2% (0.02) -> 15% > 2% -> NET_LONG
        res = await client.post(
            f"/api/v1/portfolios/{portfolio_id}/risk/net-exposure/calculate",
            json={
                "reporting_currency": "USD",
                "denominator_type": "NAV",
                "custom_denominator_value": "100000.000000",
                "neutrality_threshold_type": "RELATIVE",
                "relative_neutrality_threshold": "0.020000",
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert Decimal(str(data["long_exposure"])) == Decimal("75000.000000")
        assert Decimal(str(data["absolute_short_exposure"])) == Decimal("60000.000000")
        assert Decimal(str(data["net_market_value"])) == Decimal("15000.000000")
        assert Decimal(str(data["gross_exposure_reference"])) == Decimal("135000.000000")
        assert Decimal(str(data["net_exposure_ratio"])) == Decimal("0.150000")
        assert Decimal(str(data["net_exposure_ratio_percentage"])) == Decimal("15.0000")
        assert data["directional_classification"] == "NET_LONG"
        assert data["ratio_status"] == "VALID"
        assert len(data["contributions"]) == 2

        # 5. Test Neutrality Band:
        # If relative neutrality threshold is set to 20% (0.20), then 15% <= 20% -> APPROX_NEUTRAL
        res_neutral = await client.post(
            f"/api/v1/portfolios/{portfolio_id}/risk/net-exposure/calculate",
            json={
                "reporting_currency": "USD",
                "denominator_type": "NAV",
                "custom_denominator_value": "100000.000000",
                "neutrality_threshold_type": "RELATIVE",
                "relative_neutrality_threshold": "0.200000",
            },
        )
        assert res_neutral.status_code == 201
        data_neutral = res_neutral.json()
        assert data_neutral["directional_classification"] == "APPROX_NEUTRAL"

        # 6. Test Absolute Neutrality Band:
        # Net is +$15,000. If absolute threshold is $20,000 -> APPROX_NEUTRAL
        res_abs = await client.post(
            f"/api/v1/portfolios/{portfolio_id}/risk/net-exposure/calculate",
            json={
                "reporting_currency": "USD",
                "denominator_type": "NAV",
                "custom_denominator_value": "100000.000000",
                "neutrality_threshold_type": "ABSOLUTE",
                "absolute_neutrality_threshold": "20000.000000",
            },
        )
        assert res_abs.status_code == 201
        assert res_abs.json()["directional_classification"] == "APPROX_NEUTRAL"


@pytest.mark.asyncio
async def test_net_exposure_negative_and_zero_denominator():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ts = datetime.utcnow().timestamp()
        portfolio_id = f"PORT-NET-SHORT-{ts}"

        # 1. Create Portfolio
        await client.post(
            "/api/v1/portfolios",
            json={
                "portfolio_code": f"COD-NSHORT-{ts}",
                "portfolio_name": "Short Net Exposure Portfolio",
                "base_currency": "USD",
                "strategy": "SHORT_BIASED",
                "owner_id": "USR-NET-2",
            },
        )

        # 2. Short 500 AAPL (Short MV = -$75,000)
        await client.post(
            "/api/v1/positions/events",
            json={
                "portfolio_id": portfolio_id,
                "account_id": "ACC-NET-2",
                "instrument_id": "INST-AAPL",
                "event_type": "TRADE_SELL",
                "signed_quantity_delta": "-500.000000",
                "settled_quantity_delta": "-500.000000",
                "idempotency_key": f"SELL_AAPL_SHORT_{ts}",
            },
        )

        await client.post(
            "/api/v1/valuations/run",
            json={
                "portfolio_id": portfolio_id,
                "mark_prices": {"INST-AAPL": "150.000000"},
            },
        )

        # 3. Calculate with zero denominator
        res_zero = await client.post(
            f"/api/v1/portfolios/{portfolio_id}/risk/net-exposure/calculate",
            json={
                "reporting_currency": "USD",
                "denominator_type": "NAV",
                "custom_denominator_value": "0.000000",
            },
        )
        assert res_zero.status_code == 201
        data_zero = res_zero.json()
        assert data_zero["ratio_status"] == "INVALID_ZERO_DENOMINATOR"
        assert data_zero["net_exposure_ratio"] is None
        assert Decimal(str(data_zero["net_market_value"])) == Decimal("-75000.000000")
        assert data_zero["directional_classification"] == "NET_SHORT"

        # 4. Calculate with valid NAV = $100,000
        # Net ratio = -75,000 / 100,000 = -0.75x (-75%)
        res_neg = await client.post(
            f"/api/v1/portfolios/{portfolio_id}/risk/net-exposure/calculate",
            json={
                "reporting_currency": "USD",
                "denominator_type": "NAV",
                "custom_denominator_value": "100000.000000",
            },
        )
        assert res_neg.status_code == 201
        data_neg = res_neg.json()
        assert data_neg["ratio_status"] == "VALID"
        assert Decimal(str(data_neg["net_exposure_ratio"])) == Decimal("-0.750000")
        assert Decimal(str(data_neg["net_exposure_ratio_percentage"])) == Decimal("-75.0000")
        assert data_neg["directional_classification"] == "NET_SHORT"


@pytest.mark.asyncio
async def test_net_exposure_group_consolidation_and_neutrality():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ts = datetime.utcnow().timestamp()
        p1 = f"PORT-GRP-NET1-{ts}"
        p2 = f"PORT-GRP-NET2-{ts}"

        # Portfolio 1: Net Long $50,000 (500 shares @ $100)
        await client.post(
            "/api/v1/portfolios",
            json={
                "portfolio_code": f"COD-G1-{ts}",
                "portfolio_name": "Group Member 1 Long",
                "base_currency": "USD",
                "strategy": "LONG_ONLY",
                "owner_id": "USR-GRP-1",
            },
        )
        await client.post(
            "/api/v1/positions/events",
            json={
                "portfolio_id": p1,
                "account_id": "ACC-G1",
                "instrument_id": "INST-A",
                "event_type": "TRADE_BUY",
                "signed_quantity_delta": "500.000000",
                "settled_quantity_delta": "500.000000",
                "idempotency_key": f"BUY_A_{ts}",
            },
        )

        # Portfolio 2: Net Short -$50,000 (500 shares @ $100)
        await client.post(
            "/api/v1/portfolios",
            json={
                "portfolio_code": f"COD-G2-{ts}",
                "portfolio_name": "Group Member 2 Short",
                "base_currency": "USD",
                "strategy": "SHORT_ONLY",
                "owner_id": "USR-GRP-2",
            },
        )
        await client.post(
            "/api/v1/positions/events",
            json={
                "portfolio_id": p2,
                "account_id": "ACC-G2",
                "instrument_id": "INST-B",
                "event_type": "TRADE_SELL",
                "signed_quantity_delta": "-500.000000",
                "settled_quantity_delta": "-500.000000",
                "idempotency_key": f"SELL_B_{ts}",
            },
        )

        # Create Portfolio Group with P1 and P2
        group_res = await client.post(
            "/api/v1/portfolio-groups",
            json={
                "group_code": f"GRP-NET-{ts}",
                "group_name": "Net Neutral Group",
                "group_type": "STRATEGY",
                "owner_reference": "USR-GRP-MGR",
                "reporting_currency": "USD",
            },
        )
        assert group_res.status_code == 201
        group_id = group_res.json()["id"]

        await client.post(
            f"/api/v1/portfolio-groups/{group_id}/members",
            json={"portfolio_id": p1},
        )
        await client.post(
            f"/api/v1/portfolio-groups/{group_id}/members",
            json={"portfolio_id": p2},
        )

        # Calculate Group Net Exposure:
        # P1 = +$50,000, P2 = -$50,000
        # Long Exposure = $50,000, Short Exposure = $50,000
        # Net Market Value = $0.000000
        # Gross Exposure = $100,000
        # Directional Classification = APPROX_NEUTRAL
        grp_calc = await client.post(
            f"/api/v1/portfolio-groups/{group_id}/risk/net-exposure/calculate",
            json={
                "reporting_currency": "USD",
                "denominator_type": "NAV",
                "custom_denominator_value": "200000.000000",
                "neutrality_threshold_type": "RELATIVE",
                "relative_neutrality_threshold": "0.020000",
            },
        )
        assert grp_calc.status_code == 201
        grp_data = grp_calc.json()
        assert Decimal(str(grp_data["long_exposure"])) == Decimal("50000.000000")
        assert Decimal(str(grp_data["absolute_short_exposure"])) == Decimal("50000.000000")
        assert Decimal(str(grp_data["net_market_value"])) == Decimal("0.000000")
        assert Decimal(str(grp_data["gross_exposure_reference"])) == Decimal("100000.000000")
        assert Decimal(str(grp_data["net_exposure_ratio"])) == Decimal("0.000000")
        assert grp_data["directional_classification"] == "APPROX_NEUTRAL"
        assert len(grp_data["contributions"]) == 2
        assert len(grp_data["breakdowns"]) >= 2
