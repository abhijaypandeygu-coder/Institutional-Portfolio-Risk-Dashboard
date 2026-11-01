"""Comprehensive test suite for M05.03 - Position Valuation."""
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
from backend.app.modules.portfolio_management.position_management.models import PositionSide, PositionEventType
from backend.app.modules.portfolio_management.position_management.services.service import PositionManagementService
from backend.app.modules.portfolio_management.position_management.schemas import PositionEventRegisterRequest
from backend.app.modules.portfolio_management.position_valuation.models import ValuationStatus, AccountingMethod
from backend.app.modules.portfolio_management.position_valuation.services.service import PositionValuationService


@pytest.fixture(autouse=True)
async def setup_database():
    await init_db()
    yield


@pytest.fixture
async def setup_valuation_fixture():
    async with AsyncSessionLocal() as session:
        rand_id = uuid.uuid4().hex[:6].upper()
        # 1. Create Instrument
        inst = await InstrumentMasterService.create_instrument(
            session,
            InstrumentCreateRequest(
                canonical_name=f"Valuation Test Asset {rand_id}",
                short_name=f"VAL_{rand_id}",
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
                portfolio_code=f"PF_VAL_{rand_id}",
                portfolio_name=f"Valuation Fund {rand_id}",
                short_name=f"PF_{rand_id}",
                base_currency="USD",
            ),
            actor_id="admin",
        )
        return pf.portfolio_id, inst.instrument_id


@pytest.mark.asyncio
async def test_long_position_market_value_and_unrealized_pnl(setup_valuation_fixture):
    """
    Verify long position valuation:
    Buy 100 shares at $100 (Cost Basis = $10,000)
    Mark Price = $120
    Signed Market Value = +$12,000
    Signed Unrealized P&L = +$2,000 (+20%)
    """
    portfolio_id, instrument_id = setup_valuation_fixture
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        account_id = "ACC_VAL_LONG"

        # 1. Ingest Trade Buy via M05.02
        await client.post("/api/v1/positions/events", json={
            "portfolio_id": portfolio_id,
            "account_id": account_id,
            "instrument_id": instrument_id,
            "event_type": "TRADE_BUY",
            "signed_quantity_delta": "100.0",
            "settled_quantity_delta": "100.0",
            "idempotency_key": f"BUY_{uuid.uuid4().hex}",
        })

        # 2. Record Acquisition Lot in M05.03
        async with AsyncSessionLocal() as session:
            val_svc = PositionValuationService(session)
            await val_svc.record_acquisition_lot(
                portfolio_id=portfolio_id,
                account_id=account_id,
                instrument_id=instrument_id,
                listing_id=None,
                position_side=PositionSide.LONG,
                quantity=Decimal("100.0"),
                unit_price=Decimal("100.00"),
                currency="USD",
                effective_at=datetime.utcnow(),
            )

        # 3. Run Valuation at Mark Price = $120.00
        res_val = await client.post("/api/v1/valuations/run", json={
            "portfolio_id": portfolio_id,
            "mark_prices": {instrument_id: "120.00"},
        })
        assert res_val.status_code == 201
        summary = res_val.json()
        assert Decimal(summary["gross_long_market_value"]) == Decimal("12000.0")
        assert Decimal(summary["gross_short_market_value"]) == Decimal("0.0")
        assert Decimal(summary["net_market_value"]) == Decimal("12000.0")
        assert Decimal(summary["total_cost_basis"]) == Decimal("10000.0")
        assert Decimal(summary["total_unrealized_pnl"]) == Decimal("2000.0")

        # 4. Check Individual Position Valuation endpoint
        res_pos = await client.get(f"/api/v1/valuations/portfolios/{portfolio_id}/positions/{instrument_id}")
        assert res_pos.status_code == 200
        pv = res_pos.json()
        assert Decimal(pv["signed_quantity"]) == Decimal("100.0")
        assert Decimal(pv["signed_market_value_base"]) == Decimal("12000.0")
        assert Decimal(pv["signed_cost_basis_base"]) == Decimal("10000.0")
        assert Decimal(pv["unrealized_pnl_base"]) == Decimal("2000.0")
        assert Decimal(pv["unrealized_pnl_pct"]) == Decimal("20.0000")


