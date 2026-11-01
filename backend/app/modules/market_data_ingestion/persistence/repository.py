"""
Module 02: Market Data Ingestion Engine - Ingestion Persistence Repository.
Provides async batch write operations and query access for raw events,
normalized ticks, OHLCV, trades, order book snapshots, and backfill jobs.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_data_ingestion.normalization.schemas import (
    MarketTick,
    OHLCVCandle,
    OrderBookDelta,
    OrderBookSnapshot,
    TradeEvent,
)
from backend.app.modules.market_data_ingestion.persistence.models import (
    HistoricalBackfillJob,
    IngestionCheckpoint,
    MarketOHLCV,
    MarketTradeEvent,
    NormalizedMarketTick,
    OrderBookDeltaRecord,
    OrderBookSnapshotRecord,
    RawMarketEvent,
)


class IngestionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_raw_event(
        self,
        feed_id: str,
        provider_id: str,
        event_type: str,
        instrument_reference: str,
        event_timestamp: datetime,
        raw_payload: Dict[str, Any],
        provider_event_id: Optional[str] = None,
        provider_sequence: Optional[int] = None,
    ) -> RawMarketEvent:
        record = RawMarketEvent(
            feed_id=feed_id,
            provider_id=provider_id,
            event_type=event_type,
            instrument_reference=instrument_reference,
            event_timestamp=event_timestamp,
            raw_payload=raw_payload,
            provider_event_id=provider_event_id,
            provider_sequence=provider_sequence,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def save_normalized_tick(self, tick: MarketTick) -> NormalizedMarketTick:
        record = NormalizedMarketTick(
            event_id=tick.event_id,
            feed_id=tick.feed_id,
            instrument_id=tick.instrument_id,
            exchange=tick.exchange,
            symbol=tick.symbol,
            price=tick.last_traded_price,
            quantity=tick.last_traded_quantity,
            best_bid_price=tick.best_bid_price,
            best_bid_quantity=tick.best_bid_quantity,
            best_ask_price=tick.best_ask_price,
            best_ask_quantity=tick.best_ask_quantity,
            event_timestamp=tick.event_timestamp,
            receive_timestamp=tick.receive_timestamp,
            provider_sequence=tick.provider_sequence,
            provider_event_id=tick.provider_event_id,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def save_trade_event(self, trade: TradeEvent) -> MarketTradeEvent:
        record = MarketTradeEvent(
            event_id=trade.event_id,
            feed_id=trade.feed_id,
            instrument_id=trade.instrument_id,
            exchange=trade.exchange,
            provider_trade_id=trade.provider_trade_id,
            price=trade.price,
            quantity=trade.quantity,
            trade_timestamp=trade.trade_timestamp,
            receive_timestamp=trade.receive_timestamp,
            aggressor_side=trade.aggressor_side.value if trade.aggressor_side else None,
            sequence_number=trade.sequence_number,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def save_order_book_snapshot(self, snap: OrderBookSnapshot) -> OrderBookSnapshotRecord:
        record = OrderBookSnapshotRecord(
            event_id=snap.event_id,
            feed_id=snap.feed_id,
            instrument_id=snap.instrument_id,
            exchange=snap.exchange,
            sequence_number=snap.snapshot_sequence,
            snapshot_timestamp=snap.snapshot_timestamp,
            bid_levels=[b.model_dump() for b in snap.bids],
            ask_levels=[a.model_dump() for a in snap.asks],
            receive_timestamp=snap.receive_timestamp,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def save_order_book_delta(self, delta: OrderBookDelta) -> OrderBookDeltaRecord:
        record = OrderBookDeltaRecord(
            event_id=delta.event_id,
            feed_id=delta.feed_id,
            instrument_id=delta.instrument_id,
            sequence_number=delta.sequence_number,
            previous_sequence_number=delta.previous_sequence_number,
            event_timestamp=delta.event_timestamp,
            side=delta.side.value,
            price=delta.price,
            quantity=delta.quantity,
            operation=delta.operation.value,
            order_count=delta.order_count,
            receive_timestamp=delta.receive_timestamp,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def save_ohlcv_candle(self, candle: OHLCVCandle) -> MarketOHLCV:
        record = MarketOHLCV(
            event_id=candle.event_id,
            feed_id=candle.feed_id,
            instrument_id=candle.instrument_id,
            interval=candle.interval,
            open_price=candle.open,
            high_price=candle.high,
            low_price=candle.low,
            close_price=candle.close,
            volume=candle.volume,
            candle_start=candle.candle_start,
            candle_end=candle.candle_end,
            source_provider=candle.source_provider,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def list_recent_ticks(self, instrument_id: str, limit: int = 50) -> List[NormalizedMarketTick]:
        stmt = (
            select(NormalizedMarketTick)
            .where(NormalizedMarketTick.instrument_id == instrument_id)
            .order_by(desc(NormalizedMarketTick.event_timestamp))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_recent_trades(self, instrument_id: str, limit: int = 50) -> List[MarketTradeEvent]:
        stmt = (
            select(MarketTradeEvent)
            .where(MarketTradeEvent.instrument_id == instrument_id)
            .order_by(desc(MarketTradeEvent.trade_timestamp))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_backfill_job(self, job: HistoricalBackfillJob) -> HistoricalBackfillJob:
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_backfill_job(self, job_id: str) -> Optional[HistoricalBackfillJob]:
        stmt = select(HistoricalBackfillJob).where(HistoricalBackfillJob.id == job_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
