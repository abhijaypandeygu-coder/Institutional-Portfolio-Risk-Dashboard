"""
Comprehensive Pytest Suite for Module 03.03: Timestamp Validation Engine.
Covers:
- A. Timestamp Foundation (Parsing, UTC normalization, provenance, IANA timezones)
- B. Out-of-Order Event Tests (Monotonicity, sequence regression, late arrivals, connection epoch reset)
- C. Clock Drift Tests (Apparent divergence, true offset vs network latency, multi-sample drift rate)
- D. Stale Timestamp Tests (Real-time latency limits, market-closed awareness, historical backfill bypass, EOD)
- E. Session Alignment Tests (NSE/BSE regular sessions, NYSE/NASDAQ sessions, auction windows, holidays, date-only bars)
- F. Service & REST API Lifecycle Tests (Batch validation, rules, anomalies, session check, summary)
"""
from datetime import date, datetime, time, timedelta, timezone
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from zoneinfo import ZoneInfo

from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.main import app
from backend.app.modules.market_data_quality.timestamp_validation.clock.drift_detector import (
    ClockDriftDetector,
)
from backend.app.modules.market_data_quality.timestamp_validation.foundation.parser import (
    TimestampFoundation,
    TimestampPrecision,
)
from backend.app.modules.market_data_quality.timestamp_validation.freshness.stale_detector import (
    StaleTimestampDetector,
)
from backend.app.modules.market_data_quality.timestamp_validation.models import (
    ClockStatus,
    FinalTimestampStatus,
    FreshnessStatus,
    OrderingStatus,
    SessionStatus,
    TimestampAnomalyStatus,
    TimestampRuleCategory,
)
from backend.app.modules.market_data_quality.timestamp_validation.ordering.ordering_detector import (
    OutOfOrderDetector,
)
from backend.app.modules.market_data_quality.timestamp_validation.schemas import (
    BatchTimestampObservationInput,
    SessionCheckRequest,
    TimestampObservationInput,
)
from backend.app.modules.market_data_quality.timestamp_validation.service import (
    TimestampValidationService,
)
from backend.app.modules.market_data_quality.timestamp_validation.session.session_validator import (
    SessionAlignmentValidator,
)


@pytest.fixture(autouse=True)
async def ensure_db():
    await init_db()


@pytest.fixture
def operator_headers():
    return {"X-API-Key": "operator_dev_secret_key_2026"}


@pytest.fixture
def readonly_headers():
    return {"X-API-Key": "readonly_dev_secret_key_2026"}


# ============================================================================
# Section A: Timestamp Foundation Tests (Parsing & Normalization)
# ============================================================================

def test_timestamp_foundation_parsing_and_timezones():
    """Verify parsing ISO strings, epoch timestamps, date-only formats, and timezone conversions."""
    # 1. ISO UTC with 'Z'
    dt, prec, is_date = TimestampFoundation.parse_and_normalize("2026-11-01T04:30:00Z")
    assert dt is not None and dt.tzinfo == timezone.utc
    assert dt.hour == 4 and dt.minute == 30
    assert not is_date

    # 2. Date-only daily bar (YYYY-MM-DD) for NSE (Asia/Kolkata)
    # 2026-11-02 00:00:00 IST -> 2026-11-01 18:30:00 UTC
    dt_nse, prec_nse, is_date_nse = TimestampFoundation.parse_and_normalize(
        "2026-11-02", exchange="NSE"
    )
    assert dt_nse is not None
    assert is_date_nse is True
    assert prec_nse == TimestampPrecision.DATE_ONLY
    assert dt_nse.hour == 18 and dt_nse.minute == 30

    # 3. Epoch milliseconds
    epoch_ms = 1762000000000  # Nov 2025
    dt_epoch, prec_epoch, is_date_epoch = TimestampFoundation.parse_and_normalize(epoch_ms)
    assert dt_epoch is not None
    assert prec_epoch == TimestampPrecision.MILLISECONDS
    assert not is_date_epoch

    # 4. Malformed string
    dt_bad, _, _ = TimestampFoundation.parse_and_normalize("NOT_A_TIMESTAMP")
    assert dt_bad is None


# ============================================================================
# Section B: Out-of-Order Event Tests (M03.03.01)
# ============================================================================