@pytest.mark.asyncio
async def test_short_position_market_value_and_unrealized_pnl(setup_valuation_fixture):
    """
    Verify short position signed conventions:
    Short sell 100 shares at $100 -> Signed Qty = -100
    Remaining Opening Proceeds (Signed Cost Basis) = -$10,000
    Case A: Mark = $90 (Profit)
      Signed Market Value = -100 * $90 = -$9,000
      Signed Unrealized P&L = -$9,000 - (-$10,000) = +$1,000
    Case B: Mark = $110 (Loss)
      Signed Market Value = -100 * $110 = -$11,000
      Signed Unrealized P&L = -$11,000 - (-$10,000) = -$1,000
    """
    portfolio_id, instrument_id = setup_valuation_fixture
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        account_id = "ACC_VAL_SHORT"

        # 1. Ingest Short Open via M05.02
        await client.post("/api/v1/positions/events", json={
            "portfolio_id": portfolio_id,
            "account_id": account_id,
            "instrument_id": instrument_id,
            "event_type": "SHORT_OPEN",
            "signed_quantity_delta": "-100.0",
            "settled_quantity_delta": "-100.0",
            "idempotency_key": f"SHORT_{uuid.uuid4().hex}",
        })

        # 2. Record Short Opening Proceeds Lot
        async with AsyncSessionLocal() as session:
            val_svc = PositionValuationService(session)
            await val_svc.record_acquisition_lot(
                portfolio_id=portfolio_id,
                account_id=account_id,
                instrument_id=instrument_id,
                listing_id=None,
                position_side=PositionSide.SHORT,
                quantity=Decimal("100.0"),
                unit_price=Decimal("100.00"),
                currency="USD",
                effective_at=datetime.utcnow(),
            )

        # 3. Case A: Mark Price falls to $90.00 (Short Profit)
        res_a = await client.post("/api/v1/valuations/run", json={
            "portfolio_id": portfolio_id,
            "mark_prices": {instrument_id: "90.00"},
        })
        assert res_a.status_code == 201
        sum_a = res_a.json()
        assert Decimal(sum_a["gross_short_market_value"]) == Decimal("9000.0")
        assert Decimal(sum_a["net_market_value"]) == Decimal("-9000.0")
        assert Decimal(sum_a["total_unrealized_pnl"]) == Decimal("1000.0")

        # 4. Case B: Mark Price rises to $110.00 (Short Loss)
        res_b = await client.post("/api/v1/valuations/run", json={
            "portfolio_id": portfolio_id,
            "mark_prices": {instrument_id: "110.00"},
        })
        assert res_b.status_code == 201
        sum_b = res_b.json()
        assert Decimal(sum_b["gross_short_market_value"]) == Decimal("11000.0")
        assert Decimal(sum_b["net_market_value"]) == Decimal("-11000.0")
        assert Decimal(sum_b["total_unrealized_pnl"]) == Decimal("-1000.0")


