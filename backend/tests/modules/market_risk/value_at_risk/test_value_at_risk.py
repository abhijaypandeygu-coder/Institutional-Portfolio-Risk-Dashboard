"""
Module M07.02: Value at Risk (VaR) End-to-End Test Suite.
Verifies Historical VaR, Parametric VaR with Euler Component attribution,
Monte Carlo Cholesky simulation, multi-method comparison, and historical trend reporting.
"""
import pytest
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db, AsyncSessionLocal
from backend.app.modules.instrument_reference_data.instrument_master.services.service import (
    InstrumentMasterService,
)
from backend.app.modules.instrument_reference_data.instrument_master.schemas import InstrumentCreateRequest
from backend.app.modules.portfolio_management.portfolio_history.models import PortfolioBookSnapshot
from backend.app.modules.portfolio_management.position_valuation.models import (
    PositionValuation,
    PositionSide,
    ValuationStatus,
    MarkPriceType,
)
from backend.app.modules.market_risk.value_at_risk.calculations.var_math import (
    calculate_loss_quantile_from_returns,
    calculate_parametric_portfolio_var,
    simulate_monte_carlo_portfolio_var,
)
from backend.app.modules.market_risk.value_at_risk.models import (
    VaRDistributionAssumption,
    VaRQuantileMethod,
)


def test_var_mathematical_units():
    """
    Test core statistical loss quantiles, parametric matrix variance, and Monte Carlo reproducibility.
    """
    # 1. Historical empirical loss quantile:
    # Returns R = [0.05, 0.02, 0.01, -0.01, -0.02, -0.03, -0.04, -0.05, -0.06, -0.10]
    # Losses L = -R = [-0.05, -0.02, -0.01, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.10]
    # Sorted losses: 10 items.
    # At 90% confidence, 90th percentile of loss ~ 0.064
    rets = [
        Decimal("0.05"), Decimal("0.02"), Decimal("0.01"), Decimal("-0.01"), Decimal("-0.02"),
        Decimal("-0.03"), Decimal("-0.04"), Decimal("-0.05"), Decimal("-0.06"), Decimal("-0.10")
    ]
    signed_loss, non_neg, tail_cnt = calculate_loss_quantile_from_returns(
        returns=rets,
        confidence_level=Decimal("0.9000"),
        quantile_method=VaRQuantileMethod.LINEAR_INTERPOLATION,
    )
    assert non_neg > Decimal("0.05000000")
    assert tail_cnt >= 1

    # 2. Parametric VaR with Euler Component attribution
    # Portfolio of 2 assets: weight = [0.6, 0.4]
    # Covariance matrix: [[0.0004, 0.0001], [0.0001, 0.0009]]
    # port_var = 0.36*0.0004 + 2*0.6*0.4*0.0001 + 0.16*0.0009 = 0.000144 + 0.000048 + 0.000144 = 0.000336
    # port_vol = sqrt(0.000336) ~ 0.0183303
    # At 99% confidence (norm.ppf(0.99) ~ 2.3263479)
    # VaR ~ 2.3263479 * 0.0183303 ~ 0.0426436
    weights = [Decimal("0.6"), Decimal("0.4")]
    cov_matrix = [
        [Decimal("0.00040000"), Decimal("0.00010000")],
        [Decimal("0.00010000"), Decimal("0.00090000")],
    ]
    p_vol, s_loss, non_neg_p, marginals, components = calculate_parametric_portfolio_var(
        weights=weights,
        covariance_matrix=cov_matrix,
        confidence_level=Decimal("0.9900"),
        holding_horizon_days=1,
    )
    assert abs(p_vol - Decimal("0.01833030")) < Decimal("0.0001")
    assert abs(non_neg_p - Decimal("0.04264363")) < Decimal("0.0002")
    # Euler Additivity: sum(components) == non_neg_p
    sum_components = sum(components)
    assert abs(sum_components - non_neg_p) < Decimal("0.000001")

    # 3. Monte Carlo Simulation Reproducibility with seed
    s_loss_mc1, non_neg_mc1, cnt1, _ = simulate_monte_carlo_portfolio_var(
        weights=weights,
        covariance_matrix=cov_matrix,
        confidence_level=Decimal("0.9900"),
        simulation_count=5000,
        random_seed=12345,
    )
    s_loss_mc2, non_neg_mc2, cnt2, _ = simulate_monte_carlo_portfolio_var(
        weights=weights,
        covariance_matrix=cov_matrix,
        confidence_level=Decimal("0.9900"),
        simulation_count=5000,
        random_seed=12345,
    )
    assert non_neg_mc1 == non_neg_mc2
    # Monte Carlo estimate should be close to analytical parametric normal
    assert abs(non_neg_mc1 - non_neg_p) < Decimal("0.005")


