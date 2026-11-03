"""
Microstructure Monitoring Repository (M09.09).
Provides asynchronous database persistence and query operations.
"""

from typing import List, Optional
from datetime import datetime
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.monitoring_models import (
    MicrostructureMonitoringConfig,
    MicrostructureSpreadMonitoring,
    MicrostructureDepthMonitoring,
    MicrostructureDepthEvent,
    MicrostructureUpdateIntensity,
    MicrostructureFeedFreshness,
    MicrostructureAnomalyRule,
    MicrostructureAnomalyEvent,
    MicrostructureAnomalyEvidence,
    MicrostructureAnomalyTransition,
    MicrostructureAnomalyEpisode,
    MicrostructureMonitoringBaseline
)


class MicrostructureMonitoringRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_config(self, config_data: dict) -> MicrostructureMonitoringConfig:
        stmt = select(MicrostructureMonitoringConfig).where(
            MicrostructureMonitoringConfig.config_name == config_data.get("config_name")
        )
        res = await self.db.execute(stmt)
        cfg = res.scalar_one_or_none()
        if not cfg:
            cfg = MicrostructureMonitoringConfig(**config_data)
            self.db.add(cfg)
            await self.db.flush()
        return cfg

    async def get_config_by_id(self, config_id: str) -> Optional[MicrostructureMonitoringConfig]:
        stmt = select(MicrostructureMonitoringConfig).where(MicrostructureMonitoringConfig.id == config_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def save_spread_monitoring(self, record: MicrostructureSpreadMonitoring) -> MicrostructureSpreadMonitoring:
        self.db.add(record)
        await self.db.flush()
        return record

    async def get_spread_history(
        self,
        instrument_id: str,
        limit: int = 100
    ) -> List[MicrostructureSpreadMonitoring]:
        stmt = select(MicrostructureSpreadMonitoring).where(
            MicrostructureSpreadMonitoring.instrument_id == instrument_id
        ).order_by(desc(MicrostructureSpreadMonitoring.observation_timestamp)).limit(limit)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_depth_monitoring(self, record: MicrostructureDepthMonitoring) -> MicrostructureDepthMonitoring:
        self.db.add(record)
        await self.db.flush()
        return record

    async def get_depth_history(
        self,
        instrument_id: str,
        side: Optional[str] = None,
        limit: int = 100
    ) -> List[MicrostructureDepthMonitoring]:
        stmt = select(MicrostructureDepthMonitoring).where(
            MicrostructureDepthMonitoring.instrument_id == instrument_id
        )
        if side:
            stmt = stmt.where(MicrostructureDepthMonitoring.side == side)
        stmt = stmt.order_by(desc(MicrostructureDepthMonitoring.event_timestamp)).limit(limit)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_depth_event(self, record: MicrostructureDepthEvent) -> MicrostructureDepthEvent:
        self.db.add(record)
        await self.db.flush()
        return record

    async def get_depth_events(
        self,
        instrument_id: str,
        limit: int = 100
    ) -> List[MicrostructureDepthEvent]:
        stmt = select(MicrostructureDepthEvent).where(
            MicrostructureDepthEvent.instrument_id == instrument_id
        ).order_by(desc(MicrostructureDepthEvent.event_timestamp)).limit(limit)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_update_intensity(self, record: MicrostructureUpdateIntensity) -> MicrostructureUpdateIntensity:
        self.db.add(record)
        await self.db.flush()
        return record

    async def get_latest_intensity(
        self,
        instrument_id: str
    ) -> Optional[MicrostructureUpdateIntensity]:
        stmt = select(MicrostructureUpdateIntensity).where(
            MicrostructureUpdateIntensity.instrument_id == instrument_id
        ).order_by(desc(MicrostructureUpdateIntensity.interval_end)).limit(1)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def save_feed_freshness(self, record: MicrostructureFeedFreshness) -> MicrostructureFeedFreshness:
        self.db.add(record)
        await self.db.flush()
        return record

    async def get_latest_feed_freshness(
        self,
        instrument_id: str
    ) -> Optional[MicrostructureFeedFreshness]:
        stmt = select(MicrostructureFeedFreshness).where(
            MicrostructureFeedFreshness.instrument_id == instrument_id
        ).order_by(desc(MicrostructureFeedFreshness.monitoring_timestamp)).limit(1)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def save_anomaly_event(self, anomaly: MicrostructureAnomalyEvent) -> MicrostructureAnomalyEvent:
        self.db.add(anomaly)
        await self.db.flush()
        return anomaly

    async def get_anomaly_by_id(self, anomaly_id: str) -> Optional[MicrostructureAnomalyEvent]:
        stmt = select(MicrostructureAnomalyEvent).where(MicrostructureAnomalyEvent.id == anomaly_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_anomalies(
        self,
        instrument_id: Optional[str] = None,
        severity: Optional[str] = None,
        lifecycle_status: Optional[str] = None,
        limit: int = 50
    ) -> List[MicrostructureAnomalyEvent]:
        stmt = select(MicrostructureAnomalyEvent)
        if instrument_id:
            stmt = stmt.where(MicrostructureAnomalyEvent.instrument_id == instrument_id)
        if severity:
            stmt = stmt.where(MicrostructureAnomalyEvent.severity == severity)
        if lifecycle_status:
            stmt = stmt.where(MicrostructureAnomalyEvent.lifecycle_status == lifecycle_status)
        stmt = stmt.order_by(desc(MicrostructureAnomalyEvent.detection_timestamp)).limit(limit)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_anomaly_transition(self, transition: MicrostructureAnomalyTransition) -> MicrostructureAnomalyTransition:
        self.db.add(transition)
        await self.db.flush()
        return transition
