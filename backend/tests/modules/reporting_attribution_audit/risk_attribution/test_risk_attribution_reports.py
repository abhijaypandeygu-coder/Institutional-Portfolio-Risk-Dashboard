"""
Unit and integration tests for M14.03 — Risk Attribution Reports.
Tests mathematical decomposition, Euler reconciliation, sector/industry aggregation,
factor contribution, caveat deduction, artifact generation, and API endpoints.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
import numpy as np
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.core.database import Base, init_db
from backend.app.main import app
from backend.app.modules.market_risk.risk_contribution.calculations.risk_contribution_math import (
    decompose_portfolio_risk,
)
from backend.app.modules.reporting_attribution_audit.risk_attribution.models.risk_attribution_models import (
    RiskMeasureType,
    ValuationCutoffPolicy,
    ReconciliationStatusType,
    ReportArtifactType,
    RiskAttributionReportConfiguration,
    RiskAttributionReportRun,
    RiskAttributionReportVersion,
)
from backend.app.modules.reporting_attribution_audit.risk_attribution.schemas.risk_attribution_schemas import (
    RiskAttributionGenerateRequest,
    RiskAttributionConfigCreate,
)
from backend.app.modules.reporting_attribution_audit.risk_attribution.services.risk_attribution_service import (
    RiskAttributionReportService,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def test_db_session():
    """Isolated in-memory SQLite database session for M14.03 tests."""
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
# 1. Mathematical Tests
# -----------------------------------------------------------------------------
def test_euler_volatility_decomposition_mathematics():
    """
    Test Euler decomposition formula: sum(RC_i) = sigma_p
    """
    weights = np.array([0.4, 0.4, 0.2])
    cov_matrix = np.array([
        [0.04, 0.01, 0.005],
        [0.01, 0.05, 0.008],
        [0.005, 0.008, 0.03],
    ])
    asset_ids = ["INST-1", "INST-2", "INST-3"]

    res = decompose_portfolio_risk(weights, cov_matrix, asset_ids)

    port_vol = res["portfolio_volatility"]
    sum_crc = sum(h["component_risk_contribution"] for h in res["holdings"])

    assert abs(port_vol - sum_crc) < 1e-6
    # Percentage shares sum to 100%
    sum_pct = sum(h["percentage_risk_contribution"] for h in res["holdings"])
    assert abs(sum_pct - 100.0) < 1e-4


def test_short_hedging_negative_risk_contribution():
    """
    Test signed long/short portfolio where short position yields negative risk contribution.
    """
    weights = np.array([0.8, -0.3])
    # High positive correlation between long asset and short hedge
    cov_matrix = np.array([
        [0.04, 0.035],
        [0.035, 0.04],
    ])
    asset_ids = ["LONG-1", "SHORT-HEDGE"]

    res = decompose_portfolio_risk(weights, cov_matrix, asset_ids)

    port_vol = res["portfolio_volatility"]
    holdings = res["holdings"]

    # Short position component risk contribution should be negative, reducing risk
    short_h = next(h for h in holdings if h["asset_id"] == "SHORT-HEDGE")
    assert short_h["component_risk_contribution"] < 0
    # Reconciliation holds even with negative contributor
    sum_crc = sum(h["component_risk_contribution"] for h in holdings)
    assert abs(port_vol - sum_crc) < 1e-6


# -----------------------------------------------------------------------------
# 2. Service Lifecycle & Reconciliation Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_risk_attribution_service_lifecycle(test_db_session: AsyncSession):
    service = RiskAttributionReportService(test_db_session)
    port_id = "PORT-ATTR-TEST-01"
    rep_date = date(2026, 11, 17)

    # 1. Config creation
    config = await service.get_or_create_configuration(port_id)
    assert config.portfolio_id == port_id
    assert config.risk_measure == RiskMeasureType.PORTFOLIO_VOLATILITY

    # 2. Generate initial report (v1)
    req = RiskAttributionGenerateRequest(
        portfolio_id=port_id,
        reporting_date=rep_date,
        risk_measure=RiskMeasureType.PORTFOLIO_VOLATILITY,
        force_regenerate=False,
    )
    report_v1 = await service.generate_report(req)
    assert report_v1.portfolio_id == port_id
    assert report_v1.report_version == 1
    assert len(report_v1.security_contributions) > 0
    assert len(report_v1.sector_contributions) > 0
    assert len(report_v1.factor_contributions) > 0
    assert len(report_v1.artifacts) == 3  # CSV, HTML, PDF

    # Verify reconciliation
    sec_rec = next(r for r in report_v1.reconciliations if r.attribution_level.value == "SECURITY")
    assert sec_rec.reconciliation_status in (
        ReconciliationStatusType.EXACT_RECONCILIATION,
        ReconciliationStatusType.ROUNDING_DIFFERENCE,
    )

    # 3. Non-destructive force regeneration (v2)
    req_v2 = RiskAttributionGenerateRequest(
        portfolio_id=port_id,
        reporting_date=rep_date,
        risk_measure=RiskMeasureType.PORTFOLIO_VOLATILITY,
        force_regenerate=True,
        regeneration_reason="Updated market covariance matrix",
    )
    report_v2 = await service.generate_report(req_v2)
    assert report_v2.report_version == 2
    assert report_v2.report_id != report_v1.report_id

    # 4. Verify historical run versions count
    runs = await service.list_runs(port_id)
    assert len(runs) == 2
    assert runs[0].report_version == 2
    assert runs[1].report_version == 1


# -----------------------------------------------------------------------------
# 3. Integrity & Cryptographic Checksum Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_artifact_integrity_verification(test_db_session: AsyncSession):
    service = RiskAttributionReportService(test_db_session)
    port_id = "PORT-ATTR-INTEG-01"
    rep_date = date(2026, 11, 17)

    req = RiskAttributionGenerateRequest(
        portfolio_id=port_id,
        reporting_date=rep_date,
    )
    report = await service.generate_report(req)

    # Verify integrity
    integ = await service.verify_artifact_integrity(report.report_id)
    assert integ["is_valid"] is True
    assert len(integ["artifacts"]) == 3
    for art in integ["artifacts"]:
        assert art["status"] == "VALID"
        assert len(art["stored_hash"]) == 64  # SHA-256 length


# -----------------------------------------------------------------------------
# 4. API Endpoints Integration Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_risk_attribution_api_endpoints(test_db_session: AsyncSession):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Config endpoint
        c_res = await ac.get("/api/v1/reports/risk-attribution/configurations/PORT-ATTR-API-01")
        assert c_res.status_code == 200
        c_data = c_res.json()
        assert c_data["portfolio_id"] == "PORT-ATTR-API-01"

        # 2. Generate endpoint
        g_res = await ac.post(
            "/api/v1/reports/risk-attribution/generate",
            json={
                "portfolio_id": "PORT-ATTR-API-01",
                "reporting_date": "2026-11-17",
            },
        )
        assert g_res.status_code == 200
        g_data = g_res.json()
        run_id = g_data["report_id"]
        assert run_id is not None
        assert len(g_data["security_contributions"]) > 0

        # 3. Query sub-endpoints
        sec_res = await ac.get(f"/api/v1/reports/risk-attribution/runs/{run_id}/securities")
        assert sec_res.status_code == 200
        assert len(sec_res.json()) > 0

        sec_res2 = await ac.get(f"/api/v1/reports/risk-attribution/runs/{run_id}/sectors")
        assert sec_res2.status_code == 200
        assert len(sec_res2.json()) > 0

        fac_res = await ac.get(f"/api/v1/reports/risk-attribution/runs/{run_id}/factors")
        assert fac_res.status_code == 200
        assert len(fac_res.json()) > 0

        rec_res = await ac.get(f"/api/v1/reports/risk-attribution/runs/{run_id}/reconciliation")
        assert rec_res.status_code == 200
        assert len(rec_res.json()) > 0

        # 4. Artifact download
        art_res = await ac.get(f"/api/v1/reports/risk-attribution/runs/{run_id}/artifacts/CSV")
        assert art_res.status_code == 200
        assert "text/csv" in art_res.headers["content-type"]
        assert "X-Content-SHA256" in art_res.headers

        # 5. Integrity verification
        v_res = await ac.post(f"/api/v1/reports/risk-attribution/runs/{run_id}/verify-integrity")
        assert v_res.status_code == 200
        assert v_res.json()["is_valid"] is True
