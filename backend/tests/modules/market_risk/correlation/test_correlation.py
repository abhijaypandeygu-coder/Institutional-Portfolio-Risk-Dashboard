"""
Integration and mathematical tests for M07.05 Correlation Analysis.
"""
from datetime import date, timedelta, datetime, timezone
from decimal import Decimal
import numpy as np
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.modules.market_risk.correlation.calculations.correlation_math import (
    align_two_series,
    calculate_pairwise_correlation,
    compute_correlation_matrix,
    repair_psd_matrix,
    calculate_rolling_correlation,
)
from backend.app.modules.market_risk.correlation.models import CorrelationEstimator, PSDStatus
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


def test_correlation_math_perfect_positive_and_negative():
    # Synthetic identical / inverse series
    x = np.array([0.01, -0.02, 0.015, -0.005, 0.03, -0.01, 0.02], dtype=np.float64)
    y_pos = 2.0 * x + 0.001
    y_neg = -3.0 * x - 0.002

    res_pos = calculate_pairwise_correlation(x, y_pos, estimator=CorrelationEstimator.PEARSON)
    assert res_pos["is_valid"] is True
    assert pytest.approx(res_pos["correlation"], 1e-4) == 1.0

    res_neg = calculate_pairwise_correlation(x, y_neg, estimator=CorrelationEstimator.PEARSON)
    assert res_neg["is_valid"] is True
    assert pytest.approx(res_neg["correlation"], 1e-4) == -1.0


def test_correlation_math_estimators_and_zero_variance():
    x = np.array([0.01, 0.02, 0.03, 0.04, 0.05, 0.06], dtype=np.float64)
    # Monotonic non-linear: y = x^3
    y = x ** 3

    pearson = calculate_pairwise_correlation(x, y, estimator=CorrelationEstimator.PEARSON)
    spearman = calculate_pairwise_correlation(x, y, estimator=CorrelationEstimator.SPEARMAN)
    kendall = calculate_pairwise_correlation(x, y, estimator=CorrelationEstimator.KENDALL_TAU_B)

    # Spearman rank correlation should be exactly 1.0 for strictly monotonic relationship
    assert pytest.approx(spearman["correlation"], 1e-4) == 1.0
    assert pytest.approx(kendall["correlation"], 1e-4) == 1.0
    # Pearson is slightly less than 1 due to non-linearity
    assert pearson["correlation"] < 1.0 and pearson["correlation"] > 0.90

    # Zero variance test
    zero_var = np.array([0.02, 0.02, 0.02, 0.02, 0.02, 0.02], dtype=np.float64)
    res_zero = calculate_pairwise_correlation(x, zero_var, estimator=CorrelationEstimator.PEARSON)
    assert res_zero["correlation"] == 0.0


def test_matrix_psd_diagnostics_and_repair():
    # Create non-PSD 3x3 matrix where R_12=0.9, R_23=0.9, R_13=-0.9 (mathematically non-PSD)
    raw_non_psd = np.array([
        [1.0, 0.9, -0.9],
        [0.9, 1.0, 0.9],
        [-0.9, 0.9, 1.0],
    ], dtype=np.float64)

    eigs = np.linalg.eigvalsh(raw_non_psd)
    assert np.min(eigs) < 0  # Confirmed non-PSD

    repaired, t_info = repair_psd_matrix(raw_non_psd, method="EIGENVALUE_CLIPPING")
    repaired_eigs = np.linalg.eigvalsh(repaired)
    assert np.min(repaired_eigs) >= -1e-8  # Must be PSD
    assert np.allclose(np.diag(repaired), 1.0)  # Unit diagonal preserved
    assert np.allclose(repaired, repaired.T)  # Symmetry preserved
    assert t_info["min_eigenvalue_after"] >= 0


def test_rolling_correlation_and_delta():
    dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(40)]
    x = np.random.normal(0, 0.01, 40)
    y = np.random.normal(0, 0.01, 40)

    rolling = calculate_rolling_correlation(dates, x, y, window_days=15)
    assert len(rolling) == 26
    assert "delta_rho" in rolling[1]
    assert "baseline_deviation" in rolling[1]
    assert rolling[0]["sample_size"] == 15


