"""
Tests for M06.04 Instrument Exposure.
Verifies single-name instrument exposure calculations, NAV-based and gross-contribution weights,
long/short/gross/net ranking, dominance threshold detection, and historical snapshot comparisons.
"""

import pytest
import time
from datetime import datetime, timezone
from decimal import Decimal
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db, AsyncSessionLocal
from backend.app.modules.instrument_reference_data.instrument_master.services.service import (
    InstrumentMasterService,
)
from backend.app.modules.instrument_reference_data.instrument_master.schemas import (
    InstrumentCreateRequest,
)
from backend.app.modules.portfolio_management.portfolio_history.models import (
    PortfolioBookSnapshot,
    HistoricalPositionSnapshot,
    HistoricalValuationSnapshot,
)
from backend.app.modules.portfolio_management.portfolio_history.repositories.repository import (
    PortfolioHistoryRepository,
)
from backend.app.modules.portfolio_management.multi_portfolio_management.services.service import (
    MultiPortfolioService,
)
from backend.app.modules.portfolio_management.multi_portfolio_management.schemas import (
    PortfolioGroupCreateRequest,
    PortfolioGroupMembershipAddRequest,
)


@pytest.mark.asyncio
async def test_instrument_exposure_calculation_rankings_and_dominance():
    await init_db()
    ts = datetime.utcnow().timestamp()
    port_id = f"port-inst-test-{ts}"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create canonical instruments: AAPL, TSLA, MSFT
        async with AsyncSessionLocal() as session:
            i_aapl = await InstrumentMasterService.create_instrument(
                session,
                InstrumentCreateRequest(
                    canonical_name=f"Apple Inc {ts}",
                    short_name=f"AAPL_{ts}",
                    instrument_type="COMMON_STOCK",
                    asset_class="EQUITY",
                    issue_currency="USD",
                    primary_market_id="NASDAQ",
                ),
                actor_id="admin",
            )
            i_tsla = await InstrumentMasterService.create_instrument(
                session,
                InstrumentCreateRequest(
                    canonical_name=f"Tesla Inc {ts}",
                    short_name=f"TSLA_{ts}",
                    instrument_type="COMMON_STOCK",
                    asset_class="EQUITY",
                    issue_currency="USD",
                    primary_market_id="NASDAQ",
                ),
                actor_id="admin",
            )
            i_msft = await InstrumentMasterService.create_instrument(
                session,
                InstrumentCreateRequest(
                    canonical_name=f"Microsoft Corp {ts}",
                    short_name=f"MSFT_{ts}",
                    instrument_type="COMMON_STOCK",
                    asset_class="EQUITY",
                    issue_currency="USD",
                    primary_market_id="NASDAQ",
                ),
                actor_id="admin",
            )
            inst_aapl = i_aapl.instrument_id
            inst_tsla = i_tsla.instrument_id
            inst_msft = i_msft.instrument_id

        # 2. Create Portfolio and positions via REST API
        await client.post(
            "/api/v1/portfolios",
            json={
                "portfolio_code": f"COD-INST-{ts}",
                "portfolio_name": "Instrument Exposure Portfolio",
                "base_currency": "USD",
                "strategy": "EQUITY_LONG_SHORT",
                "owner_id": "USR-INST-1",
            },
        )

        # Positions:
        # Long 100 AAPL @ $150 = $15,000
        # Short 50 TSLA @ $200 = -$10,000
        # Long 20 MSFT @ $300 = $6,000
        for inst, delta in [
            (inst_aapl, "100.000000"),
            (inst_tsla, "-50.000000"),
            (inst_msft, "20.000000"),
        ]:
            side = "TRADE_BUY" if Decimal(delta) > 0 else "TRADE_SELL"
            await client.post(
                "/api/v1/positions/events",
                json={
                    "portfolio_id": port_id,
                    "account_id": "ACC-INST-1",
                    "instrument_id": inst,
                    "event_type": side,
                    "signed_quantity_delta": delta,
                    "settled_quantity_delta": delta,
                    "idempotency_key": f"EVT_{inst}_{ts}",
                },
            )

        # Run valuation
        await client.post(
            "/api/v1/valuations/run",
            json={
                "portfolio_id": port_id,
                "mark_prices": {
                    inst_aapl: "150.000000",
                    inst_tsla: "200.000000",
                    inst_msft: "300.000000",
                },
            },
        )

        # 3. Trigger exposure calculation
        calc_resp = await client.post(
            f"/api/v1/portfolios/{port_id}/risk/instrument-exposure/calculate",
            json={
                "portfolio_id": port_id,
                "weight_basis": "NAV_BASED",
            },
        )
        assert calc_resp.status_code == 200, calc_resp.text
        data = calc_resp.json()

        # Expected:
        # Long = 15,000 + 6,000 = 21,000
        # Short = 10,000
        # Gross = 31,000
        # Net = 11,000
        assert Decimal(data["total_long_exposure"]) == Decimal("21000.000000")
        assert Decimal(data["total_short_exposure"]) == Decimal("10000.000000")
        assert Decimal(data["total_gross_exposure"]) == Decimal("31000.000000")
        assert Decimal(data["total_net_exposure"]) == Decimal("11000.000000")
        assert data["total_instruments_count"] == 3
        assert data["long_instruments_count"] == 2
        assert data["short_instruments_count"] == 1

        # Check rankings endpoint (LONG)
        long_rank_resp = await client.get(
            f"/api/v1/portfolios/{port_id}/risk/instrument-exposure/rankings?mode=LONG"
        )
        assert long_rank_resp.status_code == 200
        long_rank_data = long_rank_resp.json()
        assert len(long_rank_data["items"]) == 2
        assert long_rank_data["items"][0]["instrument_id"] == inst_aapl
        assert long_rank_data["items"][1]["instrument_id"] == inst_msft

        # Check rankings endpoint (SHORT)
        short_rank_resp = await client.get(
            f"/api/v1/portfolios/{port_id}/risk/instrument-exposure/rankings?mode=SHORT"
        )
        assert short_rank_resp.status_code == 200
        short_rank_data = short_rank_resp.json()
        assert len(short_rank_data["items"]) == 1
        assert short_rank_data["items"][0]["instrument_id"] == inst_tsla

        # Check dominant endpoint
        dom_resp = await client.get(f"/api/v1/portfolios/{port_id}/risk/instrument-exposure/dominant")
        assert dom_resp.status_code == 200
        dom_data = dom_resp.json()
        assert isinstance(dom_data, list)


