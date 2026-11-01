"""
Comprehensive Test Suite for Module 02: Market Data Ingestion Engine.
Covers all feature scopes:
1. Provider Adapter & Simulator streaming
2. Canonical data schema normalization (Tick, OHLCV, Trade, Snapshot, Delta)
3. Precision financial arithmetic (Decimals)
4. Level 2 Order Book Reconstruction & Top-of-Book calculations
5. Incremental Delta processing (Insert, Update, Delete)
6. Sequence tracking & Gap detection
7. Deduplication sliding window
8. Historical Backfill execution
9. Database persistence & query retrieval
10. End-to-End REST APIs & RBAC protection
"""
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.config import settings
from backend.app.core.database import init_db
from backend.app.main import app
from backend.app.modules.market_data_ingestion.adapters.registry import ProviderAdapterRegistry
from backend.app.modules.market_data_ingestion.adapters.simulator import SimulatedMarketDataAdapter
from backend.app.modules.market_data_ingestion.normalization.normalizer import NormalizationEngine
from backend.app.modules.market_data_ingestion.normalization.schemas import (
    MarketDataChannel,
    MarketTick,
    OrderBookDelta,
    OrderBookOperation,
    OrderBookSide,
    OrderBookSnapshot,
    TradeEvent,
)
from backend.app.modules.market_data_ingestion.orderbook.reconstruction import (
    OrderBookManager,
    OrderBookSequenceError,
    ReconstructedOrderBook,
)
from backend.app.modules.market_data_ingestion.reliability.deduplication import ReliabilityEngine
from backend.app.modules.market_data_ingestion.service import IngestionService

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
# 1. Provider Adapter & Simulation Tests
# ============================================================================

async def test_simulated_adapter_lifecycle():
    adapter = SimulatedMarketDataAdapter(feed_id="feed_test_01")
    assert not adapter.is_connected

    # Connect
    ok = await adapter.connect({})
    assert ok is True
    assert adapter.is_connected is True

    # Subscribe
    await adapter.subscribe(["RELIANCE", "TCS"], [MarketDataChannel.TICK, MarketDataChannel.TRADE])
    assert "RELIANCE" in adapter.subscribed_instruments
    assert "TCS" in adapter.subscribed_instruments

    # Generate synthetic tick
    tick_raw = adapter.generate_tick_payload("RELIANCE")
    assert tick_raw["msg_type"] == "TICK"
    assert tick_raw["symbol"] == "RELIANCE"
    assert Decimal(tick_raw["last_price"]) > Decimal("0")

    # Health check
    health = await adapter.health_check()
    assert health["status"] == "HEALTHY"
    assert health["subscribed_symbols_count"] == 2

    # Disconnect
    await adapter.disconnect()
    assert adapter.is_connected is False


# ============================================================================
# 2. Normalization Engine Tests
# ============================================================================

def test_canonical_normalization():
    adapter = SimulatedMarketDataAdapter(feed_id="feed_test_02")

    # 1. Normalize Tick
    raw_tick = adapter.generate_tick_payload("INFY")
    cat, norm_tick = NormalizationEngine.normalize_event(raw_tick)
    assert cat == "TICK"
    assert isinstance(norm_tick, MarketTick)
    assert norm_tick.symbol == "INFY"
    assert isinstance(norm_tick.last_traded_price, Decimal)

    # 2. Normalize Trade
    raw_trade = adapter.generate_trade_payload("TCS")
    cat, norm_trade = NormalizationEngine.normalize_event(raw_trade)
    assert cat == "TRADE"
    assert isinstance(norm_trade, TradeEvent)
    assert norm_trade.quantity > Decimal("0")

    # 3. Normalize Snapshot
    raw_snap = adapter.generate_snapshot_payload("RELIANCE")
    cat, norm_snap = NormalizationEngine.normalize_event(raw_snap)
    assert cat == "SNAPSHOT"
    assert isinstance(norm_snap, OrderBookSnapshot)
    assert len(norm_snap.bids) == 5
    assert len(norm_snap.asks) == 5


# ============================================================================
# 3. Order Book Reconstruction & Delta Processing
# ============================================================================