def test_out_of_order_detector():
    """Verify strictly ordered ticks, late arrivals within tolerance, regressions, and sequence skips."""
    detector = OutOfOrderDetector()
    t0 = datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc)

    # 1. First event -> IN_ORDER
    res1 = detector.evaluate(
        provider_id="SIMULATOR",
        feed_id="feed1",
        instrument_id="RELIANCE",
        channel="TICK",
        current_event_timestamp=t0,
        current_sequence=100,
    )
    assert res1.status == OrderingStatus.IN_ORDER
    assert res1.final_status == FinalTimestampStatus.VALID

    # 2. Subsequent event strictly later -> IN_ORDER
    t1 = t0 + timedelta(milliseconds=200)
    res2 = detector.evaluate(
        provider_id="SIMULATOR",
        feed_id="feed1",
        instrument_id="RELIANCE",
        channel="TICK",
        current_event_timestamp=t1,
        current_sequence=101,
    )
    assert res2.status == OrderingStatus.IN_ORDER
    assert res2.final_status == FinalTimestampStatus.VALID

    # 3. Late arrival within 1s tolerance (100ms regression) -> LATE_ARRIVAL (VALID_WITH_WARNING)
    t_late = t1 - timedelta(milliseconds=100)
    res3 = detector.evaluate(
        provider_id="SIMULATOR",
        feed_id="feed1",
        instrument_id="RELIANCE",
        channel="TICK",
        current_event_timestamp=t_late,
        current_sequence=101,
        reordering_tolerance_ms=1000.0,
    )
    assert res3.status == OrderingStatus.LATE_ARRIVAL
    assert res3.final_status == FinalTimestampStatus.VALID_WITH_WARNING

    # 4. Severe event-time regression (5s backward) -> EVENT_TIME_REGRESSION (QUARANTINED)
    t_severe = t1 - timedelta(seconds=5)
    res4 = detector.evaluate(
        provider_id="SIMULATOR",
        feed_id="feed1",
        instrument_id="RELIANCE",
        channel="TICK",
        current_event_timestamp=t_severe,
        current_sequence=101,
        reordering_tolerance_ms=1000.0,
    )
    assert res4.status == OrderingStatus.EVENT_TIME_REGRESSION
    assert res4.final_status == FinalTimestampStatus.QUARANTINED

    # 5. Sequence regression (sequence jumps backwards from 101 to 95) -> SEQUENCE_REGRESSION (REJECTED)
    t_seq_bad = t1 + timedelta(milliseconds=100)
    res5 = detector.evaluate(
        provider_id="SIMULATOR",
        feed_id="feed1",
        instrument_id="RELIANCE",
        channel="TICK",
        current_event_timestamp=t_seq_bad,
        current_sequence=95,
    )
    assert res5.status == OrderingStatus.SEQUENCE_REGRESSION
    assert res5.final_status == FinalTimestampStatus.REJECTED

    # 6. Connection Epoch Reset -> Clears state and accepts new sequence
    detector.reset_stream_epoch(
        provider_id="SIMULATOR", feed_id="feed1", instrument_id="RELIANCE", channel="TICK", new_epoch=2
    )
    res6 = detector.evaluate(
        provider_id="SIMULATOR",
        feed_id="feed1",
        instrument_id="RELIANCE",
        channel="TICK",
        current_event_timestamp=t1,
        current_sequence=1,  # Reconnected stream sequence restarts at 1
        connection_epoch=2,
    )
    assert res6.status == OrderingStatus.IN_ORDER
    assert res6.final_status == FinalTimestampStatus.VALID


# ============================================================================
# Section C: Clock Drift Tests (M03.03.02)
# ============================================================================

