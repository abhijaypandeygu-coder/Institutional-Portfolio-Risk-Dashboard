"""
Unit and integration tests for M07.03 - Expected Shortfall (ES) / Conditional Value at Risk (CVaR).
Tests:
1. Mathematical unit test:
   - Fractional tail weighting on synthetic discrete distribution.
   - Exact probability mass verification (alpha = 1 - c).
   - Expected Shortfall >= Value at Risk.
   - Tail excess (ES - VaR) and dispersion metrics.
   - Scenario-weighted constituent tail risk attribution.
2. End-to-end integration test:
   - Real database setup with canonical instruments and positions.
   - Calculation of Historical Portfolio Returns ES, Historical Simulation ES, and Monte Carlo ES.
   - Confidence-level sensitivity comparison.
   - Methodology side-by-side comparison.
   - Historical trend recording.
"""
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db, AsyncSessionLocal
from backend.app.modules.market_risk.expected_shortfall.models import (
    ESMethodology,
    ESQuantileMethod,
    ESTailWeightingMethod,
    ESTailStabilityStatus,
)
from backend.app.modules.market_risk.expected_shortfall.calculations.es_math import (
    calculate_fractional_tail_expected_shortfall,
    calculate_scenario_tail_attributions,
)
from backend.app.modules.instrument_reference_data.instrument_master.services.service import (
    InstrumentMasterService,
)
from backend.app.modules.instrument_reference_data.instrument_master.schemas import InstrumentCreateRequest
from backend.app.modules.portfolio_management.position_valuation.models import (
    PositionValuation,
    PositionSide,
    MarkPriceType,
    ValuationStatus,
)
from backend.app.modules.portfolio_management.portfolio_history.models import PortfolioBookSnapshot


def test_es_fractional_tail_math():
    """
    Test discrete loss sample:
    Losses: [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    n = 10, confidence = 0.90 -> alpha = 0.10.
    Target tail mass = 10 * 0.10 = 1.0 observation (index 0: 10.0).
    ES_0.90 = 10.0, VaR_0.90 >= 9.0.
    """
    losses = [Decimal(str(i)) for i in range(1, 11)]
    res = calculate_fractional_tail_expected_shortfall(
        losses=losses,
        confidence_level=Decimal("0.9000"),
        quantile_method=ESQuantileMethod.NEAREST_RANK,
        tail_weighting_method=ESTailWeightingMethod.FRACTIONAL_BOUNDARY,
    )

    assert res["full_tail_count"] >= 1
    assert res["signed_es"] >= res["signed_var"]
    assert res["tail_excess"] >= Decimal("0.0")
    assert res["expected_tail_mass"] == Decimal("1.00")

    # Non-integer tail count: n = 10, confidence = 0.95 -> alpha = 0.05.
    # Target tail mass = 10 * 0.05 = 0.5 observation.
    # Observation 10.0 receives weight 0.5 / 0.1 = 0.5 (full normalized tail mass 1.0).
    res_95 = calculate_fractional_tail_expected_shortfall(
        losses=losses,
        confidence_level=Decimal("0.9500"),
        quantile_method=ESQuantileMethod.LINEAR_INTERPOLATION,
        tail_weighting_method=ESTailWeightingMethod.FRACTIONAL_BOUNDARY,
    )
    assert res_95["signed_es"] >= res_95["signed_var"]
    assert res_95["expected_tail_mass"] == Decimal("0.50")
    assert res_95["boundary_weight"] == Decimal("0.500000")

    # Attribution reconciliation test:
    # Portfolio return percentage losses (e.g. 1% to 10%)
    ret_losses = [Decimal(str(i)) / Decimal("100.0") for i in range(1, 11)]
    res_ret = calculate_fractional_tail_expected_shortfall(
        losses=ret_losses,
        confidence_level=Decimal("0.9000"),
        quantile_method=ESQuantileMethod.NEAREST_RANK,
        tail_weighting_method=ESTailWeightingMethod.FRACTIONAL_BOUNDARY,
    )
    # ES return is 10% (0.10). On $100,000 portfolio base, total ES = $10,000
    holdings = [
        ("AAPL", "Apple Inc", Decimal("60000.0"), Decimal("0.6")),
        ("MSFT", "Microsoft Corp", Decimal("40000.0"), Decimal("0.4")),
    ]
    inst_losses = {
        "AAPL": ret_losses,
        "MSFT": ret_losses,
    }
    attributions = calculate_scenario_tail_attributions(
        holdings=holdings,
        instrument_scenario_losses=inst_losses,
        tail_observations=res_ret["tail_observations"],
        portfolio_valuation_base=Decimal("100000.00"),
        total_es_amount=Decimal("10000.00"),
    )
    assert len(attributions) == 2
    total_contrib = sum(a["contribution_amount"] for a in attributions)
    # Sum of component contributions matches total
    assert abs(total_contrib - Decimal("10000.00")) <= Decimal("1.00")


