"""
Module M07.01: Historical Volatility End-to-End Test Suite.
Verifies return calculation formulas, sample standard deviation, rolling volatility,
annualization scaling, multi-horizon window comparisons, volatility trends, and intraday suitability.
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
from backend.app.modules.instrument_reference_data.price_reference.models import (
    PriceReferenceObservation,
    PriceReferenceType,
    PriceBasis,
    PriceOrigin,
    CurrencyBasis,
    VerificationStatus,
)
from backend.app.modules.market_data_ingestion.persistence.models import MarketOHLCV
from backend.app.modules.market_risk.historical_volatility.calculations.volatility_math import (
    calculate_return,
    calculate_sample_variance_and_std_dev,
    annualize_volatility,
    calculate_volatility_trend_slope,
    classify_volatility_trend,
    compare_volatility_horizons,
)
from backend.app.modules.market_risk.historical_volatility.models import (
    ReturnType,
    StatisticalEstimator,
    VolatilityTrendClassification,
    VolatilityWindowComparisonLabel,
)


def test_volatility_mathematical_units():
    """
    Test pure mathematical formulas for returns, sample variance, standard deviation,
    annualization, and trend slope.
    """
    # 1. Log and Simple returns
    # Price moves from 100 to 105
    p0 = Decimal("100.00")
    p1 = Decimal("105.00")
    simple_ret = calculate_return(p0, p1, return_type=ReturnType.SIMPLE)
    log_ret = calculate_return(p0, p1, return_type=ReturnType.LOGARITHMIC)
    assert simple_ret == Decimal("0.05000000")
    # ln(1.05) ~ 0.04879016
    assert abs(log_ret - Decimal("0.04879016")) < Decimal("0.000001")

    # Constant price return must yield zero variance
    p_const = Decimal("100.00")
    zero_rets = [calculate_return(p_const, p_const, return_type=ReturnType.LOGARITHMIC) for _ in range(10)]
    mean, var, std = calculate_sample_variance_and_std_dev(zero_rets)
    assert mean == Decimal("0.00000000")
    assert var == Decimal("0.00000000")
    assert std == Decimal("0.00000000")

    # Sample standard deviation test: [0.01, -0.01, 0.02, -0.02]
    # Mean = 0.0
    # Sum of sq diff = 0.0001 + 0.0001 + 0.0004 + 0.0004 = 0.0010
    # N - 1 = 3 -> Var = 0.0010 / 3 = 0.00033333... -> Std = 0.01825742
    rets = [Decimal("0.01"), Decimal("-0.01"), Decimal("0.02"), Decimal("-0.02")]
    m, v, s = calculate_sample_variance_and_std_dev(rets, StatisticalEstimator.SAMPLE_STD_DEV)
    assert m == Decimal("0.00000000")
    assert abs(s - Decimal("0.01825742")) < Decimal("0.00001")

    # Annualization: sigma * sqrt(252)
    # sqrt(252) = 15.874508
    factor, ann_vol = annualize_volatility(s, 252)
    assert factor == Decimal("15.874508")
    expected_ann = (s * Decimal("15.874508")).quantize(Decimal("0.00000001"))
    assert ann_vol == expected_ann

    # Trend slope
    # Increasing volatility: [0.10, 0.12, 0.14, 0.16] -> slope should be +0.02
    vols = [Decimal("0.10"), Decimal("0.12"), Decimal("0.14"), Decimal("0.16")]
    alpha, beta = calculate_volatility_trend_slope(vols)
    assert beta == Decimal("0.02000000")


@pytest.mark.asyncio
async def test_historical_volatility_daily_and_rolling_pipeline():
    """
    Integration test for M07.01:
    1. Create instrument (e.g. AAPL)
    2. Seed 25 daily price observations via M04.05 PriceReferenceObservation
    3. Compute historical volatility for 20-day lookback
    4. Verify rolling volatility series
    5. Verify window comparison (short vs medium vs long)
    6. Verify trend classification
    """
    await init_db()
    ts = datetime.utcnow().timestamp()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create Instrument
        async with AsyncSessionLocal() as session:
            inst = await InstrumentMasterService.create_instrument(
                session,
                InstrumentCreateRequest(
                    canonical_name=f"Apple Inc Vol Test {ts}",
                    short_name=f"AAPL_{ts}",
                    instrument_type="COMMON_STOCK",
                    asset_class="EQUITY",
                    issue_currency="USD",
                    primary_market_id="NASDAQ",
                ),
                actor_id="admin",
            )
            inst_id = inst.instrument_id

            # 2. Seed 25 daily prices: 100, 102, 101, 103, 105, ...
            base_date = date(2026, 1, 1)
            # Create synthetic oscillating upward trend
            price_series = [
                100, 102, 101, 103, 102, 104, 103, 106, 105, 107,
                106, 109, 108, 110, 112, 111, 114, 113, 115, 117,
                116, 119, 118, 120, 122
            ]
            for idx, p in enumerate(price_series):
                obs = PriceReferenceObservation(
                    price_reference_id=f"PREF_{ts}_{idx}",
                    instrument_id=inst_id,
                    exchange_code="NASDAQ",
                    trading_date=base_date + timedelta(days=idx),
                    reference_type=PriceReferenceType.OFFICIAL_CLOSE,
                    price_value=Decimal(str(p)),
                    currency="USD",
                    price_basis=PriceBasis.SPLIT_ADJUSTED,
                    price_origin=PriceOrigin.EXCHANGE_OFFICIAL,
                    verification_status=VerificationStatus.VERIFIED,
                )
                session.add(obs)
            await session.commit()

        # 3. GET /market-risk/historical-volatility (lookback 20)
        resp = await client.get(
            f"/api/v1/market-risk/historical-volatility?instrument_id={inst_id}&lookback_window=20"
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert data["instrument_id"] == inst_id
        assert data["observation_count"] == 20
        assert data["expected_observation_count"] == 20
        assert Decimal(data["coverage_percentage"]) == Decimal("100.0000")
        assert Decimal(data["period_volatility"]) > Decimal("0.0")
        assert Decimal(data["annualized_volatility"]) > Decimal("0.0")
        assert data["calculation_status"] == "CALCULATED"

        # 4. GET /market-risk/historical-volatility/rolling (rolling 20)
        rolling_resp = await client.get(
            f"/api/v1/market-risk/historical-volatility/rolling?instrument_id={inst_id}&lookback_window=20"
        )
        assert rolling_resp.status_code == 200
        rolling_data = rolling_resp.json()
        assert rolling_data["total_points"] >= 20
        assert len(rolling_data["series"]) >= 20

        # 5. GET /market-risk/historical-volatility/window-comparison
        comp_resp = await client.get(
            f"/api/v1/market-risk/historical-volatility/window-comparison?instrument_id={inst_id}&short_window=10&medium_window=20&long_window=60"
        )
        assert comp_resp.status_code == 200
        comp_data = comp_resp.json()
        assert len(comp_data["horizons"]) == 3
        short_h = next(h for h in comp_data["horizons"] if h["horizon"] == "SHORT")
        assert short_h["observation_count"] == 10
        assert short_h["status"] == "CALCULATED"

        # 6. GET /market-risk/historical-volatility/trend
        trend_resp = await client.get(
            f"/api/v1/market-risk/historical-volatility/trend?instrument_id={inst_id}&lookback_window=10"
        )
        assert trend_resp.status_code == 200
        trend_data = trend_resp.json()
        assert trend_data["current_volatility"] is not None
        assert trend_data["trend_classification"] in [
            "VOLATILITY_INCREASING",
            "VOLATILITY_DECREASING",
            "VOLATILITY_STABLE",
        ]


@pytest.mark.asyncio
async def test_intraday_volatility_and_microstructure_suitability():
    """
    Test intraday 5m bar volatility calculation using M02 MarketOHLCV bars.
    """
    await init_db()
    ts = datetime.utcnow().timestamp()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        inst_id = f"INST_INTRADAY_{ts}"

        # Seed 80 5m bars in MarketOHLCV
        base_time = datetime(2026, 1, 5, 9, 30, tzinfo=timezone.utc)
        async with AsyncSessionLocal() as session:
            for i in range(80):
                c = MarketOHLCV(
                    event_id=f"EVT_5M_{ts}_{i}",
                    feed_id="FEED_M02",
                    instrument_id=inst_id,
                    interval="5m",
                    open_price=Decimal("150.00") + Decimal(str(i * 0.1)),
                    high_price=Decimal("150.50") + Decimal(str(i * 0.1)),
                    low_price=Decimal("149.80") + Decimal(str(i * 0.1)),
                    close_price=Decimal("150.20") + Decimal(str(i * 0.1)),
                    volume=Decimal("1000.0"),
                    candle_start=base_time + timedelta(minutes=i * 5),
                    candle_end=base_time + timedelta(minutes=(i + 1) * 5),
                    source_provider="SIMULATOR",
                )
                session.add(c)
            await session.commit()

        # Call GET /market-risk/historical-volatility/intraday
        resp = await client.get(
            f"/api/v1/market-risk/historical-volatility/intraday?instrument_id={inst_id}&sampling_interval=5m"
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert data["instrument_id"] == inst_id
        assert data["sampling_interval"] == "5m"
        assert data["bars_evaluated"] == 80
        assert data["is_suitable"] is True
        assert data["status"] == "CALCULATED"
        assert Decimal(data["annualized_volatility"]) >= Decimal("0.0")