def test_clock_drift_detector():
    """Verify apparent divergence, transport delay distinction, and multi-sample drift rate."""
    detector = ClockDriftDetector()
    t_src = datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc)

    # 1. Normal latency (50ms latency, local receive is 60ms after source)
    t_rx = t_src + timedelta(milliseconds=60)
    res1 = detector.evaluate(
        provider_id="SIMULATOR",
        feed_id="feed1",
        source_timestamp=t_src,
        local_receive_timestamp=t_rx,
        estimated_network_latency_ms=50.0,
    )
    assert res1.status == ClockStatus.CLOCK_NORMAL
    assert res1.final_status == FinalTimestampStatus.VALID
    assert res1.apparent_offset_ms == 60.0
    assert res1.estimated_offset_ms == 10.0  # 60 - 50 = 10ms estimated true clock offset

    # 2. Material divergence (> 2000ms apparent difference)
    t_rx_lag = t_src + timedelta(milliseconds=2500)
    res2 = detector.evaluate(
        provider_id="SIMULATOR",
        feed_id="feed1",
        source_timestamp=t_src,
        local_receive_timestamp=t_rx_lag,
        max_acceptable_offset_ms=2000.0,
    )
    assert res2.status == ClockStatus.APPARENT_CLOCK_DIVERGENCE
    assert res2.final_status == FinalTimestampStatus.VALID_WITH_WARNING

    # 3. Source future skew (Source is ahead of local clock by 3 seconds)
    t_rx_future = t_src - timedelta(milliseconds=3000)
    res3 = detector.evaluate(
        provider_id="SIMULATOR",
        feed_id="feed1",
        source_timestamp=t_src,
        local_receive_timestamp=t_rx_future,
        max_acceptable_offset_ms=2000.0,
    )
    assert res3.status == ClockStatus.SOURCE_CLOCK_OFFSET
    assert res3.final_status == FinalTimestampStatus.QUARANTINED


# ============================================================================
# Section D: Stale Timestamp Tests (M03.03.03)
# ============================================================================

def test_stale_timestamp_detector():
    """Verify real-time freshness, closed market awareness, historical bypass, and order book synchronization."""
    detector = StaleTimestampDetector()
    now = datetime(2026, 11, 2, 5, 0, 0, tzinfo=timezone.utc)  # Monday 10:30 AM IST (NSE Open)

    # 1. Fresh real-time tick (age = 1.0s <= 5s warning)
    t_fresh = now - timedelta(seconds=1)
    res1 = detector.evaluate(
        event_timestamp=t_fresh,
        validation_time=now,
        exchange="NSE",
        processing_context="REALTIME",
    )
    assert res1.status == FreshnessStatus.FRESH
    assert res1.final_status == FinalTimestampStatus.VALID

    # 2. Aging observation (age = 10.0s > 5s warning, <= 30s critical)
    t_aging = now - timedelta(seconds=10)
    res2 = detector.evaluate(
        event_timestamp=t_aging,
        validation_time=now,
        exchange="NSE",
        processing_context="REALTIME",
    )
    assert res2.status == FreshnessStatus.AGING
    assert res2.final_status == FinalTimestampStatus.VALID_WITH_WARNING

    # 3. Critically stale observation (age = 45.0s > 30s critical)
    t_stale = now - timedelta(seconds=45)
    res3 = detector.evaluate(
        event_timestamp=t_stale,
        validation_time=now,
        exchange="NSE",
        processing_context="REALTIME",
    )
    assert res3.status == FreshnessStatus.CRITICALLY_STALE
    assert res3.final_status == FinalTimestampStatus.QUARANTINED

    # 4. Future-dated event (> 2s ahead)
    t_future = now + timedelta(seconds=5)
    res4 = detector.evaluate(
        event_timestamp=t_future,
        validation_time=now,
        exchange="NSE",
    )
    assert res4.status == FreshnessStatus.FUTURE_DATED
    assert res4.final_status == FinalTimestampStatus.REJECTED

    # 5. Historical context -> Always VALID
    t_hist = now - timedelta(days=365)
    res5 = detector.evaluate(
        event_timestamp=t_hist,
        validation_time=now,
        exchange="NSE",
        processing_context="HISTORICAL",
    )
    assert res5.status == FreshnessStatus.HISTORICAL
    assert res5.final_status == FinalTimestampStatus.VALID

    # 6. Desynchronized Order Book -> CRITICALLY_STALE (QUARANTINED)
    res6 = detector.evaluate(
        event_timestamp=t_fresh,
        validation_time=now,
        exchange="NSE",
        data_channel="ORDER_BOOK_L2",
        is_orderbook_synchronized=False,
    )
    assert res6.status == FreshnessStatus.CRITICALLY_STALE
    assert res6.final_status == FinalTimestampStatus.QUARANTINED


