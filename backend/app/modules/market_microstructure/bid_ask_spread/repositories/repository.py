"""
M09.01 Bid-Ask Spread - Repository Layer.
Handles database persistence and queries for spread observations, configs, quality results, and aggregates.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List, Optional
from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_microstructure.bid_ask_spread.models import (
    SpreadCalculationConfig,
    SpreadObservation,
    SpreadQualityResult,
    SpreadIntervalAggregate,
    SpreadSessionSummary,
    SpreadQualitySummary,
)


class SpreadRepository:
    """Async repository for M09.01 entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # =========================================================================
    # Config CRUD
    # =========================================================================
    async def create_config(self, config: SpreadCalculationConfig) -> SpreadCalculationConfig:
        self.session.add(config)
        await self.session.flush()
        return config

    async def get_config_by_id(self, config_id: str) -> Optional[SpreadCalculationConfig]:
        stmt = select(SpreadCalculationConfig).where(SpreadCalculationConfig.config_id == config_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_config_by_code(self, config_code: str) -> Optional[SpreadCalculationConfig]:
        stmt = (
            select(SpreadCalculationConfig)
            .where(SpreadCalculationConfig.config_code == config_code)
            .order_by(desc(SpreadCalculationConfig.version))
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_default_config(self) -> Optional[SpreadCalculationConfig]:
        stmt = select(SpreadCalculationConfig).where(
            SpreadCalculationConfig.status == "ACTIVE"
        ).order_by(desc(SpreadCalculationConfig.created_at))
        res = await self.session.execute(stmt)
        return res.scalars().first()

    # =========================================================================
    # Observations CRUD
    # =========================================================================
    async def save_observation(self, obs: SpreadObservation) -> SpreadObservation:
        self.session.add(obs)
        await self.session.flush()
        return obs

    async def save_observations(self, obs_list: List[SpreadObservation]) -> List[SpreadObservation]:
        self.session.add_all(obs_list)
        await self.session.flush()
        return obs_list

    async def get_observation_by_id(self, observation_id: str) -> Optional[SpreadObservation]:
        stmt = select(SpreadObservation).where(SpreadObservation.observation_id == observation_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_latest_observation(
        self,
        instrument_id: str,
        venue: Optional[str] = None,
        book_scope: Optional[str] = None,
    ) -> Optional[SpreadObservation]:
        stmt = select(SpreadObservation).where(SpreadObservation.instrument_id == instrument_id)
        if venue:
            stmt = stmt.where(SpreadObservation.venue == venue)
        if book_scope:
            stmt = stmt.where(SpreadObservation.book_scope == book_scope)
        stmt = stmt.order_by(desc(SpreadObservation.book_timestamp))
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def query_observations(
        self,
        instrument_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        venue: Optional[str] = None,
        book_scope: Optional[str] = None,
        quality_status: Optional[str] = None,
        limit: int = 500,
        offset: int = 0,
    ) -> List[SpreadObservation]:
        stmt = select(SpreadObservation).where(SpreadObservation.instrument_id == instrument_id)
        if start_time:
            stmt = stmt.where(SpreadObservation.book_timestamp >= start_time)
        if end_time:
            stmt = stmt.where(SpreadObservation.book_timestamp <= end_time)
        if venue:
            stmt = stmt.where(SpreadObservation.venue == venue)
        if book_scope:
            stmt = stmt.where(SpreadObservation.book_scope == book_scope)
        if quality_status:
            stmt = stmt.where(SpreadObservation.quality_status == quality_status)

        stmt = stmt.order_by(desc(SpreadObservation.book_timestamp)).limit(limit).offset(offset)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # =========================================================================
    # Quality Results CRUD
    # =========================================================================
    async def save_quality_result(self, qr: SpreadQualityResult) -> SpreadQualityResult:
        self.session.add(qr)
        await self.session.flush()
        return qr

    async def save_quality_results(self, qrs: List[SpreadQualityResult]) -> List[SpreadQualityResult]:
        self.session.add_all(qrs)
        await self.session.flush()
        return qrs

    async def query_quality_results(
        self,
        observation_id: Optional[str] = None,
        source_quote_ref: Optional[str] = None,
        limit: int = 100,
    ) -> List[SpreadQualityResult]:
        stmt = select(SpreadQualityResult)
        if observation_id:
            stmt = stmt.where(SpreadQualityResult.observation_id == observation_id)
        if source_quote_ref:
            stmt = stmt.where(SpreadQualityResult.source_quote_reference == source_quote_ref)
        stmt = stmt.order_by(desc(SpreadQualityResult.created_at)).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # =========================================================================
    # Aggregates & Summaries
    # =========================================================================
    async def save_aggregate(self, agg: SpreadIntervalAggregate) -> SpreadIntervalAggregate:
        self.session.add(agg)
        await self.session.flush()
        return agg

    async def query_aggregates(
        self,
        instrument_id: str,
        frequency: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        venue: Optional[str] = None,
        limit: int = 500,
    ) -> List[SpreadIntervalAggregate]:
        stmt = select(SpreadIntervalAggregate).where(
            SpreadIntervalAggregate.instrument_id == instrument_id,
            SpreadIntervalAggregate.aggregation_frequency == frequency,
        )
        if start_time:
            stmt = stmt.where(SpreadIntervalAggregate.aggregation_start >= start_time)
        if end_time:
            stmt = stmt.where(SpreadIntervalAggregate.aggregation_end <= end_time)
        if venue:
            stmt = stmt.where(SpreadIntervalAggregate.venue == venue)

        stmt = stmt.order_by(desc(SpreadIntervalAggregate.aggregation_start)).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def save_session_summary(self, summary: SpreadSessionSummary) -> SpreadSessionSummary:
        self.session.add(summary)
        await self.session.flush()
        return summary

    async def get_session_summary(
        self,
        instrument_id: str,
        trading_date: date,
        exchange: str,
        venue: str,
        session_type: str = "REGULAR_TRADING",
    ) -> Optional[SpreadSessionSummary]:
        stmt = select(SpreadSessionSummary).where(
            SpreadSessionSummary.instrument_id == instrument_id,
            SpreadSessionSummary.trading_date == trading_date,
            SpreadSessionSummary.exchange == exchange,
            SpreadSessionSummary.venue == venue,
            SpreadSessionSummary.session_type == session_type,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def save_quality_summary(self, summary: SpreadQualitySummary) -> SpreadQualitySummary:
        self.session.add(summary)
        await self.session.flush()
        return summary

    async def get_latest_quality_summary(
        self,
        instrument_id: str,
        venue: Optional[str] = None,
    ) -> Optional[SpreadQualitySummary]:
        stmt = select(SpreadQualitySummary).where(SpreadQualitySummary.instrument_id == instrument_id)
        if venue:
            stmt = stmt.where(SpreadQualitySummary.venue == venue)
        stmt = stmt.order_by(desc(SpreadQualitySummary.aggregation_end))
        res = await self.session.execute(stmt)
        return res.scalars().first()

