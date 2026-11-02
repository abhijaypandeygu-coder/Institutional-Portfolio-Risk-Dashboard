"""
Integration and mathematical tests for M07.07 Portfolio Beta Engine.
"""
from datetime import date, timedelta, datetime, timezone
from decimal import Decimal
import numpy as np
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.modules.market_risk.beta.calculations.beta_math import (
    calculate_ols_beta,
    calculate_portfolio_weighted_beta,
)
from backend.app.modules.market_risk.beta.models import (
    BetaModelType,
    BetaCalculationMethod,
    BetaRegressionStatus,
    BenchmarkReference,
)
from backend.app.modules.instrument_reference_data.instrument_master.models import Instrument
from backend.app.modules.instrument_reference_data.price_reference.models import (
    PriceReferenceObservation,
    PriceReferenceType,
)
from backend.app.modules.portfolio_management.portfolio_creation.models import (
    Portfolio,
    PortfolioTypeEnum,
    PortfolioLifecycleStatus,
)
from backend.app.modules.portfolio_management.position_management.models import (
    PositionBook,
    PositionStatus,
    PositionSide,
)
from backend.app.modules.portfolio_management.portfolio_history.models import PortfolioBookSnapshot


def test_ols_beta_math_known_linear_relationships():
    # 1. Benchmark returns
    rb = np.array([0.01, -0.02, 0.015, -0.005, 0.03, -0.01, 0.02, 0.005, -0.015, 0.025], dtype=np.float64)

    # Asset A: Perfect identical returns (beta=1.0, alpha=0.0, R2=1.0)
    ra = rb.copy()
    res_a = calculate_ols_beta(ra, rb, include_intercept=True)
    assert res_a["regression_status"] == BetaRegressionStatus.VALID
    assert pytest.approx(res_a["beta"], 1e-6) == 1.0
    assert pytest.approx(res_a["alpha"], 1e-6) == 0.0
    assert pytest.approx(res_a["r_squared"], 1e-6) == 1.0
    assert pytest.approx(res_a["residual_std_error"], 1e-6) == 0.0

    # Asset B: Scaled returns Y = 1.5 * X + 0.001
    rb_scaled = 1.5 * rb + 0.001
    res_b = calculate_ols_beta(rb_scaled, rb, include_intercept=True)
    assert res_b["regression_status"] == BetaRegressionStatus.VALID
    assert pytest.approx(res_b["beta"], 1e-6) == 1.5
    assert pytest.approx(res_b["alpha"], 1e-6) == 0.001
    assert pytest.approx(res_b["r_squared"], 1e-6) == 1.0

    # Asset C: Negative beta Y = -0.8 * X
    rc = -0.8 * rb
    res_c = calculate_ols_beta(rc, rb, include_intercept=True)
    assert res_c["regression_status"] == BetaRegressionStatus.VALID
    assert pytest.approx(res_c["beta"], 1e-6) == -0.8
    assert pytest.approx(res_c["r_squared"], 1e-6) == 1.0


def test_ols_beta_math_zero_variance_and_low_sample():
    # Flat benchmark returns (zero variance)
    rb_flat = np.array([0.01, 0.01, 0.01, 0.01, 0.01], dtype=np.float64)
    ry = np.array([0.02, -0.01, 0.03, 0.01, -0.02], dtype=np.float64)

    res_zero = calculate_ols_beta(ry, rb_flat)
    assert res_zero["regression_status"] == BetaRegressionStatus.ZERO_BENCHMARK_VARIANCE
    assert res_zero["beta"] is None

    # Insufficient sample
    res_small = calculate_ols_beta(np.array([0.01, 0.02]), np.array([0.01, 0.02]), min_observations=5)
    assert res_small["regression_status"] == BetaRegressionStatus.INSUFFICIENT_OBSERVATIONS
    assert res_small["beta"] is None


def test_portfolio_weighted_beta_math():
    weights = np.array([0.5, 0.3, 0.2], dtype=np.float64)
    betas = np.array([1.2, 0.8, 1.5], dtype=np.float64)

    res = calculate_portfolio_weighted_beta(weights, betas)
    expected_beta = 0.5 * 1.2 + 0.3 * 0.8 + 0.2 * 1.5  # 0.6 + 0.24 + 0.3 = 1.14
    assert pytest.approx(res["portfolio_beta"], 1e-6) == expected_beta
    assert pytest.approx(res["reconciliation_sum"], 1e-6) == expected_beta
    assert pytest.approx(res["discrepancy"], 1e-8) == 0.0
    assert len(res["contributions"]) == 3
    assert pytest.approx(res["contributions"][0]["weighted_beta"], 1e-6) == 0.6
    assert pytest.approx(res["contributions"][1]["weighted_beta"], 1e-6) == 0.24
    assert pytest.approx(res["contributions"][2]["weighted_beta"], 1e-6) == 0.3