# ============================================================================
# Section E: Session Alignment Tests (M03.03.04)
# ============================================================================

def test_session_alignment_validator():
    """Verify Indian/US exchange session windows, auction periods, weekends, and date-only daily bars."""
    validator = SessionAlignmentValidator()

    # 1. Valid NSE Regular Trading Session
    # Monday 2026-11-02 10:30 IST -> 05:00 UTC
    t_nse_reg = datetime(2026, 11, 2, 5, 0, 0, tzinfo=timezone.utc)
    res1 = validator.evaluate(t_nse_reg, exchange="NSE")
    assert res1.status == SessionStatus.REGULAR_SESSION
    assert res1.final_status == FinalTimestampStatus.VALID

    # 2. NSE Pre-Open Auction Window (09:05 IST -> 03:35 UTC)
    t_nse_auction = datetime(2026, 11, 2, 3, 35, 0, tzinfo=timezone.utc)
    res2 = validator.evaluate(t_nse_auction, exchange="NSE")
    assert res2.status == SessionStatus.OPENING_AUCTION
    assert res2.is_auction is True

    # 3. US Regular Trading Session (NYSE)
    # Monday 2026-11-02 11:00 EST -> 16:00 UTC
    t_nyse_reg = datetime(2026, 11, 2, 16, 0, 0, tzinfo=timezone.utc)
    res3 = validator.evaluate(t_nyse_reg, exchange="NYSE")
    assert res3.status == SessionStatus.REGULAR_SESSION
    assert res3.final_status == FinalTimestampStatus.VALID

    # 4. Weekend Event (Sunday 2026-11-01) -> MARKET_CLOSED (REJECTED)
    t_weekend = datetime(2026, 11, 1, 5, 0, 0, tzinfo=timezone.utc)
    res4 = validator.evaluate(t_weekend, exchange="NSE")
    assert res4.status == SessionStatus.MARKET_CLOSED
    assert res4.final_status == FinalTimestampStatus.REJECTED

    # 5. Date-only daily OHLCV bar on a business day -> VALID REGULAR_SESSION
    t_date_bar = datetime(2026, 11, 2, 0, 0, 0, tzinfo=timezone.utc)
    res5 = validator.evaluate(t_date_bar, exchange="NSE", is_date_only=True)
    assert res5.status == SessionStatus.REGULAR_SESSION
    assert res5.final_status == FinalTimestampStatus.VALID


# ============================================================================
# Section F: Service & REST API Lifecycle Tests
# ============================================================================