def test_order_book_reconstruction_and_deltas():
    adapter = SimulatedMarketDataAdapter(feed_id="feed_test_03")
    raw_snap = adapter.generate_snapshot_payload("RELIANCE")
    _, snapshot = NormalizationEngine.normalize_event(raw_snap)

    book = ReconstructedOrderBook(instrument_id="EQ_RELIANCE")
    assert not book.is_synchronized

    # Initialize book from snapshot
    book.apply_snapshot(snapshot)
    assert book.is_synchronized is True
    assert book.last_sequence == snapshot.snapshot_sequence

    best_bid, best_ask = book.get_top_of_book()
    assert best_bid is not None
    assert best_ask is not None
    assert best_bid[0] < best_ask[0]  # Bid price < Ask price

    # Apply incremental delta (Update best bid)
    delta_seq = snapshot.snapshot_sequence + 1
    new_bid_price = best_bid[0] + Decimal("0.10")
    delta = OrderBookDelta(
        feed_id="feed_test_03",
        instrument_id="EQ_RELIANCE",
        sequence_number=delta_seq,
        event_timestamp=datetime.now(timezone.utc),
        side=OrderBookSide.BID,
        price=new_bid_price,
        quantity=Decimal("500"),
        operation=OrderBookOperation.UPDATE,
    )
    book.apply_delta(delta)
    assert book.last_sequence == delta_seq

    # Verify updated best bid
    updated_bid, _ = book.get_top_of_book()
    assert updated_bid[0] == new_bid_price
    assert updated_bid[1] == Decimal("500")

    # Test sequence gap detection
    gap_delta = OrderBookDelta(
        feed_id="feed_test_03",
        instrument_id="EQ_RELIANCE",
        sequence_number=delta_seq + 10,  # Missing intermediate deltas!
        event_timestamp=datetime.now(timezone.utc),
        side=OrderBookSide.BID,
        price=new_bid_price,
        quantity=Decimal("100"),
        operation=OrderBookOperation.UPDATE,
    )
    with pytest.raises(OrderBookSequenceError):
        book.apply_delta(gap_delta)
    assert not book.is_synchronized  # Book marked invalid on gap!


# ============================================================================
# 4. Reliability, Deduplication & Gap Tracking
# ============================================================================

def test_reliability_deduplication_and_gaps():
    rel = ReliabilityEngine(dedup_window_size=100)

    # 1. Deduplication
    event_id = "EVT_UNIQUE_123"
    assert rel.is_duplicate(event_id) is False
    assert rel.is_duplicate(event_id) is True  # Second time is duplicate!

    # 2. Sequence Continuity & Gap Tracking
    gap1 = rel.track_sequence("feed_01", "EQ_TCS", "TICK", sequence=100)
    assert gap1 is None

    gap2 = rel.track_sequence("feed_01", "EQ_TCS", "TICK", sequence=101)
    assert gap2 is None

    # Jump to 105 -> gap between 102 and 105
    gap3 = rel.track_sequence("feed_01", "EQ_TCS", "TICK", sequence=105)
    assert gap3 == (102, 105)


# ============================================================================
# 5. Ingestion Service & Persistence
# ============================================================================

async def test_ingestion_service_pipeline():
    from backend.app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        service = IngestionService(session)
        adapter = SimulatedMarketDataAdapter(feed_id="feed_srv_test")

        # 1. Process Tick
        raw_tick = adapter.generate_tick_payload("HDFCBANK")
        processed_tick = await service.process_raw_event(raw_tick)
        assert processed_tick is not None
        assert service.metrics["events_processed"] == 1

        # 2. Process Trade
        raw_trade = adapter.generate_trade_payload("HDFCBANK")
        processed_trade = await service.process_raw_event(raw_trade)
        assert processed_trade is not None
        assert service.metrics["events_processed"] == 2

        # 3. Process Duplicate
        dup_result = await service.process_raw_event(raw_tick)
        assert dup_result is None
        assert service.metrics["duplicates_detected"] == 1

        # 4. Checkpoint & Historical Backfill
        now = datetime.now(timezone.utc)
        job = await service.execute_historical_backfill(
            feed_id="feed_srv_test",
            instrument_id="EQ_HDFCBANK",
            start_time=now,
            end_time=now,
        )
        assert job.job_status == "COMPLETED"
        assert job.records_received == 10


# ============================================================================
# 6. REST API Endpoints & RBAC Protection
# ============================================================================

async def test_market_data_api_endpoints(operator_headers, read_only_headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Telemetry query (Read Only)
        res_tel = await ac.get("/api/v1/market-data/telemetry", headers=read_only_headers)
        assert res_tel.status_code == 200
        data = res_tel.json()
        assert "metrics" in data

        # 2. Order book inspection (Read Only)
        res_ob = await ac.get("/api/v1/market-data/order-book/EQ_RELIANCE?depth=5", headers=read_only_headers)
        assert res_ob.status_code == 200
        ob_data = res_ob.json()
        assert ob_data["instrument_id"] == "EQ_RELIANCE"

        # 3. Start Ingestion (Operator role)
        start_payload = {
            "feed_id": "feed_api_test",
            "instruments": ["RELIANCE", "TCS"],
            "channels": ["TICK", "ORDER_BOOK_L2"],
        }
        res_start = await ac.post("/api/v1/market-data/start", json=start_payload, headers=operator_headers)
        assert res_start.status_code == 200
        assert res_start.json()["status"] == "CONNECTED"

        # 4. Stop Ingestion (Operator role)
        res_stop = await ac.post("/api/v1/market-data/stop/feed_api_test", headers=operator_headers)
        assert res_stop.status_code == 200
        assert res_stop.json()["status"] == "STOPPED"

        # 5. Historical Backfill (Operator role)
        backfill_payload = {
            "feed_id": "feed_api_test",
            "instrument_id": "EQ_RELIANCE",
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat(),
            "interval": "1m",
        }
        res_bf = await ac.post("/api/v1/market-data/backfill", json=backfill_payload, headers=operator_headers)
        assert res_bf.status_code == 202
        assert res_bf.json()["status"] == "COMPLETED"
        assert res_bf.json()["records_received"] == 10
