"""
Repository layer for M09.08 Order Book Imbalance.
"""

from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_microstructure.order_book_imbalance.models.imbalance_models import (
    OrderBookImbalanceConfig,
    OrderBookImbalanceSnapshot,
    OrderBookImbalancePersistenceResult,
    OrderBookImbalanceReversalEvent,
    OrderBookImbalanceMonitoringSnapshot,
)


class OrderBookImbalanceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_config_by_id(self, config_id: str) -> Optional[OrderBookImbalanceConfig]:
        stmt = select(OrderBookImbalanceConfig).where(OrderBookImbalanceConfig.config_id == config_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_default_config(self) -> Optional[OrderBookImbalanceConfig]:
        stmt = select(OrderBookImbalanceConfig).where(OrderBookImbalanceConfig.is_active == True).order_by(OrderBookImbalanceConfig.created_at.asc())
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def save_config(self, config: OrderBookImbalanceConfig) -> OrderBookImbalanceConfig:
        self.session.add(config)
        await self.session.flush()
        return config

    async def save_snapshot(self, snapshot: OrderBookImbalanceSnapshot) -> OrderBookImbalanceSnapshot:
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot

    async def get_latest_snapshot(self, instrument_id: str, venue_id: Optional[str] = None) -> Optional[OrderBookImbalanceSnapshot]:
        stmt = (
            select(OrderBookImbalanceSnapshot)
            .where(OrderBookImbalanceSnapshot.instrument_id == instrument_id)
        )
        if venue_id:
            stmt = stmt.where(OrderBookImbalanceSnapshot.venue_id == venue_id)
        stmt = stmt.order_by(OrderBookImbalanceSnapshot.event_timestamp.desc())
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_snapshots_for_instrument(
        self, instrument_id: str, venue_id: Optional[str] = None, limit: int = 100
    ) -> List[OrderBookImbalanceSnapshot]:
        stmt = (
            select(OrderBookImbalanceSnapshot)
            .where(OrderBookImbalanceSnapshot.instrument_id == instrument_id)
        )
        if venue_id:
            stmt = stmt.where(OrderBookImbalanceSnapshot.venue_id == venue_id)
        stmt = stmt.order_by(OrderBookImbalanceSnapshot.event_timestamp.desc()).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def save_persistence_result(self, res: OrderBookImbalancePersistenceResult) -> OrderBookImbalancePersistenceResult:
        self.session.add(res)
        await self.session.flush()
        return res

    async def save_reversal_events(self, events: List[OrderBookImbalanceReversalEvent]) -> List[OrderBookImbalanceReversalEvent]:
        self.session.add_all(events)
        await self.session.flush()
        return events

