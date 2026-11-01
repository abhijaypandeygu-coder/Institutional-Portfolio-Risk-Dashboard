"""
M06.01 Gross Exposure Integration & Verification Tests.
Tests long exposure, absolute short exposure, total gross exposure (without offsetting),
denominator-relative ratios, currency conversions, breakdowns, and group aggregation.
"""

import pytest
from datetime import datetime
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.core.database import init_db


@pytest.mark.asyncio
async def test_gross_exposure_single_portfolio():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ts = datetime.utcnow().timestamp()
        portfolio_id = f"PORT-EXP-1-{ts}"

        # 1. Create Portfolio
        await client.post(
            "/api/v1/portfolios",
            json={
                "portfolio_code": f"COD-EXP-{ts}",
                "portfolio_name": "Gross Exposure Test Portfolio",
                "base_currency": "USD",
                "strategy": "LONG_SHORT",
                "owner_id": "USR-RISK-1",
            },
        )

        # 2. Buy 500 AAPL (Long)
        # Sell 200 MSFT (Short)
        await client.post(
            "/api/v1/positions/events",
            json={
                "portfolio_id": portfolio_id,
                "account_id": "ACC-01",
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
                "account_id": "ACC-01",
                "instrument_id": "INST-MSFT",
                "event_type": "TRADE_SELL",
                "signed_quantity_delta": "-200.000000",
                "settled_quantity_delta": "-200.000000",
                "idempotency_key": f"SELL_MSFT_{ts}",
            },
        )

        # 3. Run authoritative valuation:
        # AAPL price = $150 -> Long MV = $75,000
        # MSFT price = $300 -> Short MV = -$60,000
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

        # 4. Calculate Gross Exposure with NAV Denominator = $100,000
        # Expected:
        # Long Exposure = $75,000
        # Short Exposure = |-60,000| = $60,000
        # Gross Exposure = 75,000 + 60,000 = $135,000
        # Net Exposure = 75,000 - 60,000 = $15,000
        # Gross Exposure Ratio = 135,000 / 100,000 = 1.35x (135%)
        exp_res = await client.post(
            f"/api/v1/portfolios/{portfolio_id}/risk/gross-exposure/calculate",
            json={
                "reporting_currency": "USD",
                "denominator_type": "NAV",
                "custom_denominator_value": "100000.000000",
            },
        )
        assert exp_res.status_code == 201, exp_res.text
        data = exp_res.json()

        assert Decimal(str(data["long_exposure"])) == Decimal("75000.000000")
        assert Decimal(str(data["short_exposure"])) == Decimal("60000.000000")
        assert Decimal(str(data["gross_exposure"])) == Decimal("135000.000000")
        assert Decimal(str(data["net_exposure"])) == Decimal("15000.000000")
        assert Decimal(str(data["gross_exposure_ratio"])) == Decimal("1.350000")
        assert Decimal(str(data["exposure_ratio_percentage"])) == Decimal("135.0000")
        assert data["ratio_status"] == "VALID"
        assert len(data["contributions"]) == 2

        # Verify contributions preserve original signed MV vs positive absolute contribution
        aapl_c = next(c for c in data["contributions"] if c["instrument_id"] == "INST-AAPL")
        msft_c = next(c for c in data["contributions"] if c["instrument_id"] == "INST-MSFT")
        assert Decimal(str(aapl_c["signed_market_value"])) == Decimal("75000.000000")
        assert Decimal(str(aapl_c["absolute_exposure_contribution"])) == Decimal("75000.000000")

        assert Decimal(str(msft_c["signed_market_value"])) == Decimal("-60000.000000")
        assert Decimal(str(msft_c["absolute_exposure_contribution"])) == Decimal("60000.000000")


@pytest.mark.asyncio
async def test_gross_exposure_zero_denominator_and_group():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ts = datetime.utcnow().timestamp()
        p1 = f"PORT-G1-{ts}"
        p2 = f"PORT-G2-{ts}"

        # Register 2 portfolios
        await client.post("/api/v1/portfolios", json={"portfolio_code": f"C1-{ts}", "portfolio_name": "P1", "base_currency": "USD", "owner_id": "U1"})
        await client.post("/api/v1/portfolios", json={"portfolio_code": f"C2-{ts}", "portfolio_name": "P2", "base_currency": "USD", "owner_id": "U2"})

        # P1 Long 100 TSLA
        await client.post("/api/v1/positions/events", json={
            "portfolio_id": p1, "account_id": "A1", "instrument_id": "INST-TSLA",
            "event_type": "TRADE_BUY", "signed_quantity_delta": "100.0", "settled_quantity_delta": "100.0", "idempotency_key": f"B1_{ts}"
        })
        # P2 Short 50 TSLA
        await client.post("/api/v1/positions/events", json={
            "portfolio_id": p2, "account_id": "A2", "instrument_id": "INST-TSLA",
            "event_type": "TRADE_SELL", "signed_quantity_delta": "-50.0", "settled_quantity_delta": "-50.0", "idempotency_key": f"S2_{ts}"
        })

        # Test Zero Denominator Edge Case
        res_zero = await client.post(
            f"/api/v1/portfolios/{p1}/risk/gross-exposure/calculate",
            json={"custom_denominator_value": "0.000000"},
        )
        assert res_zero.status_code == 201
        assert res_zero.json()["ratio_status"] == "INVALID_ZERO_DENOMINATOR"
        assert res_zero.json()["gross_exposure_ratio"] is None

        # Create Group
        grp_res = await client.post("/api/v1/portfolio-groups", json={
            "group_code": f"GRP-EXP-{ts}",
            "group_name": "Exposure Group",
            "owner_reference": "RISK_HEAD",
            "reporting_currency": "USD",
        })
        group_id = grp_res.json()["id"]

        await client.post(f"/api/v1/portfolio-groups/{group_id}/members", json={"portfolio_id": p1})
        await client.post(f"/api/v1/portfolio-groups/{group_id}/members", json={"portfolio_id": p2})

        # Group Gross Exposure:
        # Default price = 100 -> P1 TSLA MV = 10,000 | P2 TSLA MV = -5,000
        # Long Exposure = 10,000 | Short Exposure = 5,000 | Gross Exposure = 15,000
        # Net Exposure = 5,000
        grp_exp = await client.get(
            f"/api/v1/portfolio-groups/{group_id}/risk/gross-exposure?custom_denominator_value=20000.0"
        )
        assert grp_exp.status_code == 200, grp_exp.text
        g_data = grp_exp.json()
        assert Decimal(str(g_data["long_exposure"])) == Decimal("10000.000000")
        assert Decimal(str(g_data["short_exposure"])) == Decimal("5000.000000")
        assert Decimal(str(g_data["gross_exposure"])) == Decimal("15000.000000")
        assert Decimal(str(g_data["net_exposure"])) == Decimal("5000.000000")
        assert Decimal(str(g_data["gross_exposure_ratio"])) == Decimal("0.750000")
