"""Comprehensive test suite for M05.02 - Position Management."""
import uuid
from datetime import datetime, date
from decimal import Decimal
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db, AsyncSessionLocal
from backend.app.modules.instrument_reference_data.instrument_master.services.service import InstrumentMasterService
from backend.app.modules.instrument_reference_data.instrument_master.schemas import InstrumentCreateRequest
from backend.app.modules.portfolio_management.portfolio_creation.services.service import PortfolioCreationService
from backend.app.modules.portfolio_management.portfolio_creation.schemas import PortfolioCreateRequest
from backend.app.modules.portfolio_management.position_management.models import (
    PositionSide,
    PositionStatus,
    PositionEventType,
    TransferStatus,
    BorrowStatus,
    ReconciliationStatus,
)


@pytest.fixture(autouse=True)
async def setup_database():
    await init_db()
    yield


@pytest.fixture
async def setup_portfolio_and_instrument():
    async with AsyncSessionLocal() as session:
        rand_id = uuid.uuid4().hex[:6].upper()
        # 1. Create Instrument
        inst = await InstrumentMasterService.create_instrument(
            session,
            InstrumentCreateRequest(
                canonical_name=f"Position Test Asset {rand_id}",
                short_name=f"POS_{rand_id}",
                instrument_type="COMMON_STOCK",
                asset_class="EQUITY",
                issue_currency="USD",
            ),
            actor_id="admin",
        )

        # 2. Create Portfolio
        pf_service = PortfolioCreationService(session)
        pf = await pf_service.create_portfolio(
            PortfolioCreateRequest(
                portfolio_code=f"PF_POS_{rand_id}",
                portfolio_name=f"Position Test Fund {rand_id}",
                short_name=f"PF_{rand_id}",
                base_currency="USD",
            ),
            actor_id="admin",
        )
        return pf.portfolio_id, inst.instrument_id


@pytest.mark.asyncio
async def test_long_position_lifecycle(setup_portfolio_and_instrument):
    """Test positive long position: buy -> increase -> partial sell -> full close."""
    portfolio_id, instrument_id = setup_portfolio_and_instrument
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        account_id = "ACC_LONG_01"

        # 1. Buy 100 shares (unsettled)
        res_buy = await client.post("/api/v1/positions/events", json={
            "portfolio_id": portfolio_id,
            "account_id": account_id,
            "instrument_id": instrument_id,
            "event_type": "TRADE_BUY",
            "signed_quantity_delta": "100.0",
            "unsettled_quantity_delta": "100.0",
            "idempotency_key": f"BUY_{uuid.uuid4().hex}",
            "transaction_reference": "TR_001",
        })
        assert res_buy.status_code == 201
        snap1 = res_buy.json()
        assert snap1["position_side"] == "LONG"
        assert Decimal(snap1["net_signed_quantity"]) == Decimal("100.0")
        assert Decimal(snap1["gross_long_quantity"]) == Decimal("100.0")
        assert Decimal(snap1["gross_short_quantity"]) == Decimal("0.0")
        assert Decimal(snap1["settled_quantity"]) == Decimal("0.0")
        assert Decimal(snap1["unsettled_quantity"]) == Decimal("100.0")
        position_id = snap1["position_id"]

        # 2. Settlement event: 100 shares settle
        res_set = await client.post("/api/v1/positions/events", json={
            "portfolio_id": portfolio_id,
            "account_id": account_id,
            "instrument_id": instrument_id,
            "event_type": "SETTLEMENT",
            "signed_quantity_delta": "0.0",
            "settled_quantity_delta": "100.0",
            "unsettled_quantity_delta": "-100.0",
            "idempotency_key": f"SET_{uuid.uuid4().hex}",
            "transaction_reference": "TR_001",
        })
        assert res_set.status_code == 201
        snap2 = res_set.json()
        assert Decimal(snap2["net_signed_quantity"]) == Decimal("100.0")
        assert Decimal(snap2["settled_quantity"]) == Decimal("100.0")
        assert Decimal(snap2["unsettled_quantity"]) == Decimal("0.0")
        assert Decimal(snap2["available_quantity"]) == Decimal("100.0")

        # 3. Partial sell of 40 shares
        res_sell = await client.post("/api/v1/positions/events", json={
            "portfolio_id": portfolio_id,
            "account_id": account_id,
            "instrument_id": instrument_id,
            "event_type": "TRADE_SELL",
            "signed_quantity_delta": "-40.0",
            "settled_quantity_delta": "-40.0",
            "idempotency_key": f"SELL_{uuid.uuid4().hex}",
        })
        assert res_sell.status_code == 201
        snap3 = res_sell.json()
        assert Decimal(snap3["net_signed_quantity"]) == Decimal("60.0")
        assert Decimal(snap3["gross_long_quantity"]) == Decimal("60.0")
        assert snap3["position_side"] == "LONG"

        # 4. Sell remaining 60 shares -> FLAT / CLOSED
        res_close = await client.post("/api/v1/positions/events", json={
            "portfolio_id": portfolio_id,
            "account_id": account_id,
            "instrument_id": instrument_id,
            "event_type": "TRADE_SELL",
            "signed_quantity_delta": "-60.0",
            "settled_quantity_delta": "-60.0",
            "idempotency_key": f"CLOSE_{uuid.uuid4().hex}",
        })
        assert res_close.status_code == 201
        snap4 = res_close.json()
        assert Decimal(snap4["net_signed_quantity"]) == Decimal("0.0")
        assert snap4["position_side"] == "FLAT"


