"""
Comprehensive Pytest Suite for M03.05 - Duplicate Detection.
Covers:
- Section A: Duplicate Trade Detection (provider trade ID replay, exchange trade ID replay, sequence replay, identical legitimate trades preserved, identity conflicts).
- Section B: Repeated Market Event Detection (quote replays, order book snapshot/delta replays, OHLCV bar deduplication).
- Section C: Idempotent Ingestion & Concurrency (first accepted, replay returns canonical ID, concurrent workers).
- Section D: Duplicate Audit & Aggregates (receipts, duplicate rate, prevented volume & turnover calculations).
- Section E: REST API Verification.
"""

import uuid
import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.modules.market_data_quality.duplicate_detection.service import (
    DuplicateDetectionService,
)
from backend.app.modules.market_data_quality.duplicate_detection.schemas import (
    EventDetectionInput,
    DuplicateDetectionRuleCreate,
)
from backend.app.modules.market_data_quality.duplicate_detection.audit.repository import (
    DuplicateRepository,
)


@pytest.fixture(autouse=True)
async def setup_database():
    await init_db()


@pytest.fixture
def auth_headers():
    return {"X-API-Key": "operator_dev_secret_key_2026"}


@pytest.fixture
def admin_headers():
    return {"X-API-Key": "admin_dev_secret_key_2026"}


# ============================================================================
# Section A: Duplicate Trade Tests (M03.05.01)
# ============================================================================

@pytest.mark.asyncio
async def test_duplicate_trade_id_and_legitimate_identical_trades():
    """
    1. Same provider trade ID replayed -> DUPLICATE_EVENT, same canonical ID.
    2. Two legitimate trades with identical price, quantity, and timestamp but different trade IDs -> BOTH ACCEPTED!
    """
    async with AsyncSessionLocal() as session:
        t_time = datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc)
        rand_id = uuid.uuid4().hex[:6]

        # Event 1: Initial trade
        trade_1 = EventDetectionInput(
            provider_id="SIMULATOR",
            feed_id="SIM_TRADE_FEED",
            instrument_id=f"RELIANCE_{rand_id}",
            exchange="NSE",
            event_type="TRADE",
            provider_event_id=f"TRD_1001_{rand_id}",
            event_timestamp=t_time,
            price=Decimal("2950.00"),
            quantity=Decimal("100"),
            side="BID",
        )
        res_1 = await DuplicateDetectionService.process_market_event(session, trade_1)
        assert res_1.classification == "NEW_EVENT"
        assert res_1.is_new is True
        canonical_id_1 = res_1.canonical_event_id

        # Replay Event 1
        res_replay = await DuplicateDetectionService.process_market_event(session, trade_1)
        assert res_replay.classification == "DUPLICATE_EVENT"
        assert res_replay.is_duplicate is True
        assert res_replay.canonical_event_id == canonical_id_1  # References original
        assert res_replay.existing_delivery_count == 2

        # Event 2: Distinct trade with IDENTICAL price, quantity, and timestamp but different Trade ID
        trade_2 = EventDetectionInput(
            provider_id="SIMULATOR",
            feed_id="SIM_TRADE_FEED",
            instrument_id=f"RELIANCE_{rand_id}",
            exchange="NSE",
            event_type="TRADE",
            provider_event_id=f"TRD_1002_{rand_id}",  # Distinct ID!
            event_timestamp=t_time,
            price=Decimal("2950.00"),
            quantity=Decimal("100"),
            side="BID",
        )
        res_2 = await DuplicateDetectionService.process_market_event(session, trade_2)
        assert res_2.classification == "NEW_EVENT"  # Must NOT be falsely dropped as duplicate
        assert res_2.is_new is True
        assert res_2.canonical_event_id != canonical_id_1


@pytest.mark.asyncio
async def test_trade_identity_conflict():
    """
    Same trade ID arriving with different price or quantity -> IDENTITY_CONFLICT.
    """
    async with AsyncSessionLocal() as session:
        t_time = datetime(2026, 11, 1, 10, 5, 0, tzinfo=timezone.utc)
        rand_id = uuid.uuid4().hex[:6]

        trade_original = EventDetectionInput(
            provider_id="SIMULATOR",
            feed_id="SIM_TRADE_FEED",
            instrument_id=f"INFY_{rand_id}",
            exchange="NSE",
            event_type="TRADE",
            provider_event_id=f"TRD_CNF_{rand_id}",
            event_timestamp=t_time,
            price=Decimal("1500.00"),
            quantity=Decimal("50"),
        )
        res_orig = await DuplicateDetectionService.process_market_event(session, trade_original)
        assert res_orig.classification == "NEW_EVENT"

        # Conflicting message under same Trade ID (price changed from 1500 to 1550)
        trade_conflict = EventDetectionInput(
            provider_id="SIMULATOR",
            feed_id="SIM_TRADE_FEED",
            instrument_id=f"INFY_{rand_id}",
            exchange="NSE",
            event_type="TRADE",
            provider_event_id=f"TRD_CNF_{rand_id}",
            event_timestamp=t_time,
            price=Decimal("1550.00"),  # Changed!
            quantity=Decimal("50"),
        )
        res_cnf = await DuplicateDetectionService.process_market_event(session, trade_conflict)
        assert res_cnf.classification == "IDENTITY_CONFLICT"
        assert res_cnf.is_conflict is True


