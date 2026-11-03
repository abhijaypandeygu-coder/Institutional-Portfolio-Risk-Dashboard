"""
M09.02 Order Book Depth - Repository Layer.
Handles asynchronous database access for depth configurations, snapshots, levels, bands, persistence, and history.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_microstructure.order_book_depth.models import (
    DepthCalculationConfig,
    OrderBookDepthSnapshot,
    OrderBookDepthLevel,
    OrderBookDepthBand,
    OrderBookDepthPersistence,
    OrderBookDepthHistoryAggregate,
)


class DepthRepository:
    """Async repository for M09.02 Order Book Depth entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # =========================================================================
    # Config CRUD
    # =========================================================================
    async def create_config(self, config: DepthCalculationConfig) -> DepthCalculationConfig:
        self.session.add(config)
        await self.session.flush()
        return config

    async def get_config_by_id(self, config_id: str) -> Optional[DepthCalculationConfig]:
        stmt = select(DepthCalculationConfig).where(DepthCalculationConfig.config_id == config_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_config_by_code(self, config_code: str) -> Optional[DepthCalculationConfig]:
        stmt = select(DepthCalculationConfig).where(
            DepthCalculationConfig.config_code == config_code
        ).order_by(desc(DepthCalculationConfig.version))
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_default_config(self) -> Optional[DepthCalculationConfig]:
        stmt = select(DepthCalculationConfig).where(
            DepthCalculationConfig.status == "ACTIVE"
        ).order_by(desc(DepthCalculationConfig.created_at))
        res = await self.session.execute(stmt)
        return res.scalars().first()

    # =========================================================================
    # Snapshots & Levels CRUD
    # =========================================================================
    async def save_snapshot(
        self,
        snapshot: OrderBookDepthSnapshot,
        levels: Optional[List[OrderBookDepthLevel]] = None,
        bands: Optional[List[OrderBookDepthBand]] = None,
    ) -> OrderBookDepthSnapshot:
        self.session.add(snapshot)
        if levels:
            self.session.add_all(levels)
        if bands:
            self.session.add_all(bands)
        await self.session.flush()
        return snapshot

    async def get_latest_snapshot(
        self,
        instrument_id: str,
        venue: Optional[str] = None,
    ) -> Optional[OrderBookDepthSnapshot]:
        stmt = select(OrderBookDepthSnapshot).where(OrderBookDepthSnapshot.instrument_id == instrument_id)
        if venue:
            stmt = stmt.where(OrderBookDepthSnapshot.venue == venue)
        stmt = stmt.order_by(desc(OrderBookDepthSnapshot.event_timestamp))
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_snapshot_levels(self, depth_snapshot_id: str) -> List[OrderBookDepthLevel]:
        stmt = select(OrderBookDepthLevel).where(
            OrderBookDepthLevel.depth_snapshot_id == depth_snapshot_id
        ).order_by(OrderBookDepthLevel.side, OrderBookDepthLevel.level_index)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_snapshot_bands(self, depth_snapshot_id: str) -> List[OrderBookDepthBand]:
        stmt = select(OrderBookDepthBand).where(
            OrderBookDepthBand.depth_snapshot_id == depth_snapshot_id
        ).order_by(OrderBookDepthBand.band_lower_bound)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def query_snapshots(
        self,
        instrument_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        venue: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> List[OrderBookDepthSnapshot]:
        stmt = select(OrderBookDepthSnapshot).where(OrderBookDepthSnapshot.instrument_id == instrument_id)
        if start_time:
            stmt = stmt.where(OrderBookDepthSnapshot.event_timestamp >= start_time)
        if end_time:
            stmt = stmt.where(OrderBookDepthSnapshot.event_timestamp <= end_time)
        if venue:
            stmt = stmt.where(OrderBookDepthSnapshot.venue == venue)

        stmt = stmt.order_by(desc(OrderBookDepthSnapshot.event_timestamp)).limit(limit).offset(offset)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # =========================================================================
    # Persistence & Aggregates
    # =========================================================================
    async def save_persistence(self, persistence: OrderBookDepthPersistence) -> OrderBookDepthPersistence:
        self.session.add(persistence)
        await self.session.flush()
        return persistence

    async def get_latest_persistence(
        self,
        instrument_id: str,
        venue: Optional[str] = None,
    ) -> Optional[OrderBookDepthPersistence]:
        stmt = select(OrderBookDepthPersistence).where(OrderBookDepthPersistence.instrument_id == instrument_id)
        if venue:
            stmt = stmt.where(OrderBookDepthPersistence.venue == venue)
        stmt = stmt.order_by(desc(OrderBookDepthPersistence.window_end))
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def save_history_aggregate(self, agg: OrderBookDepthHistoryAggregate) -> OrderBookDepthHistoryAggregate:
        self.session.add(agg)
        await self.session.flush()
        return agg

    async def query_history_aggregates(
        self,
        instrument_id: str,
        interval: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        venue: Optional[str] = None,
        limit: int = 200,
    ) -> List[OrderBookDepthHistoryAggregate]:
        stmt = select(OrderBookDepthHistoryAggregate).where(
            OrderBookDepthHistoryAggregate.instrument_id == instrument_id,
            OrderBookDepthHistoryAggregate.aggregation_interval == interval,
        )
        if start_time:
            stmt = stmt.where(OrderBookDepthHistoryAggregate.aggregation_start >= start_time)
        if end_time:
            stmt = stmt.where(OrderBookDepthHistoryAggregate.aggregation_end <= end_time)
        if venue:
            stmt = stmt.where(OrderBookDepthHistoryAggregate.venue == venue)

        stmt = stmt.order_by(desc(OrderBookDepthHistoryAggregate.aggregation_start)).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
