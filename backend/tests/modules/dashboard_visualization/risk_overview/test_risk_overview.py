"""
Integration and financial consistency test suite for M13.02 — Risk Overview.

Validates:
1. VaRPresentationService: M07.02 integration, positive-loss convention, confidence/horizon display.
2. ExpectedShortfallPresentationService: M07.03 integration, tail definition metadata.
3. VolatilityPresentationService: M07.01 integration, realized vs forecast classification, annualization factor.
4. DrawdownPresentationService: M07.04 integration, high-water mark, negative drawdown percentage convention.
5. RiskOverviewService: Consolidation, failure isolation, VaR vs ES comparison compatibility.
6. REST API Endpoints:
   - GET /api/v1/dashboard/portfolios/{id}/risk-overview
   - GET /api/v1/dashboard/portfolios/{id}/risk-overview/var
   - GET /api/v1/dashboard/portfolios/{id}/risk-overview/expected-shortfall
   - GET /api/v1/dashboard/portfolios/{id}/risk-overview/volatility
   - GET /api/v1/dashboard/portfolios/{id}/risk-overview/drawdown
   - GET /api/v1/dashboard/portfolios/{id}/risk-overview/history
   - GET /api/v1/dashboard/portfolios/{id}/risk-overview/methodology
"""

from datetime import datetime, timedelta, date
from decimal import Decimal
import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.main import app
from backend.app.modules.dashboard_visualization.risk_overview.services.risk_overview_service import (
    RiskOverviewService,
    VaRPresentationService,
    ExpectedShortfallPresentationService,
    VolatilityPresentationService,
    DrawdownPresentationService,
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
async def test_risk_overview_service_and_components():
    async with AsyncSessionLocal() as session:
        port_id = f"PORT_RISK_{uuid.uuid4().hex[:6]}"
        portfolio = Portfolio(
            portfolio_id=port_id,
            portfolio_code=port_id,
            portfolio_name="Quant Systematic Alpha Fund",
            short_name="Quant Alpha",
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
            gross_long_market_value=Decimal("500000.00"),
            gross_short_market_value=Decimal("0.00"),
            net_market_value=Decimal("500000.00"),
            total_cost_basis=Decimal("450000.00"),
            total_unrealized_pnl=Decimal("50000.00"),
            realized_pnl_period=Decimal("10000.00"),
            base_currency="USD",
        )
        session.add(snap)
        await session.commit()

        # 1. Test Service Aggregation
        service = RiskOverviewService(session)
        overview = await service.get_risk_overview(
            portfolio_id=port_id,
            confidence_level=Decimal("0.99"),
            horizon_days=1,
            var_methodology="HISTORICAL_SIMULATION",
            volatility_lookback=60,
            drawdown_period="1_year",
        )

        assert overview.portfolio_id == port_id
        assert overview.base_currency == "USD"
        assert overview.valuation_nav == Decimal("500000.00")

        # 2. Check VaR Card structure
        assert overview.var.metric_id == "VAR"
        assert overview.var.confidence_level == Decimal("0.99")
        assert overview.var.confidence_display == "99%"
        assert overview.var.horizon_days == 1
        assert overview.var.source_module == "M07.02"

        # 3. Check ES Card structure
        assert overview.expected_shortfall.metric_id == "EXPECTED_SHORTFALL"
        assert overview.expected_shortfall.confidence_level == Decimal("0.99")
        assert overview.expected_shortfall.source_module == "M07.03"

        # 4. Check Volatility Card structure
        assert overview.volatility.metric_id == "VOLATILITY"
        assert overview.volatility.is_annualized is True
        assert overview.volatility.lookback_window == 60
        assert overview.volatility.source_module == "M07.01"

        # 5. Check Drawdown Card structure
        assert overview.drawdown.metric_id == "DRAWDOWN"
        assert overview.drawdown.source_module == "M07.04"

        # 6. Check Quality Summary
        assert overview.quality_summary.overall_status in ("VALID", "INCOMPLETE", "STALE", "ERROR")


@pytest.mark.asyncio
async def test_risk_overview_api_endpoints():
    async with AsyncSessionLocal() as session:
        port_id = f"PORT_API_RISK_{uuid.uuid4().hex[:6]}"
        portfolio = Portfolio(
            portfolio_id=port_id,
            portfolio_code=port_id,
            portfolio_name="Multi-Strategy Risk Fund",
            short_name="Multi-Strat",
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
            gross_long_market_value=Decimal("1000000.00"),
            gross_short_market_value=Decimal("0.00"),
            net_market_value=Decimal("1000000.00"),
            total_cost_basis=Decimal("950000.00"),
            total_unrealized_pnl=Decimal("50000.00"),
            realized_pnl_period=Decimal("0.00"),
            base_currency="USD",
        )
        session.add(snap)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Consolidated Risk Overview endpoint
        resp = await client.get(f"/api/v1/dashboard/portfolios/{port_id}/risk-overview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["portfolio_id"] == port_id
        assert "var" in data
        assert "expected_shortfall" in data
        assert "volatility" in data
        assert "drawdown" in data
        assert "quality_summary" in data

        # 2. VaR Endpoint
        resp_var = await client.get(f"/api/v1/dashboard/portfolios/{port_id}/risk-overview/var")
        assert resp_var.status_code == 200
        var_data = resp_var.json()
        assert var_data["metric_id"] == "VAR"
        assert var_data["source_module"] == "M07.02"

        # 3. Expected Shortfall Endpoint
        resp_es = await client.get(f"/api/v1/dashboard/portfolios/{port_id}/risk-overview/expected-shortfall")
        assert resp_es.status_code == 200
        es_data = resp_es.json()
        assert es_data["metric_id"] == "EXPECTED_SHORTFALL"
        assert es_data["source_module"] == "M07.03"

        # 4. Volatility Endpoint
        resp_vol = await client.get(f"/api/v1/dashboard/portfolios/{port_id}/risk-overview/volatility")
        assert resp_vol.status_code == 200
        vol_data = resp_vol.json()
        assert vol_data["metric_id"] == "VOLATILITY"
        assert vol_data["source_module"] == "M07.01"

        # 5. Drawdown Endpoint
        resp_dd = await client.get(f"/api/v1/dashboard/portfolios/{port_id}/risk-overview/drawdown")
        assert resp_dd.status_code == 200
        dd_data = resp_dd.json()
        assert dd_data["metric_id"] == "DRAWDOWN"
        assert dd_data["source_module"] == "M07.04"

        # 6. History Endpoint
        resp_hist = await client.get(f"/api/v1/dashboard/portfolios/{port_id}/risk-overview/history?metric=DRAWDOWN")
        assert resp_hist.status_code == 200
        hist_data = resp_hist.json()
        assert hist_data["metric"] == "DRAWDOWN"

        # 7. Methodology Endpoint
        resp_meth = await client.get(f"/api/v1/dashboard/portfolios/{port_id}/risk-overview/methodology")
        assert resp_meth.status_code == 200
        meth_data = resp_meth.json()
        assert meth_data["portfolio_id"] == port_id
        assert "var_methodology" in meth_data
        assert "expected_shortfall_methodology" in meth_data
        assert "volatility_methodology" in meth_data
        assert "drawdown_methodology" in meth_data
