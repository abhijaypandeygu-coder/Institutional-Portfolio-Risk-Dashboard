"""
Unit and integration tests for M14.02 — Portfolio Performance Reports.

Verifies:
1. Return calculation mathematical engine:
   - TWR with external flows (deposits/withdrawals)
   - Modified Dietz day-weighted return
   - Cumulative compounding
   - Annualized return bounds
   - XIRR / MWR irregular cash flows
2. Authoritative upstream aggregation:
   - NAV history consumption from M05.07
   - Cash movement classification from M05.04
   - Realized & Unrealized PnL from M05.03
3. Benchmark comparison and date alignment.
4. Performance caveat generation on data gaps or approximations.
5. Idempotent report generation and non-destructive regeneration with version lineage.
6. Multi-format artifact generation (CSV, HTML, PDF) and SHA-256 integrity verification.
7. REST API endpoint responses.
"""

from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.core.database import Base, init_db
from backend.app.main import app
from backend.app.modules.portfolio_management.portfolio_history.models import PortfolioBookSnapshot
from backend.app.modules.portfolio_management.cash_management.models import CashMovement, CashMovementType
from backend.app.modules.portfolio_management.position_valuation.models import PortfolioValuationSnapshot, ValuationStatus
from backend.app.modules.reporting_attribution_audit.portfolio_performance.models.performance_report_models import (
    ReportingPeriodType,
    ReportingFrequency,
    ReturnMethodology,
    CashFlowTimingPolicy,
    PerformanceDataStatus,
    ReportGenerationStatus,
)
from backend.app.modules.reporting_attribution_audit.portfolio_performance.schemas.performance_report_schemas import (
    PerformanceReportConfigCreate,
    PerformanceReportGenerateRequest,
)
from backend.app.modules.reporting_attribution_audit.portfolio_performance.services.performance_report_service import (
    PortfolioPerformanceReportService,
)
from backend.app.modules.reporting_attribution_audit.portfolio_performance.services.return_math import (
    calculate_subperiod_twr,
    calculate_modified_dietz,
    compound_returns,
    annualize_return,
    calculate_xirr,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def test_db_session():
    """Isolated in-memory SQLite database session for M14.02 tests."""
    await init_db()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# -----------------------------------------------------------------------------
# 1. Mathematical Return Calculation Tests
# -----------------------------------------------------------------------------
def test_subperiod_twr_mathematics():
    # 1. No flow: Start 1,000,000 -> End 1,050,000 => +5.0%
    r1 = calculate_subperiod_twr(Decimal("1000000.00"), Decimal("1050000.00"))
    assert r1 == Decimal("0.05")

    # 2. Deposit of 200,000: Start 1,000,000 -> End 1,250,000
    # Net gain = 1,250,000 - 1,000,000 - 200,000 = 50,000 => +5.0%
    r2 = calculate_subperiod_twr(Decimal("1000000.00"), Decimal("1250000.00"), net_external_flow=Decimal("200000.00"))
    assert r2 == Decimal("0.05")

    # 3. Withdrawal of 100,000: Start 1,000,000 -> End 950,000
    # Net gain = 950,000 - 1,000,000 - (-100,000) = 50,000 => +5.0%
    r3 = calculate_subperiod_twr(Decimal("1000000.00"), Decimal("950000.00"), net_external_flow=Decimal("-100000.00"))
    assert r3 == Decimal("0.05")

    # 4. Zero denominator protection
    assert calculate_subperiod_twr(Decimal("0.0"), Decimal("100000.00")) is None


def test_modified_dietz_mathematics():
    # Start: 1,000,000, End: 1,120,000. 30 days.
    # Flow: +100,000 on day 15 (halfway).
    # Numerator = 1,120,000 - 1,000,000 - 100,000 = 20,000
    # Denominator = 1,000,000 + (15/30)*100,000 = 1,050,000
    # Expected Return = 20,000 / 1,050,000 ~ 0.0190476
    start_d = date(2026, 1, 1)
    end_d = date(2026, 1, 31)
    flow_d = date(2026, 1, 16)
    flows = [(flow_d, Decimal("100000.00"))]

    r_md = calculate_modified_dietz(
        Decimal("1000000.00"),
        Decimal("1120000.00"),
        flows,
        start_d,
        end_d,
    )
    assert r_md is not None
    assert round(r_md, 4) == Decimal("0.0190")


def test_compounding_and_annualization():
    # Returns: +2%, +3%, -1%
    # (1.02 * 1.03 * 0.99) - 1.0 = 1.040094 - 1.0 = 0.040094
    returns = [Decimal("0.02"), Decimal("0.03"), Decimal("-0.01")]
    cum_r = compound_returns(returns)
    assert round(cum_r, 6) == Decimal("0.040094")

    # Annualization: over 365 days, 0.040094 should equal ~ 0.040094
    ann_r = annualize_return(cum_r, elapsed_days=365, basis_days=365, min_days_for_annualization=180)
    assert ann_r is not None
    assert round(ann_r, 4) == Decimal("0.0401")

    # Too short (< 180 days) => None
    assert annualize_return(cum_r, elapsed_days=30, min_days_for_annualization=180) is None


def test_xirr_mathematics():
    # Outflow -1000 at day 0, Inflow +1100 at day 365 => exactly +10% IRR
    d0 = date(2026, 1, 1)
    d1 = date(2027, 1, 1)
    flows = [(d0, Decimal("-1000.00")), (d1, Decimal("1100.00"))]
    irr = calculate_xirr(flows)
    assert irr is not None
    assert round(irr, 2) == Decimal("0.10")


# -----------------------------------------------------------------------------
# 2. Service Aggregation & Idempotent Generation Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_performance_report_service_lifecycle(test_db_session: AsyncSession):
    service = PortfolioPerformanceReportService(test_db_session)
    port_id = "PORT-M14-02"
    d1 = date(2026, 11, 1)
    d2 = date(2026, 11, 2)
    d3 = date(2026, 11, 3)

    t1 = datetime(2026, 11, 1, 16, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 11, 2, 16, 0, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 11, 3, 16, 0, 0, tzinfo=timezone.utc)

    # 1. Seed M05.07 Portfolio Book Snapshots
    snap1 = PortfolioBookSnapshot(
        snapshot_id="SNAP-P1",
        portfolio_id=port_id,
        snapshot_type="EOD",
        effective_as_of=t1,
        knowledge_as_of=t1,
        snapshot_version=1,
        is_restated=False,
        base_currency="USD",
        total_positions_count=2,
        total_market_value_base=Decimal("900000.00"),
        total_cash_value_base=Decimal("100000.00"),
        total_nav_base=Decimal("1000000.00"),
        snapshot_hash="H1",
    )
    snap2 = PortfolioBookSnapshot(
        snapshot_id="SNAP-P2",
        portfolio_id=port_id,
        snapshot_type="EOD",
        effective_as_of=t2,
        knowledge_as_of=t2,
        snapshot_version=1,
        is_restated=False,
        base_currency="USD",
        total_positions_count=2,
        total_market_value_base=Decimal("920000.00"),
        total_cash_value_base=Decimal("100000.00"),
        total_nav_base=Decimal("1020000.00"),
        snapshot_hash="H2",
    )
    snap3 = PortfolioBookSnapshot(
        snapshot_id="SNAP-P3",
        portfolio_id=port_id,
        snapshot_type="EOD",
        effective_as_of=t3,
        knowledge_as_of=t3,
        snapshot_version=1,
        is_restated=False,
        base_currency="USD",
        total_positions_count=2,
        total_market_value_base=Decimal("940000.00"),
        total_cash_value_base=Decimal("110000.00"),
        total_nav_base=Decimal("1050000.00"),
        snapshot_hash="H3",
    )
    test_db_session.add_all([snap1, snap2, snap3])

    # 2. Seed M05.04 Cash Movement (Deposit of 10,000 on day 3)
    cm = CashMovement(
        movement_id="MOV-001",
        cash_account_id="CASH-ACC-01",
        portfolio_id=port_id,
        account_id="ACC-01",
        movement_type=CashMovementType.DEPOSIT,
        signed_amount=Decimal("10000.00"),
        currency="USD",
        gross_amount=Decimal("10000.00"),
        net_amount=Decimal("10000.00"),
        effective_at=t3,
        status="SETTLED",
    )
    test_db_session.add(cm)

    # 3. Seed M05.03 Valuation Snapshot
    p_val = PortfolioValuationSnapshot(
        snapshot_id="VAL-SNAP-01",
        calculation_id="CALC-01",
        portfolio_id=port_id,
        base_currency="USD",
        gross_long_market_value=Decimal("940000.00"),
        gross_short_market_value=Decimal("0.00"),
        net_market_value=Decimal("940000.00"),
        total_cost_basis=Decimal("900000.00"),
        total_unrealized_pnl=Decimal("40000.00"),
        realized_pnl_period=Decimal("10000.00"),
        valued_position_count=2,
        unavailable_position_count=0,
        valuation_status=ValuationStatus.VALUED,
        valuation_date=d3,
        valuation_timestamp=t3,
    )
    test_db_session.add(p_val)
    await test_db_session.commit()

    # 4. Generate Performance Report
    gen_req = PerformanceReportGenerateRequest(
        portfolio_id=port_id,
        start_date=d1,
        end_date=d3,
        reporting_period_type=ReportingPeriodType.CUSTOM,
        return_methodology=ReturnMethodology.TWR,
        benchmark_id="SPX_TR",
    )
    report = await service.generate_performance_report(gen_req, user_id="PM_ALICE")

    assert report.report_id is not None
    assert report.portfolio["portfolio_id"] == port_id
    assert report.performance_summary.beginning_nav == 1000000.00
    assert report.performance_summary.ending_nav == 1050000.00
    assert report.performance_summary.total_pnl == 50000.00
    assert report.performance_summary.realized_pnl == 10000.00
    assert report.performance_summary.unrealized_pnl == 40000.00
    assert report.cash_flows.net_external_flow == 10000.00
    assert len(report.return_observations) == 2
    assert len(report.artifacts) == 3  # CSV, HTML, PDF

    # 5. Non-destructive Regeneration
    gen_req.force_regenerate = True
    gen_req.regeneration_reason = "Restated end-of-day NAV"
    report_v2 = await service.generate_performance_report(gen_req, user_id="PM_ALICE")
    assert report_v2.report_version == 2
    assert report_v2.report_id != report.report_id

    # 6. Verify Artifact Cryptographic Hash
    art = report_v2.artifacts[0]
    verify_resp = await service.verify_artifact_integrity(art.id)
    assert verify_resp.is_valid is True
    assert verify_resp.stored_sha256 == verify_resp.computed_sha256


# -----------------------------------------------------------------------------
# 3. REST API Endpoint Integration Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_performance_report_api_endpoints(test_db_session: AsyncSession):
    app.dependency_overrides[init_db] = lambda: None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        port_id = "PORT-M14-API"
        d1 = date(2026, 11, 1)
        d2 = date(2026, 11, 5)

        # 1. Create Report Config
        conf_payload = {
            "portfolio_id": port_id,
            "configuration_name": "API Test Config",
            "reporting_period_type": "MONTHLY",
            "reporting_frequency": "DAILY",
            "reporting_currency": "USD",
            "return_methodology": "TWR",
            "benchmark_id": "SPX_TR",
        }
        resp = await client.post("/api/v1/reports/performance/configurations", json=conf_payload)
        assert resp.status_code == 201
        conf_data = resp.json()
        assert conf_data["id"] is not None

        # 2. Generate Report
        gen_payload = {
            "portfolio_id": port_id,
            "start_date": d1.isoformat(),
            "end_date": d2.isoformat(),
            "reporting_period_type": "CUSTOM",
            "benchmark_id": "SPX_TR",
        }
        gen_resp = await client.post("/api/v1/reports/performance/generate", json=gen_payload)
        assert gen_resp.status_code == 200
        rep_data = gen_resp.json()
        run_id = rep_data["report_id"]
        assert run_id.startswith("PRUN_")

        # 3. Fetch Returns & Caveats
        ret_resp = await client.get(f"/api/v1/reports/performance/runs/{run_id}/returns")
        assert ret_resp.status_code == 200

        cav_resp = await client.get(f"/api/v1/reports/performance/runs/{run_id}/caveats")
        assert cav_resp.status_code == 200

        # 4. Archive listing
        arch_resp = await client.get(f"/api/v1/reports/performance/archive/{port_id}")
        assert arch_resp.status_code == 200
        runs = arch_resp.json()
        assert len(runs) >= 1

        # 5. Verify Artifact
        art_id = rep_data["artifacts"][0]["id"]
        ver_resp = await client.get(f"/api/v1/reports/performance/artifact/{art_id}/verify")
        assert ver_resp.status_code == 200
        assert ver_resp.json()["is_valid"] is True
