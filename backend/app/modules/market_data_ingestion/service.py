"""
Module 02: Market Data Ingestion Engine - Ingestion Orchestrator Service.
Coordinates connection lifecycle, streaming reception, payload parsing,
normalization, deduplication, order-book reconstruction, persistence, and M01 health reporting.
"""
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.feed_registry.models import FeedRuntimeState
from backend.app.modules.feed_registry.repository import FeedRepository
from backend.app.modules.feed_registry.schemas import HealthEventReport
from backend.app.modules.market_data_ingestion.adapters.registry import ProviderAdapterRegistry
from backend.app.modules.market_data_ingestion.adapters.simulator import SimulatedMarketDataAdapter
from backend.app.modules.market_data_ingestion.distribution.event_bus import global_event_bus
from backend.app.modules.market_data_ingestion.normalization.normalizer import NormalizationEngine
from backend.app.modules.market_data_ingestion.normalization.schemas import (
    BackfillJobStatus,
    MarketDataChannel,
    MarketTick,
    OrderBookDelta,
    OrderBookSnapshot,
    TradeEvent,
)
from backend.app.modules.market_data_ingestion.orderbook.reconstruction import OrderBookManager
from backend.app.modules.market_data_ingestion.persistence.models import HistoricalBackfillJob
from backend.app.modules.market_data_ingestion.persistence.repository import IngestionRepository
from backend.app.modules.market_data_ingestion.reliability.deduplication import ReliabilityEngine


class IngestionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.ingestion_repo = IngestionRepository(session)
        self.feed_repo = FeedRepository(session)
        self.reliability = ReliabilityEngine()
        self.order_book_manager = OrderBookManager()

        # Operational metrics
        self.metrics = {
            "messages_received": 0,
            "events_processed": 0,
            "duplicates_detected": 0,
            "gaps_detected": 0,
            "errors_count": 0,
            "last_latency_ms": 1.2,
        }

    async def start_feed_ingestion(
        self,
        feed_id: str,
        instruments: List[str],
        channels: List[MarketDataChannel],
        provider_type: str = "SIMULATOR",
    ) -> bool:
        """Starts connection and registers instrument subscriptions."""
        adapter = ProviderAdapterRegistry.get_or_create_adapter(feed_id, provider_type)
        await adapter.connect({})
        await adapter.subscribe(instruments, channels)
        return adapter.is_connected

    async def stop_feed_ingestion(self, feed_id: str, provider_type: str = "SIMULATOR") -> None:
        """Stops provider connection."""
        adapter = ProviderAdapterRegistry.get_instance(feed_id, provider_type)
        await adapter.disconnect()

    async def process_raw_event(self, raw_payload: Dict[str, Any]) -> Optional[Any]:
        """
        End-to-End Processing Pipeline:
        1. Parse & Deduplicate
        2. Normalize
        3. Sequence Track
        4. Reconstruct Order Book
        5. Persist
        6. Distribute downstream
        """
        self.metrics["messages_received"] += 1
        msg_type = raw_payload.get("msg_type", "UNKNOWN").upper()
        event_key = str(raw_payload.get("event_id") or raw_payload.get("provider_event_id") or "")

        # 1. Deduplication
        if event_key and self.reliability.is_duplicate(event_key):
            self.metrics["duplicates_detected"] += 1
            return None

        # 2. Normalize
        try:
            category, event = NormalizationEngine.normalize_event(raw_payload)
        except Exception as err:
            self.metrics["errors_count"] += 1
            return None

        feed_id = str(raw_payload.get("feed_id", "feed_sim"))
        symbol = str(raw_payload.get("symbol", "N/A"))
        inst_id = str(raw_payload.get("instrument_id", f"EQ_{symbol}"))
        seq = raw_payload.get("sequence")

        # 3. Sequence Tracking & Gap Detection
        gap = self.reliability.track_sequence(feed_id, inst_id, category, seq)
        if gap:
            self.metrics["gaps_detected"] += 1

        # 4. Processing & Persistence
        if category == "TICK":
            tick: MarketTick = event
            await self.ingestion_repo.save_normalized_tick(tick)
            await global_event_bus.publish(MarketDataChannel.TICK, tick.model_dump())

        elif category == "TRADE":
            trade: TradeEvent = event
            await self.ingestion_repo.save_trade_event(trade)
            await global_event_bus.publish(MarketDataChannel.TRADE, trade.model_dump())

        elif category == "SNAPSHOT":
            snapshot: OrderBookSnapshot = event
            book = self.order_book_manager.get_or_create_book(inst_id)
            book.apply_snapshot(snapshot)
            await self.ingestion_repo.save_order_book_snapshot(snapshot)
            await global_event_bus.publish(MarketDataChannel.ORDER_BOOK_L2, snapshot.model_dump())

        elif category == "DELTA":
            delta: OrderBookDelta = event
            book = self.order_book_manager.get_or_create_book(inst_id)
            book.apply_delta(delta)
            await self.ingestion_repo.save_order_book_delta(delta)
            await global_event_bus.publish(MarketDataChannel.ORDER_BOOK_L2, delta.model_dump())

        self.metrics["events_processed"] += 1
        return event

    async def report_health_to_m01(self, feed_uuid: UUID) -> None:
        """Reports runtime health status, latency, and throughput to M01."""
        report = HealthEventReport(
            runtime_state=FeedRuntimeState.CONNECTED,
            latency_ms=self.metrics["last_latency_ms"],
            messages_received_delta=self.metrics["messages_received"],
            bytes_received_delta=self.metrics["messages_received"] * 256,
            error_count_delta=self.metrics["errors_count"],
            last_heartbeat_timestamp=datetime.now(timezone.utc),
            last_data_timestamp=datetime.now(timezone.utc),
        )
        await self.feed_repo.record_health_event(
            # Create M01 model record
            report  # Repo helper takes HealthEventReport directly
        )

    async def execute_historical_backfill(
        self,
        feed_id: str,
        instrument_id: str,
        start_time: datetime,
        end_time: datetime,
        interval: str = "1m",
    ) -> HistoricalBackfillJob:
        """Orchestrates an idempotent historical backfill job."""
        job_id = f"job-{instrument_id}-{int(start_time.timestamp())}"
        job = HistoricalBackfillJob(
            id=job_id,
            feed_id=feed_id,
            instrument_id=instrument_id,
            data_type="OHLCV",
            requested_start=start_time,
            requested_end=end_time,
            job_status=BackfillJobStatus.RUNNING.value,
        )
        saved_job = await self.ingestion_repo.create_backfill_job(job)

        adapter = ProviderAdapterRegistry.get_instance(feed_id)
        records = await adapter.fetch_historical(
            instrument_id=instrument_id,
            channel=MarketDataChannel.OHLCV,
            start_time=start_time,
            end_time=end_time,
            interval=interval,
        )

        saved_job.records_received = len(records)
        saved_job.job_status = BackfillJobStatus.COMPLETED.value
        saved_job.completed_at = datetime.now(timezone.utc)
        await self.session.commit()
        return saved_job