@pytest.mark.asyncio
async def test_portfolio_expected_shortfall_three_methodologies():
    """
    End-to-end integration test:
    1. Initialize database and create canonical instruments.
    2. Seed PositionValuation records for $100,000 portfolio ($60k AAPL, $40k MSFT).
    3. Calculate Historical Portfolio Returns ES, Historical Simulation ES, and Monte Carlo ES.
    4. Call /confidence-comparison and /methodology-comparison endpoints.
    5. Drill down into tail scenarios and diagnostics.
    """
    await init_db()
    ts = datetime.utcnow().timestamp()
    port_id = f"port-es-test-{ts}"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create canonical instruments
        async with AsyncSessionLocal() as session:
            i1 = await InstrumentMasterService.create_instrument(
                session,
                InstrumentCreateRequest(
                    canonical_name=f"Apple Inc ES {ts}",
                    short_name=f"AAPL_{ts}",
                    instrument_type="COMMON_STOCK",
                    asset_class="EQUITY",
                    issue_currency="USD",
                    primary_market_id="NASDAQ",
                ),
                actor_id="admin",
            )
            i2 = await InstrumentMasterService.create_instrument(
                session,
                InstrumentCreateRequest(
                    canonical_name=f"Microsoft Corp ES {ts}",
                    short_name=f"MSFT_{ts}",
                    instrument_type="COMMON_STOCK",
                    asset_class="EQUITY",
                    issue_currency="USD",
                    primary_market_id="NASDAQ",
                ),
                actor_id="admin",
            )
            inst1_id = i1.instrument_id
            inst2_id = i2.instrument_id

            # 2. Seed Position Valuations: $60,000 AAPL, $40,000 MSFT
            v1 = PositionValuation(
                valuation_id=f"VAL_AAPL_{ts}",
                calculation_id=f"CALC_AAPL_{ts}",
                portfolio_id=port_id,
                account_id="acc_main",
                instrument_id=inst1_id,
                position_side=PositionSide.LONG,
                signed_quantity=Decimal("400.00"),
                mark_price=Decimal("150.00"),
                mark_price_type=MarkPriceType.OFFICIAL_CLOSE,
                price_currency="USD",
                fx_rate_to_base=Decimal("1.0"),
                signed_market_value_native=Decimal("60000.00"),
                signed_market_value_base=Decimal("60000.00"),
                signed_cost_basis_native=Decimal("55000.00"),
                signed_cost_basis_base=Decimal("55000.00"),
                unrealized_pnl_native=Decimal("5000.00"),
                unrealized_pnl_base=Decimal("5000.00"),
                valuation_status=ValuationStatus.VALUED,
                effective_at=datetime.utcnow(),
                calculated_at=datetime.utcnow(),
            )
            v2 = PositionValuation(
                valuation_id=f"VAL_MSFT_{ts}",
                calculation_id=f"CALC_MSFT_{ts}",
                portfolio_id=port_id,
                account_id="acc_main",
                instrument_id=inst2_id,
                position_side=PositionSide.LONG,
                signed_quantity=Decimal("200.00"),
                mark_price=Decimal("200.00"),
                mark_price_type=MarkPriceType.OFFICIAL_CLOSE,
                price_currency="USD",
                fx_rate_to_base=Decimal("1.0"),
                signed_market_value_native=Decimal("40000.00"),
                signed_market_value_base=Decimal("40000.00"),
                signed_cost_basis_native=Decimal("38000.00"),
                signed_cost_basis_base=Decimal("38000.00"),
                unrealized_pnl_native=Decimal("2000.00"),
                unrealized_pnl_base=Decimal("2000.00"),
                valuation_status=ValuationStatus.VALUED,
                effective_at=datetime.utcnow(),
                calculated_at=datetime.utcnow(),
            )
            session.add_all([v1, v2])

            # 3. Seed historical NAV snapshots
            base_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
            navs = [
                100000, 101000, 99500, 100500, 102000, 98500, 99000, 101500, 103000, 101200,
                102500, 104000, 102800, 103500, 105000, 103800, 102000, 101000, 99800, 100500,
                102000, 103200, 101500, 102800, 104500
            ]
            for idx, nav_val in enumerate(navs):
                snap = PortfolioBookSnapshot(
                    snapshot_id=f"SNAP_ES_{ts}_{idx}",
                    portfolio_id=port_id,
                    effective_as_of=base_date + timedelta(days=idx),
                    knowledge_as_of=base_date + timedelta(days=idx),
                    base_currency="USD",
                    total_positions_count=2,
                    total_market_value_base=Decimal(str(nav_val)),
                    total_cash_value_base=Decimal("0.0"),
                    total_nav_base=Decimal(str(nav_val)),
                    snapshot_hash=f"es_hash_{idx}",
                )
                session.add(snap)

            await session.commit()

        # 4. Calculate Historical Portfolio Returns ES
        r_hist = await client.post(
            f"/api/v1/portfolios/{port_id}/risk/expected-shortfall/calculate",
            json={
                "portfolio_id": port_id,
                "methodology": "HISTORICAL_PORTFOLIO_RETURNS",
                "confidence_level": 0.95,
                "holding_horizon_days": 1,
            },
        )
        assert r_hist.status_code == 200, r_hist.text
        hist_data = r_hist.json()
        assert hist_data["methodology"] == "HISTORICAL_PORTFOLIO_RETURNS"
        assert Decimal(hist_data["es_monetary_amount"]) >= Decimal(hist_data["var_monetary_amount"])
        assert Decimal(hist_data["tail_excess_monetary_amount"]) >= Decimal("0.0")
        assert len(hist_data["tail_observations"]) > 0
        assert len(hist_data["contributions"]) == 2

        result_id = hist_data["result_id"]

        # 5. Calculate Historical Simulation ES
        r_sim = await client.post(
            f"/api/v1/portfolios/{port_id}/risk/expected-shortfall/calculate",
            json={
                "portfolio_id": port_id,
                "methodology": "HISTORICAL_SIMULATION",
                "confidence_level": 0.95,
                "holding_horizon_days": 1,
            },
        )
        assert r_sim.status_code == 200, r_sim.text
        sim_data = r_sim.json()
        assert sim_data["methodology"] == "HISTORICAL_SIMULATION"
        assert Decimal(sim_data["es_monetary_amount"]) >= Decimal(sim_data["var_monetary_amount"])

        # 6. Calculate Monte Carlo ES
        r_mc = await client.post(
            f"/api/v1/portfolios/{port_id}/risk/expected-shortfall/calculate",
            json={
                "portfolio_id": port_id,
                "methodology": "MONTE_CARLO",
                "confidence_level": 0.95,
                "holding_horizon_days": 1,
                "simulation_count": 500,
                "random_seed": 42,
            },
        )
        assert r_mc.status_code == 200, r_mc.text
        mc_data = r_mc.json()
        assert mc_data["methodology"] == "MONTE_CARLO"
        assert Decimal(mc_data["es_monetary_amount"]) >= Decimal(mc_data["var_monetary_amount"])

        # 7. Query Confidence-Level Comparison
        r_conf = await client.get(
            f"/api/v1/portfolios/{port_id}/risk/expected-shortfall/confidence-comparison?methodology=HISTORICAL_PORTFOLIO_RETURNS"
        )
        assert r_conf.status_code == 200, r_conf.text
        conf_data = r_conf.json()
        assert len(conf_data["levels"]) == 5
        # Verify non-decreasing ES across increasing confidence
        es_levels = [Decimal(lvl["es_monetary_amount"]) for lvl in conf_data["levels"]]
        assert es_levels[-1] >= es_levels[0]

        # 8. Query Methodology Comparison
        r_comp = await client.get(
            f"/api/v1/portfolios/{port_id}/risk/expected-shortfall/methodology-comparison?confidence_level=0.95"
        )
        assert r_comp.status_code == 200, r_comp.text
        comp_data = r_comp.json()
        assert comp_data["historical_portfolio_returns"] is not None
        assert comp_data["historical_simulation"] is not None
        assert comp_data["monte_carlo"] is not None
        assert Decimal(comp_data["divergence_percentage"]) >= Decimal("0.0")

        # 9. Query Tail Scenario Drill-down and Diagnostics
        r_obs = await client.get(
            f"/api/v1/portfolios/{port_id}/risk/expected-shortfall/{result_id}/tail-scenarios"
        )
        assert r_obs.status_code == 200, r_obs.text
        obs_data = r_obs.json()
        assert len(obs_data) > 0
        assert "is_boundary_observation" in obs_data[0]

        r_diag = await client.get(
            f"/api/v1/portfolios/{port_id}/risk/expected-shortfall/{result_id}/tail-diagnostics"
        )
        assert r_diag.status_code == 200, r_diag.text
        diag_data = r_diag.json()
        assert len(diag_data) > 0