# ============================================================================
# Section B: Repeated Market Event Detection (M03.05.02)
# ============================================================================

@pytest.mark.asyncio
async def test_repeated_quote_and_sequence_events():
    """
    Quotes and order book deltas:
    - Same sequence replayed -> DUPLICATE_EVENT
    - Different sequence with identical values -> NEW_EVENT
    """
    async with AsyncSessionLocal() as session:
        t_time = datetime(2026, 11, 1, 10, 10, 0, tzinfo=timezone.utc)
        rand_id = uuid.uuid4().hex[:6]

        # Delta 1: Sequence 5001
        delta_1 = EventDetectionInput(
            provider_id="SIMULATOR",
            feed_id="SIM_L2_FEED",
            instrument_id=f"AAPL_{rand_id}",
            exchange="NASDAQ",
            event_type="DELTA",
            sequence_number=5001,
            connection_epoch=1,
            event_timestamp=t_time,
            price=Decimal("220.00"),
            quantity=Decimal("500"),
            side="BID",
        )
        res_d1 = await DuplicateDetectionService.process_market_event(session, delta_1)
        assert res_d1.classification == "NEW_EVENT"

        # Replay Delta 1
        res_replay = await DuplicateDetectionService.process_market_event(session, delta_1)
        assert res_replay.classification == "DUPLICATE_EVENT"

        # Delta 2: Sequence 5002 (Same values, different sequence)
        delta_2 = EventDetectionInput(
            provider_id="SIMULATOR",
            feed_id="SIM_L2_FEED",
            instrument_id=f"AAPL_{rand_id}",
            exchange="NASDAQ",
            event_type="DELTA",
            sequence_number=5002,  # New sequence!
            connection_epoch=1,
            event_timestamp=t_time,
            price=Decimal("220.00"),
            quantity=Decimal("500"),
            side="BID",
        )
        res_d2 = await DuplicateDetectionService.process_market_event(session, delta_2)
        assert res_d2.classification == "NEW_EVENT"


@pytest.mark.asyncio
async def test_historical_ohlcv_deduplication():
    """
    Verifies that repeatedly fetching the same daily bar (e.g. from Alpha Vantage)
    deduplicates cleanly without duplicating candle rows.
    """
    async with AsyncSessionLocal() as session:
        b_time = datetime(2026, 10, 31, 0, 0, 0, tzinfo=timezone.utc)
        rand_id = uuid.uuid4().hex[:6]
        candle = EventDetectionInput(
            provider_id="ALPHA_VANTAGE",
            feed_id="AV_DAILY_FEED",
            instrument_id=f"IBM_{rand_id}",
            exchange="NYSE",
            event_type="OHLCV",
            interval="1d",
            event_timestamp=b_time,
            price=Decimal("210.50"),  # close price
            quantity=Decimal("1200000"),  # volume
        )

        res_first = await DuplicateDetectionService.process_market_event(session, candle)
        assert res_first.classification == "NEW_EVENT"

        res_second = await DuplicateDetectionService.process_market_event(session, candle)
        assert res_second.classification == "DUPLICATE_EVENT"
        assert res_second.canonical_event_id == res_first.canonical_event_id


# ============================================================================
# Section C: Idempotent Ingestion & Concurrency (M03.05.03)
# ============================================================================

@pytest.mark.asyncio
async def test_concurrent_duplicate_arrivals():
    """
    Simulates multiple concurrent worker tasks submitting the exact same event simultaneously.
    Asserts that exactly one canonical record is established and other workers receive DUPLICATE.
    """
    t_time = datetime(2026, 11, 1, 10, 20, 0, tzinfo=timezone.utc)
    concurrent_event = EventDetectionInput(
        provider_id="SIMULATOR",
        feed_id="CONCURRENCY_FEED",
        instrument_id="TCS",
        exchange="NSE",
        event_type="TRADE",
        provider_event_id=f"CONCUR_TRD_{uuid.uuid4().hex[:6]}",
        event_timestamp=t_time,
        price=Decimal("3800.00"),
        quantity=Decimal("200"),
    )

    async def worker_task():
        async with AsyncSessionLocal() as session:
            return await DuplicateDetectionService.process_market_event(session, concurrent_event)

    # Launch 5 concurrent workers simultaneously
    results = await asyncio.gather(*[worker_task() for _ in range(5)])

    # Exactly 1 worker must register NEW_EVENT; the remaining 4 must be DUPLICATE_EVENT
    new_events = [r for r in results if r.classification == "NEW_EVENT"]
    dup_events = [r for r in results if r.classification == "DUPLICATE_EVENT"]

    assert len(new_events) == 1
    assert len(dup_events) == 4
    # All must agree on the same canonical_event_id
    canonical_id = new_events[0].canonical_event_id
    for d in dup_events:
        assert d.canonical_event_id == canonical_id


# ============================================================================
# Section D: Duplicate Audit & Aggregates (M03.05.04)
# ============================================================================

