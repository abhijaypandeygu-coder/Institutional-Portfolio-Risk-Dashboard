"""
M05.07 - Portfolio History Integration & Verification Tests.
Tests bitemporal querying (Query A vs Query B), snapshot capture & restatement,
chronological timeline indexing, and immutable risk run manifests.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.core.database import init_db
from backend.app.modules.portfolio_management.portfolio_history.models import (
    SnapshotType,
    ChangeEventCategory,
)
from backend.app.modules.portfolio_management.portfolio_history.schemas import (
    PortfolioBookSnapshotCreateRequest,
    HistoricalPositionItemSchema,
    HistoricalCashItemSchema,
    HistoricalValuationItemSchema,
    SnapshotSourceManifestSchema,
    PortfolioChangeRecordCreateRequest,
    BitemporalStateQueryRequest,
    RiskRunInputManifestCreateRequest,
)
from backend.app.modules.portfolio_management.portfolio_history.services.service import (
    PortfolioHistoryService,
)


@pytest.mark.asyncio
async def test_portfolio_history_bitemporal_and_snapshots():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        portfolio_id = f"PORT-HIST-SNAP-{datetime.utcnow().timestamp()}"
        t0_eff = datetime(2026, 10, 1, 16, 0, 0)
        t0_know = datetime(2026, 10, 1, 17, 0, 0)

        # 1. Capture initial EOD snapshot at T0 knowledge time
        snap1_payload = {
            "portfolio_id": portfolio_id,
            "snapshot_type": "EOD",
            "effective_as_of": t0_eff.isoformat(),
            "knowledge_as_of": t0_know.isoformat(),
            "base_currency": "USD",
            "positions": [
                {
                    "account_id": "ACC-01",
                    "instrument_id": "INST-AAPL",
                    "net_signed_quantity": "100.000000",
                    "gross_long_quantity": "100.000000",
                    "gross_short_quantity": "0.000000",
                    "settled_quantity": "100.000000",
                    "available_quantity": "100.000000",
                    "currency": "USD",
                    "cost_basis_amount": "15000.000000",
                    "cost_basis_base": "15000.000000",
                    "market_price": "160.000000",
                    "market_value_base": "16000.000000",
                    "unrealized_pnl_base": "1000.000000",
                    "effective_as_of": t0_eff.isoformat(),
                    "knowledge_as_of": t0_know.isoformat(),
                }
            ],
            "cash_balances": [
                {
                    "account_id": "ACC-01",
                    "currency": "USD",
                    "settled_cash": "25000.000000",
                    "available_cash": "25000.000000",
                    "fx_rate_to_base": "1.000000",
                    "available_cash_base": "25000.000000",
                    "effective_as_of": t0_eff.isoformat(),
                    "knowledge_as_of": t0_know.isoformat(),
                }
            ],
            "valuations": [
                {
                    "instrument_id": "INST-AAPL",
                    "price_source": "EOD_OFFICIAL",
                    "price_timestamp": t0_eff.isoformat(),
                    "market_price": "160.000000",
                    "price_currency": "USD",
                    "fx_rate_to_base": "1.000000",
                    "market_value_local": "16000.000000",
                    "market_value_base": "16000.000000",
                    "cost_basis_base": "15000.000000",
                    "unrealized_pnl_base": "1000.000000",
                }
            ],
            "source_manifests": [
                {
                    "source_module": "M05.02_POSITIONS",
                    "records_count": 1,
                }
            ],
        }

        res1 = await client.post(f"/api/v1/portfolios/{portfolio_id}/history/snapshots", json=snap1_payload)
        assert res1.status_code == 201, res1.text
        snap1 = res1.json()
        assert snap1["snapshot_version"] == 1
        assert snap1["total_positions_count"] == 1
        assert Decimal(str(snap1["total_nav_base"])) == Decimal("41000.000000")
        assert snap1["is_restated"] is False

        # 2. Later, at T1 knowledge time (2 days later), a late trade correction arrives for T0: AAPL was actually 95 shares
        t1_know = datetime(2026, 10, 3, 10, 0, 0)
        snap2_restated_payload = dict(snap1_payload)
        snap2_restated_payload["snapshot_type"] = "RESTATED"
        snap2_restated_payload["knowledge_as_of"] = t1_know.isoformat()
        snap2_restated_payload["superseded_snapshot_id"] = snap1["snapshot_id"]
        snap2_restated_payload["restatement_reason"] = "Late broker trade break resolution"
        snap2_restated_payload["positions"][0]["net_signed_quantity"] = "95.000000"
        snap2_restated_payload["positions"][0]["market_value_base"] = "15200.000000"

        res2 = await client.post(f"/api/v1/portfolios/{portfolio_id}/history/snapshots", json=snap2_restated_payload)
        assert res2.status_code == 201, res2.text
        snap2 = res2.json()
        assert snap2["snapshot_version"] == 2
        assert snap2["is_restated"] is True
        assert snap2["superseded_snapshot_id"] == snap1["snapshot_id"]

        # 3. Query B (Historical Knowledge State): Ask what was known at T0 knowledge time
        # Must return the ORIGINAL snapshot with 100 shares!
        query_b_req = {
            "portfolio_id": portfolio_id,
            "effective_as_of": t0_eff.isoformat(),
            "knowledge_as_of": t0_know.isoformat(),
        }
        res_b = await client.post(f"/api/v1/portfolios/{portfolio_id}/history/query-as-of", json=query_b_req)
        assert res_b.status_code == 200, res_b.text
        data_b = res_b.json()
        assert data_b["query_type"] == "QUERY_B_POINT_IN_TIME_KNOWLEDGE"
        assert data_b["matched_snapshot_id"] == snap1["snapshot_id"]
        assert Decimal(str(data_b["positions"][0]["net_signed_quantity"])) == Decimal("100.000000")

        # 4. Query A (Effective Time State with Latest Knowledge): Ask what is the best known state for T0 today
        # Must return the RESTATED snapshot with 95 shares!
        query_a_req = {
            "portfolio_id": portfolio_id,
            "effective_as_of": t0_eff.isoformat(),
            "knowledge_as_of": None,  # Latest knowledge
        }
        res_a = await client.post(f"/api/v1/portfolios/{portfolio_id}/history/query-as-of", json=query_a_req)
        assert res_a.status_code == 200, res_a.text
        data_a = res_a.json()
        assert data_a["query_type"] == "QUERY_A_LATEST_KNOWLEDGE"
        assert data_a["matched_snapshot_id"] == snap2["snapshot_id"]
        assert Decimal(str(data_a["positions"][0]["net_signed_quantity"])) == Decimal("95.000000")


@pytest.mark.asyncio
async def test_portfolio_change_timeline_and_risk_manifest():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        portfolio_id = f"PORT-HIST-TIMELINE-{datetime.utcnow().timestamp()}"
        now = datetime.utcnow()

        # 1. Record chronological events
        event1 = {
            "portfolio_id": portfolio_id,
            "event_category": "TRADE",
            "source_module": "M05.05_TRANSACTIONS",
            "source_event_id": "TXN-1001",
            "effective_at": (now - timedelta(hours=2)).isoformat(),
            "recorded_at": (now - timedelta(hours=2)).isoformat(),
            "instrument_id": "INST-MSFT",
            "account_id": "ACC-01",
            "quantity_delta": "50.000000",
            "cash_delta": "-15000.000000",
            "currency": "USD",
            "change_description": "Bought 50 shares of MSFT at 300.00 USD",
        }
        res_e1 = await client.post(f"/api/v1/portfolios/{portfolio_id}/history/timeline", json=event1)
        assert res_e1.status_code == 201, res_e1.text
        e1_data = res_e1.json()
        assert e1_data["sequence_number"] == 1

        event2 = {
            "portfolio_id": portfolio_id,
            "event_category": "DIVIDEND_CASH",
            "source_module": "M04.03_CORPORATE_ACTIONS",
            "source_event_id": "DIV-2001",
            "effective_at": (now - timedelta(hours=1)).isoformat(),
            "recorded_at": (now - timedelta(hours=1)).isoformat(),
            "instrument_id": "INST-MSFT",
            "account_id": "ACC-01",
            "cash_delta": "150.000000",
            "currency": "USD",
            "change_description": "Cash dividend received on MSFT holdings",
        }
        res_e2 = await client.post(f"/api/v1/portfolios/{portfolio_id}/history/timeline", json=event2)
        assert res_e2.status_code == 201
        assert res_e2.json()["sequence_number"] == 2

        # 2. Retrieve chronological timeline
        res_timeline = await client.get(f"/api/v1/portfolios/{portfolio_id}/history/timeline")
        assert res_timeline.status_code == 200
        timeline_list = res_timeline.json()
        assert len(timeline_list) >= 2
        assert timeline_list[0]["source_event_id"] == "TXN-1001"
        assert timeline_list[1]["source_event_id"] == "DIV-2001"

        # 3. Capture an EOD snapshot for PORT-HIST-002
        snap_req = {
            "portfolio_id": portfolio_id,
            "snapshot_type": "EOD",
            "effective_as_of": now.isoformat(),
            "base_currency": "USD",
            "positions": [
                {
                    "account_id": "ACC-01",
                    "instrument_id": "INST-MSFT",
                    "net_signed_quantity": "50.000000",
                    "currency": "USD",
                    "market_value_base": "16500.000000",
                    "effective_as_of": now.isoformat(),
                    "knowledge_as_of": now.isoformat(),
                }
            ],
            "cash_balances": [
                {
                    "account_id": "ACC-01",
                    "currency": "USD",
                    "settled_cash": "35150.000000",
                    "available_cash": "35150.000000",
                    "available_cash_base": "35150.000000",
                    "effective_as_of": now.isoformat(),
                    "knowledge_as_of": now.isoformat(),
                }
            ],
            "valuations": [],
            "source_manifests": [],
        }
        snap_res = await client.post(f"/api/v1/portfolios/{portfolio_id}/history/snapshots", json=snap_req)
        assert snap_res.status_code == 201
        snapshot = snap_res.json()

        # 4. Generate Risk Run Input Manifest
        manifest_req = {
            "portfolio_id": portfolio_id,
            "risk_run_id": "RUN-VAR-99-DAILY",
            "snapshot_id": snapshot["snapshot_id"],
            "market_data_partition_id": "PART-2026-10-US-EOD",
            "pricing_policy_version": "POL-US-CLOSE-V2",
            "fx_rate_table_version": "FX-OFFICIAL-EOD-202610",
            "corporate_action_version": "CA-V4",
        }
        res_m = await client.post(f"/api/v1/portfolios/{portfolio_id}/history/risk-manifests", json=manifest_req)
        assert res_m.status_code == 201, res_m.text
        m_data = res_m.json()
        assert m_data["manifest_id"].startswith("RMAN-")
        assert len(m_data["manifest_hash"]) == 64
        assert m_data["positions_count"] == 1
        assert Decimal(str(m_data["total_nav_base"])) == Decimal("51650.000000")

        # 5. Retrieve Risk Manifest
        res_get_m = await client.get(f"/api/v1/portfolios/{portfolio_id}/history/risk-manifests/{m_data['manifest_id']}")
        assert res_get_m.status_code == 200
        assert res_get_m.json()["manifest_hash"] == m_data["manifest_hash"]
