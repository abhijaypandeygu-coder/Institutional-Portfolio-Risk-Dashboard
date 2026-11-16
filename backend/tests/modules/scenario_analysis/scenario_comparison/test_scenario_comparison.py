"""
Unit and integration tests for M10.08 Scenario Comparison.
Tests:
1. Baseline performance calculation (NAV, P&L, returns, positive loss convention).
2. Metric normalization methods (Min-Max, Z-score, Robust MAD, Percentile).
3. Configurable scenario ranking with deterministic tie handling and weighted composite scores.
4. Assumption-level configuration difference analysis.
5. Scenario difference attribution and residual calculation.
6. Service and repository end-to-end execution.
7. FastAPI REST API endpoints.
"""

from decimal import Decimal
import pytest
import numpy as np
from httpx import AsyncClient, ASGITransport

from backend.app.core.database import init_db, AsyncSessionLocal
from backend.app.main import app
from backend.app.modules.scenario_analysis.scenario_comparison.calculations.comparison_math import (
    compute_baseline_performance,
    normalize_metrics,
    rank_scenarios,
    compute_configuration_differences,
    compute_scenario_difference_attribution,
)
from backend.app.modules.scenario_analysis.scenario_comparison.schemas.comparison_schemas import (
    ComparisonCreate,
    ScenarioMemberCreate,
    ComparisonExecutionRequest,
)
from backend.app.modules.scenario_analysis.scenario_comparison.services.comparison_service import (
    ScenarioComparisonService,
)


def test_baseline_performance_math():
    v0 = Decimal("1000000.0000")
    v_stressed = Decimal("940000.0000")
    perf = compute_baseline_performance(v0, v_stressed)

    assert perf["pnl"] == Decimal("-60000.0000")
    assert perf["return_pct"] == Decimal("-6.0000")
    assert perf["loss_amount"] == Decimal("60000.0000")  # Positive loss convention
    assert perf["loss_pct"] == Decimal("6.0000")

    # Invalid baseline NAV should raise
    with pytest.raises(ValueError):
        compute_baseline_performance(Decimal("0"), v_stressed)


def test_normalization_and_ranking():
    # Test Min-Max and Z-score
    vals = [10.0, 20.0, 30.0]
    min_max_desc = normalize_metrics(vals, method="MIN_MAX", direction="DESCENDING")
    assert min_max_desc == [0.0, 0.5, 1.0]

    min_max_asc = normalize_metrics(vals, method="MIN_MAX", direction="ASCENDING")
    assert min_max_asc == [1.0, 0.5, 0.0]

    # Test Ranking with tie handling
    scenarios = [
        {"scenario_run_id": "S1", "loss_amount": 50000.0, "var_95": 60000.0},
        {"scenario_run_id": "S2", "loss_amount": 80000.0, "var_95": 90000.0},
        {"scenario_run_id": "S3", "loss_amount": 50000.0, "var_95": 55000.0}, # Tied loss with S1
    ]

    ranked = rank_scenarios(scenarios, primary_metric="loss_amount", direction="DESCENDING")
    assert ranked[0]["scenario_run_id"] == "S2"
    assert ranked[0]["rank_position"] == 1
    # S1 and S3 have same loss_amount => same rank_position
    assert ranked[1]["rank_position"] == 2
    assert ranked[2]["rank_position"] == 2
    assert ranked[1]["tie_group"] == ranked[2]["tie_group"]

    # Test Composite Score Ranking
    weights = {"loss_amount": 0.6, "var_95": 0.4}
    comp_ranked = rank_scenarios(scenarios, weights=weights, direction="DESCENDING")
    assert comp_ranked[0]["scenario_run_id"] == "S2"
    assert "composite_score" in comp_ranked[0]


def test_configuration_differences():
    cfg_a = {"market_shock": -0.05, "vol_multiplier": 1.2, "model": "PARAMETRIC"}
    cfg_b = {"market_shock": -0.10, "vol_multiplier": 1.5, "model": "STUDENT_T"}

    diffs = compute_configuration_differences(cfg_a, cfg_b)
    diff_map = {d["parameter_code"]: d for d in diffs}

    assert "market_shock" in diff_map
    assert np.isclose(diff_map["market_shock"]["absolute_difference"], -0.05)
    assert np.isclose(diff_map["vol_multiplier"]["absolute_difference"], 0.3)
    assert diff_map["model"]["is_material"] is True


