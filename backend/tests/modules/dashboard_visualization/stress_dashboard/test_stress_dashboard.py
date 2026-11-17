"""
Test suite for M13.07 — Stress Testing Dashboard.

Validates:
1. Scenario Library & Selection: Retrieving historical events, hypothetical scenarios, and Monte Carlo definitions.
2. Stressed Portfolio Results: Baseline NAV, stressed NAV, stressed P&L, % return, and position-level outcomes.
3. Monte Carlo Loss Distribution: Histogram bins, quantiles (p01..p99), and tail loss (VaR 95/99, CVaR 95/99).
4. Scenario Comparison: Side-by-side comparison table, ranking by loss magnitude, and compatibility validation.
5. Stress Loss Attribution: Position, sector, and factor contribution decomposition and residual reconciliation.
6. Persistence: Dashboard preferences, saved comparison views, and scenario annotations.
7. REST API Endpoints: Complete contract testing with AsyncClient.
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.main import app
from backend.app.modules.instrument_reference_data.instrument_master.models import Instrument
from backend.app.modules.portfolio_management.portfolio_creation.models import (
    Portfolio,
    PortfolioLifecycleStatus,
    PortfolioTypeEnum,
    CreationSourceEnum,
    MarketScopeEnum,
)
from backend.app.modules.scenario_analysis.historical_scenarios.models.scenario_models import (
    HistoricalScenarioEvent,
    HistoricalScenarioReplayRun,
    HistoricalScenarioReplayPosition,
)
from backend.app.modules.scenario_analysis.monte_carlo.models.monte_carlo_models import (
    MonteCarloScenario,
    MonteCarloSimulationRun,
    MonteCarloSimulationSummary,
    MonteCarloRiskMetric,
    MonteCarloInstrumentResult,
)
from backend.app.modules.scenario_analysis.loss_attribution.models.attribution_models import (
    StressLossAttribution,
    StressLossAttributionRun,
    StressPositionContribution,
    StressSectorContribution,
    StressFactorContribution,
)
from backend.app.modules.dashboard_visualization.stress_dashboard.services.stress_dashboard_service import (
    StressDashboardService,
)
from backend.app.modules.dashboard_visualization.stress_dashboard.schemas.stress_dashboard_schemas import (
    StressPreferenceCreateRequest,
    StressSavedViewCreateRequest,
    StressAnnotationCreateRequest,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()
    yield


@pytest.mark.asyncio
async def test_stress_dashboard_services_and_analytics():
    """Verifies scenario library, results, Monte Carlo distributions, comparisons, and attributions."""
    suffix = uuid.uuid4().hex[:6]
    port_id = f"PORT_STR_{suffix}"
    hist_event_id = f"EVT_STR_{suffix}"
    hist_run_id = f"RUN_STR_{suffix}"
    mc_scen_id = f"MC_SCEN_{suffix}"
    mc_run_id = f"MC_RUN_{suffix}"
    attr_id = f"ATTR_STR_{suffix}"
    attr_run_id = f"ATTR_RUN_{suffix}"

    inst_id_1 = f"INST_A_{suffix}"
    inst_id_2 = f"INST_B_{suffix}"

    now = utc_now()

    async with AsyncSessionLocal() as session:
        # 1. Create Portfolio & Instruments
        port = Portfolio(
            portfolio_id=port_id,
            portfolio_code=port_id,
            portfolio_name=f"Stress Test Portfolio {suffix}",
            short_name="Stress Port",
            base_currency="USD",
            lifecycle_status=PortfolioLifecycleStatus.ACTIVE,
            portfolio_type=PortfolioTypeEnum.DISCRETIONARY,
            creation_source=CreationSourceEnum.MANUAL_ADMINISTRATION,
            market_scope=MarketScopeEnum.UNITED_STATES,
            created_by="TEST_ADMIN",
        )
        ia = Instrument(
            instrument_id=inst_id_1,
            canonical_name="Stress Asset A",
            short_name="ST_A",
            instrument_type="COMMON_STOCK",
            asset_class="EQUITY",
            issue_currency="USD",
        )
        ib = Instrument(
            instrument_id=inst_id_2,
            canonical_name="Stress Asset B",
            short_name="ST_B",
            instrument_type="COMMON_STOCK",
            asset_class="EQUITY",
            issue_currency="USD",
        )
        session.add_all([port, ia, ib])

        # 2. Historical Scenario Event & Replay Run
        event = HistoricalScenarioEvent(
            id=hist_event_id,
            event_code=f"GFC_2008_{suffix}",
            event_name="Global Financial Crisis 2008",
            description="Lehman collapse credit shock episode",
            category="CRISIS",
            start_date=now - timedelta(days=60),
            end_date=now - timedelta(days=30),
            event_status="ACTIVE",
            current_version="1.0.0",
        )
        session.add(event)

        replay_run = HistoricalScenarioReplayRun(
            id=hist_run_id,
            replay_code=f"REPLAY_{suffix}",
            portfolio_id=port_id,
            scenario_event_id=hist_event_id,
            base_currency="USD",
            replay_status="COMPLETED",
            baseline_nav=Decimal("10000000.00"),
            scenario_nav=Decimal("8200000.00"),
            scenario_pnl=Decimal("-1800000.00"),
            scenario_return=Decimal("-0.18"),
            direct_coverage=Decimal("0.80"),
            proxy_coverage=Decimal("0.20"),
            started_at=now - timedelta(hours=2),
            completed_at=now - timedelta(hours=1),
        )
        session.add(replay_run)

        pos_1 = HistoricalScenarioReplayPosition(
            id=f"POS_REP_1_{suffix}",
            replay_id=hist_run_id,
            instrument_id=inst_id_1,
            listing_id="ST_A",
            signed_quantity=Decimal("10000.0"),
            baseline_price=Decimal("500.00"),
            baseline_market_value=Decimal("5000000.00"),
            local_currency="USD",
            local_return=Decimal("-0.24"),
            fx_return=Decimal("0.0"),
            base_currency_return=Decimal("-0.24"),
            scenario_price=Decimal("380.00"),
            scenario_market_value=Decimal("3800000.00"),
            scenario_pnl=Decimal("-1200000.00"),
            portfolio_weight=Decimal("0.50"),
            portfolio_contribution=Decimal("-0.12"),
            mapping_method="EXACT_DIRECT",
        )
        pos_2 = HistoricalScenarioReplayPosition(
            id=f"POS_REP_2_{suffix}",
            replay_id=hist_run_id,
            instrument_id=inst_id_2,
            listing_id="ST_B",
            signed_quantity=Decimal("20000.0"),
            baseline_price=Decimal("250.00"),
            baseline_market_value=Decimal("5000000.00"),
            local_currency="USD",
            local_return=Decimal("-0.12"),
            fx_return=Decimal("0.0"),
            base_currency_return=Decimal("-0.12"),
            scenario_price=Decimal("220.00"),
            scenario_market_value=Decimal("4400000.00"),
            scenario_pnl=Decimal("-600000.00"),
            portfolio_weight=Decimal("0.50"),
            portfolio_contribution=Decimal("-0.06"),
            mapping_method="EXACT_DIRECT",
        )
        session.add_all([pos_1, pos_2])

        # 3. Monte Carlo Scenario & Run
        mc_scen = MonteCarloScenario(
            id=mc_scen_id,
            scenario_code=f"MC_SIM_{suffix}",
            name="20-Day Heavy Tail Simulation",
            description="Student-t 5 DOF simulation",
            horizon_days=20,
            distribution_type="STUDENT_T",
            degrees_of_freedom=5.0,
            is_active=True,
        )
        session.add(mc_scen)

        mc_run = MonteCarloSimulationRun(
            id=mc_run_id,
            scenario_id=mc_scen_id,
            run_code=f"MC_RUN_{suffix}",
            portfolio_id=port_id,
            n_paths=10000,
            n_steps=20,
            random_seed=12345,
            generator_algorithm="PCG64",
            status="COMPLETED",
            input_parameters_hash=f"hash_{suffix}",
            executed_at=now - timedelta(hours=1),
        )
        session.add(mc_run)

        mc_sum = MonteCarloSimulationSummary(
            id=f"MC_SUM_{suffix}",
            run_id=mc_run_id,
            baseline_portfolio_value=Decimal("10000000.00"),
            mean_terminal_value=Decimal("9850000.00"),
            median_terminal_value=Decimal("9920000.00"),
            std_terminal_value=Decimal("450000.00"),
            mean_pnl=Decimal("-150000.00"),
            median_pnl=Decimal("-80000.00"),
            std_pnl=Decimal("450000.00"),
            skewness_pnl=-0.42,
            excess_kurtosis_pnl=1.85,
            loss_probability=0.55,
            min_pnl=Decimal("-1950000.00"),
            max_pnl=Decimal("1200000.00"),
            percentiles_json={
                "p01": -1650000.0,
                "p05": -920000.0,
                "p10": -640000.0,
                "p50": -80000.0,
                "p95": 650000.0,
                "p99": 1050000.0,
            },
        )
        mc_metric = MonteCarloRiskMetric(
            id=f"MC_METRIC_{suffix}",
            run_id=mc_run_id,
            confidence_level=0.95,
            var_loss_amount=Decimal("920000.00"),
            cvar_loss_amount=Decimal("1280000.00"),
            var_percent=0.092,
            cvar_percent=0.128,
            pnl_cutoff_amount=Decimal("-920000.00"),
        )
        mc_inst = MonteCarloInstrumentResult(
            id=f"MC_INST_{suffix}",
            run_id=mc_run_id,
            symbol="ST_A",
            quantity=Decimal("10000.0"),
            baseline_price=Decimal("500.00"),
            baseline_market_value=Decimal("5000000.00"),
            mean_terminal_price=Decimal("485.00"),
            mean_pnl=Decimal("-150000.00"),
            pnl_std=Decimal("450000.00"),
            var_95_loss=Decimal("460000.00"),
            annualized_volatility=0.25,
        )
        session.add_all([mc_sum, mc_metric, mc_inst])

        # 4. Stress Loss Attribution Run
        attr = StressLossAttribution(
            id=attr_id,
            attribution_code=f"ATTR_CODE_{suffix}",
            name="GFC Loss Attribution",
            portfolio_id=port_id,
            scenario_id=hist_event_id,
            scenario_run_id=hist_run_id,
            scenario_type="HISTORICAL",
            base_currency="USD",
        )
        session.add(attr)

        attr_run = StressLossAttributionRun(
            id=attr_run_id,
            attribution_id=attr_id,
            run_code=f"ATTR_RUN_CODE_{suffix}",
            scenario_run_id=hist_run_id,
            execution_status="COMPLETED",
            authoritative_total_pnl=Decimal("-1800000.00"),
            explained_pnl=Decimal("-1800000.00"),
            residual_amount=Decimal("0.0"),
            is_reconciled=True,
            loss_hhi=0.55,
            effective_contributor_count=1.8,
        )
        session.add(attr_run)

        pos_attr_1 = StressPositionContribution(
            id=f"PAC_1_{suffix}",
            attribution_run_id=attr_run_id,
            symbol="ST_A",
            quantity=Decimal("10000.0"),
            position_direction="LONG",
            baseline_price=Decimal("500.00"),
            stressed_price=Decimal("380.00"),
            baseline_market_value=Decimal("5000000.00"),
            stressed_market_value=Decimal("3800000.00"),
            price_pnl=Decimal("-1200000.00"),
            total_pnl=Decimal("-1200000.00"),
            loss_contribution=Decimal("-1200000.00"),
            contribution_percentage=Decimal("66.67"),
            sector="Financials",
            industry="Banking",
        )
        pos_attr_2 = StressPositionContribution(
            id=f"PAC_2_{suffix}",
            attribution_run_id=attr_run_id,
            symbol="ST_B",
            quantity=Decimal("20000.0"),
            position_direction="LONG",
            baseline_price=Decimal("250.00"),
            stressed_price=Decimal("220.00"),
            baseline_market_value=Decimal("5000000.00"),
            stressed_market_value=Decimal("4400000.00"),
            price_pnl=Decimal("-600000.00"),
            total_pnl=Decimal("-600000.00"),
            loss_contribution=Decimal("-600000.00"),
            contribution_percentage=Decimal("33.33"),
            sector="Technology",
            industry="Software",
        )
        sec_attr_1 = StressSectorContribution(
            id=f"SAC_1_{suffix}",
            attribution_run_id=attr_run_id,
            sector_name="Financials",
            holding_count=1,
            baseline_market_value=Decimal("5000000.00"),
            stressed_market_value=Decimal("3800000.00"),
            total_pnl=Decimal("-1200000.00"),
            loss_contribution=Decimal("-1200000.00"),
            contribution_percentage=Decimal("66.67"),
        )
        fac_attr_1 = StressFactorContribution(
            id=f"FAC_1_{suffix}",
            attribution_run_id=attr_run_id,
            factor_name="MARKET_BETA",
            factor_exposure=1.20,
            factor_shock=-0.15,
            contribution_value=Decimal("-1500000.00"),
            loss_contribution=Decimal("-1500000.00"),
        )
        session.add_all([pos_attr_1, pos_attr_2, sec_attr_1, fac_attr_1])
        await session.commit()

    # --- Run Service Layer Assertions ---
    async with AsyncSessionLocal() as session:
        svc = StressDashboardService(session)

        # 1. Scenario Library Listing
        scenarios = await svc.list_scenarios(portfolio_id=port_id)
        assert len(scenarios) >= 2
        categories = [s.category for s in scenarios]
        assert "HISTORICAL" in categories
        assert "MONTE_CARLO" in categories

        # 2. Detailed Definition Inspection
        defn = await svc.get_scenario_definition(hist_event_id)
        assert defn.scenario_id == hist_event_id
        assert defn.category == "HISTORICAL"
        assert defn.scenario_name == "Global Financial Crisis 2008"

        # 3. Scenario Results & Positions
        res = await svc.get_scenario_result(hist_run_id)
        assert res.summary.calculation_id == hist_run_id
        assert res.summary.baseline_nav == Decimal("10000000.00")
        assert res.summary.stressed_nav == Decimal("8200000.00")
        assert res.summary.stressed_pnl == Decimal("-1800000.00")
        assert res.summary.return_percentage == Decimal("-18.0")
        assert len(res.positions) == 2
        assert res.positions[0].symbol == "ST_A"
        assert res.positions[0].stressed_pnl == Decimal("-1200000.00")

        # 4. Monte Carlo Distribution
        dist = await svc.get_monte_carlo_distribution(mc_run_id)
        assert dist.simulation_id == mc_run_id
        assert dist.n_paths == 10000
        assert dist.horizon_days == 20
        assert dist.var_95_loss == Decimal("920000.00")
        assert dist.cvar_95_loss == Decimal("1280000.00")
        assert "p01" in dist.quantiles
        assert len(dist.histogram_bins) == 15

        # 5. Scenario Comparison
        comp = await svc.compare_scenarios(portfolio_id=port_id, calculation_ids=[hist_run_id, mc_run_id])
        assert len(comp.scenarios) == 2
        assert comp.worst_scenario_name == "Global Financial Crisis 2008"
        assert comp.max_loss_pnl == Decimal("-1800000.00")
        # Worst loss ranked #1
        assert comp.scenarios[0].loss_rank == 1
        assert comp.scenarios[0].stressed_pnl == Decimal("-1800000.00")

        # 6. Stress Loss Attribution
        attr_res = await svc.get_loss_attribution(hist_run_id)
        assert attr_res.is_reconciled is True
        assert attr_res.total_stressed_pnl == Decimal("-1800000.00")
        assert len(attr_res.position_contributors) == 2
        assert attr_res.position_contributors[0].dimension_name == "ST_A"
        assert attr_res.position_contributors[0].contribution_percentage == Decimal("66.67")
        assert len(attr_res.sector_contributors) == 1
        assert len(attr_res.factor_contributors) == 1


@pytest.mark.asyncio
async def test_stress_dashboard_persistence_and_api():
    """Verifies preferences, saved views, annotations, and FastAPI endpoints."""
    user_id = f"analyst_{uuid.uuid4().hex[:6]}"
    scen_id = f"SCEN_API_{uuid.uuid4().hex[:6]}"
    calc_id = f"CALC_API_{uuid.uuid4().hex[:6]}"
    port_id = f"PORT_API_{uuid.uuid4().hex[:6]}"

    async with AsyncSessionLocal() as session:
        svc = StressDashboardService(session)

        # 1. Preferences persistence
        pref_req = StressPreferenceCreateRequest(
            dashboard_name="Macro Stress Desk",
            default_scenario_category="HISTORICAL",
            preferred_currency_display="USD",
            default_comparison_limit=8,
            default_quantile_selection=["p01", "p05", "p95"],
        )
        pref = await svc.update_user_preferences(user_id=user_id, req=pref_req)
        assert pref.dashboard_name == "Macro Stress Desk"
        assert pref.default_comparison_limit == 8

        # 2. Saved View persistence
        view_req = StressSavedViewCreateRequest(
            view_name="Credit Crisis Comparison Set",
            description="2008 GFC vs COVID vs Dotcom",
            portfolio_id=port_id,
            selected_scenario_ids=[scen_id],
            selected_calculation_ids=[calc_id],
            is_public=True,
        )
        view = await svc.create_saved_view(user_id=user_id, req=view_req)
        assert view.id.startswith("sview_")
        assert view.view_name == "Credit Crisis Comparison Set"

        views = await svc.list_saved_views(user_id=user_id)
        assert len(views) >= 1

        # 3. Annotation note persistence
        anno_req = StressAnnotationCreateRequest(
            portfolio_id=port_id,
            scenario_id=scen_id,
            calculation_id=calc_id,
            annotation_type="INVESTIGATION",
            severity="HIGH",
            title="Tail Risk Concentration in Financials",
            notes="Loss contribution exceeds 60% of total scenario loss due to leveraged banking sleeve.",
            metrics_snapshot={"financials_loss_pct": 66.67},
        )
        anno = await svc.create_annotation(user_id=user_id, req=anno_req)
        assert anno.id.startswith("sanno_")
        assert anno.severity == "HIGH"
        assert anno.status == "OPEN"

        annos = await svc.list_annotations(scenario_id=scen_id)
        assert len(annos) == 1

    # 4. HTTP API Endpoints via AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Scenarios endpoint
        resp = await ac.get("/api/v1/dashboard/stress/scenarios")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

        # Scenario definition
        resp = await ac.get(f"/api/v1/dashboard/stress/scenarios/{scen_id}")
        assert resp.status_code == 200
        assert resp.json()["scenario_id"] == scen_id

        # Scenario result
        resp = await ac.get(f"/api/v1/dashboard/stress/results/{calc_id}")
        assert resp.status_code == 200
        res_data = resp.json()
        assert "summary" in res_data
        assert "positions" in res_data

        # Scenario positions
        resp = await ac.get(f"/api/v1/dashboard/stress/results/{calc_id}/positions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

        # Monte Carlo distribution
        resp = await ac.get(f"/api/v1/dashboard/stress/results/{calc_id}/distribution")
        assert resp.status_code == 200
        dist_data = resp.json()
        assert "quantiles" in dist_data
        assert "histogram_bins" in dist_data

        # Compare endpoint
        resp = await ac.post(
            f"/api/v1/dashboard/stress/compare?portfolio_id={port_id}",
            json={"calculation_ids": [calc_id]},
        )
        assert resp.status_code == 200
        comp_data = resp.json()
        assert "scenarios" in comp_data

        # Attribution endpoint
        resp = await ac.get(f"/api/v1/dashboard/stress/attribution/{calc_id}")
        assert resp.status_code == 200
        attr_data = resp.json()
        assert "position_contributors" in attr_data

        # Preferences API
        resp = await ac.get(
            f"/api/v1/dashboard/stress/preferences?user_id={user_id}&dashboard_name=Macro Stress Desk"
        )
        assert resp.status_code == 200
        assert resp.json()["default_comparison_limit"] == 8

        # Saved Views API
        resp = await ac.get(f"/api/v1/dashboard/stress/saved-views?user_id={user_id}")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

        # Annotations API
        resp = await ac.get(f"/api/v1/dashboard/stress/annotations?scenario_id={scen_id}")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