@pytest.mark.asyncio
async def test_portfolio_var_three_methodologies_and_comparison():
    """
    Integration test:
    1. Create 2 canonical instruments (AAPL and MSFT)
    2. Seed PositionValuation records for portfolio ($60k AAPL, $40k MSFT = $100k NAV)
    3. Seed PortfolioBookSnapshot records with historical NAVs
    4. Execute Historical VaR, Parametric VaR, and Monte Carlo VaR
    5. Call /model-comparison and verify side-by-side output and risk attribution
    """
    await init_db()
    ts = datetime.utcnow().timestamp()
    port_id = f"port-var-test-{ts}"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create canonical instruments
        async with AsyncSessionLocal() as session:
            i1 = await InstrumentMasterService.create_instrument(
                session,
                InstrumentCreateRequest(
                    canonical_name=f"Apple Inc VaR {ts}",
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
                    canonical_name=f"Microsoft Corp VaR {ts}",
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

            # 2. Seed Position Valuations: $60,000 in AAPL, $40,000 in MSFT
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

            # 3. Seed 25 PortfolioBookSnapshots with realistic NAV fluctuation (~ $100,000 baseline)
            base_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
            navs = [
                100000, 101000, 99500, 100500, 102000, 98500, 99000, 101500, 103000, 101200,
                102500, 104000, 102800, 103500, 105000, 103800, 102000, 101000, 99800, 100500,
                102000, 103200, 101500, 102800, 104500
            ]
            for idx, nav_val in enumerate(navs):
                snap = PortfolioBookSnapshot(
                    snapshot_id=f"SNAP_VAR_{ts}_{idx}",
                    portfolio_id=port_id,
                    effective_as_of=base_date + timedelta(days=idx),
                    knowledge_as_of=base_date + timedelta(days=idx),
                    base_currency="USD",
                    total_positions_count=2,
                    total_market_value_base=Decimal(str(nav_val)),
                    total_cash_value_base=Decimal("0.0"),
                    total_nav_base=Decimal(str(nav_val)),
                    snapshot_hash=f"hash_{idx}",
                )
                session.add(snap)
            await session.commit()

        # 4. POST /portfolios/{portfolio_id}/risk/var/historical (99% 1-day)
        hist_resp = await client.post(
            f"/api/v1/portfolios/{port_id}/risk/var/historical?confidence_level=0.99&holding_horizon_days=1"
        )
        assert hist_resp.status_code == 200, hist_resp.text
        hist_data = hist_resp.json()
        assert hist_data["methodology"] == "HISTORICAL"
        assert Decimal(hist_data["valuation_base_amount"]) > Decimal("0.0")
        assert Decimal(hist_data["var_monetary_amount"]) > Decimal("0.0")
        assert Decimal(hist_data["var_return_percentage"]) > Decimal("0.0")
        assert hist_data["calculation_status"] == "CALCULATED"

        # 5. POST /portfolios/{portfolio_id}/risk/var/parametric (99% 1-day)
        param_resp = await client.post(
            f"/api/v1/portfolios/{port_id}/risk/var/parametric?confidence_level=0.99&holding_horizon_days=1"
        )
        assert param_resp.status_code == 200, param_resp.text
        param_data = param_resp.json()
        assert param_data["methodology"] == "PARAMETRIC"
        assert Decimal(param_data["var_monetary_amount"]) > Decimal("0.0")
        assert param_data["contributions"] is not None
        assert len(param_data["contributions"]) == 2
        # Verify Euler sum matches total VaR amount
        sum_c = sum(Decimal(c["component_var_amount"]) for c in param_data["contributions"])
        assert abs(sum_c - Decimal(param_data["var_monetary_amount"])) < Decimal("1.0")

        # 6. POST /portfolios/{portfolio_id}/risk/var/monte-carlo (99% 1-day)
        mc_resp = await client.post(
            f"/api/v1/portfolios/{port_id}/risk/var/monte-carlo?confidence_level=0.99&holding_horizon_days=1&simulation_count=5000&random_seed=42"
        )
        assert mc_resp.status_code == 200, mc_resp.text
        mc_data = mc_resp.json()
        assert mc_data["methodology"] == "MONTE_CARLO"
        assert mc_data["simulation_count"] == 5000
        assert Decimal(mc_data["var_monetary_amount"]) > Decimal("0.0")

        # 7. GET /portfolios/{portfolio_id}/risk/var/model-comparison
        comp_resp = await client.get(
            f"/api/v1/portfolios/{port_id}/risk/var/model-comparison?confidence_level=0.99&holding_horizon_days=1"
        )
        assert comp_resp.status_code == 200, comp_resp.text
        comp_data = comp_resp.json()
        assert comp_data["historical_var"] is not None
        assert comp_data["parametric_var"] is not None
        assert comp_data["monte_carlo_var"] is not None
        assert comp_data["diff_historical_minus_parametric"] is not None

        # 8. GET /portfolios/{portfolio_id}/risk/var/history
        trend_resp = await client.get(
            f"/api/v1/portfolios/{port_id}/risk/var/history?methodology=HISTORICAL"
        )
        assert trend_resp.status_code == 200, trend_resp.text
        trend_data = trend_resp.json()
        assert trend_data["total_points"] >= 1
        assert Decimal(trend_data["current_var_amount"]) > Decimal("0.0")
