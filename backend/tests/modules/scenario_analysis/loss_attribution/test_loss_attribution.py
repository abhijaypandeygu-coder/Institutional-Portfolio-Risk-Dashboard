"""
Unit and integration tests for M10.09 Stress Loss Attribution.
Tests:
1. Position-level price & FX exact decomposition and signed long/short handling.
2. Sector and industry aggregation including UNCLASSIFIED handling.
3. Economic factor shock attribution (View B).
4. Controlled combined-shock interaction effect estimation.
5. Loss concentration metrics (HHI, effective contributor count).
6. Financial reconciliation residual verification.
7. Service and repository end-to-end execution.
8. FastAPI REST API endpoints.
"""

from decimal import Decimal
import pytest
import numpy as np
from httpx import AsyncClient, ASGITransport

from backend.app.core.database import init_db, AsyncSessionLocal
from backend.app.main import app
from backend.app.modules.scenario_analysis.loss_attribution.calculations.attribution_math import (
    compute_position_pnl_and_decomposition,
    aggregate_by_dimension,
    compute_factor_shock_attribution,
    compute_interaction_effect,
    compute_loss_concentration_metrics,
    compute_reconciliation_residual,
)
from backend.app.modules.scenario_analysis.loss_attribution.schemas.attribution_schemas import (
    AttributionCreate,
    AttributionExecutionRequest,
)
from backend.app.modules.scenario_analysis.loss_attribution.services.attribution_service import (
    StressLossAttributionService,
)


def test_position_pnl_and_exact_decomposition():
    # Long position with price drop and FX change
    # q = 100, P0 = 100, Ps = 90, FX0 = 1.0, FXs = 1.05, liq_cost = 50
    # MV0 = 100 * 100 * 1.0 = 10,000
    # MVs = 100 * 90 * 1.05 = 9,450
    # Price effect = 100 * (90 - 100) * 1.0 = -1,000
    # FX effect = 100 * 90 * (1.05 - 1.0) = 450
    # Delta MV = -1000 + 450 = -550
    # Total PnL = -550 - 50 = -600
    # Loss contribution = -(-600) = +600
    decomp = compute_position_pnl_and_decomposition(
        signed_quantity=Decimal("100"),
        baseline_price=Decimal("100.0"),
        stressed_price=Decimal("90.0"),
        baseline_fx=Decimal("1.0"),
        stressed_fx=Decimal("1.05"),
        liquidity_cost=Decimal("50.0")
    )
    assert decomp["baseline_market_value"] == Decimal("10000.0000")
    assert decomp["stressed_market_value"] == Decimal("9450.0000")
    assert decomp["price_pnl"] == Decimal("-1000.0000")
    assert decomp["fx_pnl"] == Decimal("450.0000")
    assert decomp["total_pnl"] == Decimal("-600.0000")
    assert decomp["loss_contribution"] == Decimal("600.0000")

    # Short position test: q = -50, price drop from 100 to 80 => Gain of 1000
    short_decomp = compute_position_pnl_and_decomposition(
        signed_quantity=Decimal("-50"),
        baseline_price=Decimal("100.0"),
        stressed_price=Decimal("80.0")
    )
    assert short_decomp["total_pnl"] == Decimal("1000.0000")
    assert short_decomp["loss_contribution"] == Decimal("-1000.0000") # Negative loss indicates gain


def test_sector_and_industry_aggregation():
    positions = [
        {"sector": "Tech", "industry": "Software", "baseline_market_value": Decimal("1000"), "stressed_market_value": Decimal("900"), "total_pnl": Decimal("-100"), "loss_contribution": Decimal("100")},
        {"sector": "Tech", "industry": "Hardware", "baseline_market_value": Decimal("2000"), "stressed_market_value": Decimal("1800"), "total_pnl": Decimal("-200"), "loss_contribution": Decimal("200")},
        {"sector": None, "industry": None, "baseline_market_value": Decimal("500"), "stressed_market_value": Decimal("450"), "total_pnl": Decimal("-50"), "loss_contribution": Decimal("50")},
    ]

    sectors = aggregate_by_dimension(positions, "sector", total_portfolio_pnl=Decimal("-350"))
    sec_map = {s["dimension_name"]: s for s in sectors}

    assert sec_map["Tech"]["holding_count"] == 2
    assert sec_map["Tech"]["total_pnl"] == Decimal("-300.0000")
    assert sec_map["Tech"]["loss_contribution"] == Decimal("300.0000")
    assert sec_map["UNCLASSIFIED"]["holding_count"] == 1
    assert sec_map["UNCLASSIFIED"]["total_pnl"] == Decimal("-50.0000")


