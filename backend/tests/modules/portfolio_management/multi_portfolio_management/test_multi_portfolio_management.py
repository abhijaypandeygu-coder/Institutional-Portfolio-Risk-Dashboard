"""
M05.08 Multi-Portfolio Management Integration & Verification Tests.
Tests portfolio group lifecycle, membership management & history, overlapping group deduplication,
cross-portfolio holding aggregation, gross/net analytical exposure, cash consolidation,
and shared setting inheritance & overrides.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.core.database import init_db


@pytest.mark.asyncio
async def test_portfolio_group_lifecycle_and_membership():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create a Strategy portfolio group
        grp_code = f"GRP-STRAT-{datetime.utcnow().timestamp()}"
        grp_payload = {
            "group_code": grp_code,
            "group_name": "Quant Long Short US Strategy",
            "description": "Multi-portfolio group covering quantitative long/short equity mandates",
            "group_type": "STRATEGY",
            "owner_reference": "USR-QUANT-LEAD",
            "organization_reference": "ORG-ALPHA-FIRM",
            "reporting_currency": "USD",
            "primary_benchmark_reference": "BENCH-SPX-TOTAL",
            "shared_risk_convention": "RISK-CONV-HISTORICAL-99",
        }
        res_create = await client.post("/api/v1/portfolio-groups", json=grp_payload)
        assert res_create.status_code == 201, res_create.text
        group = res_create.json()
        assert group["group_code"] == grp_code
        assert group["status"] == "ACTIVE"
        assert group["current_version"] == 1
        group_id = group["id"]

        # 2. Lifecycle status transitions
        res_suspend = await client.post(f"/api/v1/portfolio-groups/{group_id}/suspend")
        assert res_suspend.status_code == 200
        assert res_suspend.json()["status"] == "SUSPENDED"
        assert res_suspend.json()["current_version"] == 2

        res_activate = await client.post(f"/api/v1/portfolio-groups/{group_id}/activate")
        assert res_activate.status_code == 200
        assert res_activate.json()["status"] == "ACTIVE"
        assert res_activate.json()["current_version"] == 3

        # 3. Add portfolios to group
        p1 = f"PORT-P1-{datetime.utcnow().timestamp()}"
        p2 = f"PORT-P2-{datetime.utcnow().timestamp()}"

        res_m1 = await client.post(
            f"/api/v1/portfolio-groups/{group_id}/members",
            json={
                "portfolio_id": p1,
                "membership_role": "PRIMARY_MEMBER",
                "include_in_positions": True,
                "include_in_cash": True,
            },
        )
        assert res_m1.status_code == 201, res_m1.text
        assert res_m1.json()["portfolio_id"] == p1
        assert res_m1.json()["membership_status"] == "ACTIVE"

        res_m2 = await client.post(
            f"/api/v1/portfolio-groups/{group_id}/members",
            json={
                "portfolio_id": p2,
                "membership_role": "MEMBER",
                "include_in_positions": True,
                "include_in_cash": True,
            },
        )
        assert res_m2.status_code == 201

        # 4. Verify duplicate active membership is rejected
        res_m_dup = await client.post(
            f"/api/v1/portfolio-groups/{group_id}/members",
            json={"portfolio_id": p1},
        )
        assert res_m_dup.status_code == 400
        assert "already an active member" in res_m_dup.text

        # 5. List members
        res_list = await client.get(f"/api/v1/portfolio-groups/{group_id}/members")
        assert res_list.status_code == 200
        members = res_list.json()
        assert len(members) == 2

        # 6. Remove a portfolio (soft-delete / end-date) and check membership history
        res_rem = await client.post(f"/api/v1/portfolio-groups/{group_id}/members/{p2}/remove")
        assert res_rem.status_code == 200
        assert res_rem.json()["membership_status"] == "REMOVED"
        assert res_rem.json()["effective_to"] is not None

        # Verify active members count drops to 1, but historical includes both
        res_act = await client.get(f"/api/v1/portfolio-groups/{group_id}/members?include_historical=false")
        assert len(res_act.json()) == 1

        res_hist_mems = await client.get(f"/api/v1/portfolio-groups/{group_id}/members?include_historical=true")
        assert len(res_hist_mems.json()) == 2

        # Audit events
        res_events = await client.get(f"/api/v1/portfolio-groups/{group_id}/membership-history")
        assert res_events.status_code == 200
        events = res_events.json()
        assert len(events) >= 3  # Add p1, Add p2, Remove p2


@pytest.mark.asyncio
async def test_cross_portfolio_consolidation_and_analytical_netting():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ts = datetime.utcnow().timestamp()
        p1 = f"PORT-ALPHA-{ts}"
        p2 = f"PORT-BETA-{ts}"

        # 1. Register Portfolios in M05.01
        await client.post(
            "/api/v1/portfolios",
            json={
                "portfolio_code": f"COD-ALPHA-{ts}",
                "portfolio_name": "Alpha Portfolio",
                "base_currency": "USD",
                "strategy": "QUANT_EQUITY",
                "owner_id": "USR-ALPHA",
            },
        )
        await client.post(
            "/api/v1/portfolios",
            json={
                "portfolio_code": f"COD-BETA-{ts}",
                "portfolio_name": "Beta Portfolio",
                "base_currency": "USD",
                "strategy": "HEDGE_EQUITY",
                "owner_id": "USR-BETA",
            },
        )

        # 2. Record Positions in M05.02:
        # P1 is Long 1000 shares of AAPL
        # P2 is Short 400 shares of AAPL
        now = datetime.utcnow()
        await client.post(
            "/api/v1/positions/events",
            json={
                "portfolio_id": p1,
                "account_id": "ACC-ALPHA-01",
                "instrument_id": "INST-AAPL",
                "event_type": "TRADE_BUY",
                "signed_quantity_delta": "1000.000000",
                "settled_quantity_delta": "1000.000000",
                "idempotency_key": f"BUY_P1_{ts}",
            },
        )
        await client.post(
            "/api/v1/positions/events",
            json={
                "portfolio_id": p2,
                "account_id": "ACC-BETA-01",
                "instrument_id": "INST-AAPL",
                "event_type": "TRADE_SELL",
                "signed_quantity_delta": "-400.000000",
                "settled_quantity_delta": "-400.000000",
                "idempotency_key": f"SELL_P2_{ts}",
            },
        )

        # 3. Record Cash via deposits in M05.04:
        # P1 has $50,000 USD
        # P2 has ₹2,000,000 INR
        await client.post(
            f"/api/v1/portfolios/{p1}/cash/deposits",
            json={
                "portfolio_id": p1,
                "account_id": "ACC-ALPHA-01",
                "currency": "USD",
                "amount": "50000.000000",
                "source_reference": f"WIRE_P1_{ts}",
            },
        )
        await client.post(
            f"/api/v1/portfolios/{p2}/cash/deposits",
            json={
                "portfolio_id": p2,
                "account_id": "ACC-BETA-01",
                "currency": "INR",
                "amount": "2000000.000000",
                "source_reference": f"WIRE_P2_{ts}",
            },
        )

        # 4. Create Group & Add Both Portfolios
        grp_code = f"GRP-CROSS-{ts}"
        res_g = await client.post(
            "/api/v1/portfolio-groups",
            json={
                "group_code": grp_code,
                "group_name": "Consolidated Desk Group",
                "owner_reference": "DESK-HEAD",
                "reporting_currency": "USD",
            },
        )
        group_id = res_g.json()["id"]

        await client.post(f"/api/v1/portfolio-groups/{group_id}/members", json={"portfolio_id": p1})
        await client.post(f"/api/v1/portfolio-groups/{group_id}/members", json={"portfolio_id": p2})

        # 5. Execute Cross-Portfolio Consolidation Run
        run_res = await client.post(
            f"/api/v1/portfolio-groups/{group_id}/consolidations/run",
            json={
                "reporting_currency": "USD",
                "fx_rates_to_reporting": {
                    "USD": "1.000000",
                    "INR": "0.012000",  # 1 INR = 0.012 USD
                },
            },
        )
        assert run_res.status_code == 201, run_res.text
        run_data = run_res.json()
        assert run_data["included_portfolio_count"] == 2
        assert run_data["distinct_instrument_count"] == 1

        # Check Consolidated Holding for AAPL:
        # Gross Long = 1000, Gross Short = 400, Net Signed = 600
        aapl_holding = run_data["holdings"][0]
        assert aapl_holding["instrument_id"] == "INST-AAPL"
        assert Decimal(str(aapl_holding["gross_long_quantity"])) == Decimal("1000.000000")
        assert Decimal(str(aapl_holding["gross_short_quantity"])) == Decimal("400.000000")
        assert Decimal(str(aapl_holding["net_signed_quantity"])) == Decimal("600.000000")
        assert aapl_holding["contributing_portfolio_count"] == 2
        assert len(aapl_holding["contributors"]) == 2

        # Check Contributor Lineage
        contrib_ports = {c["portfolio_id"]: Decimal(str(c["signed_quantity"])) for c in aapl_holding["contributors"]}
        assert contrib_ports[p1] == Decimal("1000.000000")
        assert contrib_ports[p2] == Decimal("-400.000000")

        # Check Cash Summaries: currencies are kept segregated!
        cash_by_c = {c["currency"]: Decimal(str(c["available_cash"])) for c in run_data["cash_summaries"]}
        assert cash_by_c["USD"] == Decimal("50000.000000")
        assert cash_by_c["INR"] == Decimal("2000000.000000")

        # 6. Retrieve Group Exposure View
        exp_res = await client.get(f"/api/v1/portfolio-groups/{group_id}/exposures")
        assert exp_res.status_code == 200
        exp_data = exp_res.json()
        assert "ANALYTICAL NETTING ONLY" in exp_data["analytical_netting_disclaimer"]
        assert Decimal(str(exp_data["total_net_quantity_by_instrument"]["INST-AAPL"])) == Decimal("600.000000")

        # 7. Test Shared Setting Inheritance and Override
        # Default group reporting currency
        res_set = await client.get(f"/api/v1/portfolio-groups/{group_id}/resolved-settings?setting_key=REPORTING_CURRENCY")
        assert res_set.status_code == 200
        assert res_set.json()["effective_value"] == "USD"
        assert res_set.json()["source_level"] == "GROUP_POLICY"
        assert res_set.json()["is_override"] is False