@pytest.mark.asyncio
async def test_duplicate_audit_volume_turnover_protection():
    """
    Verifies that duplicate trade replays correctly calculate prevented volume
    and turnover without inflating financial metrics.
    """
    async with AsyncSessionLocal() as session:
        test_inst = f"TEST_AUDIT_{uuid.uuid4().hex[:6]}"
        t_time = datetime(2026, 11, 1, 10, 30, 0, tzinfo=timezone.utc)

        trade = EventDetectionInput(
            provider_id="SIMULATOR",
            feed_id="AUDIT_FEED",
            instrument_id=test_inst,
            exchange="NSE",
            event_type="TRADE",
            provider_event_id=f"AUDIT_TRD_{uuid.uuid4().hex[:6]}",
            event_timestamp=t_time,
            price=Decimal("100.00"),
            quantity=Decimal("50.0"),  # 50 shares @ 100 = 5000 turnover
        )

        # 1st: accepted
        await DuplicateDetectionService.process_market_event(session, trade)

        # 2nd, 3rd: replays
        await DuplicateDetectionService.process_market_event(session, trade)
        await DuplicateDetectionService.process_market_event(session, trade)

        summary = await DuplicateRepository.get_audit_summary(session, instrument_id=test_inst)
        assert summary["unique_canonical_events"] == 1
        assert summary["confirmed_duplicates"] == 2
        assert summary["prevented_business_inserts"] == 2
        # Prevented volume: 2 duplicates * 50 = 100 shares
        assert summary["prevented_volume"] == Decimal("100.0")
        # Prevented turnover: 2 duplicates * 5000 = 10000
        assert summary["prevented_turnover"] == Decimal("10000.0")
        # Duplicate rate: 2 / 3 * 100 = 66.67%
        assert summary["duplicate_rate_percentage"] == 66.67


# ============================================================================
# Section E: REST API Verification
# ============================================================================

@pytest.mark.asyncio
async def test_rest_api_lifecycle(auth_headers, admin_headers):
    """
    Verifies:
    - POST /api/v1/quality/duplicates/detect
    - POST /api/v1/quality/duplicates/detect/batch
    - GET /api/v1/quality/duplicates/receipts
    - GET /api/v1/quality/duplicates/audit/summary
    - POST /api/v1/quality/duplicates/rules
    - GET /api/v1/quality/duplicates/rules
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Configure custom rule
        rule_code = f"RULE_DUP_{uuid.uuid4().hex[:8]}"
        rule_payload = {
            "rule_code": rule_code,
            "rule_name": "Test Duplicate Rule",
            "event_type": "TRADE",
            "provider_id": "SIMULATOR",
            "identity_strategy": "PROVIDER_EVENT_ID",
            "confidence_policy": "CONSERVATIVE",
        }
        resp = await client.post("/api/v1/quality/duplicates/rules", json=rule_payload, headers=admin_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["rule_code"] == rule_code

        # 2. Detect single event via REST
        ev_payload = {
            "provider_id": "SIMULATOR",
            "feed_id": "SIM_API_FEED",
            "instrument_id": "RELIANCE",
            "exchange": "NSE",
            "event_type": "TRADE",
            "provider_event_id": f"API_TRD_{uuid.uuid4().hex[:6]}",
            "event_timestamp": "2026-11-01T10:40:00Z",
            "price": "2980.00",
            "quantity": "25",
        }
        resp_1 = await client.post("/api/v1/quality/duplicates/detect", json=ev_payload, headers=auth_headers)
        assert resp_1.status_code == 200
        assert resp_1.json()["classification"] == "NEW_EVENT"

        # Replay via REST
        resp_2 = await client.post("/api/v1/quality/duplicates/detect", json=ev_payload, headers=auth_headers)
        assert resp_2.status_code == 200
        assert resp_2.json()["classification"] == "DUPLICATE_EVENT"
        assert resp_2.json()["is_duplicate"] is True

        # 3. Batch evaluation
        batch_payload = [
            ev_payload,
            {
                "provider_id": "SIMULATOR",
                "feed_id": "SIM_API_FEED",
                "instrument_id": "RELIANCE",
                "exchange": "NSE",
                "event_type": "QUOTE",
                "provider_event_id": f"API_QTE_{uuid.uuid4().hex[:6]}",
                "event_timestamp": "2026-11-01T10:41:00Z",
                "price": "2980.50",
                "quantity": "100",
            }
        ]
        resp_batch = await client.post("/api/v1/quality/duplicates/detect/batch", json=batch_payload, headers=auth_headers)
        assert resp_batch.status_code == 200
        assert len(resp_batch.json()) == 2

        # 4. Receipts & Audit Summary
        resp_rcp = await client.get("/api/v1/quality/duplicates/receipts?limit=10", headers=auth_headers)
        assert resp_rcp.status_code == 200
        assert len(resp_rcp.json()) >= 1

        resp_sum = await client.get("/api/v1/quality/duplicates/audit/summary", headers=auth_headers)
        assert resp_sum.status_code == 200
        assert resp_sum.json()["confirmed_duplicates"] >= 1
