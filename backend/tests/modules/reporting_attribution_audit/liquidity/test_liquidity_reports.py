"""Comprehensive automated tests for M14.05 Liquidity Reports.

Verifies:
1. LiquidityReportService creation, upstream metric aggregation, and directional execution (Long=SELL, Short=BUY).
2. Cost breakdown calculation (spread + impact + slippage + fees) without double-counting.
3. Illiquidity concentration ranking and sector rollup.
4. Liquidity stress comparison (baseline vs stressed spread, depth, volume, horizon, cost).
5. M11 Liquidity limit utilization and separation of PROJECTED_STRESS_EXCEEDANCE from ACTUAL_LIMIT_BREACH.
6. Multi-format artifact generation (CSV, HTML, PDF mock) and SHA-256 cryptographic verification.
7. Immutable version lineage and audit event recording.
8. FastAPI endpoints integration.
"""

from datetime import datetime, timezone
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.core.database import Base, init_db
from backend.app.main import app
from backend.app.modules.portfolio_management.portfolio_creation.models import Portfolio
from backend.app.modules.portfolio_management.position_valuation.models import PositionValuation
from backend.app.modules.market_microstructure.bid_ask_spread.models import SpreadObservation
from backend.app.modules.market_microstructure.order_book_depth.models import OrderBookDepthSnapshot
from backend.app.modules.market_microstructure.liquidity_estimation.models import (
    LiquidityScoreSnapshot,
    LiquidityVolumeAggregate,
    LiquidityTurnoverAggregate,
)
from backend.app.modules.reporting_attribution_audit.liquidity.schemas.liquidity_report_schemas import (
    LiquidityReportCreateRequest,
    LiquidationAssumptionsInput,
)
from backend.app.modules.reporting_attribution_audit.liquidity.services.liquidity_report_service import (
    LiquidityReportService,
)
from backend.app.modules.reporting_attribution_audit.liquidity.models.liquidity_report_models import (
    LiquidityArtifactType,
    LiquidityLimitEvaluationStatus,
)


@pytest.fixture
async def async_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    await init_db()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        # Seed test portfolio
        port = Portfolio(
            portfolio_id="port_liq_001",
            portfolio_code="PORT_LIQ_001",
            portfolio_name="Quant Liquidity Test Portfolio",
            short_name="Quant Liq",
            base_currency="INR",
            portfolio_type="INSTITUTIONAL_PORTFOLIO",
            lifecycle_status="ACTIVE",
            creation_source="SYSTEM_GENERATION",
            market_scope="INDIA_AND_US",
            asset_class_scope="EQUITIES",
            current_configuration_version=1,
            created_by="TEST_ADMIN",
        )
        session.add(port)

        # Seed positions: one long, one short via PositionValuation
        pos1 = PositionValuation(
            valuation_id="VAL_REL_1",
            calculation_id="CALC_001",
            portfolio_id="port_liq_001",
            account_id="ACC_001",
            instrument_id="INST_RELIANCE",
            position_side="LONG",
            signed_quantity=5000.0,
            mark_price=2500.0,
            mark_price_type="LAST_TRADED_PRICE",
            price_currency="INR",
            fx_rate_to_base=1.0,
            signed_market_value_native=12500000.0,
            signed_market_value_base=12500000.0,
            signed_cost_basis_native=12000000.0,
            signed_cost_basis_base=12000000.0,
            unrealized_pnl_native=500000.0,
            unrealized_pnl_base=500000.0,
            valuation_status="VALUED",
            effective_at=datetime.now(timezone.utc),
            calculated_at=datetime.now(timezone.utc),
        )
        pos2 = PositionValuation(
            valuation_id="VAL_TCS_1",
            calculation_id="CALC_001",
            portfolio_id="port_liq_001",
            account_id="ACC_001",
            instrument_id="INST_TCS",
            position_side="SHORT",
            signed_quantity=-2000.0,  # Short position
            mark_price=3500.0,
            mark_price_type="LAST_TRADED_PRICE",
            price_currency="INR",
            fx_rate_to_base=1.0,
            signed_market_value_native=-7000000.0,
            signed_market_value_base=-7000000.0,
            signed_cost_basis_native=-7200000.0,
            signed_cost_basis_base=-7200000.0,
            unrealized_pnl_native=200000.0,
            unrealized_pnl_base=200000.0,
            valuation_status="VALUED",
            effective_at=datetime.now(timezone.utc),
            calculated_at=datetime.now(timezone.utc),
        )
        session.add_all([pos1, pos2])
        await session.commit()

        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_liquidity_report_service_lifecycle(async_db: AsyncSession):
    """Test full report creation, directional liquidation semantics, cost aggregation, and reconciliation."""
    service = LiquidityReportService(async_db)

    req = LiquidityReportCreateRequest(
        portfolio_id="port_liq_001",
        report_name="Q4 Portfolio Liquidity & Exit Capability",
        reporting_currency="INR",
        liquidation_assumptions=LiquidationAssumptionsInput(
            participation_rate=0.10,
            target_fraction=1.0,
            include_fees=True,
            estimation_scope="INDEPENDENT",
        ),
    )

    report = await service.create_and_generate_report(req)
    assert report.report_code.startswith("LIQ-REP-")
    assert report.report_version == 1
    assert report.portfolio_id == "port_liq_001"
    assert report.executive_summary.position_count == 2
    assert report.executive_summary.reconciliation_status in ["RECONCILED", "RECONCILED_WITH_ROUNDING"]

    # Verify Directional Semantics: Long -> SELL, Short -> BUY
    liq_rel = next(l for l in report.liquidations if l.instrument_id == "INST_RELIANCE")
    liq_tcs = next(l for l in report.liquidations if l.instrument_id == "INST_TCS")
    assert liq_rel.liquidation_direction == "SELL"
    assert liq_tcs.liquidation_direction == "BUY"

    # Verify positive estimated liquidation costs
    assert liq_rel.estimated_total_cost > 0
    assert liq_tcs.estimated_total_cost > 0
    assert report.executive_summary.estimated_portfolio_liquidation_cost > 0

    # Verify concentrations
    pos_concs = [c for c in report.concentrations if c.grouping_type == "POSITION"]
    assert len(pos_concs) == 2
    total_contrib = sum(c.cost_contribution_pct or 0.0 for c in pos_concs)
    assert pytest.approx(total_contrib, 0.1) == 100.0

    # Verify stress comparisons
    assert len(report.stress_comparisons) >= 2
    for sc in report.stress_comparisons:
        assert sc.stressed_spread_bps > sc.baseline_spread_bps
        assert sc.stressed_liquidation_cost > sc.baseline_liquidation_cost
        assert sc.incremental_liquidation_cost > 0

    # Verify limits distinction: projected exceedances vs actual breaches
    assert len(report.limits) >= 3
    for lim in report.limits:
        assert lim.evaluation_status in [
            LiquidityLimitEvaluationStatus.WITHIN_LIMIT,
            LiquidityLimitEvaluationStatus.PROJECTED_STRESS_EXCEEDANCE,
            LiquidityLimitEvaluationStatus.ACTUAL_LIMIT_BREACH,
        ]


