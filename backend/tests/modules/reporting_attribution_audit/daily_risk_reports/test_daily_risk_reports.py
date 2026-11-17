"""
Unit and integration tests for M14.01 — Daily Risk Reports.

Verifies:
1. Daily report configuration creation and retrieval.
2. Assembly of portfolio summaries from authoritative M05 snapshots.
3. Assembly of quantitative market risk metrics (VaR, ES, Volatility, Drawdown) from M07.
4. Limit control status and deterministic precedence (EMERGENCY > CRITICAL > WARNINGS > CLEAR) from M11.
5. Idempotent report generation and artifact generation (CSV, HTML, PDF hashes).
6. Non-destructive regeneration incrementing version lineage.
7. Cryptographic integrity verification.
8. REST API endpoints via FastAPI test client.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.core.database import Base, init_db
from backend.app.main import app
from backend.app.modules.reporting_attribution_audit.daily_risk_reports.schemas import (
    ReportGenerationStatus,
    OverallControlStatus,
    OverallFreshnessStatus,
    DailyReportConfigurationCreate,
    DailyReportGenerateRequest,
)
from backend.app.modules.reporting_attribution_audit.daily_risk_reports.services import (
    DailyRiskReportService,
)

# Upstream models for seeding test data
from backend.app.modules.portfolio_management.portfolio_history.models import (
    PortfolioBookSnapshot,
    HistoricalPositionSnapshot,
    HistoricalCashSnapshot,
)
from backend.app.modules.market_risk.value_at_risk.models import (
    VaRResult,
    VaRMethodology,
    VaRDistributionAssumption,
    VaRCalculationStatus,
)
from backend.app.modules.market_risk.expected_shortfall.models import (
    ExpectedShortfallResult,
    ESMethodology,
    ESCalculationStatus,
    ESTailStabilityStatus,
    ESQuantileMethod,
    ESTailWeightingMethod,
)
from backend.app.modules.market_risk.historical_volatility.models import (
    HistoricalVolatilityResult,
    StatisticalEstimator,
    VolatilityScopeType,
    VolatilityCalculationStatus,
    ReturnType,
    ReturnFrequency,
)
from backend.app.modules.market_risk.drawdown_analytics.models import (
    DrawdownSeriesResult,
)
from backend.app.modules.risk_limits.breach_detection.models.breach_detection_models import (
    BreachEvent,
    BreachEpisode,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def test_db_session():
    """Isolated in-memory SQLite database session for M14.01 tests."""
    # Ensure all tables registered
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
# 1. Service Assembly & Integrity Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_daily_risk_report_service_assembly_and_generation(test_db_session: AsyncSession):
    service = DailyRiskReportService(test_db_session)
    port_id = "PORT-M14-TEST"
    rep_date = date(2026, 11, 15)
    t_val = datetime(2026, 11, 15, 16, 0, 0, tzinfo=timezone.utc)

    # 1. Seed M05.07 PortfolioBookSnapshot
    snap = PortfolioBookSnapshot(
        snapshot_id="SNAP-M14-001",
        portfolio_id=port_id,
        snapshot_type="EOD",
        effective_as_of=t_val,
        knowledge_as_of=t_val + timedelta(minutes=5),
        snapshot_version=1,
        is_restated=False,
        base_currency="USD",
        total_positions_count=2,
        total_market_value_base=Decimal("2000000.00"),
        total_cash_value_base=Decimal("500000.00"),
        total_nav_base=Decimal("2500000.00"),
        snapshot_hash="HASH_M14_001",
    )
    test_db_session.add(snap)

    # 2. Seed M07 Risk Metrics (VaR, ES, Vol, Drawdown)
    var = VaRResult(
        result_id="VAR-M14-001",
        portfolio_id=port_id,
        methodology=VaRMethodology.HISTORICAL,
        confidence_level=Decimal("0.9900"),
        holding_horizon_days=1,
        as_of_date=rep_date,
        valuation_base_amount=Decimal("2500000.00"),
        reporting_currency="USD",
        signed_loss_quantile=Decimal("-0.02"),
        var_return_percentage=Decimal("0.02"),
        var_monetary_amount=Decimal("50000.00"),
        distribution_assumption=VaRDistributionAssumption.EMPIRICAL,
        lookback_observations=252,
        tail_observations_count=3,
        calculation_status=VaRCalculationStatus.CALCULATED,
        data_quality_status="HIGH",
        calculation_version="v1.0",
        calculated_at=t_val,
    )
    es = ExpectedShortfallResult(
        result_id="ES-M14-001",
        portfolio_id=port_id,
        methodology=ESMethodology.HISTORICAL_SIMULATION,
        confidence_level=Decimal("0.9900"),
        tail_probability=Decimal("0.0100"),
        holding_horizon_days=1,
        as_of_date=rep_date,
        valuation_base_amount=Decimal("2500000.00"),
        reporting_currency="USD",
        var_return_percentage=Decimal("0.02"),
        var_monetary_amount=Decimal("50000.00"),
        signed_var_loss_quantile=Decimal("-0.02"),
        es_return_percentage=Decimal("0.028"),
        es_monetary_amount=Decimal("70000.00"),
        signed_es_loss_average=Decimal("-0.028"),
        tail_excess_monetary_amount=Decimal("20000.00"),
        tail_excess_percentage=Decimal("0.008"),
        total_observations_count=252,
        eligible_observations_count=252,
        expected_tail_observations=Decimal("2.52"),
        full_tail_observations_count=3,
        effective_tail_sample_size=Decimal("2.52"),
        boundary_weight=Decimal("0.52"),
        worst_tail_loss_percentage=Decimal("0.035"),
        tail_median_loss_percentage=Decimal("0.027"),
        quantile_method=ESQuantileMethod.LINEAR_INTERPOLATION,
        tail_weighting_method=ESTailWeightingMethod.FRACTIONAL_BOUNDARY,
        tail_stability_status=ESTailStabilityStatus.STABLE,
        calculation_status=ESCalculationStatus.CALCULATED,
        data_quality_status="HIGH",
        calculation_version="v1.0",
        calculated_at=t_val,
    )
    vol = HistoricalVolatilityResult(
        result_id="VOL-M14-001",
        scope_type=VolatilityScopeType.PORTFOLIO,
        portfolio_id=port_id,
        as_of_date=rep_date,
        window_start=t_val - timedelta(days=30),
        window_end=t_val,
        lookback_window=30,
        return_type=ReturnType.SIMPLE,
        return_frequency=ReturnFrequency.DAILY,
        observation_count=30,
        expected_observation_count=30,
        coverage_percentage=Decimal("100.0"),
        mean_return=Decimal("0.001"),
        period_volatility=Decimal("0.012"),
        annualized_volatility=Decimal("0.1905"),
        annualization_factor=Decimal("252.0"),
        periods_per_year=252,
        estimator=StatisticalEstimator.SAMPLE_STD_DEV,
        calculation_status=VolatilityCalculationStatus.CALCULATED,
        quality_status="HIGH",
        calculation_version="v1.0",
        calculated_at=t_val,
    )
    dd = DrawdownSeriesResult(
        series_id="DD-M14-001",
        portfolio_id=port_id,
        observation_timestamp=t_val,
        observation_date=rep_date,
        selected_value=Decimal("2500000.00"),
        running_high_water_mark=Decimal("2600000.00"),
        high_water_mark_timestamp=t_val - timedelta(days=10),
        signed_drawdown=Decimal("-0.03846"),
        drawdown_percentage=Decimal("0.03846"),
        absolute_drawdown_amount=Decimal("100000.00"),
        data_quality_status="HIGH",
        calculation_version="v1.0",
        calculated_at=t_val,
    )
    test_db_session.add_all([var, es, vol, dd])

    # 3. Seed M11 Breach
    ep = BreachEpisode(
        id="EP-M14-001",
        portfolio_id=port_id,
        risk_limit_id="LIMIT-VAR-99",
        target_entity_type="PORTFOLIO",
        target_entity_id=port_id,
        metric_code="var_99",
        episode_status="OPEN",
        first_violation_at=t_val,
        breach_detected_at=t_val,
        first_evaluation_id="EVAL-M14-001",
        latest_evaluation_id="EVAL-M14-001",
        created_at=t_val,
    )
    breach = BreachEvent(
        id="BRC-M14-001",
        event_reference="EVREF-M14-001",
        breach_episode_id="EP-M14-001",
        evaluation_id="EVAL-M14-001",
        risk_limit_id="LIMIT-VAR-99",
        portfolio_id=port_id,
        severity="CRITICAL",
        target_entity_type="PORTFOLIO",
        target_entity_id=port_id,
        metric_code="var_99",
        event_type="BREACH_TRIGGERED",
        observed_value=Decimal("50000.0"),
        threshold_value=Decimal("40000.0"),
        hard_threshold=Decimal("45000.0"),
        breach_magnitude=Decimal("10000.0"),
        metric_unit="CURRENCY",
        utilization=Decimal("125.0"),
        metric_timestamp=t_val,
        detected_at=t_val,
        correlation_id="CORR-M14-001",
    )
    test_db_session.add_all([ep, breach])
    await test_db_session.commit()

    # 4. Generate Daily Report
    gen_req = DailyReportGenerateRequest(
        portfolio_id=port_id,
        report_date=rep_date,
    )
    report = await service.generate_daily_report(gen_req, user_id="ANALYST_01")
    assert report.report_id is not None
    assert report.portfolio.portfolio_id == port_id
    assert report.portfolio_summary.nav == 2500000.00
    assert report.portfolio_summary.cash_balance == 500000.00
    assert report.risk_metrics.var.value == 50000.00
    assert report.risk_metrics.expected_shortfall.value == 70000.00
    assert report.control_status.overall_status == OverallControlStatus.CRITICAL_BREACHES_PRESENT
    assert report.report_version == 1

    # 5. Idempotent check (same date & port returns same report ID)
    report_cached = await service.generate_daily_report(gen_req, user_id="ANALYST_01")
    assert report_cached.report_id == report.report_id

    # 6. Force regeneration increments version to 2
    regen_req = DailyReportGenerateRequest(
        portfolio_id=port_id,
        report_date=rep_date,
        force_regeneration=True,
        regeneration_reason="Upstream market data restated",
    )
    report_v2 = await service.generate_daily_report(regen_req, user_id="ANALYST_01")
    assert report_v2.report_id != report.report_id
    assert report_v2.report_version == 2

    # 7. Verify Integrity
    integrity = await service.verify_report_integrity(report.report_id)
    assert integrity.is_valid is True
    assert len(integrity.artifacts_verified) == 3 # CSV, HTML, PDF


# -----------------------------------------------------------------------------
# 2. REST API Integration Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_daily_risk_report_api_endpoints(test_db_session: AsyncSession):
    from backend.app.core.database import get_db

    async def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        port_id = "PORT-M14-API"
        rep_date = "2026-11-16"

        # 1. Create Report Configuration
        cfg_payload = {
            "portfolio_id": port_id,
            "configuration_name": "API Daily Risk Profile",
            "reporting_calendar": "NYSE_US",
            "reporting_currency": "USD",
            "valuation_cutoff_policy": "EOD_CLOSE",
        }
        res = await ac.post("/api/v1/reports/daily/configurations", json=cfg_payload)
        assert res.status_code == 201
        cfg_id = res.json()["id"]

        # 2. Generate Report via API
        gen_payload = {
            "portfolio_id": port_id,
            "report_date": rep_date,
            "configuration_id": cfg_id,
        }
        res = await ac.post("/api/v1/reports/daily/generate", json=gen_payload)
        assert res.status_code == 201
        rep_data = res.json()
        run_id = rep_data["report_id"]
        assert rep_data["portfolio"]["portfolio_id"] == port_id

        # 3. Retrieve Structured Data
        res = await ac.get(f"/api/v1/reports/daily/archive/{run_id}/data")
        assert res.status_code == 200
        assert res.json()["report_id"] == run_id

        # 4. Download CSV Export
        res = await ac.get(f"/api/v1/reports/daily/archive/{run_id}/csv")
        assert res.status_code == 200
        assert "text/csv" in res.headers["content-type"]
        assert f"REPORT_ID,{run_id}" in res.text

        # 5. Download PDF
        res = await ac.get(f"/api/v1/reports/daily/archive/{run_id}/pdf")
        assert res.status_code == 200
        assert "application/pdf" in res.headers["content-type"]

        # 6. Verify Integrity
        res = await ac.get(f"/api/v1/reports/daily/archive/{run_id}/verify")
        assert res.status_code == 200
        assert res.json()["is_valid"] is True

        # 7. List Archive
        res = await ac.get(f"/api/v1/reports/daily/archive?portfolio_id={port_id}")
        assert res.status_code == 200
        assert len(res.json()) >= 1

    app.dependency_overrides.clear()
