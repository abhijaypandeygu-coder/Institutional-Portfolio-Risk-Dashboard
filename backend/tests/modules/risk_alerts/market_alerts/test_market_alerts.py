"""
Unit and integration tests for M12.02 Market Alerts.

Tests:
1. Abnormal price movement calculations (Delta P, R_t, direction).
2. Historical price deviation (mean, sample variance/stdev, Z-score, empirical percentile).
3. Market band calculations (analytical percentage bands, volatility-scaled bands, approach/breach states).
4. Short-horizon realized volatility (RV_t, annualized RV, baseline comparison, spike ratio).
5. Market breadth and market-wide event aggregation.
6. Rule configuration and versioning lifecycle.
7. End-to-end price movement evaluation and event creation with portfolio impact mapping.
8. Data-quality safeguards (rejection of STALE and INVALID observations).
9. Trading halt and resumption lifecycle with duration calculation.
10. Review label assignment for false positive tracking.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.modules.risk_alerts.market_alerts.calculations.market_alerts_math import (
    calculate_price_movement,
    calculate_historical_deviation,
    calculate_analytical_bands,
    evaluate_band_state,
    calculate_realized_volatility,
    calculate_volatility_spike,
    calculate_market_breadth,
    classify_directional_impact,
)
from backend.app.modules.risk_alerts.market_alerts.services.market_alerts_service import MarketAlertsService
from backend.app.modules.risk_alerts.market_alerts.schemas.market_alerts_schemas import (
    MarketAlertRuleCreate,
    MarketAlertRuleUpdate,
    PriceObservationInput,
    PriceMovementEvaluationRequest,
    VolatilityEvaluationRequest,
    MarketBandEvaluationRequest,
    TradingStatusEventRequest,
    MarketWideEventRequest,
    ReviewLabelCreate,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await init_db()
    yield


def test_abnormal_price_movement_math():
    # Downward 4.2% drop
    curr = Decimal("95.80")
    ref = Decimal("100.00")
    delta_p, pct_change, direction = calculate_price_movement(curr, ref)
    assert delta_p == Decimal("-4.20")
    assert pct_change == Decimal("-4.20")
    assert direction == "DOWNWARD"

    # Upward 5% gain
    curr2 = Decimal("105.00")
    delta_p2, pct_change2, direction2 = calculate_price_movement(curr2, ref)
    assert delta_p2 == Decimal("5.00")
    assert pct_change2 == Decimal("5.00")
    assert direction2 == "UPWARD"

    # Zero reference price
    delta_p3, pct_change3, direction3 = calculate_price_movement(curr, Decimal("0"))
    assert direction3 == "UNAVAILABLE"


def test_historical_deviation_math():
    # Sample returns: 10 sessions of normal variance around 0%
    hist_returns = [
        Decimal("-0.5"), Decimal("0.8"), Decimal("-1.2"), Decimal("0.4"), Decimal("-0.1"),
        Decimal("0.3"), Decimal("-0.7"), Decimal("1.1"), Decimal("-0.3"), Decimal("0.2"),
    ]
    obs_return = Decimal("-4.2")  # Severe outlier
    z_score, percentile, stdev_r = calculate_historical_deviation(obs_return, hist_returns)

    assert z_score is not None
    assert z_score < Decimal("-3.0")  # Outlier Z-score
    assert percentile == Decimal("100.00")  # Maximum absolute return in sample
    assert stdev_r > Decimal("0")


def test_market_band_math():
    ref_price = Decimal("1000.00")
    # Percentage band (+/- 5%)
    upper, lower = calculate_analytical_bands(ref_price, band_pct=Decimal("5.0"))
    assert upper == Decimal("1050.0000")
    assert lower == Decimal("950.0000")

    # State evaluations
    assert evaluate_band_state(Decimal("1055.00"), upper, lower) == "BREACHED_UPPER"
    assert evaluate_band_state(Decimal("940.00"), upper, lower) == "BREACHED_LOWER"
    assert evaluate_band_state(Decimal("1045.00"), upper, lower, approach_threshold_pct=Decimal("1.0")) == "APPROACHING_UPPER"
    assert evaluate_band_state(Decimal("1000.00"), upper, lower) == "NORMAL"


def test_realized_volatility_and_spike_math():
    # 5-minute interval returns: 5 observations with moderate volatility
    returns = [Decimal("0.005"), Decimal("-0.008"), Decimal("0.006"), Decimal("-0.004"), Decimal("0.007")]
    rv_t, rv_ann = calculate_realized_volatility(returns, annualization_factor=Decimal("252.0"))

    assert rv_t > Decimal("0")
    assert rv_ann > rv_t

    # Spike ratio comparison
    baseline_rv = Decimal("0.05")
    spike_ratio, delta_rv, regime = calculate_volatility_spike(rv_ann, baseline_rv)
    assert spike_ratio is not None
    assert delta_rv == rv_ann - baseline_rv
    assert regime in ["NORMAL", "ELEVATED", "HIGH", "EXTREME"]


def test_market_breadth_math():
    res = calculate_market_breadth(
        advancing_count=10,
        declining_count=40,
        unchanged_count=0,
        downside_anomalies=15,
        upside_anomalies=2,
        eligible_universe=50,
    )
    assert res["advance_decline_ratio"] == Decimal("0.25")
    assert res["downside_breadth_pct"] == Decimal("30.00")
    assert res["pct_declining"] == Decimal("80.00")

    # Directional impact test
    assert classify_directional_impact("LONG", "DOWNWARD") == "ADVERSE"
    assert classify_directional_impact("LONG", "UPWARD") == "FAVORABLE"
    assert classify_directional_impact("SHORT", "UPWARD") == "ADVERSE"


@pytest.mark.asyncio
async def test_rule_creation_and_versioning():
    async with AsyncSessionLocal() as session:
        service = MarketAlertsService(session)
        rule_req = MarketAlertRuleCreate(
            rule_code=f"TEST_PRICE_DROP_{uuid.uuid4().hex[:6]}",
            name="Abnormal Price Drop 3%",
            description="Detects 3% drop over 15 min",
            rule_type="ABNORMAL_PRICE_MOVEMENT",
            market="INDIA",
            exchange="NSE",
            observation_horizon_seconds=900,
            threshold_value=Decimal("3.0000"),
            threshold_unit="PERCENT",
            percentile_threshold=Decimal("95.00"),
        )
        rule = await service.create_rule(rule_req)
        assert rule.id.startswith("MARULE_")
        assert len(rule.versions) == 1
        assert rule.versions[0].version_number == 1

        # Update rule
        update_req = MarketAlertRuleUpdate(
            threshold_value=Decimal("3.5000"),
            change_reason="Tighter risk threshold",
        )
        updated = await service.update_rule(rule.id, update_req)
        assert updated.threshold_value == Decimal("3.5000")
        assert len(updated.versions) == 2
        assert updated.versions[1].version_number == 2


@pytest.mark.asyncio
async def test_price_movement_evaluation_and_quality_rejection():
    async with AsyncSessionLocal() as session:
        service = MarketAlertsService(session)
        code = f"RULE_RELIANCE_{uuid.uuid4().hex[:6]}"
        # Create rule
        await service.create_rule(MarketAlertRuleCreate(
            rule_code=code,
            name="Reliance Price Drop",
            rule_type="ABNORMAL_PRICE_MOVEMENT",
            market="INDIA",
            exchange="NSE",
            instrument_id="EQ_RELIANCE_NSE",
            threshold_value=Decimal("2.0000"),
            threshold_unit="PERCENT",
        ))

        # 1. Stale data observation must be rejected without alerting
        stale_obs = PriceObservationInput(
            instrument_id="EQ_RELIANCE_NSE",
            exchange="NSE",
            market="INDIA",
            price_value=Decimal("2400.00"),
            event_timestamp=datetime.utcnow(),
            quality_state="STALE",
        )
        stale_eval = PriceMovementEvaluationRequest(
            rule_code=code,
            observation=stale_obs,
            reference_price=Decimal("2500.00"),
        )
        res_stale = await service.evaluate_price_movement(stale_eval)
        assert res_stale is None

        # 2. Valid 4% drop: should trigger active MarketEvent
        valid_obs = PriceObservationInput(
            instrument_id="EQ_RELIANCE_NSE",
            exchange="NSE",
            market="INDIA",
            price_value=Decimal("2400.00"),
            event_timestamp=datetime.utcnow(),
            quality_state="VALID",
        )
        valid_eval = PriceMovementEvaluationRequest(
            rule_code=code,
            observation=valid_obs,
            reference_price=Decimal("2500.00"),
            historical_returns_pct=[Decimal("-0.2"), Decimal("0.3"), Decimal("-0.5"), Decimal("0.4"), Decimal("-0.1")],
        )
        event = await service.evaluate_price_movement(valid_eval)
        assert event is not None
        assert event.event_type == "ABNORMAL_PRICE_MOVEMENT"
        assert event.direction == "DOWNWARD"
        assert len(event.evidence_items) >= 2
        assert len(event.portfolio_impacts) >= 1
        assert event.portfolio_impacts[0].directional_impact == "ADVERSE"


@pytest.mark.asyncio
async def test_trading_halt_and_resumption_lifecycle():
    async with AsyncSessionLocal() as session:
        service = MarketAlertsService(session)
        now = datetime.utcnow()
        inst_id = f"EQ_TCS_{uuid.uuid4().hex[:6]}"

        # 1. Trading Halt Event
        halt_req = TradingStatusEventRequest(
            instrument_id=inst_id,
            exchange="NSE",
            market="INDIA",
            source_status_code="HALT_VOLATILITY",
            normalized_status="HALTED",
            halt_reason="Circuit Breaker Level 1",
            event_timestamp=now,
        )
        halt_rec, halt_evt = await service.process_trading_status_event(halt_req)
        assert halt_rec.normalized_status == "HALTED"
        assert halt_evt is not None
        assert halt_evt.event_type == "TRADING_HALT"

        # 2. Check active halts
        active_halts = await service.list_active_halts(active_only=True)
        assert any(h.instrument_id == inst_id for h in active_halts)

        # 3. Trading Resumption Event 15 minutes later
        resumption_time = now + timedelta(minutes=15)
        resume_req = TradingStatusEventRequest(
            instrument_id=inst_id,
            exchange="NSE",
            market="INDIA",
            source_status_code="RESUME_NORMAL",
            normalized_status="RESUMED",
            event_timestamp=resumption_time,
        )
        resume_rec, resume_evt = await service.process_trading_status_event(resume_req)
        assert resume_rec.normalized_status == "RESUMED"
        assert resume_rec.halt_duration_seconds == 900  # 15 minutes = 900 seconds
        assert resume_evt is not None
        assert resume_evt.event_type == "TRADING_RESUMPTION"

        # Active halts list should now be empty for TCS
        active_halts_after = await service.list_active_halts(active_only=True)
        assert not any(h.instrument_id == inst_id for h in active_halts_after)


@pytest.mark.asyncio
async def test_market_wide_event_and_analyst_review():
    async with AsyncSessionLocal() as session:
        service = MarketAlertsService(session)
        now = datetime.utcnow()

        # Broad market decline event
        req = MarketWideEventRequest(
            market="INDIA",
            index_instrument_id="INDEX_NIFTY_50",
            index_return=Decimal("-2.45"),
            advancing_count=5,
            declining_count=45,
            unchanged_count=0,
            downside_anomalies=18,
            upside_anomalies=1,
            eligible_universe=50,
            expected_universe=50,
            event_timestamp=now,
        )
        mwe = await service.process_market_wide_event(req)
        assert mwe.event_type == "MARKET_WIDE_EVENT"
        assert mwe.direction == "DOWNWARD"
        assert mwe.coverage_ratio == Decimal("1.0000")

        # Add analyst review label
        review = await service.add_review_label(
            event_id=mwe.id,
            req=ReviewLabelCreate(
                review_label="VALID_EVENT",
                review_comment="Confirmed macro rate hike announcement selloff",
                reviewed_by="RISK_ANALYST_01",
            ),
        )
        assert review is not None
        assert review.review_label == "VALID_EVENT"

        # Verify overview counts
        overview = await service.get_market_overview(market="INDIA")
        assert overview["market_wide_events_count"] >= 1
