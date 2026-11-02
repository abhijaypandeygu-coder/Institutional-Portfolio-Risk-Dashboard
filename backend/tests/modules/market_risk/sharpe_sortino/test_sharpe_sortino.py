"""
Unit and integration tests for M07.08 Sharpe & Sortino Ratios.
"""
from datetime import date, timedelta, datetime, timezone
from decimal import Decimal
import numpy as np
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.modules.market_risk.sharpe_sortino.calculations.ratio_math import (
    convert_rate_to_period_return,
    calculate_sharpe_ratio,
    calculate_downside_deviation,
    calculate_sortino_ratio,
)
from backend.app.modules.market_risk.sharpe_sortino.models import (
    RateConvention,
    DayCountConvention,
    SharpeDenominatorPolicy,
    SortinoTargetPolicy,
    SortinoDenominatorPolicy,
    RatioCalculationStatus,
    RiskFreeRateSeries,
    RiskFreeRateObservation,
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
from backend.app.modules.portfolio_management.portfolio_history.models import PortfolioBookSnapshot


# -------------------------------------------------------------
# 1. Pure Mathematical Tests
# -------------------------------------------------------------
def test_rate_conversion_math():
    # 6.5% effective annual rate -> 1 day period return: (1 + 0.065)^(1/365) - 1
    r_eff = convert_rate_to_period_return(0.065, RateConvention.EFFECTIVE_ANNUAL_RATE, DayCountConvention.ACTUAL_365, 1)
    expected_eff = (1.0 + 0.065) ** (1.0 / 365.0) - 1.0
    assert pytest.approx(r_eff, 1e-8) == expected_eff

    # Simple rate: y * (1/365)
    r_simple = convert_rate_to_period_return(0.065, RateConvention.SIMPLE_ANNUAL_RATE, DayCountConvention.ACTUAL_365, 1)
    assert pytest.approx(r_simple, 1e-8) == 0.065 / 365.0

    # Actual/360 divisor
    r_360 = convert_rate_to_period_return(0.065, RateConvention.SIMPLE_ANNUAL_RATE, DayCountConvention.ACTUAL_360, 1)
    assert pytest.approx(r_360, 1e-8) == 0.065 / 360.0


def test_sharpe_ratio_math():
    # Known dataset: mean excess return = 0.001, volatility = 0.01
    # Sharpe period = 0.1, Annualized (sqrt(252)) ~ 0.1 * 15.8745 = 1.58745
    rf = np.zeros(20, dtype=np.float64)
    # create series with mean 0.001
    rp = np.array([
        0.011, -0.009, 0.008, -0.006, 0.015, -0.013, 0.004, -0.002, 0.007, -0.005,
        0.012, -0.010, 0.009, -0.007, 0.014, -0.012, 0.003, -0.001, 0.006, -0.004
    ], dtype=np.float64)
    res = calculate_sharpe_ratio(rp, rf, annualization_factor=252.0)
    assert res["status"] == RatioCalculationStatus.VALID
    assert pytest.approx(res["mean_excess_return"], 1e-6) == 0.001
    assert res["volatility"] > 0.0
    assert res["period_sharpe"] == pytest.approx(res["mean_excess_return"] / res["volatility"], 1e-6)
    assert res["annualized_sharpe"] == pytest.approx(res["period_sharpe"] * np.sqrt(252.0), 1e-6)

    # Zero volatility test
    flat_rp = np.full(20, 0.001, dtype=np.float64)
    res_zero = calculate_sharpe_ratio(flat_rp, rf)
    assert res_zero["status"] == RatioCalculationStatus.ZERO_VOLATILITY
    assert res_zero["period_sharpe"] is None


def test_sortino_ratio_math():
    target = np.zeros(10, dtype=np.float64)
    # 5 positive returns, 5 negative returns
    rp = np.array([0.02, 0.03, 0.01, 0.04, 0.02, -0.01, -0.02, -0.01, -0.03, -0.01], dtype=np.float64)
    # mean return = (0.12 - 0.08) / 10 = 0.04 / 10 = 0.004
    # shortfalls squared: 0.01^2, 0.02^2, 0.01^2, 0.03^2, 0.01^2 = 0.0001 + 0.0004 + 0.0001 + 0.0009 + 0.0001 = 0.0016
    # All periods semideviation: sqrt( 0.0016 / 10 ) = sqrt(0.00016) = 0.01264911
    res = calculate_sortino_ratio(rp, target, annualization_factor=252.0)
    assert res["status"] == RatioCalculationStatus.VALID
    assert pytest.approx(res["mean_return"], 1e-6) == 0.004
    assert pytest.approx(res["downside_deviation"], 1e-6) == np.sqrt(0.0016 / 10.0)
    expected_sortino = 0.004 / np.sqrt(0.0016 / 10.0)
    assert pytest.approx(res["period_sortino"], 1e-6) == expected_sortino
    assert pytest.approx(res["annualized_sortino"], 1e-6) == expected_sortino * np.sqrt(252.0)
    assert res["downside_periods_count"] == 5
    assert res["downside_percentage"] == 50.0

    # Zero downside deviation test (all returns exceed target)
    positive_rp = np.array([0.01, 0.02, 0.03, 0.01, 0.02, 0.04], dtype=np.float64)
    res_pos = calculate_sortino_ratio(positive_rp, np.zeros(6))
    assert res_pos["status"] == RatioCalculationStatus.ZERO_DOWNSIDE_DEVIATION
    assert res_pos["period_sortino"] is None


# -------------------------------------------------------------
# 2. End-to-End API & Integration Test
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_sharpe_sortino_api_integration():
    await init_db()
    ts = int(datetime.now().timestamp())
    portfolio_id = f"PORT_RATIOS_{ts}"
    rf_code = f"RF_TEST_{ts}"
    inst_id = f"INST_RATIOS_{ts}"

    async with AsyncSessionLocal() as session:
        # 1. Register Risk Free Series
        rf_series = RiskFreeRateSeries(
            series_code=rf_code,
            rate_name="Test Risk Free Rate",
            currency="INR",
            market="INDIA",
            provider="RBI",
            rate_convention=RateConvention.EFFECTIVE_ANNUAL_RATE,
            day_count_convention=DayCountConvention.ACTUAL_365,
            is_active=True,
        )
        session.add(rf_series)
        await session.flush()

        # 2. Register Instrument
        inst = Instrument(
            instrument_id=inst_id,
            canonical_name="Test Ratio Asset Corp",
            short_name="RATIO_ASSET",
            instrument_type="COMMON_STOCK",
            asset_class="EQUITY",
            issue_currency="INR",
        )
        session.add(inst)

        # 3. Register Portfolio
        port = Portfolio(
            portfolio_id=portfolio_id,
            portfolio_code=f"CODE_RATIOS_{ts}",
            portfolio_name="Ratio Analysis Test Portfolio",
            short_name="RATIO_PORT",
            portfolio_type=PortfolioTypeEnum.PROPRIETARY,
            lifecycle_status=PortfolioLifecycleStatus.ACTIVE,
            base_currency="INR",
            created_by="TEST_RUNNER",
        )
        session.add(port)

        # 4. Add 35 daily observations for Instrument and Portfolio
        base_date = date.today() - timedelta(days=40)
        p_sec = 100.0
        p_port = 100000.0

        for i in range(35):
            d = base_date + timedelta(days=i)
            # Add daily rate observation (6.5% flat)
            session.add(RiskFreeRateObservation(
                series_id=rf_series.id,
                rate_date=d,
                annualized_rate=Decimal("0.0650"),
            ))

            # Price path: upward drift
            shock = 0.002 if i % 2 == 0 else -0.001
            p_sec = p_sec * (1.0 + shock)
            p_port = p_port * (1.0 + shock)

            session.add(PriceReferenceObservation(
                price_reference_id=f"REF_RATIO_{ts}_{i}",
                instrument_id=inst_id,
                exchange_code="NSE",
                trading_date=d,
                reference_type=PriceReferenceType.OFFICIAL_CLOSE,
                price_value=Decimal(str(round(p_sec, 4))),
                currency="INR",
            ))

            session.add(PortfolioBookSnapshot(
                snapshot_id=f"SNAP_RATIO_{ts}_{i}",
                portfolio_id=portfolio_id,
                snapshot_type="EOD",
                effective_as_of=datetime.combine(d, datetime.min.time()),
                knowledge_as_of=datetime.combine(d, datetime.min.time()),
                base_currency="INR",
                total_positions_count=1,
                total_nav_base=Decimal(str(round(p_port, 2))),
                total_market_value_base=Decimal(str(round(p_port, 2))),
                total_cash_value_base=Decimal("0.00"),
                snapshot_hash=f"hash_{ts}_{i}",
            ))

        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Health check includes M07.08
        resp_health = await ac.get("/health")
        assert resp_health.status_code == 200
        assert "M07.08 - Sharpe & Sortino Ratios Engine" in resp_health.json()["modules"]

        # 2. Sharpe endpoint for Portfolio
        resp_sharpe = await ac.post(
            "/api/v1/market-risk/ratios/sharpe",
            json={
                "scope": "PORTFOLIO",
                "entity_id": portfolio_id,
                "risk_free_series_code": rf_code,
                "lookback_days": 40,
            },
        )
        assert resp_sharpe.status_code == 200
        sh_data = resp_sharpe.json()
        assert sh_data["status"] == "VALID"
        assert sh_data["period_sharpe"] is not None
        assert sh_data["annualized_sharpe"] is not None
        assert sh_data["sample_size"] == 34

        # 3. Sortino endpoint for Portfolio
        resp_sortino = await ac.post(
            "/api/v1/market-risk/ratios/sortino",
            json={
                "scope": "PORTFOLIO",
                "entity_id": portfolio_id,
                "risk_free_series_code": rf_code,
                "lookback_days": 40,
            },
        )
        assert resp_sortino.status_code == 200
        so_data = resp_sortino.json()
        assert so_data["status"] == "VALID"
        assert so_data["period_sortino"] is not None
        assert so_data["annualized_sortino"] is not None
        assert so_data["downside_periods_count"] > 0

        # 4. Combined endpoint
        resp_comb = await ac.post(
            "/api/v1/market-risk/ratios/combined",
            json={
                "scope": "PORTFOLIO",
                "entity_id": portfolio_id,
                "risk_free_series_code": rf_code,
                "lookback_days": 40,
            },
        )
        assert resp_comb.status_code == 200
        comb_data = resp_comb.json()
        assert comb_data["sharpe"]["period_sharpe"] is not None
        assert comb_data["sortino"]["period_sortino"] is not None

        # 5. Rolling ratios endpoint
        resp_roll = await ac.post(
            "/api/v1/market-risk/ratios/rolling",
            json={
                "scope": "PORTFOLIO",
                "entity_id": portfolio_id,
                "risk_free_series_code": rf_code,
                "window_days": 15,
            },
        )
        assert resp_roll.status_code == 200
        roll_data = resp_roll.json()
        assert len(roll_data["points"]) > 0
        assert roll_data["points"][0]["period_sharpe"] is not None

        # 6. Portfolio Nested Router
        resp_nest = await ac.get(
            f"/api/v1/portfolios/{portfolio_id}/risk/ratios?risk_free_series_code={rf_code}&lookback_days=40"
        )
        assert resp_nest.status_code == 200
        assert resp_nest.json()["sharpe"]["period_sharpe"] is not None
