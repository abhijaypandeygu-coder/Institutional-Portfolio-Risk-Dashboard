"""
Module M07.04: Drawdown Analytics Repository.
AsyncSession database access for:
- Configurations
- Drawdown Series Points
- Drawdown Episodes
- Maximum Drawdown Records
- Recovery Statistics
- Diagnostics
"""
from datetime import date
from typing import List, Optional
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_risk.drawdown_analytics.models import (
    DrawdownConfig,
    DrawdownSeriesResult,
    DrawdownEpisode,
    MaximumDrawdownResult,
    DrawdownRecoveryStatistics,
    DrawdownDiagnostic,
    DrawdownScopeType,
)


class DrawdownRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_config(self, config: DrawdownConfig) -> DrawdownConfig:
        self.session.add(config)
        await self.session.flush()
        return config

    async def get_config_by_id(self, config_id: str) -> Optional[DrawdownConfig]:
        stmt = select(DrawdownConfig).where(DrawdownConfig.config_id == config_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def save_drawdown_execution(
        self,
        series_points: List[DrawdownSeriesResult],
        episodes: List[DrawdownEpisode],
        mdd_result: MaximumDrawdownResult,
        recovery_stats: Optional[DrawdownRecoveryStatistics] = None,
        diagnostics: Optional[List[DrawdownDiagnostic]] = None,
    ) -> None:
        if mdd_result:
            self.session.add(mdd_result)

        if recovery_stats:
            self.session.add(recovery_stats)

        for ep in episodes:
            self.session.add(ep)

        for pt in series_points:
            self.session.add(pt)

        if diagnostics:
            for d in diagnostics:
                self.session.add(d)

        await self.session.flush()

    async def get_episodes(
        self, series_id: str, limit: int = 50, offset: int = 0
    ) -> List[DrawdownEpisode]:
        stmt = (
            select(DrawdownEpisode)
            .where(DrawdownEpisode.series_id == series_id)
            .order_by(desc(DrawdownEpisode.drawdown_percentage))
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_episode_by_id(self, episode_id: str) -> Optional[DrawdownEpisode]:
        stmt = select(DrawdownEpisode).where(DrawdownEpisode.episode_id == episode_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_latest_mdd(self, series_id: str) -> Optional[MaximumDrawdownResult]:
        stmt = (
            select(MaximumDrawdownResult)
            .where(MaximumDrawdownResult.series_id == series_id)
            .order_by(desc(MaximumDrawdownResult.calculated_at))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_series_points(
        self, series_id: str, limit: int = 252
    ) -> List[DrawdownSeriesResult]:
        stmt = (
            select(DrawdownSeriesResult)
            .where(DrawdownSeriesResult.series_id == series_id)
            .order_by(DrawdownSeriesResult.observation_timestamp)
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_recovery_stats(self, series_id: str) -> Optional[DrawdownRecoveryStatistics]:
        stmt = (
            select(DrawdownRecoveryStatistics)
            .where(DrawdownRecoveryStatistics.series_id == series_id)
            .order_by(desc(DrawdownRecoveryStatistics.calculated_at))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