@pytest.mark.asyncio
async def test_short_position_and_borrow_metadata(setup_portfolio_and_instrument):
    """Test explicit negative short position: short open -> borrow metadata -> short cover."""
    portfolio_id, instrument_id = setup_portfolio_and_instrument
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        account_id = "ACC_SHORT_01"

        # 1. Short Open: -50 shares
        res_short = await client.post("/api/v1/positions/events", json={
            "portfolio_id": portfolio_id,
            "account_id": account_id,
            "instrument_id": instrument_id,
            "event_type": "SHORT_OPEN",
            "signed_quantity_delta": "-50.0",
            "settled_quantity_delta": "-50.0",
            "idempotency_key": f"SHORT_{uuid.uuid4().hex}",
        })
        assert res_short.status_code == 201
        snap = res_short.json()
        assert snap["position_side"] == "SHORT"
        assert Decimal(snap["net_signed_quantity"]) == Decimal("-50.0")
        assert Decimal(snap["gross_short_quantity"]) == Decimal("50.0")
        assert Decimal(snap["gross_long_quantity"]) == Decimal("0.0")
        position_id = snap["position_id"]

        # 2. Attach Borrow Metadata
        res_borrow = await client.post(f"/api/v1/positions/{position_id}/borrow", json={
            "lender_reference": "MORGAN_STANLEY_PRIME",
            "locate_reference": "LOC_998822",
            "borrowed_quantity": "50.0",
            "borrow_rate_annual_pct": "0.0150",
            "borrow_status": "APPROVED",
            "effective_date": "2026-04-01",
        })
        assert res_borrow.status_code == 201
        brw_data = res_borrow.json()
        assert brw_data["lender_reference"] == "MORGAN_STANLEY_PRIME"
        assert Decimal(brw_data["borrowed_quantity"]) == Decimal("50.0")

        # 3. Short Cover: +50 shares -> FLAT
        res_cover = await client.post("/api/v1/positions/events", json={
            "portfolio_id": portfolio_id,
            "account_id": account_id,
            "instrument_id": instrument_id,
            "event_type": "SHORT_COVER",
            "signed_quantity_delta": "50.0",
            "settled_quantity_delta": "50.0",
            "idempotency_key": f"COVER_{uuid.uuid4().hex}",
        })
        assert res_cover.status_code == 201
        snap_cover = res_cover.json()
        assert Decimal(snap_cover["net_signed_quantity"]) == Decimal("0.0")
        assert snap_cover["position_side"] == "FLAT"