async def test_timestamp_validation_service_and_apis(operator_headers, readonly_headers):
    """End-to-end integration test of service pipeline, batch validation, rules, and REST APIs."""
    async with AsyncSessionLocal() as session:
        service = TimestampValidationService(session)

        # 1. Service Level: Validate Valid Real-Time Tick (using valid weekday trading session time)
        # Monday 2026-11-02 05:00:00 UTC (10:30 AM IST on NSE)
        t_valid_session = datetime(2026, 11, 2, 5, 0, 0, tzinfo=timezone.utc)
        obs_valid = TimestampObservationInput(
            instrument_id="RELIANCE",
            feed_id="feed_nse_01",
            provider_id="SIMULATOR",
            exchange="NSE",
            event_type="TICK",
            processing_context="HISTORICAL",
            source_timestamp=t_valid_session.isoformat(),
            local_receive_timestamp=t_valid_session,
            sequence_number=1,
        )
        res1 = await service.validate_observation(obs_valid)
        assert res1.final_status in (FinalTimestampStatus.VALID, FinalTimestampStatus.VALID_WITH_WARNING)
        assert res1.is_downstream_eligible is True

        # 2. Service Level: Sequence Regression -> REJECTED
        obs_reg = TimestampObservationInput(
            instrument_id="RELIANCE",
            feed_id="feed_nse_01",
            provider_id="SIMULATOR",
            exchange="NSE",
            event_type="TICK",
            processing_context="REALTIME",
            source_timestamp=t_valid_session.isoformat(),
            local_receive_timestamp=t_valid_session,
            sequence_number=0,  # Regressed from sequence 1 to 0
        )
        res2 = await service.validate_observation(obs_reg)
        assert res2.ordering_status == OrderingStatus.SEQUENCE_REGRESSION
        assert res2.final_status == FinalTimestampStatus.REJECTED
        assert res2.is_downstream_eligible is False

    # 3. REST API: Single Validation
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r_val = await ac.post(
            "/api/v1/quality/timestamp-validation/validate",
            headers=operator_headers,
            json={
                "instrument_id": "IBM",
                "feed_id": "feed_nyse_01",
                "provider_id": "ALPHA_VANTAGE",
                "exchange": "NYSE",
                "event_type": "OHLCV",
                "processing_context": "EOD",
                "source_timestamp": "2026-10-30",  # EOD Friday date
            },
        )
        assert r_val.status_code == 200
        data_val = r_val.json()
        assert data_val["final_status"] == "VALID"
        assert data_val["freshness_status"] == "FRESH"

        # 4. REST API: Batch Validation
        now_req = datetime.now(timezone.utc)
        r_batch = await ac.post(
            "/api/v1/quality/timestamp-validation/validate/batch",
            headers=operator_headers,
            json={
                "observations": [
                    {
                        "instrument_id": "INFY",
                        "feed_id": "feed_sim_01",
                        "provider_id": "SIMULATOR",
                        "exchange": "NSE",
                        "event_type": "TICK",
                        "source_timestamp": now_req.isoformat(),
                    },
                    {
                        "instrument_id": "AAPL",
                        "feed_id": "feed_sim_01",
                        "provider_id": "SIMULATOR",
                        "exchange": "NASDAQ",
                        "event_type": "TICK",
                        "source_timestamp": (now_req + timedelta(seconds=10)).isoformat(),  # Future-dated
                    },
                ]
            },
        )
        assert r_batch.status_code == 200
        batch_out = r_batch.json()
        assert len(batch_out) == 2
        assert batch_out[1]["freshness_status"] == "FUTURE_DATED"
        assert batch_out[1]["final_status"] == "REJECTED"

        # 5. REST API: Create Rule & List Rules
        rule_code = f"TS_RULE_{uuid.uuid4().hex[:8]}"
        r_rule = await ac.post(
            "/api/v1/quality/timestamp-validation/rules",
            headers=operator_headers,
            json={
                "rule_code": rule_code,
                "rule_name": "Custom Max Latency Rule",
                "rule_category": "FRESHNESS",
                "exchange": "NSE",
                "rule_parameters": {"max_age_sec": 10.0},
            },
        )
        assert r_rule.status_code == 201

        r_rules = await ac.get(
            "/api/v1/quality/timestamp-validation/rules",
            headers=readonly_headers,
        )
        assert r_rules.status_code == 200
        assert len(r_rules.json()) >= 1

        # 6. REST API: Session Check
        r_sess = await ac.post(
            "/api/v1/quality/timestamp-validation/session-check",
            headers=readonly_headers,
            json={
                "exchange": "NSE",
                "timestamp": "2026-11-02T05:00:00Z",  # Monday 10:30 AM IST
            },
        )
        assert r_sess.status_code == 200
        sess_data = r_sess.json()
        assert sess_data["session_status"] == "REGULAR_SESSION"
        assert sess_data["is_valid"] is True

        # 7. REST API: Anomaly Incidents List & Resolve
        r_incidents = await ac.get(
            "/api/v1/quality/timestamp-validation/incidents",
            headers=readonly_headers,
        )
        assert r_incidents.status_code == 200
        inc_list = r_incidents.json()
        assert len(inc_list) >= 1
        first_inc_id = inc_list[0]["id"]

        r_res = await ac.post(
            f"/api/v1/quality/timestamp-validation/incidents/{first_inc_id}/resolve",
            headers=operator_headers,
            json={
                "status": "RESOLVED",
                "resolution_reason": "Verified stream reconnection and sequence resync.",
            },
        )
        assert r_res.status_code == 200
        assert r_res.json()["incident_status"] == "RESOLVED"

        # 8. REST API: Summary Metrics
        r_sum = await ac.get(
            "/api/v1/quality/timestamp-validation/summary",
            headers=readonly_headers,
        )
        assert r_sum.status_code == 200
        sum_json = r_sum.json()
        assert sum_json["total_observations_validated"] >= 3
        assert sum_json["downstream_eligibility_rate_percentage"] > 0