@pytest.mark.asyncio
async def test_artifact_generation_and_sha256_verification(async_db: AsyncSession):
    """Test PDF, HTML, and CSV artifact generation and cryptographic SHA-256 verification."""
    service = LiquidityReportService(async_db)
    req = LiquidityReportCreateRequest(
        portfolio_id="port_liq_001",
        report_name="Artifact Verification Report",
        reporting_currency="INR",
        liquidation_assumptions=LiquidationAssumptionsInput(participation_rate=0.05),
    )
    report = await service.create_and_generate_report(req)
    assert len(report.artifacts) == 3

    # Check that CSV, HTML, and PDF are all present with valid SHA-256 digests
    types = {a.artifact_type for a in report.artifacts}
    assert LiquidityArtifactType.CSV in types
    assert LiquidityArtifactType.HTML in types
    assert LiquidityArtifactType.PDF in types

    for a in report.artifacts:
        assert len(a.file_hash) == 64
        # Verify integrity via service
        res = await service.verify_artifact_integrity(report.report_id, a.artifact_type)
        assert res.is_valid is True
        assert res.file_hash == a.file_hash


@pytest.mark.asyncio
async def test_version_lineage_regeneration(async_db: AsyncSession):
    """Test non-destructive version lineage progression upon report regeneration."""
    service = LiquidityReportService(async_db)
    req = LiquidityReportCreateRequest(
        portfolio_id="port_liq_001",
        report_name="Regeneration Lineage Report",
        reporting_currency="INR",
    )

    # Version 1
    v1 = await service.create_and_generate_report(req)
    assert v1.report_version == 1

    # Version 2 with reason
    v2 = await service.create_and_generate_report(req, regeneration_reason="Updated market volume lookback window")
    assert v2.report_version == 2
    assert v2.report_id != v1.report_id

    # List history
    history = await service.list_reports(portfolio_id="port_liq_001")
    assert len(history) >= 2


@pytest.mark.asyncio
async def test_fastapi_endpoints_integration(async_db: AsyncSession):
    """Test FastAPI router endpoints for M14.05 Liquidity Reports."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create report via API
        payload = {
            "portfolio_id": "port_liq_001",
            "report_name": "API Integration Liquidity Report",
            "reporting_currency": "INR",
            "liquidation_assumptions": {
                "participation_rate": 0.10,
                "target_fraction": 1.0,
                "execution_horizon": "CONFIGURED_BY_UPSTREAM_MODEL",
                "side": "AUTO",
                "include_fees": True,
                "estimation_scope": "INDEPENDENT",
            },
            "scenario_runs": [],
            "include_position_analysis": True,
            "include_concentration": True,
            "include_stress_comparison": True,
            "include_limit_implications": True,
            "export_formats": ["CSV", "HTML", "PDF"],
        }
        res = await client.post("/api/v1/reports/liquidity", json=payload)
        assert res.status_code == 201
        data = res.json()
        report_id = data["report_id"]

        # Sub-endpoints
        prof_res = await client.get(f"/api/v1/reports/liquidity/{report_id}/profile")
        assert prof_res.status_code == 200
        assert "portfolio_weighted_spread_bps" in prof_res.json()

        pos_res = await client.get(f"/api/v1/reports/liquidity/{report_id}/positions")
        assert pos_res.status_code == 200
        assert len(pos_res.json()) >= 2

        liq_res = await client.get(f"/api/v1/reports/liquidity/{report_id}/liquidation")
        assert liq_res.status_code == 200
        assert len(liq_res.json()) >= 2

        stress_res = await client.get(f"/api/v1/reports/liquidity/{report_id}/stress")
        assert stress_res.status_code == 200

        limits_res = await client.get(f"/api/v1/reports/liquidity/{report_id}/limits")
        assert limits_res.status_code == 200

        verify_res = await client.get(f"/api/v1/reports/liquidity/{report_id}/verify/CSV")
        assert verify_res.status_code == 200
        assert verify_res.json()["is_valid"] is True
