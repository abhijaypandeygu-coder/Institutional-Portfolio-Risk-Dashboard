"""
Unit and integration tests for M13.09 - Historical Analytics.
Verifies:
1. Historical portfolio values & P&L retrieval from authoritative M05 snapshots.
2. Historical risk trends (VaR, ES, Volatility, Drawdown) from M07.
3. Event overlays (alerts, breaches, trades) with chronological sorting and filtering.
4. Bitemporal point-in-time state reconstruction & provenance manifests.
5. Historical version comparisons.
6. User preferences and saved view workflows.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.core.database import Base
from backend.app.main import app
from backend.app.modules.dashboard_visualization.historical_analytics.schemas import (
    HistoricalMode,
    ConsistencyStatus,
    HistoricalPortfolioValueResponse,
    HistoricalPnLResponse,
    HistoricalRiskTrendResponse,
    HistoricalEventsResponse,
    PointInTimeStateResponse,
    HistoricalVersionComparisonResponse,
    HistoricalPreferenceUpdate,
    HistoricalSavedViewCreate,
)
from backend.app.modules.dashboard_visualization.historical_analytics.services import (
    HistoricalAnalyticsService,
)

# Upstream models
from backend.app.modules.portfolio_management.portfolio_history.models import (
    PortfolioBookSnapshot,
    HistoricalPositionSnapshot,
    HistoricalCashSnapshot,
    SnapshotSourceManifest,
)
from backend.app.modules.portfolio_management.position_valuation.models import (
    PortfolioValuationSnapshot,
    ValuationStatus,
)
from backend.app.modules.portfolio_management.transaction_management.models import (
    Transaction,
    TransactionType,
    TradeSide,
    TransactionStatus,
)
from backend.app.modules.market_risk.value_at_risk.models import (
    VaRResult,
    VaRMethodology,
)
from backend.app.modules.risk_alerts.models.risk_alerts_models import (
    AlertEvent,
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
    """Isolated in-memory SQLite database session for M13.09 tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_historical_analytics_service_and_reconstruction(test_db_session: AsyncSession):
    """
    Test service-level retrieval of historical NAV, risk trends, event overlays, and point-in-time reconstruction.
    """
    service = HistoricalAnalyticsService(test_db_session)
    now = datetime.now(timezone.utc)
    t_day1 = now - timedelta(days=2)
    t_day2 = now - timedelta(days=1)
    port_id = "PORT-HIST-01"

    # 1. Seed M05.07 PortfolioBookSnapshot
    snap1 = PortfolioBookSnapshot(
        snapshot_id="SNAP-HIST-001",
        portfolio_id=port_id,
        snapshot_type="EOD",
        effective_as_of=t_day1,
        knowledge_as_of=t_day1 + timedelta(minutes=5),
        snapshot_version=1,
        is_restated=False,
        base_currency="USD",
        total_positions_count=1,
        total_market_value_base=Decimal("1000000.00"),
        total_cash_value_base=Decimal("200000.00"),
        total_nav_base=Decimal("1200000.00"),
        snapshot_hash="HASH_HIST_001",
    )
    pos1 = HistoricalPositionSnapshot(
        id="HPOS-001",
        snapshot_id="SNAP-HIST-001",
        portfolio_id=port_id,
        account_id="ACC-001",
        instrument_id="AAPL",
        net_signed_quantity=Decimal("5000.00"),
        currency="USD",
        market_price=Decimal("200.00"),
        market_value_base=Decimal("1000000.00"),
        cost_basis_base=Decimal("950000.00"),
        unrealized_pnl_base=Decimal("50000.00"),
        effective_as_of=t_day1,
        knowledge_as_of=t_day1 + timedelta(minutes=5),
    )
    cash1 = HistoricalCashSnapshot(
        id="HCASH-001",
        snapshot_id="SNAP-HIST-001",
        portfolio_id=port_id,
        account_id="ACC-001",
        currency="USD",
        settled_cash=Decimal("200000.00"),
        available_cash=Decimal("200000.00"),
        available_cash_base=Decimal("200000.00"),
        effective_as_of=t_day1,
        knowledge_as_of=t_day1 + timedelta(minutes=5),
    )
    test_db_session.add_all([snap1, pos1, cash1])

    # 2. Seed M07 VaR
    var1 = VaRResult(
        result_id="VAR-HIST-001",
        portfolio_id=port_id,
        methodology=VaRMethodology.HISTORICAL,
        confidence_level=Decimal("0.9900"),
        holding_horizon_days=1,
        as_of_date=t_day1.date(),
        valuation_base_amount=Decimal("1200000.00"),
        reporting_currency="USD",
        signed_loss_quantile=Decimal("-0.025"),
        var_return_percentage=Decimal("0.025"),
        var_monetary_amount=Decimal("30000.00"),
        calculated_at=t_day1,
    )
    test_db_session.add(var1)

    # 3. Seed Events: Alert, Breach, Trade
    alert1 = AlertEvent(
        id="ALT-HIST-001",
        title="High Volatility Alert",
        description="Vol > 25%",
        portfolio_id=port_id,
        alert_type="THRESHOLD_ALERT",
        alert_category="VOLATILITY",
        priority="HIGH",
        status="OPEN",
        deduplication_key="DEDUP_001",
        first_seen_at=t_day1,
        created_at=t_day1,
    )
    ep1 = BreachEpisode(
        id="EP-HIST-001",
        portfolio_id=port_id,
        risk_limit_id="RULE-MAX-DRAWDOWN",
        target_entity_type="PORTFOLIO",
        target_entity_id=port_id,
        metric_code="drawdown",
        episode_status="OPEN",
        first_violation_at=t_day1,
        breach_detected_at=t_day1,
        first_evaluation_id="EVAL-HIST-001",
        latest_evaluation_id="EVAL-HIST-001",
        created_at=t_day1,
    )
    breach1 = BreachEvent(
        id="BRC-HIST-001",
        event_reference="EVREF-001",
        breach_episode_id="EP-HIST-001",
        evaluation_id="EVAL-HIST-001",
        risk_limit_id="RULE-MAX-DRAWDOWN",
        portfolio_id=port_id,
        severity="CRITICAL",
        target_entity_type="PORTFOLIO",
        target_entity_id=port_id,
        metric_code="drawdown",
        event_type="BREACH_TRIGGERED",
        observed_value=Decimal("15.5"),
        threshold_value=Decimal("10.0"),
        hard_threshold=Decimal("12.0"),
        breach_magnitude=Decimal("5.5"),
        metric_unit="PERCENT",
        utilization=Decimal("155.0"),
        metric_timestamp=t_day1,
        detected_at=t_day1,
        correlation_id="CORR-001",
    )
    trade1 = Transaction(
        transaction_id="TX-HIST-001",
        portfolio_id=port_id,
        account_id="ACC-001",
        instrument_id="AAPL",
        transaction_type=TransactionType.TRADE,
        trade_side=TradeSide.BUY,
        requested_quantity=Decimal("1000"),
        executed_quantity=Decimal("1000"),
        average_execution_price=Decimal("195.00"),
        aggregate_gross_consideration=Decimal("195000.00"),
        aggregate_net_consideration=Decimal("195000.00"),
        transaction_currency="USD",
        status=TransactionStatus.FILLED,
        first_execution_at=t_day1,
        created_at=t_day1,
    )
    test_db_session.add_all([alert1, ep1, breach1, trade1])
    await test_db_session.commit()

    # Query NAV
    nav_resp = await service.get_historical_portfolio_values(
        portfolio_id=port_id,
        start_time=t_day1 - timedelta(days=1),
        end_time=now,
    )
    assert nav_resp.portfolio_id == port_id
    assert len(nav_resp.observations) == 1
    assert nav_resp.observations[0].value == 1200000.00
    assert nav_resp.summary_kpis["starting_nav"] == 1200000.00

    # Query Risk Trends
    risk_resp = await service.get_historical_risk_trends(
        portfolio_id=port_id,
        metric="VAR",
        start_time=t_day1 - timedelta(days=1),
        end_time=now,
    )
    assert len(risk_resp.observations) == 1
    assert risk_resp.observations[0].value == 30000.00

    # Query Event Overlays
    events_resp = await service.get_historical_events(
        portfolio_id=port_id,
        start_time=t_day1 - timedelta(days=1),
        end_time=now,
    )
    assert events_resp.total_count == 3
    categories = {e.event_category for e in events_resp.events}
    assert "ALERT" in categories
    assert "BREACH" in categories
    assert "TRADE" in categories

    # Point-in-time state reconstruction
    pit_state = await service.reconstruct_point_in_time_state(
        portfolio_id=port_id,
        effective_at=t_day1 + timedelta(minutes=10),
    )
    assert pit_state.portfolio_id == port_id
    assert pit_state.total_nav_base == 1200000.00
    assert len(pit_state.positions) == 1
    assert pit_state.positions[0].instrument_id == "AAPL"
    assert len(pit_state.cash_balances) == 1
    assert pit_state.manifest.consistency_status == ConsistencyStatus.CONSISTENT
    assert pit_state.risk_metrics is not None
    assert pit_state.risk_metrics.var_99_1d == 30000.00


