"""
Integration and mathematical tests for M07.06 Covariance Analysis.
"""
from datetime import date, timedelta, datetime
from decimal import Decimal
import numpy as np
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.modules.market_risk.covariance.calculations.covariance_math import (
    calculate_sample_covariance,
    compute_covariance_matrix,
    repair_covariance_psd,
    calculate_portfolio_variance_and_risk_contributions,
    calculate_portfolio_pair_covariance,
    calculate_rolling_covariance,
)
from backend.app.modules.market_risk.covariance.models import (
    CovarianceEstimator,
    DenominatorPolicy,
    MatrixPSDStatus,
    WeightBasis,
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


def test_covariance_math_known_linear_relationships():
    # Dataset A & B: Identical & Negatively scaled series
    x = np.array([0.01, -0.02, 0.015, -0.005, 0.03, -0.01, 0.02], dtype=np.float64)
    var_x = float(np.var(x, ddof=1))

    # Identical: Cov(X, X) == Var(X)
    res_ident = calculate_sample_covariance(x, x, denominator_policy=DenominatorPolicy.UNBIASED_SAMPLE)
    assert res_ident["is_valid"] is True
    assert pytest.approx(res_ident["covariance"], 1e-8) == var_x
    assert pytest.approx(res_ident["correlation"], 1e-6) == 1.0

    # Negatively scaled: Y = -2X => Cov(X, Y) == -2 * Var(X)
    y_neg = -2.0 * x
    res_neg = calculate_sample_covariance(x, y_neg, denominator_policy=DenominatorPolicy.UNBIASED_SAMPLE)
    assert res_neg["is_valid"] is True
    assert pytest.approx(res_neg["covariance"], 1e-8) == -2.0 * var_x
    assert pytest.approx(res_neg["correlation"], 1e-6) == -1.0


def test_covariance_denominator_policy():
    x = np.array([0.01, 0.02, -0.01, 0.03, -0.02], dtype=np.float64)
    y = np.array([0.02, 0.01, -0.03, 0.04, -0.01], dtype=np.float64)

    # Sample (ddof=1) vs Population (ddof=0)
    sample_res = calculate_sample_covariance(x, y, denominator_policy=DenominatorPolicy.UNBIASED_SAMPLE)
    pop_res = calculate_sample_covariance(x, y, denominator_policy=DenominatorPolicy.POPULATION)

    # Ratio of sample to pop covariance should be n / (n-1) = 5 / 4 = 1.25
    ratio = sample_res["covariance"] / pop_res["covariance"]
    assert pytest.approx(ratio, 1e-6) == 1.25


def test_portfolio_variance_and_risk_contributions():
    # 3-asset universe with known covariance matrix
    # Sigma = [[0.04, 0.01, 0.0], [0.01, 0.09, -0.02], [0.0, -0.02, 0.16]]
    cov = np.array([
        [0.04, 0.01, 0.0],
        [0.01, 0.09, -0.02],
        [0.0, -0.02, 0.16]
    ], dtype=np.float64)
    weights = np.array([0.4, 0.4, 0.2], dtype=np.float64)
    symbols = ["A", "B", "C"]

    calc = calculate_portfolio_variance_and_risk_contributions(weights, cov, symbols, annualization_factor=252.0)

    # Independent formula: sigma_p^2 = w^T Sigma w
    # = 0.16*0.04 + 0.16*0.09 + 0.04*0.16 + 2*(0.16*0.01 + 0.08*0.0 - 0.08*0.02)
    # = 0.0064 + 0.0144 + 0.0064 + 2*(0.0016 + 0.0 - 0.0016) = 0.0272
    assert pytest.approx(calc["period_portfolio_variance"], 1e-6) == 0.0272
    assert pytest.approx(calc["period_portfolio_volatility"], 1e-6) == np.sqrt(0.0272)

    # Check risk contribution reconciliation: sum(CV_i) == sigma_p^2, sum(CR_i) == sigma_p
    assert pytest.approx(calc["variance_discrepancy"], 1e-8) == 0.0
    assert pytest.approx(calc["volatility_discrepancy"], 1e-8) == 0.0


def test_portfolio_pair_cross_covariance():
    cov = np.array([
        [0.04, 0.02],
        [0.02, 0.09]
    ], dtype=np.float64)
    w_a = np.array([1.0, 0.0], dtype=np.float64)  # 100% in asset 1
    w_b = np.array([0.0, 1.0], dtype=np.float64)  # 100% in asset 2

    res = calculate_portfolio_pair_covariance(w_a, w_b, cov)
    # Cov(R_A, R_B) = w_A^T Sigma w_B = Sigma[0, 1] = 0.02
    assert pytest.approx(res["period_covariance"], 1e-6) == 0.02
    assert pytest.approx(res["portfolio_a_variance"], 1e-6) == 0.04
    assert pytest.approx(res["portfolio_b_variance"], 1e-6) == 0.09
    # Correlation = 0.02 / (0.2 * 0.3) = 0.02 / 0.06 = 1/3
    assert pytest.approx(res["derived_correlation"], 1e-6) == 1.0 / 3.0


def test_rolling_covariance():
    dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(40)]
    x = np.random.normal(0, 0.02, 40)
    y = np.random.normal(0, 0.02, 40)

    rolling = calculate_rolling_covariance(dates, x, y, window_days=15)
    assert len(rolling) == 26
    assert "delta_covariance" in rolling[1]
    assert rolling[0]["sample_size"] == 15