@pytest.mark.asyncio
async def test_end_to_end_correlation_api():
    await init_db()
    ts = int(datetime.now().timestamp())
    inst_a_id = f"INST_CORR_AAPL_{ts}"
    inst_b_id = f"INST_CORR_MSFT_{ts}"
    port_id = f"PORT_CORR_{ts}"

    async with AsyncSessionLocal() as session:
        # 1. Seed two instruments
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

        # Seed 35 daily price observations for both
        base_date = date(2026, 1, 1)
        prices_a = [Decimal(str(150 + i * 0.8)) for i in range(35)]
        prices_b = [Decimal(str(250 + i * 1.2)) for i in range(35)]

        for i in range(35):
            d = base_date + timedelta(days=i)
            session.add(PriceReferenceObservation(
                price_reference_id=f"REF_A_{ts}_{i}",
                instrument_id=inst_a.instrument_id,
                exchange_code="NASDAQ",
                trading_date=d,
                reference_type=PriceReferenceType.OFFICIAL_CLOSE,
                price_value=prices_a[i],
                currency="USD",
            ))
            session.add(PriceReferenceObservation(
                price_reference_id=f"REF_B_{ts}_{i}",
                instrument_id=inst_b.instrument_id,
                exchange_code="NASDAQ",
                trading_date=d,
                reference_type=PriceReferenceType.OFFICIAL_CLOSE,
                price_value=prices_b[i],
                currency="USD",
            ))

        # Seed a test portfolio
        port = Portfolio(
            portfolio_id=port_id,
            portfolio_code=f"CODE_CORR_{ts}",
            portfolio_name="Correlation Test Portfolio",
            short_name="CORR_PORT",
            portfolio_type=PortfolioTypeEnum.PROPRIETARY,
            lifecycle_status=PortfolioLifecycleStatus.ACTIVE,
            base_currency="USD",
            created_by="TEST_RUNNER",
        )
        session.add(port)
        await session.flush()

        # Seed positions
        session.add(PositionBook(
            position_id=f"POS_CORR_1_{ts}",
            portfolio_id=port.portfolio_id,
            account_id="ACC_01",
            instrument_id=inst_a.instrument_id,
            position_side=PositionSide.LONG,
            position_status=PositionStatus.OPEN,
        ))
        session.add(PositionBook(
            position_id=f"POS_CORR_2_{ts}",
            portfolio_id=port.portfolio_id,
            account_id="ACC_01",
            instrument_id=inst_b.instrument_id,
            position_side=PositionSide.LONG,
            position_status=PositionStatus.OPEN,
        ))

        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test 1: Pairwise Correlation
        res = await client.post(
            "/api/v1/market-risk/correlation/pairwise",
            json={
                "asset_a_id": inst_a_id,
                "asset_b_id": inst_b_id,
                "lookback_days": 30,
                "as_of": "2026-02-04",
                "estimator": "PEARSON",
                "portfolio_id": port_id,
            },
        )
        assert res.status_code == 200, res.text
        pair_data = res.json()
        assert "correlation_coefficient" in pair_data
        assert pair_data["sample_size"] > 10
        assert pair_data["asset_a_symbol"] in ("AAPL", "MSFT")

        # Test 2: Matrix API
        mat_res = await client.post(
            "/api/v1/market-risk/correlation/matrix",
            json={
                "portfolio_id": port_id,
                "lookback_days": 30,
                "as_of": "2026-02-04",
                "estimator": "PEARSON",
            },
        )
        assert mat_res.status_code == 200, mat_res.text
        mat_data = mat_res.json()
        assert mat_data["dimension"] == 2
        assert mat_data["psd_status"] in ("VALID_PSD", "NON_PSD")
        assert len(mat_data["matrix"]) == 2

        # Test 3: Rolling Correlation
        roll_res = await client.post(
            "/api/v1/market-risk/correlation/rolling",
            json={
                "asset_a_id": inst_a_id,
                "asset_b_id": inst_b_id,
                "window_days": 10,
                "history_lookback_days": 30,
                "as_of": "2026-02-04",
                "estimator": "PEARSON",
            },
        )
        assert roll_res.status_code == 200, roll_res.text
        roll_data = roll_res.json()
        assert "series" in roll_data
        assert len(roll_data["series"]) > 0

        # Test 4: Portfolio Rankings
        rank_res = await client.get(
            f"/api/v1/portfolios/{port_id}/risk/correlation/rankings?lookback_days=30&as_of=2026-02-04"
        )
        assert rank_res.status_code == 200, rank_res.text
        rank_data = rank_res.json()
        assert "top_positive_correlations" in rank_data

        # Test 5: Multi-Horizon Lookback
        mh_res = await client.get(
            f"/api/v1/market-risk/correlation/multi-horizon?asset_a_id={inst_a_id}&asset_b_id={inst_b_id}&as_of=2026-02-04"
        )
        assert mh_res.status_code == 200, mh_res.text
        mh_data = mh_res.json()
        assert "horizons" in mh_data
        assert "20D" in mh_data["horizons"]

        # Test 6: Health Endpoint check
        h_res = await client.get("/health")
        assert h_res.status_code == 200
        assert "M07.05 - Correlation Analysis Engine" in h_res.json()["modules"]
