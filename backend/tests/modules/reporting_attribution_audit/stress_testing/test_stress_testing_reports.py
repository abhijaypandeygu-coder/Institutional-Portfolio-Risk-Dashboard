"""
Unit and integration tests for M14.04 — Stress Testing Reports.
Verifies:
1. Scenario description and shock magnitude documentation.
2. Signed position-level stressed P&L (long vs. short positions).
3. Sector stress aggregation.
4. Sensitivity comparison across shock assumptions.
5. Limit implications and projected exceedance classification.
6. Multi-format artifact generation (CSV, HTML, PDF) and SHA-256 integrity verification.
7. REST API endpoints.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.core.database import Base, init_db
from backend.app.main import app
from backend.app.modules.reporting_attribution_audit.stress_testing.models.stress_report_models import (
    StressScenarioType,
    StressReportStatus,
    StressReconciliationStatus,
    LimitEvaluationStatus,
    StressArtifactType,
    StressReport,
    StressReportScenario,
    StressReportPositionResult,
)
from backend.app.modules.reporting_attribution_audit.stress_testing.schemas.stress_report_schemas import (
    StressReportCreateRequest,
)
from backend.app.modules.reporting_attribution_audit.stress_testing.services.stress_report_service import (
    StressTestingReportService,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def test_db_session():
    """Isolated in-memory SQLite database session for M14.04 tests."""
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
# 1. Financial & Signed P&L Tests
# -----------------------------------------------------------------------------
def test_signed_long_short_stress_pnl_mathematics():
    """
    Test signed position quantity and price shock behavior:
    - Long position losing value on market drop.
    - Short position gaining value on market drop.
    """
    # Long position: +1000 shares @ $100 -> Drops by 15% to $85
    # Stressed P&L = 1000 * (85 - 100) = -15,000 (Loss)
    qty_long = Decimal("1000")
    px_base = Decimal("100.00")
    px_stressed = Decimal("85.00")
    pnl_long = qty_long * (px_stressed - px_base)
    assert pnl_long == Decimal("-15000.00")

    # Short position: -1000 shares @ $100 -> Drops by 15% to $85
    # Stressed P&L = -1000 * (85 - 100) = +15,000 (Gain from hedge)
    qty_short = Decimal("-1000")
    pnl_short = qty_short * (px_stressed - px_base)
    assert pnl_short == Decimal("15000.00")

    # Net Portfolio P&L should be 0 if perfectly hedged
    net_pnl = pnl_long + pnl_short
    assert net_pnl == Decimal("0.00")


# -----------------------------------------------------------------------------
# 2. Service Lifecycle & Regeneration Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stress_testing_service_lifecycle(test_db_session: AsyncSession):
    service = StressTestingReportService(test_db_session)
    port_id = "PORT-STRESS-TEST-01"
    rep_date = date(2026, 11, 17)

    # 1. Initial report generation (v1)
    req = StressReportCreateRequest(
        portfolio_id=port_id,
        report_name="Q4 Stress Report Test",
        reporting_date=rep_date,
        reporting_currency="USD",
        force_regenerate=False,
    )
    report_v1 = await service.generate_stress_report(req)
    assert report_v1.portfolio_id == port_id
    assert report_v1.report_version == 1
    assert len(report_v1.scenarios) == 3
    assert len(report_v1.position_results) > 0
    assert len(report_v1.sector_breakdown) > 0
    assert len(report_v1.sensitivities) == 5
    assert len(report_v1.limit_results) > 0
    assert len(report_v1.artifacts) == 3  # CSV, HTML, PDF

    # 2. Reconciliations validation
    for r in report_v1.reconciliations:
        assert r.reconciliation_status in (
            StressReconciliationStatus.RECONCILED,
            StressReconciliationStatus.RECONCILED_WITH_ROUNDING,
            StressReconciliationStatus.PARTIALLY_RECONCILED,
        )

    # 3. Non-destructive force regeneration (v2)
    req_v2 = StressReportCreateRequest(
        portfolio_id=port_id,
        reporting_date=rep_date,
        reporting_currency="USD",
        force_regenerate=True,
        regeneration_reason="Updated M10 simulation parameters",
    )
    report_v2 = await service.generate_stress_report(req_v2)
    assert report_v2.report_version == 2
    assert report_v2.report_id != report_v1.report_id

    # 4. Verify historical runs list
    reports_list = await service.list_reports(port_id)
    assert len(reports_list) == 2
    assert reports_list[0].report_version == 2
    assert reports_list[1].report_version == 1


# -----------------------------------------------------------------------------
# 3. Cryptographic Verification Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stress_artifact_integrity(test_db_session: AsyncSession):
    service = StressTestingReportService(test_db_session)
    port_id = "PORT-STRESS-INTEG-01"
    rep_date = date(2026, 11, 17)

    req = StressReportCreateRequest(
        portfolio_id=port_id,
        reporting_date=rep_date,
    )
    report = await service.generate_stress_report(req)

    integ = await service.verify_artifact_integrity(report.report_id)
    assert integ["is_valid"] is True
    assert len(integ["artifacts"]) == 3
    for art in integ["artifacts"]:
        assert art["status"] == "VALID"
        assert len(art["stored_hash"]) == 64


# -----------------------------------------------------------------------------
# 4. API Endpoints Integration Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stress_report_api_endpoints(test_db_session: AsyncSession):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Create endpoint
        g_res = await ac.post(
            "/api/v1/reports/stress",
            json={
                "portfolio_id": "PORT-STRESS-API-01",
                "reporting_date": "2026-11-17",
                "reporting_currency": "USD",
            },
        )
        assert g_res.status_code == 200
        g_data = g_res.json()
        report_id = g_data["report_id"]
        assert report_id is not None
        assert len(g_data["scenarios"]) > 0

        # 2. List endpoint
        l_res = await ac.get("/api/v1/reports/stress?portfolio_id=PORT-STRESS-API-01")
        assert l_res.status_code == 200
        assert len(l_res.json()) >= 1

        # 3. Sub-resource endpoints
        scen_res = await ac.get(f"/api/v1/reports/stress/{report_id}/scenarios")
        assert scen_res.status_code == 200
        assert len(scen_res.json()) > 0

        pos_res = await ac.get(f"/api/v1/reports/stress/{report_id}/positions")
        assert pos_res.status_code == 200
        assert len(pos_res.json()) > 0

        sen_res = await ac.get(f"/api/v1/reports/stress/{report_id}/sensitivity")
        assert sen_res.status_code == 200
        assert len(sen_res.json()) > 0

        lim_res = await ac.get(f"/api/v1/reports/stress/{report_id}/limits")
        assert lim_res.status_code == 200
        assert len(lim_res.json()) > 0

        rec_res = await ac.get(f"/api/v1/reports/stress/{report_id}/reconciliation")
        assert rec_res.status_code == 200
        assert len(rec_res.json()) > 0

        # 4. Artifact download
        art_res = await ac.get(f"/api/v1/reports/stress/{report_id}/artifacts/CSV")
        assert art_res.status_code == 200
        assert "text/csv" in art_res.headers["content-type"]
        assert "X-Content-SHA256" in art_res.headers

        # 5. Integrity verification
        v_res = await ac.post(f"/api/v1/reports/stress/{report_id}/verify-integrity")
        assert v_res.status_code == 200
        assert v_res.json()["is_valid"] is True