@pytest.mark.asyncio
async def test_end_to_end_covariance_api():
    await init_db()
    ts = int(datetime.now().timestamp())
    inst_a_id = f"INST_COV_AAPL_{ts}"
    inst_b_id = f"INST_COV_MSFT_{ts}"
    port_id = f"PORT_COV_{ts}"

    async with AsyncSessionLocal() as session:
        # Seed two instruments
        inst_a = Instrument(
            instrument_id=inst_a_id,
            canonical_name="Apple Inc Common Stock",
            short_name="AAPL",
            instrument_type="COMMON_STOCK",
            asset_class="EQUITY",
            issue_currency="USD",
        )
        inst_b = Instrument(
            instrument_id=inst_b_id,
            canonical_name="Microsoft Corp Common Stock",
            short_name="MSFT",
            instrument_type="COMMON_STOCK",
            asset_class="EQUITY",
            issue_currency="USD",
        )
        session.add_all([inst_a, inst_b])
        await session.flush()

        # Seed 35 daily price observations
        base_date = date(2026, 1, 1)
        prices_a = [Decimal(str(150 + i * 0.8)) for i in range(35)]
        prices_b = [Decimal(str(250 + i * 1.2)) for i in range(35)]

        for i in range(35):
            d = base_date + timedelta(days=i)
            session.add(PriceReferenceObservation(
                price_reference_id=f"REF_COV_A_{ts}_{i}",
                instrument_id=inst_a.instrument_id,
                exchange_code="NASDAQ",
                trading_date=d,
                reference_type=PriceReferenceType.OFFICIAL_CLOSE,
                price_value=prices_a[i],
                currency="USD",
            ))
            session.add(PriceReferenceObservation(
                price_reference_id=f"REF_COV_B_{ts}_{i}",
                instrument_id=inst_b.instrument_id,
                exchange_code="NASDAQ",
                trading_date=d,
                reference_type=PriceReferenceType.OFFICIAL_CLOSE,
                price_value=prices_b[i],
                currency="USD",
            ))

        # Seed portfolio
        port = Portfolio(
            portfolio_id=port_id,
            portfolio_code=f"CODE_COV_{ts}",
            portfolio_name="Covariance Test Portfolio",
            short_name="COV_PORT",
            portfolio_type=PortfolioTypeEnum.PROPRIETARY,
            lifecycle_status=PortfolioLifecycleStatus.ACTIVE,
            base_currency="USD",
            created_by="TEST_RUNNER",
        )
        session.add(port)
        await session.flush()

        # Seed positions
        session.add(PositionBook(
            position_id=f"POS_COV_1_{ts}",
            portfolio_id=port.portfolio_id,
            account_id="ACC_01",
            instrument_id=inst_a.instrument_id,
            position_side=PositionSide.LONG,
            position_status=PositionStatus.OPEN,
        ))
        session.add(PositionBook(
            position_id=f"POS_COV_2_{ts}",
            portfolio_id=port.portfolio_id,
            account_id="ACC_01",
            instrument_id=inst_b.instrument_id,
            position_side=PositionSide.LONG,
            position_status=PositionStatus.OPEN,
        ))

        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test 1: Pairwise Covariance Endpoint
        res = await client.post(
            "/api/v1/market-risk/covariance/pairwise",
            json={
                "asset_a_id": inst_a_id,
                "asset_b_id": inst_b_id,
                "lookback_days": 30,
                "as_of": "2026-02-04",
                "estimator": "SAMPLE",
                "annualize": True,
            },
        )
        assert res.status_code == 200, res.text
        pair_data = res.json()
        assert "covariance_value" in pair_data
        assert "annualized_covariance" in pair_data
        assert pair_data["sample_size"] > 10

        # Test 2: Full Matrix Endpoint
        mat_res = await client.post(
            "/api/v1/market-risk/covariance/matrix",
            json={
                "portfolio_id": port_id,
                "lookback_days": 30,
                "as_of": "2026-02-04",
                "estimator": "SAMPLE",
            },
        )
        assert mat_res.status_code == 200, mat_res.text
        mat_data = mat_res.json()
        assert mat_data["dimension"] == 2
        assert len(mat_data["matrix"]) == 2
        assert mat_data["is_symmetric"] is True

        # Test 3: Rolling Covariance Endpoint
        roll_res = await client.post(
            "/api/v1/market-risk/covariance/rolling",
            json={
                "asset_a_id": inst_a_id,
                "asset_b_id": inst_b_id,
                "window_days": 10,
                "history_lookback_days": 30,
                "as_of": "2026-02-04",
                "estimator": "SAMPLE",
            },
        )
        assert roll_res.status_code == 200, roll_res.text
        roll_data = roll_res.json()
        assert len(roll_data["series"]) > 0

        # Test 4: Portfolio Covariance & Risk Contributions Endpoint
        port_cov_res = await client.post(
            "/api/v1/market-risk/covariance/portfolio",
            json={
                "portfolio_id": port_id,
                "lookback_days": 30,
                "as_of": "2026-02-04",
                "weight_basis": "PORTFOLIO_NAV",
            },
        )
        assert port_cov_res.status_code == 200, port_cov_res.text
        port_cov_data = port_cov_res.json()
        assert "period_portfolio_variance" in port_cov_data
        assert len(port_cov_data["contributions"]) == 2

        # Test 5: Health Check
        h_res = await client.get("/health")
        assert h_res.status_code == 200
        assert "M07.06 - Covariance Analysis Engine" in h_res.json()["modules"]