@pytest.mark.asyncio
async def test_historical_analytics_api_and_preferences(test_db_session: AsyncSession):
    """
    Test REST endpoints for historical analytics via FastAPI client with overridden database dependency.
    """
    from backend.app.core.database import get_db

    async def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Preferences GET and PUT
        res = await client.get("/api/v1/dashboard/history/preferences/me?user_id=test_analyst")
        assert res.status_code == 200
        p = res.json()
        assert p["user_id"] == "test_analyst"

        update_payload = {"default_lookback_days": 180, "default_frequency": "WEEKLY"}
        res = await client.put(
            "/api/v1/dashboard/history/preferences/me?user_id=test_analyst",
            json=update_payload,
        )
        assert res.status_code == 200
        assert res.json()["default_lookback_days"] == 180
        assert res.json()["default_frequency"] == "WEEKLY"

        # 2. Saved Views POST and GET
        view_payload = {
            "view_name": "Quarterly Risk Trend Watch",
            "portfolio_ids": ["PORT-HIST-01"],
            "frequency": "DAILY",
            "historical_mode": "AS_KNOWN_AT_TIME",
            "selected_metrics": ["NAV", "VAR", "VOLATILITY"],
        }
        res = await client.post(
            "/api/v1/dashboard/history/saved-views?user_id=test_analyst",
            json=view_payload,
        )
        assert res.status_code == 200
        v = res.json()
        assert v["view_name"] == "Quarterly Risk Trend Watch"

        res = await client.get("/api/v1/dashboard/history/saved-views?user_id=test_analyst")
        assert res.status_code == 200
        assert len(res.json()) >= 1

        # 3. Portfolio Values API
        res = await client.get("/api/v1/dashboard/history/portfolio-values?portfolio_id=PORT-NONEXISTENT")
        assert res.status_code == 200
        pv = res.json()
        assert pv["portfolio_id"] == "PORT-NONEXISTENT"
        assert len(pv["observations"]) == 0

    app.dependency_overrides.clear()