def test_factor_shock_and_interaction_effects():
    # Economic Factor Attribution (View B)
    exposures = {"MARKET": 1.0, "VALUE": -0.2}
    shocks = {"MARKET": -0.10, "VALUE": 0.05}
    base_nav = Decimal("1000000.0")

    # Market pnl = 1000000 * (1.0 * -0.10) = -100,000
    # Value pnl = 1000000 * (-0.2 * 0.05) = -10,000
    # Total explained = -110,000
    factor_res, tot_explained = compute_factor_shock_attribution(exposures, shocks, base_nav)
    f_map = {f["factor_name"]: f for f in factor_res}
    assert f_map["MARKET"]["contribution_value"] == Decimal("-100000.0000")
    assert f_map["VALUE"]["contribution_value"] == Decimal("-1000000.0000") * Decimal("0.01")
    assert tot_explained == Decimal("-110000.0000")

    # Interaction Effect: I_AB = Y(A,B) - Y(A,0) - Y(0,B) + Y(0,0)
    # y_both = -15000, y_a = -10000, y_b = -3000, y_0 = 0
    # I_AB = -15000 - (-10000) - (-3000) + 0 = -2000
    interaction = compute_interaction_effect(
        y_both=Decimal("-15000"),
        y_only_a=Decimal("-10000"),
        y_only_b=Decimal("-3000"),
        y_baseline=Decimal("0")
    )
    assert interaction == Decimal("-2000")


def test_loss_concentration_and_reconciliation():
    losses = [Decimal("50000"), Decimal("30000"), Decimal("20000"), Decimal("-10000")] # One gain
    conc = compute_loss_concentration_metrics(losses)

    # Positive loss sum = 100,000. weights = [0.5, 0.3, 0.2]
    # HHI = 0.5^2 + 0.3^2 + 0.2^2 = 0.25 + 0.09 + 0.04 = 0.38
    # N_eff = 1 / 0.38 ~ 2.63
    assert np.isclose(conc["hhi"], 0.38, atol=1e-3)
    assert np.isclose(conc["effective_contributor_count"], 2.63, atol=0.05)
    assert conc["positive_contributor_count"] == 3

    # Reconciliation
    recon = compute_reconciliation_residual(
        authoritative_pnl=Decimal("-100000.0"),
        sum_explained_pnl=Decimal("-100000.0")
    )
    assert recon["is_reconciled"] is True
    assert recon["residual_amount"] == Decimal("0.0000")


@pytest.mark.asyncio
async def test_loss_attribution_service_lifecycle():
    await init_db()

    async with AsyncSessionLocal() as session:
        service = StressLossAttributionService(session)

        # 1. Create Attribution Configuration
        import uuid
        code = f"ATTR_{uuid.uuid4().hex[:8].upper()}"
        create_payload = AttributionCreate(
            attribution_code=code,
            name="Institutional Crash Loss Decomposition",
            description="Decomposing portfolio loss under tech crash",
            portfolio_id="PORT_ATTRIB_ALPHA",
            scenario_id="SCEN_CRASH_2026",
            scenario_run_id="RUN_CRASH_01",
            scenario_type="MARKET_CRASH",
            attribution_method="ARITHMETIC_EXACT"
        )
        attr = await service.create_attribution(create_payload)
        await session.commit()
        assert attr.attribution_code == code

        # 2. Execute Attribution
        req = AttributionExecutionRequest(
            baseline_nav_override=Decimal("1000000.0000"),
            authoritative_pnl_override=Decimal("-80000.0000")
        )
        run = await service.execute_attribution(code, req)
        await session.commit()

        assert run.execution_status == "COMPLETED"
        assert len(run.position_contributions) == 4
        assert len(run.sector_contributions) > 0
        assert len(run.industry_contributions) > 0
        assert len(run.factor_contributions) > 0
        assert len(run.interaction_effects) > 0
        assert run.loss_hhi > 0


@pytest.mark.asyncio
async def test_fastapi_loss_attribution_endpoints():
    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check health
        health = await client.get("/health")
        assert health.status_code == 200
        assert "M10.09 - Stress Loss Attribution Engine" in health.json()["modules"]

        # 1. Create Attribution via API
        import uuid
        code = f"API_ATTR_{uuid.uuid4().hex[:8].upper()}"
        attr_payload = {
            "attribution_code": code,
            "name": "API Automated Attribution",
            "portfolio_id": "PORT_API_TEST",
            "scenario_id": "SCEN_CRASH_TEST",
            "scenario_run_id": "RUN_CRASH_TEST",
            "scenario_type": "MARKET_CRASH",
            "attribution_method": "ARITHMETIC_EXACT"
        }
        res_create = await client.post("/api/v1/stress-loss-attributions/", json=attr_payload)
        assert res_create.status_code == 201
        assert res_create.json()["attribution_code"] == code

        # 2. Execute Attribution via API
        exec_payload = {
            "baseline_nav_override": "1000000.0000",
            "authoritative_pnl_override": "-80000.0000"
        }
        res_exec = await client.post(f"/api/v1/stress-loss-attributions/{code}/execute", json=exec_payload)
        assert res_exec.status_code == 200, f"Exec error: {res_exec.text}"
        run_data = res_exec.json()
        assert run_data["execution_status"] == "COMPLETED"
        assert len(run_data["position_contributions"]) == 4

        # 3. Query results by run_code
        run_code = run_data["run_code"]
        res_get_run = await client.get(f"/api/v1/stress-loss-attributions/runs/{run_code}")
        assert res_get_run.status_code == 200
        assert res_get_run.json()["run_code"] == run_code

        # 4. Query positions & sectors
        res_pos = await client.get(f"/api/v1/stress-loss-attributions/runs/{run_code}/positions")
        assert res_pos.status_code == 200
        assert len(res_pos.json()) == 4

        res_sec = await client.get(f"/api/v1/stress-loss-attributions/runs/{run_code}/sectors")
        assert res_sec.status_code == 200
        assert len(res_sec.json()) > 0

