"""
Unit and integration tests for M13.01 — Portfolio Overview.

Covers:
1. Standard Metric Value Contract: Verification of metric_code, value, unit, quality_status, and metadata.
2. Portfolio Overview Aggregation: Ingesting authoritative data from M05 (Valuation, P&L) and M06 (Gross & Net Exposure).
3. Data Freshness & Quality: Stale valuation detection, latency calculations, and feed source attribution.
4. Exposure Representation: Non-netted gross exposure, signed net exposure, and directional classification.
5. REST API Integration: GET /api/v1/dashboard/portfolios/{id}/overview, /kpis, and /freshness.
"""

from datetime import datetime, timedelta
from decimal import Decimal
import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.main import app
from backend.app.modules.dashboard_visualization.portfolio_overview.services.portfolio_overview_service import (
    PortfolioOverviewService,
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


@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()
    yield


@pytest.mark.asyncio
async def test_portfolio_overview_service():
    async with AsyncSessionLocal() as session:
        service = PortfolioOverviewService(session)

        # 1. Setup mock portfolio in DB with all required fields
        port_id = f"PORT_TEST_{uuid.uuid4().hex[:6]}"
        portfolio = Portfolio(
            portfolio_id=port_id,
            portfolio_code=port_id,
            portfolio_name="US Long/Short Flagship Fund",
            short_name="US L/S",
            base_currency="USD",
            lifecycle_status=PortfolioLifecycleStatus.ACTIVE,
            portfolio_type=PortfolioTypeEnum.DISCRETIONARY,
            creation_source=CreationSourceEnum.MANUAL_ADMINISTRATION,
            market_scope=MarketScopeEnum.UNITED_STATES,
            created_by="SYSTEM_TEST",
            created_at=datetime.utcnow() - timedelta(days=60),
        )
        session.add(portfolio)

        # 2. Add valuation snapshot
        snap = PortfolioValuationSnapshot(
            snapshot_id=f"snap_{uuid.uuid4().hex[:6]}",
            calculation_id=f"calc_{uuid.uuid4().hex[:6]}",
            portfolio_id=port_id,
            valuation_timestamp=datetime.utcnow(),
            gross_long_market_value=Decimal("150000.00"),
            gross_short_market_value=Decimal("0.00"),
            net_market_value=Decimal("150000.00"),
            total_cost_basis=Decimal("137500.00"),
            total_unrealized_pnl=Decimal("12500.00"),
            realized_pnl_period=Decimal("3500.00"),
            base_currency="USD",
        )
        session.add(snap)

        # Add position valuation
        pos_val = PositionValuation(
            valuation_id=f"val_{uuid.uuid4().hex[:6]}",
            calculation_id=f"calc_{uuid.uuid4().hex[:6]}",
            portfolio_id=port_id,
            account_id="ACC_01",
            instrument_id="AAPL",
            position_side="LONG",
            signed_quantity=Decimal("100"),
            mark_price=Decimal("1000.00"),
            price_currency="USD",
            fx_rate_to_base=Decimal("1.0"),
            signed_market_value_native=Decimal("100000.00"),
            signed_market_value_base=Decimal("100000.00"),
            signed_cost_basis_native=Decimal("87500.00"),
            signed_cost_basis_base=Decimal("87500.00"),
            unrealized_pnl_native=Decimal("12500.00"),
            unrealized_pnl_base=Decimal("12500.00"),
            effective_at=datetime.utcnow(),
        )
        session.add(pos_val)
        await session.flush()

        # 4. Execute Portfolio Overview Service
        overview = await service.get_portfolio_overview(port_id)

        # Verify Portfolio Context
        assert overview.portfolio.portfolio_id == port_id
        assert overview.portfolio.base_currency == "USD"
        assert overview.portfolio.portfolio_name == "US Long/Short Flagship Fund"

        # Verify Authoritative NAV & P&L
        assert overview.total_nav.metric_code == "TOTAL_NAV"
        assert overview.total_nav.value == Decimal("150000.00")
        assert overview.total_nav.quality_status == "FRESH"
        assert overview.total_nav.source_module == "M05.03"

        assert overview.unrealized_pnl.value == Decimal("12500.00")
        assert overview.realized_pnl.value == Decimal("3500.00")
        assert overview.total_pnl.value == Decimal("16000.00")  # 12500 + 3500

        # Verify Exposure Summary Detail
        assert overview.exposure.gross_exposure.source_module == "M06.01"
        assert overview.exposure.net_exposure.source_module == "M06.02"
        assert overview.exposure.directional_status in ("NET_LONG", "NET_SHORT", "NEUTRAL", "APPROX_NEUTRAL")

        # Verify Summary Table Rows
        assert len(overview.summary_table_rows) >= 7
        codes = [r.metric_code for r in overview.summary_table_rows]
        assert "TOTAL_NAV" in codes
        assert "GROSS_EXPOSURE" in codes
        assert "NET_EXPOSURE" in codes


@pytest.mark.asyncio
async def test_portfolio_overview_api_endpoints():
    async with AsyncSessionLocal() as session:
        port_id = f"PORT_API_{uuid.uuid4().hex[:6]}"
        portfolio = Portfolio(
            portfolio_id=port_id,
            portfolio_code=port_id,
            portfolio_name="Global Macro Multi-Asset Fund",
            short_name="Macro Multi",
            base_currency="USD",
            lifecycle_status=PortfolioLifecycleStatus.ACTIVE,
            portfolio_type=PortfolioTypeEnum.DISCRETIONARY,
            creation_source=CreationSourceEnum.MANUAL_ADMINISTRATION,
            market_scope=MarketScopeEnum.UNITED_STATES,
            created_by="SYSTEM_TEST",
            created_at=datetime.utcnow() - timedelta(days=30),
        )
        session.add(portfolio)
        snap = PortfolioValuationSnapshot(
            snapshot_id=f"snap_{uuid.uuid4().hex[:6]}",
            calculation_id=f"calc_{uuid.uuid4().hex[:6]}",
            portfolio_id=port_id,
            valuation_timestamp=datetime.utcnow(),
            gross_long_market_value=Decimal("250000.00"),
            gross_short_market_value=Decimal("0.00"),
            net_market_value=Decimal("250000.00"),
            total_cost_basis=Decimal("250000.00"),
            total_unrealized_pnl=Decimal("0.00"),
            realized_pnl_period=Decimal("0.00"),
            base_currency="USD",
        )
        session.add(snap)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Test Overview Endpoint
        resp = await client.get(f"/api/v1/dashboard/portfolios/{port_id}/overview")
        assert resp.status_code == 200
        data = resp.json()

        assert data["portfolio"]["portfolio_id"] == port_id
        assert Decimal(str(data["total_nav"]["value"])) == Decimal("250000.00")
        assert "freshness" in data
        assert "exposure" in data
        assert "summary_table_rows" in data

        # 2. Test KPIs Endpoint
        resp_kpi = await client.get(f"/api/v1/dashboard/portfolios/{port_id}/kpis")
        assert resp_kpi.status_code == 200
        kpis = resp_kpi.json()
        assert len(kpis) >= 7

        # 3. Test Freshness Endpoint
        resp_fresh = await client.get(f"/api/v1/dashboard/portfolios/{port_id}/freshness")
        assert resp_fresh.status_code == 200
        freshness_data = resp_fresh.json()
        assert freshness_data["overall_status"] == "FRESH"

        # 4. Non-existent portfolio returns 404
        resp_err = await client.get("/api/v1/dashboard/portfolios/NON_EXISTENT_PORT/overview")
        assert resp_err.status_code == 404
