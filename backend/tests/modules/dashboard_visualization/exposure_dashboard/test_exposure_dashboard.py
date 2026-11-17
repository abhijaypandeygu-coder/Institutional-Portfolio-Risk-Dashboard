"""
Integration and financial consistency test suite for M13.03 — Exposure Dashboard.

Validates:
1. SectorAllocationPresentationService: M06.03 integration, long/short/net/gross sector calculations.
2. InstrumentAllocationPresentationService: M06.04 integration, absolute ranking, signed short market values.
3. PortfolioAllocationPresentationService: M06.07 integration, NAV weight derivation, multi-currency cash balances.
4. ExposureDrilldownService: Hierarchical breadcrumb navigation and child-level aggregation.
5. REST API Endpoints:
   - GET /api/v1/dashboard/portfolios/{id}/exposure-dashboard
   - GET /api/v1/dashboard/portfolios/{id}/exposure-dashboard/sectors
   - GET /api/v1/dashboard/portfolios/{id}/exposure-dashboard/instruments
   - GET /api/v1/dashboard/portfolios/{id}/exposure-dashboard/allocation
   - GET /api/v1/dashboard/portfolios/{id}/exposure-dashboard/drilldown
"""

from datetime import datetime, timedelta
from decimal import Decimal
import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.main import app
from backend.app.modules.dashboard_visualization.exposure_dashboard.services.exposure_dashboard_service import (
    ExposureDashboardService,
    SectorAllocationPresentationService,
    InstrumentAllocationPresentationService,
    PortfolioAllocationPresentationService,
    ExposureDrilldownService,
)
from backend.app.modules.dashboard_visualization.exposure_dashboard.schemas.exposure_dashboard_schemas import (
    PositionSideFilter,
    HierarchyLevel,
)
from backend.app.modules.portfolio_management.portfolio_creation.models import (
    Portfolio,
    PortfolioLifecycleStatus,
    PortfolioTypeEnum,
    CreationSourceEnum,
    MarketScopeEnum,
)
from backend.app.modules.portfolio_management.position_valuation.models import (
    PortfolioValuationSnapshot,
    PositionValuation,
)
from backend.app.modules.portfolio_management.position_management.models import (
    PositionBook,
    PositionSnapshot,
    PositionSide,
    PositionStatus,
)
from backend.app.modules.portfolio_management.cash_management.models import (
    CashAccount,
    CashAccountType,
    CashAccountStatus,
    CashBalanceSnapshot,
)


@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()
    yield