@pytest.mark.asyncio
async def test_beta_endpoints_and_service_integration():
    await init_db()
    ts = int(datetime.now().timestamp())
    portfolio_id = f"PORT_BETA_{ts}"
    bench_code = f"BENCH_{ts}"
    inst_a_id = f"BETA_A_{ts}"
    inst_b_id = f"BETA_B_{ts}"

    async with AsyncSessionLocal() as session:
        # Create benchmark reference
        bench = BenchmarkReference(
            benchmark_code=bench_code,
            benchmark_name="Nifty 50 Test Benchmark",
            market="IN",
            currency="INR",
            provider="NSE",
            return_basis="TOTAL_RETURN",
            time_zone="Asia/Kolkata",
            is_active=True,
        )
        session.add(bench)

        # Create 2 instruments: INST_A and INST_B
        inst_a = Instrument(
            instrument_id=inst_a_id,
            canonical_name="Beta Asset A Corp",
            short_name="BETA_A",
            instrument_type="COMMON_STOCK",
            asset_class="EQUITY",
            issue_currency="INR",
        )
        inst_b = Instrument(
            instrument_id=inst_b_id,
            canonical_name="Beta Asset B Corp",
            short_name="BETA_B",
            instrument_type="COMMON_STOCK",
            asset_class="EQUITY",
            issue_currency="INR",
        )
        session.add_all([inst_a, inst_b])

        # Create Portfolio
        port = Portfolio(
            portfolio_id=portfolio_id,
            portfolio_code=f"CODE_BETA_{ts}",
            portfolio_name="Beta Risk Test Portfolio",
            short_name="BETA_PORT",
            portfolio_type=PortfolioTypeEnum.PROPRIETARY,
            lifecycle_status=PortfolioLifecycleStatus.ACTIVE,
            base_currency="INR",
            created_by="TEST_RUNNER",
        )
        session.add(port)

        # Create Positions in A and B
        pos_a = PositionBook(
            position_id=f"POS_BETA_A_{ts}",
            portfolio_id=portfolio_id,
            account_id="ACC_01",
            instrument_id=inst_a_id,
            position_side=PositionSide.LONG,
            position_status=PositionStatus.OPEN,
        )
        pos_b = PositionBook(
            position_id=f"POS_BETA_B_{ts}",
            portfolio_id=portfolio_id,
            account_id="ACC_01",
            instrument_id=inst_b_id,
            position_side=PositionSide.LONG,
            position_status=PositionStatus.OPEN,
        )
        session.add_all([pos_a, pos_b])

        # Add price observations for bench_code, inst_a_id, and inst_b_id over 30 days
        base_date = date.today() - timedelta(days=35)
        p_bench = 10000.0
        p_a = 100.0
        p_b = 100.0
        p_port = 100000.0

        np.random.seed(42)
        bench_shocks = np.random.normal(0.001, 0.015, 30)

        for i in range(30):
            d = base_date + timedelta(days=i)
            shock = float(bench_shocks[i])
            p_bench = p_bench * (1.0 + shock)
            p_a = p_a * (1.0 + 1.2 * shock + 0.0005)
            p_b = p_b * (1.0 + 0.8 * shock - 0.0002)
            p_port = p_port * (1.0 + (0.6 * 1.2 + 0.4 * 0.8) * shock)

            # Benchmark observation
            obs_bench = PriceReferenceObservation(
                price_reference_id=f"REF_BENCH_{ts}_{i}",
                instrument_id=bench_code,
                exchange_code="NSE",
                trading_date=d,
                reference_type=PriceReferenceType.OFFICIAL_CLOSE,
                price_value=Decimal(str(round(p_bench, 4))),
                currency="INR",
            )
            obs_a = PriceReferenceObservation(
                price_reference_id=f"REF_A_{ts}_{i}",
                instrument_id=inst_a_id,
                exchange_code="NSE",
                trading_date=d,
                reference_type=PriceReferenceType.OFFICIAL_CLOSE,
                price_value=Decimal(str(round(p_a, 4))),
                currency="INR",
            )
            obs_b = PriceReferenceObservation(
                price_reference_id=f"REF_B_{ts}_{i}",
                instrument_id=inst_b_id,
                exchange_code="NSE",
                trading_date=d,
                reference_type=PriceReferenceType.OFFICIAL_CLOSE,
                price_value=Decimal(str(round(p_b, 4))),
                currency="INR",
            )
            session.add_all([obs_bench, obs_a, obs_b])

            # Portfolio snapshot
            snap = PortfolioBookSnapshot(
                snapshot_id=f"SNAP_BETA_{ts}_{i}",
                portfolio_id=portfolio_id,
                snapshot_type="EOD",
                effective_as_of=datetime.combine(d, datetime.min.time()),
                knowledge_as_of=datetime.combine(d, datetime.min.time()),
                base_currency="INR",
                total_positions_count=2,
                total_nav_base=Decimal(str(round(p_port, 2))),
                total_market_value_base=Decimal(str(round(p_port, 2))),
                total_cash_value_base=Decimal("0.00"),
                snapshot_hash=f"hash_{ts}_{i}",
            )
            session.add(snap)

        await session.commit()

    # Test via API Client
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Health check includes M07.07
        resp_health = await ac.get("/health")
        assert resp_health.status_code == 200
        assert "M07.07 - Portfolio Beta Engine" in resp_health.json()["modules"]

        # 2. Benchmarks list
        resp_benches = await ac.get("/api/v1/market-risk/beta/benchmarks")
        assert resp_benches.status_code == 200
        benchmarks = resp_benches.json()
        assert any(b["benchmark_code"] == bench_code for b in benchmarks)

        # 3. Security Beta for Asset A
        resp_sec = await ac.post(
            "/api/v1/market-risk/beta/security",
            json={
                "instrument_id": inst_a_id,
                "benchmark_code": bench_code,
                "lookback_days": 40,
                "model_type": "OLS_WITH_INTERCEPT",
            },
        )
        assert resp_sec.status_code == 200
        sec_data = resp_sec.json()
        assert sec_data["instrument_id"] == inst_a_id
        assert sec_data["regression_status"] == "VALID"
        assert sec_data["beta_value"] is not None
        # ~ 1.2
        assert 1.0 < float(sec_data["beta_value"]) < 1.4
        assert sec_data["r_squared"] is not None
        assert sec_data["beta_t_statistic"] is not None
        assert sec_data["p_value"] is not None

        # 4. Portfolio Beta (Current Weight Implied)
        resp_port_wt = await ac.post(
            "/api/v1/market-risk/beta/portfolio",
            json={
                "portfolio_id": portfolio_id,
                "benchmark_code": bench_code,
                "method": "CURRENT_WEIGHT_IMPLIED",
                "lookback_days": 40,
            },
        )
        assert resp_port_wt.status_code == 200
        port_wt_data = resp_port_wt.json()
        assert port_wt_data["portfolio_beta"] is not None
        assert 0.8 < float(port_wt_data["portfolio_beta"]) < 1.3
        assert len(port_wt_data["contributions"]) == 2
        assert port_wt_data["reconciliation_discrepancy"] is not None
        assert abs(float(port_wt_data["reconciliation_discrepancy"])) < 1e-4

        # 5. Portfolio Beta (Direct Regression)
        resp_port_dir = await ac.post(
            "/api/v1/market-risk/beta/portfolio",
            json={
                "portfolio_id": portfolio_id,
                "benchmark_code": bench_code,
                "method": "DIRECT_PORTFOLIO_REGRESSION",
                "lookback_days": 40,
            },
        )
        assert resp_port_dir.status_code == 200
        port_dir_data = resp_port_dir.json()
        assert port_dir_data["portfolio_beta"] is not None
        assert 0.8 < float(port_dir_data["portfolio_beta"]) < 1.3

        # 6. Direct vs Weighted Reconciliation Endpoint
        resp_rec = await ac.get(
            f"/api/v1/market-risk/beta/reconciliation?portfolio_id={portfolio_id}&benchmark_code={bench_code}&lookback_days=40"
        )
        assert resp_rec.status_code == 200
        rec_data = resp_rec.json()
        assert rec_data["direct_beta"] is not None
        assert rec_data["weighted_beta"] is not None
        assert rec_data["beta_discrepancy"] is not None
        assert abs(float(rec_data["beta_discrepancy"])) < 0.3

        # 7. Portfolio nested router
        resp_nest = await ac.get(
            f"/api/v1/portfolios/{portfolio_id}/risk/beta?benchmark_code={bench_code}&lookback_days=40"
        )
        assert resp_nest.status_code == 200
        assert resp_nest.json()["portfolio_beta"] is not None

        resp_contribs = await ac.get(
            f"/api/v1/portfolios/{portfolio_id}/risk/beta/contributions?benchmark_code={bench_code}&lookback_days=40"
        )
        assert resp_contribs.status_code == 200
        assert len(resp_contribs.json()) == 2