@pytest.mark.asyncio
async def test_inter_account_transfer(setup_portfolio_and_instrument):
    """Verify internal transfer between two accounts within a portfolio."""
    portfolio_id, instrument_id = setup_portfolio_and_instrument
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        acc_a = "ACC_ALPHA"
        acc_b = "ACC_BETA"

        # 1. Establish initial 100 shares in Account A
        await client.post("/api/v1/positions/events", json={
            "portfolio_id": portfolio_id,
            "account_id": acc_a,
            "instrument_id": instrument_id,
            "event_type": "TRADE_BUY",
            "signed_quantity_delta": "100.0",
            "settled_quantity_delta": "100.0",
            "idempotency_key": f"INIT_{uuid.uuid4().hex}",
        })

        # 2. Transfer 40 shares from Account A to Account B
        res_trf = await client.post("/api/v1/positions/transfers", json={
            "source_portfolio_id": portfolio_id,
            "source_account_id": acc_a,
            "destination_portfolio_id": portfolio_id,
            "destination_account_id": acc_b,
            "instrument_id": instrument_id,
            "quantity": "40.0",
            "transfer_reason": "Rebalancing sleeve capital",
        })
        assert res_trf.status_code == 201
        trf_data = res_trf.json()
        assert trf_data["transfer_status"] == "COMPLETED"

        # 3. Check Account A position (60.0)
        book_a = (await client.post("/api/v1/positions/", json={
            "portfolio_id": portfolio_id,
            "account_id": acc_a,
            "instrument_id": instrument_id,
        })).json()
        snap_a = (await client.get(f"/api/v1/positions/{book_a['position_id']}/snapshot")).json()
        assert Decimal(snap_a["net_signed_quantity"]) == Decimal("60.0")

        # 4. Check Account B position (40.0)
        book_b = (await client.post("/api/v1/positions/", json={
            "portfolio_id": portfolio_id,
            "account_id": acc_b,
            "instrument_id": instrument_id,
        })).json()
        snap_b = (await client.get(f"/api/v1/positions/{book_b['position_id']}/snapshot")).json()
        assert Decimal(snap_b["net_signed_quantity"]) == Decimal("40.0")


@pytest.mark.asyncio
async def test_portfolio_aggregation_preserves_gross(setup_portfolio_and_instrument):
    """Verify portfolio aggregate preserves gross long and gross short when one account is long and another is short."""
    portfolio_id, instrument_id = setup_portfolio_and_instrument
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        acc_long = "ACC_LONG_SLEEVE"
        acc_short = "ACC_SHORT_SLEEVE"

        # Account 1: +100 Long
        await client.post("/api/v1/positions/events", json={
            "portfolio_id": portfolio_id,
            "account_id": acc_long,
            "instrument_id": instrument_id,
            "event_type": "TRADE_BUY",
            "signed_quantity_delta": "100.0",
            "settled_quantity_delta": "100.0",
            "idempotency_key": f"BUY_{uuid.uuid4().hex}",
        })

        # Account 2: -40 Short
        await client.post("/api/v1/positions/events", json={
            "portfolio_id": portfolio_id,
            "account_id": acc_short,
            "instrument_id": instrument_id,
            "event_type": "SHORT_OPEN",
            "signed_quantity_delta": "-40.0",
            "settled_quantity_delta": "-40.0",
            "idempotency_key": f"SHORT_{uuid.uuid4().hex}",
        })

        # Fetch Portfolio Aggregates
        res_agg = await client.get(f"/api/v1/positions/portfolios/{portfolio_id}/aggregates")
        assert res_agg.status_code == 200
        aggs = res_agg.json()
        assert len(aggs) >= 1
        agg = aggs[0]
        # Net = +60, Gross Long = 100, Gross Short = 40
        assert Decimal(agg["net_signed_quantity"]) == Decimal("60.0")
        assert Decimal(agg["gross_long_quantity"]) == Decimal("100.0")
        assert Decimal(agg["gross_short_quantity"]) == Decimal("40.0")
        assert agg["contributing_account_count"] == 2


