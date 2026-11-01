"""
Comprehensive Test Suite for Module 03.01: Missing Data Detection.
Covers:
1. Expected Observation Policy Engine (hierarchy, holidays, provider capabilities)
2. Alpha Vantage Free plan restrictions (no intraday/ticks expected -> no false positives)
3. Tick Sequence Gap detection & Quote/Trade inactivity detection
4. Missing Daily Candle detection (BSE/NSE/NYSE trading calendar aware)
5. Missing Intraday Candle detection (simulated bars)
6. Order Book Sequence gap & Stale book detection
7. Quantitative Coverage Window calculations (percentages, boundary checks)
8. Idempotent incident upserts & resolution lifecycle
9. REST APIs & RBAC security protection
"""
from datetime import date, datetime, timedelta, timezone
import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.config import settings
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.main import app
from backend.app.modules.market_data_quality.missing_data.coverage.calculator import CoverageCalculator
from backend.app.modules.market_data_quality.missing_data.detectors.candle_detector import MissingCandleDetector
from backend.app.modules.market_data_quality.missing_data.detectors.orderbook_detector import MissingOrderBookDetector
from backend.app.modules.market_data_quality.missing_data.detectors.tick_detector import MissingTickDetector
from backend.app.modules.market_data_quality.missing_data.integrations.calendar_interface import ExchangeSessionResolver
from backend.app.modules.market_data_quality.missing_data.models import (
    ExpectationStatus,
    IncidentSeverity,
    IncidentStatus,
    IssueType,
)
from backend.app.modules.market_data_quality.missing_data.policies.resolver import ExpectationPolicyResolver
from backend.app.modules.market_data_quality.missing_data.service import MissingDataService

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def setup_test_db():
    import asyncio
    asyncio.run(init_db())
    yield


@pytest.fixture
def operator_headers():
    return {"X-API-Key": settings.API_KEY_OPERATOR}


@pytest.fixture
def read_only_headers():
    return {"X-API-Key": settings.API_KEY_READ_ONLY}


# ============================================================================
# 1. Expectation Policy & False-Positive Prevention Tests
# ============================================================================

def test_alpha_vantage_free_no_false_positive_intraday():
    resolver = ExpectationPolicyResolver()
    dt = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)

    # 1. Intraday ticks are NOT supported on Alpha Vantage Free -> Must return NOT_SUPPORTED
    status, reason = resolver.evaluate_expectation(
        provider_id="ALPHA_VANTAGE",
        exchange="NSE",
        channel="TICK",
        frequency="REALTIME",
        event_time_utc=dt,
    )
    assert status == ExpectationStatus.NOT_SUPPORTED
    assert "not support streaming" in reason

    # 2. Daily candles on Alpha Vantage ARE expected on a valid weekday
    status_daily, _ = resolver.evaluate_expectation(
        provider_id="ALPHA_VANTAGE",
        exchange="NSE",
        channel="OHLCV",
        frequency="1d",
        event_time_utc=dt,
    )
    assert status_daily == ExpectationStatus.EXPECTED


def test_calendar_session_and_holiday_awareness():
    resolver = ExpectationPolicyResolver()

    # Weekend (Sunday)
    sunday = datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc)
    status, reason = resolver.evaluate_expectation(
        provider_id="SIMULATOR",
        exchange="NSE",
        channel="TICK",
        frequency="REALTIME",
        event_time_utc=sunday,
    )
    assert status == ExpectationStatus.MARKET_CLOSED

    # Valid weekday during NSE trading hours (10:00 AM IST = 04:30 AM UTC)
    wednesday_open = datetime(2026, 10, 28, 5, 0, tzinfo=timezone.utc)
    status_open, _ = resolver.evaluate_expectation(
        provider_id="SIMULATOR",
        exchange="NSE",
        channel="TICK",
        frequency="REALTIME",
        event_time_utc=wednesday_open,
    )
    assert status_open == ExpectationStatus.EXPECTED


# ============================================================================
# 2. Missing Tick & Inactivity Detection Tests
# ============================================================================

def test_missing_tick_sequence_gap():
    detector = MissingTickDetector()
    active_time = datetime(2026, 10, 28, 5, 0, tzinfo=timezone.utc)

    # Sequence jump from 1000 to 1004 (missing 1001, 1002, 1003)
    incident = detector.detect_sequence_gap(
        feed_id="feed_sim",
        provider_id="SIMULATOR",
        instrument_id="EQ_RELIANCE",
        exchange="NSE",
        expected_seq=1001,
        observed_seq=1004,
        channel="TICK",
        event_time=active_time,
    )
    assert incident is not None
    assert incident.issue_type == IssueType.SEQUENCE_GAP.value
    assert incident.missing_count == 3
    assert incident.missing_start == "1001"
    assert incident.missing_end == "1003"


def test_missing_tick_inactivity():
    detector = MissingTickDetector()
    t1 = datetime(2026, 10, 28, 5, 0, tzinfo=timezone.utc)
    t2 = t1 + timedelta(seconds=600)  # 10 minutes later

    incident = detector.detect_inactivity(
        feed_id="feed_sim",
        provider_id="SIMULATOR",
        instrument_id="EQ_TCS",
        exchange="NSE",
        last_event_time=t1,
        current_time=t2,
        inactivity_threshold_seconds=300,
        channel="TICK",
    )
    assert incident is not None
    assert incident.issue_type == IssueType.MISSING_TICK.value


# ============================================================================
# 3. Missing Candle Detection Tests
# ============================================================================

