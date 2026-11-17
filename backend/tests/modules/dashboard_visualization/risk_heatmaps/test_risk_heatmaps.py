"""
Integration and financial consistency test suite for M13.04 — Risk Heatmaps.

Validates:
1. Metric Registry: Supported metrics, definitions, semantic direction, default palettes.
2. HeatmapColorScaleService: Outlier handling, symmetric diverging scale, sequential normalization.
3. SectorHeatmapService: Sector-level treemap aggregation consuming M06.03 sector exposures and M05.03 valuations.
4. SecurityHeatmapService: Holdings-level heatmap cells grouped by sector and long/short filtered.
5. HeatmapDrillthroughService: Underlying positions breakdown and provenance metadata.
6. REST API Endpoints:
   - GET /api/v1/dashboard/portfolios/risk-heatmaps/metrics
   - GET /api/v1/dashboard/portfolios/{id}/risk-heatmaps/sectors
   - GET /api/v1/dashboard/portfolios/{id}/risk-heatmaps/securities
   - GET /api/v1/dashboard/portfolios/{id}/risk-heatmaps/drilldown
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.main import app
from backend.app.modules.dashboard_visualization.risk_heatmaps.services.risk_heatmaps_service import (
    RiskHeatmapsService,
    HeatmapMetricRegistryService,
    HeatmapColorScaleService,
)
from backend.app.modules.dashboard_visualization.risk_heatmaps.schemas.risk_heatmaps_schemas import (
    MetricCategory,
    MetricDirection,
    ScaleType,
    PaletteType,
    HeatmapGrouping,
    HeatmapPositionSide,
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


@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()
    yield


@pytest.mark.asyncio
async def test_risk_heatmaps_metric_registry_and_color_scale():
    # 1. Test Metric Registry
    registry = HeatmapMetricRegistryService.get_registry()
    assert registry.total_metrics >= 6
    metric_ids = [m.metric_id for m in registry.metrics]
    assert "unrealized_pnl" in metric_ids
    assert "net_market_value" in metric_ids
    assert "gross_market_value" in metric_ids
    assert "nav_weight_pct" in metric_ids

    # 2. Test Color Scale Engine (Diverging)
    pnl_metric = HeatmapMetricRegistryService.get_metric("unrealized_pnl")
    test_values = [Decimal("-5000"), Decimal("2000"), Decimal("10000"), Decimal("-1000")]
    scale_config, d_min, d_max, mid = HeatmapColorScaleService.build_color_scale_config(
        metric=pnl_metric,
        values=test_values,
    )
    assert scale_config.scale_type == ScaleType.DIVERGING
    assert d_min == Decimal("-10000")
    assert d_max == Decimal("10000")
    assert mid == Decimal("0")

    # Score and color mapping
    norm_pos, hex_pos, is_clip_pos = HeatmapColorScaleService.get_color_hex(
        val=Decimal("10000"),
        scale_config=scale_config,
        direction=MetricDirection.POSITIVE_IS_FAVORABLE,
    )
    assert norm_pos == Decimal("1.0000")
    assert hex_pos == "#14532d"  # Deep emerald
    assert not is_clip_pos

    norm_neg, hex_neg, is_clip_neg = HeatmapColorScaleService.get_color_hex(
        val=Decimal("-5000"),
        scale_config=scale_config,
        direction=MetricDirection.POSITIVE_IS_FAVORABLE,
    )
    assert norm_neg == Decimal("0.2500")
    assert hex_neg in ["#7f1d1d", "#b91c1c", "#ef4444", "#fca5a5"]

    # Test Outlier Clipping in Diverging Scale
    outlier_values = [Decimal("100")] * 20 + [Decimal("50000")]
    scale_clipped, _, _, _ = HeatmapColorScaleService.build_color_scale_config(
        metric=pnl_metric,
        values=outlier_values,
        clip_outliers=True,
    )
    assert scale_clipped.clipped_outliers_count >= 1


@pytest.mark.asyncio
async def test_risk_heatmaps_services_and_components():
    async with AsyncSessionLocal() as session:
        port_id = f"PORT_HEAT_{uuid.uuid4().hex[:6]}"
        portfolio = Portfolio(
            portfolio_id=port_id,
            portfolio_code=port_id,
            portfolio_name="Institutional Quantitative Heatmap Portfolio",
            short_name="Heatmap Alpha",
            base_currency="USD",
            lifecycle_status=PortfolioLifecycleStatus.ACTIVE,
            portfolio_type=PortfolioTypeEnum.DISCRETIONARY,
            creation_source=CreationSourceEnum.MANUAL_ADMINISTRATION,
            market_scope=MarketScopeEnum.UNITED_STATES,
            created_by="TEST_ADMIN",
            created_at=datetime.now(timezone.utc) - timedelta(days=60),
        )
        session.add(portfolio)

        snap = PortfolioValuationSnapshot(
            snapshot_id=f"snap_{uuid.uuid4().hex[:6]}",
            calculation_id=f"calc_{uuid.uuid4().hex[:6]}",
            portfolio_id=port_id,
            valuation_timestamp=datetime.now(timezone.utc),
            gross_long_market_value=Decimal("750000.00"),
            gross_short_market_value=Decimal("250000.00"),
            net_market_value=Decimal("500000.00"),
            total_cost_basis=Decimal("450000.00"),
            total_unrealized_pnl=Decimal("50000.00"),
            realized_pnl_period=Decimal("2500.00"),
            base_currency="USD",
        )
        session.add(snap)

        # 1. Long Holding AAPL (Information Technology)
        b_long = PositionBook(
            position_id=f"PB_L_{uuid.uuid4().hex[:6]}",
            portfolio_id=port_id,
            account_id="ACC_01",
            instrument_id="AAPL",
            position_side=PositionSide.LONG,
            position_status=PositionStatus.OPEN,
            current_snapshot_version=1,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(b_long)

        ps_long = PositionSnapshot(
            snapshot_id=f"PS_L_{uuid.uuid4().hex[:6]}",
            position_id=b_long.position_id,
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
            effective_timestamp=datetime.now(timezone.utc),
            recorded_at=datetime.now(timezone.utc),
            snapshot_version=1,
        )
        session.add(ps_long)

        pv_long = PositionValuation(
            valuation_id=f"val_{uuid.uuid4().hex[:6]}",
            calculation_id=f"calc_{uuid.uuid4().hex[:6]}",
            portfolio_id=port_id,
            account_id="ACC_01",
            instrument_id="AAPL",
            position_side="LONG",
            signed_quantity=Decimal("500"),
            mark_price=Decimal("1500.00"),
            price_currency="USD",
            fx_rate_to_base=Decimal("1.0"),
            signed_market_value_native=Decimal("750000.00"),
            signed_market_value_base=Decimal("750000.00"),
            signed_cost_basis_native=Decimal("700000.00"),
            signed_cost_basis_base=Decimal("700000.00"),
            unrealized_pnl_native=Decimal("50000.00"),
            unrealized_pnl_base=Decimal("50000.00"),
            effective_at=datetime.now(timezone.utc),
        )
        session.add(pv_long)

        # 2. Short Holding TSLA (Consumer Discretionary)
        b_short = PositionBook(
            position_id=f"PB_S_{uuid.uuid4().hex[:6]}",
            portfolio_id=port_id,
            account_id="ACC_01",
            instrument_id="TSLA",
            position_side=PositionSide.SHORT,
            position_status=PositionStatus.OPEN,
            current_snapshot_version=1,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(b_short)

        ps_short = PositionSnapshot(
            snapshot_id=f"PS_S_{uuid.uuid4().hex[:6]}",
            position_id=b_short.position_id,
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
            effective_timestamp=datetime.now(timezone.utc),
            recorded_at=datetime.now(timezone.utc),
            snapshot_version=1,
        )
        session.add(ps_short)

        pv_short = PositionValuation(
            valuation_id=f"val_{uuid.uuid4().hex[:6]}",
            calculation_id=f"calc_{uuid.uuid4().hex[:6]}",
            portfolio_id=port_id,
            account_id="ACC_01",
            instrument_id="TSLA",
            position_side="SHORT",
            signed_quantity=Decimal("-1000"),
            mark_price=Decimal("250.00"),
            price_currency="USD",
            fx_rate_to_base=Decimal("1.0"),
            signed_market_value_native=Decimal("-250000.00"),
            signed_market_value_base=Decimal("-250000.00"),
            signed_cost_basis_native=Decimal("-230000.00"),
            signed_cost_basis_base=Decimal("-230000.00"),
            unrealized_pnl_native=Decimal("-20000.00"),
            unrealized_pnl_base=Decimal("-20000.00"),
            effective_at=datetime.now(timezone.utc),
        )
        session.add(pv_short)
        await session.commit()

        # 3. Test Sector Heatmap Generation
        sec_res = await RiskHeatmapsService.get_sector_heatmap(
            session=session,
            portfolio_id=port_id,
            color_metric_id="unrealized_pnl",
            area_metric_id="gross_market_value",
            base_currency="USD",
        )
        assert sec_res.portfolio_id == port_id
        assert sec_res.total_area_value >= Decimal("1000000.00")
        assert len(sec_res.cells) >= 1 or sec_res.unclassified_cell is not None

        # 4. Test Security Heatmap Generation
        inst_res = await RiskHeatmapsService.get_security_heatmap(
            session=session,
            portfolio_id=port_id,
            color_metric_id="unrealized_pnl",
            area_metric_id="gross_market_value",
            grouping=HeatmapGrouping.SECTOR,
            side_filter=HeatmapPositionSide.ALL,
            base_currency="USD",
        )
        assert inst_res.portfolio_id == port_id
        assert inst_res.total_securities == 2
        symbols = [c.label for c in inst_res.cells]
        assert "AAPL" in symbols
        assert "TSLA" in symbols

        # Verify side filter
        long_only = await RiskHeatmapsService.get_security_heatmap(
            session=session,
            portfolio_id=port_id,
            side_filter=HeatmapPositionSide.LONG,
        )
        assert long_only.total_securities == 1
        assert long_only.cells[0].label == "AAPL"

        # 5. Test Drilldown for AAPL
        drilldown = await RiskHeatmapsService.get_drilldown(
            session=session,
            portfolio_id=port_id,
            entity_id="AAPL",
            entity_type="SECURITY",
            color_metric_id="unrealized_pnl",
        )
        assert drilldown.portfolio_id == port_id
        assert drilldown.total_holdings == 1
        assert drilldown.holdings[0].symbol == "AAPL"
        assert drilldown.holdings[0].market_value == Decimal("750000.00")
        assert drilldown.holdings[0].color_metric_value == Decimal("50000.00")


@pytest.mark.asyncio
async def test_risk_heatmaps_api_endpoints():
    async with AsyncSessionLocal() as session:
        port_id = f"PORT_HEAT_API_{uuid.uuid4().hex[:6]}"
        portfolio = Portfolio(
            portfolio_id=port_id,
            portfolio_code=port_id,
            portfolio_name="Institutional Quantitative Heatmap Fund API",
            short_name="Heatmap API",
            base_currency="USD",
            lifecycle_status=PortfolioLifecycleStatus.ACTIVE,
            portfolio_type=PortfolioTypeEnum.DISCRETIONARY,
            creation_source=CreationSourceEnum.MANUAL_ADMINISTRATION,
            market_scope=MarketScopeEnum.UNITED_STATES,
            created_by="TEST_ADMIN",
            created_at=datetime.now(timezone.utc) - timedelta(days=30),
        )
        session.add(portfolio)

        snap = PortfolioValuationSnapshot(
            snapshot_id=f"snap_{uuid.uuid4().hex[:6]}",
            calculation_id=f"calc_{uuid.uuid4().hex[:6]}",
            portfolio_id=port_id,
            valuation_timestamp=datetime.now(timezone.utc),
            gross_long_market_value=Decimal("500000.00"),
            gross_short_market_value=Decimal("0.00"),
            net_market_value=Decimal("500000.00"),
            total_cost_basis=Decimal("480000.00"),
            total_unrealized_pnl=Decimal("20000.00"),
            realized_pnl_period=Decimal("0.00"),
            base_currency="USD",
        )
        session.add(snap)

        b = PositionBook(
            position_id=f"PB_MSFT_{uuid.uuid4().hex[:6]}",
            portfolio_id=port_id,
            account_id="ACC_01",
            instrument_id="MSFT",
            position_side=PositionSide.LONG,
            position_status=PositionStatus.OPEN,
            current_snapshot_version=1,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(b)

        ps = PositionSnapshot(
            snapshot_id=f"PS_MSFT_{uuid.uuid4().hex[:6]}",
            position_id=b.position_id,
            portfolio_id=port_id,
            account_id="ACC_01",
            instrument_id="MSFT",
            position_side=PositionSide.LONG,
            gross_long_quantity=Decimal("1000"),
            gross_short_quantity=Decimal("0"),
            net_signed_quantity=Decimal("1000"),
            settled_quantity=Decimal("1000"),
            unsettled_quantity=Decimal("0"),
            economic_quantity=Decimal("1000"),
            available_quantity=Decimal("1000"),
            reserved_quantity=Decimal("0"),
            restricted_quantity=Decimal("0"),
            borrowed_quantity=Decimal("0"),
            effective_timestamp=datetime.now(timezone.utc),
            recorded_at=datetime.now(timezone.utc),
            snapshot_version=1,
        )
        session.add(ps)

        pv = PositionValuation(
            valuation_id=f"val_{uuid.uuid4().hex[:6]}",
            calculation_id=f"calc_{uuid.uuid4().hex[:6]}",
            portfolio_id=port_id,
            account_id="ACC_01",
            instrument_id="MSFT",
            position_side="LONG",
            signed_quantity=Decimal("1000"),
            mark_price=Decimal("500.00"),
            price_currency="USD",
            fx_rate_to_base=Decimal("1.0"),
            signed_market_value_native=Decimal("500000.00"),
            signed_market_value_base=Decimal("500000.00"),
            signed_cost_basis_native=Decimal("480000.00"),
            signed_cost_basis_base=Decimal("480000.00"),
            unrealized_pnl_native=Decimal("20000.00"),
            unrealized_pnl_base=Decimal("20000.00"),
            effective_at=datetime.now(timezone.utc),
        )
        session.add(pv)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Metric Registry
        reg_res = await client.get("/api/v1/dashboard/portfolios/risk-heatmaps/metrics")
        assert reg_res.status_code == 200
        reg_data = reg_res.json()
        assert reg_data["total_metrics"] >= 6

        # 2. Sector Heatmap
        sec_res = await client.get(f"/api/v1/dashboard/portfolios/{port_id}/risk-heatmaps/sectors?color_metric=unrealized_pnl")
        assert sec_res.status_code == 200
        sec_data = sec_res.json()
        assert sec_data["portfolio_id"] == port_id
        assert sec_data["color_metric"]["metric_id"] == "unrealized_pnl"
        assert Decimal(str(sec_data["total_area_value"])) >= Decimal("500000.00")

        # 3. Security Heatmap
        inst_res = await client.get(f"/api/v1/dashboard/portfolios/{port_id}/risk-heatmaps/securities?side_filter=ALL&grouping=SECTOR")
        assert inst_res.status_code == 200
        inst_data = inst_res.json()
        assert inst_data["total_securities"] == 1
        assert inst_data["cells"][0]["label"] == "MSFT"
        assert Decimal(str(inst_data["cells"][0]["color_metric_value"])) == Decimal("20000.00")

        # 4. Drilldown
        dd_res = await client.get(f"/api/v1/dashboard/portfolios/{port_id}/risk-heatmaps/drilldown?entity_id=MSFT&entity_type=SECURITY")
        assert dd_res.status_code == 200
        dd_data = dd_res.json()
        assert dd_data["total_holdings"] == 1
        assert dd_data["holdings"][0]["symbol"] == "MSFT"