@pytest.mark.asyncio
async def test_corporate_action_split_and_rebuild(setup_portfolio_and_instrument):
    """Verify stock split adjustment and deterministic position rebuild from immutable ledger."""
    portfolio_id, instrument_id = setup_portfolio_and_instrument
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        account_id = "ACC_SPLIT_01"

        # 1. Buy 50 shares
        res_buy = await client.post("/api/v1/positions/events", json={
            "portfolio_id": portfolio_id,
            "account_id": account_id,
            "instrument_id": instrument_id,
            "event_type": "TRADE_BUY",
            "signed_quantity_delta": "50.0",
            "settled_quantity_delta": "50.0",
            "idempotency_key": f"BUY_{uuid.uuid4().hex}",
        })
        position_id = res_buy.json()["position_id"]

        # 2. 2-for-1 Split event: +50 additional shares
        res_split = await client.post("/api/v1/positions/events", json={
            "portfolio_id": portfolio_id,
            "account_id": account_id,
            "instrument_id": instrument_id,
            "event_type": "STOCK_SPLIT",
            "signed_quantity_delta": "50.0",
            "settled_quantity_delta": "50.0",
            "corporate_action_reference": "CA_SPLIT_2_FOR_1",
            "idempotency_key": f"SPLIT_{uuid.uuid4().hex}",
        })
        assert res_split.status_code == 201
        assert Decimal(res_split.json()["net_signed_quantity"]) == Decimal("100.0")

        # 3. Deterministic Rebuild of position history from event ledger
        res_rb = await client.post(f"/api/v1/positions/{position_id}/rebuild")
        assert res_rb.status_code == 200
        snap_rb = res_rb.json()
        assert Decimal(snap_rb["net_signed_quantity"]) == Decimal("100.0")
        assert snap_rb["position_side"] == "LONG"


@pytest.mark.asyncio
async def test_position_reconciliation_and_idempotency(setup_portfolio_and_instrument):
    """Verify broker reconciliation discrepancy detection and event idempotency."""
    portfolio_id, instrument_id = setup_portfolio_and_instrument
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        account_id = "ACC_REC_01"

        # 1. Buy 100 shares
        idemp = f"IDEMP_REC_{uuid.uuid4().hex}"
        res1 = await client.post("/api/v1/positions/events", json={
            "portfolio_id": portfolio_id,
            "account_id": account_id,
            "instrument_id": instrument_id,
            "event_type": "TRADE_BUY",
            "signed_quantity_delta": "100.0",
            "settled_quantity_delta": "100.0",
            "idempotency_key": idemp,
        })
        assert res1.status_code == 201
        snap1 = res1.json()

        # Duplicate delivery must be idempotent
        res_dup = await client.post("/api/v1/positions/events", json={
            "portfolio_id": portfolio_id,
            "account_id": account_id,
            "instrument_id": instrument_id,
            "event_type": "TRADE_BUY",
            "signed_quantity_delta": "100.0",
            "settled_quantity_delta": "100.0",
            "idempotency_key": idemp,
        })
        assert res_dup.status_code == 201
        assert res_dup.json()["snapshot_id"] == snap1["snapshot_id"]

        # 2. Reconciliation with External Broker (external says 90 instead of 100)
        res_rec = await client.post("/api/v1/positions/reconciliation", json={
            "portfolio_id": portfolio_id,
            "account_id": account_id,
            "instrument_id": instrument_id,
            "external_quantity": "90.0",
            "source_name": "INTERACTIVE_BROKERS",
            "as_of_date": "2026-04-01",
        })
        assert res_rec.status_code == 201
        rec_data = res_rec.json()
        assert rec_data["reconciliation_status"] == "QUANTITY_MISMATCH"
        assert Decimal(rec_data["difference_quantity"]) == Decimal("10.0")