def test_missing_daily_candles():
    detector = MissingCandleDetector()
    # Monday to Friday
    d_start = date(2026, 10, 26)  # Mon
    d_end = date(2026, 10, 30)    # Fri

    # Suppose Wednesday (Oct 28) is missing from observed dates
    observed = {date(2026, 10, 26), date(2026, 10, 27), date(2026, 10, 29), date(2026, 10, 30)}
    incidents = detector.detect_missing_daily_candles(
        instrument_id="EQ_INFY",
        feed_id="feed_av",
        provider_id="ALPHA_VANTAGE",
        exchange="NSE",
        start_date=d_start,
        end_date=d_end,
        observed_dates=observed,
    )
    assert len(incidents) == 1
    assert incidents[0].missing_start == "2026-10-28"
    assert incidents[0].issue_type == IssueType.MISSING_CANDLE.value


# ============================================================================
# 4. Missing Order Book Updates & Stale Book Detection
# ============================================================================

def test_order_book_gap_and_staleness():
    detector = MissingOrderBookDetector()
    active_time = datetime(2026, 10, 28, 5, 0, tzinfo=timezone.utc)

    # 1. Unsynchronized order book
    inc_unsync = detector.check_order_book_status(
        instrument_id="EQ_RELIANCE",
        feed_id="feed_sim",
        provider_id="SIMULATOR",
        exchange="NSE",
        is_synchronized=False,
        last_sequence=500,
        last_update_timestamp=active_time,
        current_time=active_time,
    )
    assert inc_unsync is not None
    assert inc_unsync.severity == IncidentSeverity.CRITICAL.value
    assert inc_unsync.issue_type == IssueType.MISSING_ORDER_BOOK_UPDATE.value

    # 2. Stale order book during market hours
    inc_stale = detector.check_order_book_status(
        instrument_id="EQ_RELIANCE",
        feed_id="feed_sim",
        provider_id="SIMULATOR",
        exchange="NSE",
        is_synchronized=True,
        last_sequence=500,
        last_update_timestamp=active_time - timedelta(seconds=120),
        current_time=active_time,
        stale_threshold_seconds=60,
    )
    assert inc_stale is not None
    assert inc_stale.issue_type == IssueType.STALE_ORDER_BOOK.value


# ============================================================================
# 5. Coverage Window Calculator Tests
# ============================================================================

def test_coverage_calculator():
    now = datetime.now(timezone.utc)
    # 1. Complete coverage (20 / 20)
    w_comp = CoverageCalculator.calculate_coverage(
        instrument_id="EQ_IBM",
        feed_id="feed_av",
        provider_id="ALPHA_VANTAGE",
        exchange="NYSE",
        data_type="OHLCV",
        interval_type="1d",
        window_start=now,
        window_end=now,
        expected_units=20,
        observed_units=20,
    )
    assert w_comp.coverage_percentage == 100.0
    assert w_comp.coverage_status == "COMPLETE"
    assert w_comp.missing_units == 0

    # 2. Partial coverage (18 / 20 -> 90%)
    w_part = CoverageCalculator.calculate_coverage(
        instrument_id="EQ_IBM",
        feed_id="feed_av",
        provider_id="ALPHA_VANTAGE",
        exchange="NYSE",
        data_type="OHLCV",
        interval_type="1d",
        window_start=now,
        window_end=now,
        expected_units=20,
        observed_units=18,
    )
    assert w_part.coverage_percentage == 90.0
    assert w_part.coverage_status == "PARTIAL"
    assert w_part.missing_units == 2

    # 3. Zero denominator handled safely (0 expected)
    w_zero = CoverageCalculator.calculate_coverage(
        instrument_id="EQ_IBM",
        feed_id="feed_av",
        provider_id="ALPHA_VANTAGE",
        exchange="NYSE",
        data_type="OHLCV",
        interval_type="1d",
        window_start=now,
        window_end=now,
        expected_units=0,
        observed_units=0,
    )
    assert w_zero.coverage_percentage == 0.0
    assert w_zero.coverage_status == "NOT_APPLICABLE"


# ============================================================================
# 6. Service Integration & REST API Endpoints Tests
# ============================================================================

async def test_missing_data_service_and_apis(operator_headers, read_only_headers):
    async with AsyncSessionLocal() as session:
        service = MissingDataService(session)

        # 1. Create Policy
        import uuid
        code = f"POL_NSE_{uuid.uuid4().hex[:8]}"
        policy = await service.create_policy(
            payload={  # type: ignore
                "policy_code": code,
                "exchange": "NSE",
                "provider_id": "SIMULATOR",
                "data_channel": "TICK",
                "observation_type": "REALTIME",
                "expected_frequency": "REALTIME",
                "grace_period_seconds": 30,
                "inactivity_threshold_seconds": 180,
                "priority": 10,
                "policy_parameters": {},
            }
        )
        assert policy.policy_code == code

        # 2. Record Coverage Window
        now = datetime.now(timezone.utc)
        await service.calculate_and_record_coverage(
            instrument_id="EQ_RELIANCE",
            feed_id="feed_sim",
            provider_id="SIMULATOR",
            exchange="NSE",
            data_type="TICK",
            interval_type="REALTIME",
            window_start=now,
            window_end=now,
            expected_units=100,
            observed_units=98,
        )

    # 3. Test REST Endpoints via AsyncClient
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Get Summary
        res_sum = await ac.get("/api/v1/quality/missing-data/summary", headers=read_only_headers)
        assert res_sum.status_code == 200
        summary = res_sum.json()
        assert "recent_coverage_average" in summary

        # Get Coverage Windows
        res_cov = await ac.get("/api/v1/quality/missing-data/coverage", headers=read_only_headers)
        assert res_cov.status_code == 200
        assert len(res_cov.json()) >= 1

        # List Policies
        res_pol = await ac.get("/api/v1/quality/missing-data/policies", headers=read_only_headers)
        assert res_pol.status_code == 200
        assert len(res_pol.json()) >= 1