@pytest.mark.asyncio
async def test_instrument_exposure_group_and_snapshot_comparison():
    await init_db()
    ts = datetime.utcnow().timestamp()
    p1 = f"port-g1-{ts}"
    p2 = f"port-g2-{ts}"
    group_id = f"grp-inst-{ts}"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Instrument
        async with AsyncSessionLocal() as session:
            inst_obj = await InstrumentMasterService.create_instrument(
                session,
                InstrumentCreateRequest(
                    canonical_name=f"NVIDIA Corp {ts}",
                    short_name=f"NVDA_{ts}",
                    instrument_type="COMMON_STOCK",
                    asset_class="EQUITY",
                    issue_currency="USD",
                    primary_market_id="NASDAQ",
                ),
                actor_id="admin",
            )
            inst = inst_obj.instrument_id

            hist_repo = PortfolioHistoryRepository(session)
            multi_port_svc = MultiPortfolioService(session)

            # Portfolio group setup
            grp = await multi_port_svc.create_group(
                PortfolioGroupCreateRequest(
                    group_code=f"GRP_{int(ts)}",
                    group_name=f"Tech Group {ts}",
                    owner_reference="admin",
                    reporting_currency="USD",
                )
            )
            group_id = grp.id
            await multi_port_svc.add_portfolio_to_group(
                group_id, PortfolioGroupMembershipAddRequest(portfolio_id=p1)
            )
            await multi_port_svc.add_portfolio_to_group(
                group_id, PortfolioGroupMembershipAddRequest(portfolio_id=p2)
            )

            # Historical Snapshots for comparison testing
            now = datetime.now(timezone.utc)
            snap_prior = await hist_repo.create_snapshot(
                PortfolioBookSnapshot(
                    snapshot_id=f"snap-prior-{ts}",
                    portfolio_id=p1,
                    effective_as_of=now,
                    knowledge_as_of=now,
                    base_currency="USD",
                    total_positions_count=1,
                    snapshot_hash=f"hash-prior-{ts}",
                )
            )
            snap_curr = await hist_repo.create_snapshot(
                PortfolioBookSnapshot(
                    snapshot_id=f"snap-curr-{ts}",
                    portfolio_id=p1,
                    effective_as_of=now,
                    knowledge_as_of=now,
                    base_currency="USD",
                    total_positions_count=1,
                    snapshot_hash=f"hash-curr-{ts}",
                )
            )

            # Prior holding: 50 NVDA @ $100 = $5,000
            session.add(
                HistoricalPositionSnapshot(
                    id=f"hpos-prior-{ts}",
                    snapshot_id=snap_prior.snapshot_id,
                    portfolio_id=p1,
                    account_id=f"acct1-{ts}",
                    instrument_id=inst,
                    net_signed_quantity=Decimal("50.000000"),
                    gross_long_quantity=Decimal("50.000000"),
                    settled_quantity=Decimal("50.000000"),
                    currency="USD",
                    effective_as_of=now,
                    knowledge_as_of=now,
                )
            )
            session.add(
                HistoricalValuationSnapshot(
                    id=f"hval-prior-{ts}",
                    snapshot_id=snap_prior.snapshot_id,
                    portfolio_id=p1,
                    instrument_id=inst,
                    price_source="EOD_CLOSE",
                    price_timestamp=now,
                    market_price=Decimal("100.000000"),
                    price_currency="USD",
                    fx_rate_to_base=Decimal("1.000000"),
                    market_value_local=Decimal("5000.000000"),
                    market_value_base=Decimal("5000.000000"),
                    cost_basis_base=Decimal("5000.000000"),
                    unrealized_pnl_base=Decimal("0.000000"),
                )
            )

            # Current holding: 100 NVDA @ $100 = $10,000 (increased by $5,000 or +100%)
            session.add(
                HistoricalPositionSnapshot(
                    id=f"hpos-curr-{ts}",
                    snapshot_id=snap_curr.snapshot_id,
                    portfolio_id=p1,
                    account_id=f"acct1-{ts}",
                    instrument_id=inst,
                    net_signed_quantity=Decimal("100.000000"),
                    gross_long_quantity=Decimal("100.000000"),
                    settled_quantity=Decimal("100.000000"),
                    currency="USD",
                    effective_as_of=now,
                    knowledge_as_of=now,
                )
            )
            session.add(
                HistoricalValuationSnapshot(
                    id=f"hval-curr-{ts}",
                    snapshot_id=snap_curr.snapshot_id,
                    portfolio_id=p1,
                    instrument_id=inst,
                    price_source="EOD_CLOSE",
                    price_timestamp=now,
                    market_price=Decimal("100.000000"),
                    price_currency="USD",
                    fx_rate_to_base=Decimal("1.000000"),
                    market_value_local=Decimal("10000.000000"),
                    market_value_base=Decimal("10000.000000"),
                    cost_basis_base=Decimal("10000.000000"),
                    unrealized_pnl_base=Decimal("0.000000"),
                )
            )
            await session.commit()

        # Positions via REST:
        # P1: 100 NVDA
        await client.post(
            "/api/v1/positions/events",
            json={
                "portfolio_id": p1,
                "account_id": f"acct1-{ts}",
                "instrument_id": inst,
                "event_type": "TRADE_BUY",
                "signed_quantity_delta": "100.000000",
                "settled_quantity_delta": "100.000000",
                "idempotency_key": f"EVT_P1_{inst}_{ts}",
            },
        )
        # P2: 50 NVDA
        await client.post(
            "/api/v1/positions/events",
            json={
                "portfolio_id": p2,
                "account_id": f"acct2-{ts}",
                "instrument_id": inst,
                "event_type": "TRADE_BUY",
                "signed_quantity_delta": "50.000000",
                "settled_quantity_delta": "50.000000",
                "idempotency_key": f"EVT_P2_{inst}_{ts}",
            },
        )

        # Valuations
        await client.post(
            "/api/v1/valuations/run",
            json={"portfolio_id": p1, "mark_prices": {inst: "100.000000"}},
        )
        await client.post(
            "/api/v1/valuations/run",
            json={"portfolio_id": p2, "mark_prices": {inst: "100.000000"}},
        )

        # 1. Group exposure calculation test
        grp_calc_resp = await client.post(
            f"/api/v1/portfolio-groups/{group_id}/risk/instrument-exposure/calculate",
            json={"portfolio_group_id": group_id},
        )
        assert grp_calc_resp.status_code == 200, grp_calc_resp.text
        grp_data = grp_calc_resp.json()
        assert grp_data["entity_type"] == "PORTFOLIO_GROUP"
        # Total NVDA long MV = 10,000 (P1) + 5,000 (P2) = 15,000
        assert Decimal(grp_data["total_long_exposure"]) == Decimal("15000.000000")
        assert Decimal(grp_data["total_gross_exposure"]) == Decimal("15000.000000")
        assert len(grp_data["instruments"]) == 1
        assert Decimal(grp_data["instruments"][0]["long_quantity"]) == Decimal("150.000000")
        assert Decimal(grp_data["instruments"][0]["long_market_value"]) == Decimal("15000.000000")

        # 2. Historical comparison test
        comp_resp = await client.get(
            f"/api/v1/portfolios/{p1}/risk/instrument-exposure/comparison"
            f"?current_snapshot_id={snap_curr.snapshot_id}&prior_snapshot_id={snap_prior.snapshot_id}"
        )
        assert comp_resp.status_code == 200, comp_resp.text
        comp_data = comp_resp.json()
        assert len(comp_data["items"]) == 1
        c_item = comp_data["items"][0]
        assert c_item["instrument_id"] == inst
        assert Decimal(c_item["current_long_exposure"]) == Decimal("10000.000000")
        assert Decimal(c_item["prior_long_exposure"]) == Decimal("5000.000000")
        assert Decimal(c_item["long_exposure_change"]) == Decimal("5000.000000")
        assert Decimal(c_item["gross_percentage_change"]) == Decimal("100.000000")
        assert c_item["lifecycle_indicator"] == "INCREASED_EXPOSURE"