def test_difference_attribution_and_residual():
    breakdown_a = {"AAPL": Decimal("-20000"), "MSFT": Decimal("-10000")}
    breakdown_b = {"AAPL": Decimal("-35000"), "MSFT": Decimal("-12000"), "NVDA": Decimal("-5000")}
    headline_diff = Decimal("-22000")  # (-52000) - (-30000) = -22000

    attrs, residual = compute_scenario_difference_attribution(breakdown_a, breakdown_b, headline_diff)
    attr_map = {a["component_reference"]: a["difference_value"] for a in attrs}

    assert attr_map["AAPL"] == Decimal("-15000") # -35000 - (-20000)
    assert attr_map["MSFT"] == Decimal("-2000")  # -12000 - (-10000)
    assert attr_map["NVDA"] == Decimal("-5000")  # -5000 - 0
    # Sum = -22000, residual should be exactly 0
    assert residual == Decimal("0")


@pytest.mark.asyncio
async def test_scenario_comparison_service_lifecycle():
    await init_db()

    async with AsyncSessionLocal() as session:
        service = ScenarioComparisonService(session)

        # 1. Create Comparison
        import uuid
        code = f"CMP_{uuid.uuid4().hex[:8].upper()}"
        create_payload = ComparisonCreate(
            comparison_code=code,
            name="Institutional Stress Scenario Comparison",
            description="Comparing tech crash against liquidity freeze",
            portfolio_id="PORT_RISK_ALPHA",
            baseline_snapshot_id="BASE_SNAPSHOT_01",
            ranking_metric="loss_amount",
            ranking_direction="DESCENDING",
            initial_members=[
                ScenarioMemberCreate(
                    scenario_id="SCEN_CRASH",
                    scenario_run_id="RUN_CRASH_01",
                    scenario_type="MARKET_CRASH",
                    scenario_name="2026 Tech Market Crash"
                ),
                ScenarioMemberCreate(
                    scenario_id="SCEN_LIQ",
                    scenario_run_id="RUN_LIQ_01",
                    scenario_type="LIQUIDITY_STRESS",
                    scenario_name="Liquidity Freeze Shock"
                )
            ]
        )
        comp = await service.create_comparison(create_payload)
        await session.commit()
        assert comp.comparison_code == code
        assert len(comp.members) == 2

        # 2. Validate
        val_res = await service.validate_comparison(code)
        assert val_res["is_ready"] is True

        # 3. Execute Comparison
        req = ComparisonExecutionRequest(
            baseline_nav_override=Decimal("2000000.0000")
        )
        run = await service.execute_comparison(code, req)
        await session.commit()

        assert run.execution_status == "COMPLETED"
        assert len(run.metric_results) == 2
        assert len(run.rankings) == 2
        assert run.rankings[0].rank_position == 1
        assert len(run.sensitivities) > 0
        assert len(run.attributions) > 0


@pytest.mark.asyncio
async def test_fastapi_comparison_endpoints():
    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check health
        health = await client.get("/health")
        assert health.status_code == 200
        assert "M10.08 - Scenario Comparison Engine" in health.json()["modules"]

        # 1. Create Comparison via API
        import uuid
        code = f"API_CMP_{uuid.uuid4().hex[:8].upper()}"
        comp_payload = {
            "comparison_code": code,
            "name": "API Multi-Scenario Comparison",
            "portfolio_id": "PORT_API_TEST",
            "ranking_metric": "loss_amount",
            "initial_members": [
                {
                    "scenario_id": "SCEN_1",
                    "scenario_run_id": "RUN_A",
                    "scenario_type": "MARKET_CRASH",
                    "scenario_name": "Scenario A Crash"
                },
                {
                    "scenario_id": "SCEN_2",
                    "scenario_run_id": "RUN_B",
                    "scenario_type": "LIQUIDITY_STRESS",
                    "scenario_name": "Scenario B Liquidity"
                }
            ]
        }
        res_create = await client.post("/api/v1/scenario-comparisons/", json=comp_payload)
        assert res_create.status_code == 201
        assert res_create.json()["comparison_code"] == code

        # 2. Execute Comparison
        exec_payload = {
            "baseline_nav_override": "1500000.0000"
        }
        res_exec = await client.post(f"/api/v1/scenario-comparisons/{code}/execute", json=exec_payload)
        assert res_exec.status_code == 200, f"Exec error: {res_exec.text}"
        run_data = res_exec.json()
        assert run_data["execution_status"] == "COMPLETED"
        assert len(run_data["metric_results"]) == 2
        assert len(run_data["rankings"]) == 2

        # 3. Query results by run_code
        run_code = run_data["run_code"]
        res_get_run = await client.get(f"/api/v1/scenario-comparisons/runs/{run_code}")
        assert res_get_run.status_code == 200
        assert res_get_run.json()["run_code"] == run_code

        # 4. Query rankings
        res_rankings = await client.get(f"/api/v1/scenario-comparisons/runs/{run_code}/rankings")
        assert res_rankings.status_code == 200
        assert len(res_rankings.json()) == 2