@pytest.mark.asyncio
async def test_realized_pnl_fifo_allocation(setup_valuation_fixture):
    """
    Verify FIFO cost basis allocation on partial sale:
    Lot 1: Buy 50 at $100 ($5,000)
    Lot 2: Buy 50 at $110 ($5,500)
    Sell 70 at $120 ($8,400 proceeds)
    FIFO Allocation:
    - 50 from Lot 1 @ $100: Basis $5,000, Proceeds $6,000 -> Realized P&L = +$1,000
    - 20 from Lot 2 @ $110: Basis $2,200, Proceeds $2,400 -> Realized P&L = +$200
    Total Realized P&L = +$1,200
    Remaining in Lot 2: 30 shares @ $110 = $3,300
    """
    portfolio_id, instrument_id = setup_valuation_fixture
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        account_id = "ACC_VAL_FIFO"

        # Record Lot 1 & Lot 2
        async with AsyncSessionLocal() as session:
            val_svc = PositionValuationService(session)
            await val_svc.record_acquisition_lot(
                portfolio_id=portfolio_id,
                account_id=account_id,
                instrument_id=instrument_id,
                listing_id=None,
                position_side=PositionSide.LONG,
                quantity=Decimal("50.0"),
                unit_price=Decimal("100.00"),
                currency="USD",
                effective_at=datetime(2026, 4, 1, 10, 0, 0),
            )
            await val_svc.record_acquisition_lot(
                portfolio_id=portfolio_id,
                account_id=account_id,
                instrument_id=instrument_id,
                listing_id=None,
                position_side=PositionSide.LONG,
                quantity=Decimal("50.0"),
                unit_price=Decimal("110.00"),
                currency="USD",
                effective_at=datetime(2026, 4, 1, 11, 0, 0),
            )

            # Allocate Closing Sale of 70 shares at $120
            allocations = await val_svc.allocate_closing_event(
                portfolio_id=portfolio_id,
                account_id=account_id,
                instrument_id=instrument_id,
                closing_event_id="EVT_SELL_70",
                closed_quantity=Decimal("70.0"),
                closing_unit_price=Decimal("120.00"),
                currency="USD",
                effective_at=datetime(2026, 4, 2, 14, 0, 0),
                position_side=PositionSide.LONG,
            )
            assert len(allocations) == 2
            assert allocations[0].closed_quantity == Decimal("50.0")
            assert allocations[0].realized_pnl_base == Decimal("1000.0")
            assert allocations[1].closed_quantity == Decimal("20.0")
            assert allocations[1].realized_pnl_base == Decimal("200.0")

        # Query Realized P&L endpoint
        res_pnl = await client.get(f"/api/v1/valuations/portfolios/{portfolio_id}/realized-pnl")
        assert res_pnl.status_code == 200
        allocs_json = res_pnl.json()
        assert len(allocs_json) == 2
        total_pnl = sum((Decimal(a["realized_pnl_base"]) for a in allocs_json), Decimal("0.0"))
        assert total_pnl == Decimal("1200.0")


@pytest.mark.asyncio
async def test_currency_conversion_valuation(setup_valuation_fixture):
    """
    Verify multi-currency valuation (INR position in USD portfolio):
    Hold 100 shares of Reliance @ ₹2,500 = ₹250,000 native
    FX Rate: 1 INR = 0.012 USD
    Market Value Base = ₹250,000 * 0.012 = $3,000 USD
    """
    portfolio_id, instrument_id = setup_valuation_fixture
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        account_id = "ACC_VAL_INR"

        # Ingest 100 shares
        await client.post("/api/v1/positions/events", json={
            "portfolio_id": portfolio_id,
            "account_id": account_id,
            "instrument_id": instrument_id,
            "event_type": "TRADE_BUY",
            "signed_quantity_delta": "100.0",
            "settled_quantity_delta": "100.0",
            "idempotency_key": f"BUY_INR_{uuid.uuid4().hex}",
        })

        # Record acquisition in INR
        async with AsyncSessionLocal() as session:
            val_svc = PositionValuationService(session)
            await val_svc.record_acquisition_lot(
                portfolio_id=portfolio_id,
                account_id=account_id,
                instrument_id=instrument_id,
                listing_id=None,
                position_side=PositionSide.LONG,
                quantity=Decimal("100.0"),
                unit_price=Decimal("2000.00"),
                currency="INR",
                effective_at=datetime.utcnow(),
                fx_rate_to_base=Decimal("0.012"), # ₹200,000 * 0.012 = $2,400 cost basis
            )

        # Run valuation: Mark Price = ₹2,500, FX Rate = 0.012
        res_val = await client.post("/api/v1/valuations/run", json={
            "portfolio_id": portfolio_id,
            "mark_prices": {instrument_id: "2500.00"},
            "fx_rates_to_base": {"INR": "0.012"},
        })
        assert res_val.status_code == 201
        sum_data = res_val.json()
        assert Decimal(sum_data["gross_long_market_value"]) == Decimal("3000.0")
        assert Decimal(sum_data["total_cost_basis"]) == Decimal("2400.0")
        assert Decimal(sum_data["total_unrealized_pnl"]) == Decimal("600.0")