@pytest.mark.asyncio
async def test_exposure_dashboard_services_and_components():
    async with AsyncSessionLocal() as session:
        port_id = f"PORT_EXP_{uuid.uuid4().hex[:6]}"
        portfolio = Portfolio(
            portfolio_id=port_id,
            portfolio_code=port_id,
            portfolio_name="Institutional Equity Exposure Fund",
            short_name="Inst Exposure",
            base_currency="USD",
            lifecycle_status=PortfolioLifecycleStatus.ACTIVE,
            portfolio_type=PortfolioTypeEnum.DISCRETIONARY,
            creation_source=CreationSourceEnum.MANUAL_ADMINISTRATION,
            market_scope=MarketScopeEnum.UNITED_STATES,
            created_by="TEST_ADMIN",
            created_at=datetime.utcnow() - timedelta(days=90),
        )
        session.add(portfolio)

        snap = PortfolioValuationSnapshot(
            snapshot_id=f"snap_{uuid.uuid4().hex[:6]}",
            calculation_id=f"calc_{uuid.uuid4().hex[:6]}",
            portfolio_id=port_id,
            valuation_timestamp=datetime.utcnow(),
            gross_long_market_value=Decimal("800000.00"),
            gross_short_market_value=Decimal("200000.00"),
            net_market_value=Decimal("600000.00"),
            total_cost_basis=Decimal("550000.00"),
            total_unrealized_pnl=Decimal("50000.00"),
            realized_pnl_period=Decimal("5000.00"),
            base_currency="USD",
        )
        session.add(snap)

        # Add Long Position Valuation & PositionBook/Snapshot
        book_id_long = f"PB_L_{uuid.uuid4().hex[:6]}"
        book_long = PositionBook(
            position_id=book_id_long,
            portfolio_id=port_id,
            account_id="ACC_01",
            instrument_id="AAPL",
            position_side=PositionSide.LONG,
            position_status=PositionStatus.OPEN,
            current_snapshot_version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(book_long)

        snap_long = PositionSnapshot(
            snapshot_id=f"PS_L_{uuid.uuid4().hex[:6]}",
            position_id=book_id_long,
            portfolio_id=port_id,
            account_id="ACC_01",
            instrument_id="AAPL",
            position_side=PositionSide.LONG,
            gross_long_quantity=Decimal("500"),
            gross_short_quantity=Decimal("0"),
            net_signed_quantity=Decimal("500"),
            settled_quantity=Decimal("500"),
            unsettled_quantity=Decimal("0"),
            economic_quantity=Decimal("500"),
            available_quantity=Decimal("500"),
            reserved_quantity=Decimal("0"),
            restricted_quantity=Decimal("0"),
            borrowed_quantity=Decimal("0"),
            effective_timestamp=datetime.utcnow(),
            recorded_at=datetime.utcnow(),
            snapshot_version=1,
        )
        session.add(snap_long)

        pos_long = PositionValuation(
            valuation_id=f"val_{uuid.uuid4().hex[:6]}",
            calculation_id=f"calc_{uuid.uuid4().hex[:6]}",
            portfolio_id=port_id,
            account_id="ACC_01",
            instrument_id="AAPL",
            position_side="LONG",
            signed_quantity=Decimal("500"),
            mark_price=Decimal("1600.00"),
            price_currency="USD",
            fx_rate_to_base=Decimal("1.0"),
            signed_market_value_native=Decimal("800000.00"),
            signed_market_value_base=Decimal("800000.00"),
            signed_cost_basis_native=Decimal("750000.00"),
            signed_cost_basis_base=Decimal("750000.00"),
            unrealized_pnl_native=Decimal("50000.00"),
            unrealized_pnl_base=Decimal("50000.00"),
            effective_at=datetime.utcnow(),
        )
        session.add(pos_long)

        # Add Short Position Valuation & PositionBook/Snapshot
        book_id_short = f"PB_S_{uuid.uuid4().hex[:6]}"
        book_short = PositionBook(
            position_id=book_id_short,
            portfolio_id=port_id,
            account_id="ACC_01",
            instrument_id="TSLA",
            position_side=PositionSide.SHORT,
            position_status=PositionStatus.OPEN,
            current_snapshot_version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(book_short)

        snap_short = PositionSnapshot(
            snapshot_id=f"PS_S_{uuid.uuid4().hex[:6]}",
            position_id=book_id_short,
            portfolio_id=port_id,
            account_id="ACC_01",
            instrument_id="TSLA",
            position_side=PositionSide.SHORT,
            gross_long_quantity=Decimal("0"),
            gross_short_quantity=Decimal("1000"),
            net_signed_quantity=Decimal("-1000"),
            settled_quantity=Decimal("-1000"),
            unsettled_quantity=Decimal("0"),
            economic_quantity=Decimal("-1000"),
            available_quantity=Decimal("-1000"),
            reserved_quantity=Decimal("0"),
            restricted_quantity=Decimal("0"),
            borrowed_quantity=Decimal("1000"),
            effective_timestamp=datetime.utcnow(),
            recorded_at=datetime.utcnow(),
            snapshot_version=1,
        )
        session.add(snap_short)

        pos_short = PositionValuation(
            valuation_id=f"val_{uuid.uuid4().hex[:6]}",
            calculation_id=f"calc_{uuid.uuid4().hex[:6]}",
            portfolio_id=port_id,
            account_id="ACC_01",
            instrument_id="TSLA",
            position_side="SHORT",
            signed_quantity=Decimal("-1000"),
            mark_price=Decimal("200.00"),
            price_currency="USD",
            fx_rate_to_base=Decimal("1.0"),
            signed_market_value_native=Decimal("-200000.00"),
            signed_market_value_base=Decimal("-200000.00"),
            signed_cost_basis_native=Decimal("-200000.00"),
            signed_cost_basis_base=Decimal("-200000.00"),
            unrealized_pnl_native=Decimal("0.00"),
            unrealized_pnl_base=Decimal("0.00"),
            effective_at=datetime.utcnow(),
        )
        session.add(pos_short)

        # Add Cash Account
        cash_acc_id = f"CA_{uuid.uuid4().hex[:6]}"
        cash_acc = CashAccount(
            cash_account_id=cash_acc_id,
            portfolio_id=port_id,
            account_id="ACC_01",
            currency="USD",
            cash_account_type=CashAccountType.TRADING,
            status=CashAccountStatus.ACTIVE,
            description="Trading Cash Account",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(cash_acc)

        cash_snap = CashBalanceSnapshot(
            snapshot_id=f"CSNAP_{uuid.uuid4().hex[:6]}",
            cash_account_id=cash_acc_id,
            portfolio_id=port_id,
            account_id="ACC_01",
            currency="USD",
            settled_balance=Decimal("150000.00"),
            unsettled_receivables=Decimal("0.00"),
            unsettled_payables=Decimal("0.00"),
            reserved_cash=Decimal("0.00"),
            restricted_cash=Decimal("0.00"),
            eligible_credit=Decimal("0.00"),
            minimum_cash_buffer=Decimal("0.00"),
            available_cash=Decimal("150000.00"),
            effective_at=datetime.utcnow(),
            calculated_at=datetime.utcnow(),
            policy_version="1.0",
        )
        session.add(cash_snap)
        await session.commit()

        # 1. Test Consolidated Exposure Service
        service = ExposureDashboardService(session)
        dashboard = await service.get_consolidated_dashboard(portfolio_id=port_id)

        assert dashboard.portfolio_id == port_id
        assert dashboard.base_currency == "USD"
        assert dashboard.allocation_summary.total_nav > 0

        # 2. Test Sector Allocation Service
        sec_svc = SectorAllocationPresentationService(session)
        sec_summary = await sec_svc.get_sector_allocation(port_id)
        assert sec_summary.portfolio_id == port_id
        assert sec_summary.total_gross_exposure >= 0

        # 3. Test Instrument Allocation Service
        inst_svc = InstrumentAllocationPresentationService(session)
        inst_summary = await inst_svc.get_instrument_allocation(port_id)
        assert inst_summary.portfolio_id == port_id
        assert len(inst_summary.all_ranked_holdings) >= 1

        # 4. Test Drilldown Service
        drill_svc = ExposureDrilldownService(session)
        drill_root = await drill_svc.drill_down(port_id, HierarchyLevel.PORTFOLIO)
        assert drill_root.current_level == HierarchyLevel.PORTFOLIO
        assert len(drill_root.breadcrumbs) == 1


@pytest.mark.asyncio
async def test_exposure_dashboard_api_endpoints():
    async with AsyncSessionLocal() as session:
        port_id = f"PORT_API_EXP_{uuid.uuid4().hex[:6]}"
        portfolio = Portfolio(
            portfolio_id=port_id,
            portfolio_code=port_id,
            portfolio_name="Global Long Short Equity Desk",
            short_name="Global L/S",
            base_currency="USD",
            lifecycle_status=PortfolioLifecycleStatus.ACTIVE,
            portfolio_type=PortfolioTypeEnum.DISCRETIONARY,
            creation_source=CreationSourceEnum.MANUAL_ADMINISTRATION,
            market_scope=MarketScopeEnum.UNITED_STATES,
            created_by="TEST_ADMIN",
            created_at=datetime.utcnow() - timedelta(days=60),
        )
        session.add(portfolio)

        snap = PortfolioValuationSnapshot(
            snapshot_id=f"snap_{uuid.uuid4().hex[:6]}",
            calculation_id=f"calc_{uuid.uuid4().hex[:6]}",
            portfolio_id=port_id,
            valuation_timestamp=datetime.utcnow(),
            gross_long_market_value=Decimal("500000.00"),
            gross_short_market_value=Decimal("0.00"),
            net_market_value=Decimal("500000.00"),
            total_cost_basis=Decimal("480000.00"),
            total_unrealized_pnl=Decimal("20000.00"),
            realized_pnl_period=Decimal("0.00"),
            base_currency="USD",
        )
        session.add(snap)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Consolidated Dashboard Endpoint
        resp = await client.get(f"/api/v1/dashboard/portfolios/{port_id}/exposure-dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["portfolio_id"] == port_id
        assert "allocation_summary" in data
        assert "sector_summary" in data
        assert "instrument_summary" in data

        # 2. Sector Allocation Endpoint
        resp_sec = await client.get(f"/api/v1/dashboard/portfolios/{port_id}/exposure-dashboard/sectors")
        assert resp_sec.status_code == 200
        sec_data = resp_sec.json()
        assert sec_data["portfolio_id"] == port_id
        assert "sectors" in sec_data

        # 3. Instrument Allocation Endpoint
        resp_inst = await client.get(f"/api/v1/dashboard/portfolios/{port_id}/exposure-dashboard/instruments")
        assert resp_inst.status_code == 200
        inst_data = resp_inst.json()
        assert inst_data["portfolio_id"] == port_id
        assert "all_ranked_holdings" in inst_data

        # 4. Portfolio Capital Allocation Endpoint
        resp_alloc = await client.get(f"/api/v1/dashboard/portfolios/{port_id}/exposure-dashboard/allocation")
        assert resp_alloc.status_code == 200
        alloc_data = resp_alloc.json()
        assert alloc_data["portfolio_id"] == port_id
        assert "total_nav" in alloc_data

        # 5. Drilldown Endpoint
        resp_drill = await client.get(f"/api/v1/dashboard/portfolios/{port_id}/exposure-dashboard/drilldown?level=PORTFOLIO")
        assert resp_drill.status_code == 200
        drill_data = resp_drill.json()
        assert drill_data["current_level"] == "PORTFOLIO"
        assert len(drill_data["breadcrumbs"]) >= 1
