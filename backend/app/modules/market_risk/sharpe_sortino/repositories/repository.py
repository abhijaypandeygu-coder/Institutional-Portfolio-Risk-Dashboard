"""
M07.08 Sharpe & Sortino Database Repository.
"""
from datetime import date
from typing import List, Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_risk.sharpe_sortino.models import (
    RiskFreeRateSeries,
    RiskFreeRateObservation,
    RiskAdjustedReturnConfig,
    SharpeRatioResult,
    SortinoRatioResult,
)


class SharpeSortinoRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # 1. Risk-Free Rate Series
    async def get_rate_series_by_id(self, series_id: str) -> Optional[RiskFreeRateSeries]:
        stmt = select(RiskFreeRateSeries).where(RiskFreeRateSeries.id == series_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_rate_series_by_code(self, code: str) -> Optional[RiskFreeRateSeries]:
        stmt = select(RiskFreeRateSeries).where(RiskFreeRateSeries.series_code == code)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_default_series_for_currency(self, currency: str) -> Optional[RiskFreeRateSeries]:
        stmt = (
            select(RiskFreeRateSeries)
            .where(RiskFreeRateSeries.currency == currency, RiskFreeRateSeries.is_active == True)
            .order_by(desc(RiskFreeRateSeries.created_at))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_rate_series(self, active_only: bool = True) -> List[RiskFreeRateSeries]:
        stmt = select(RiskFreeRateSeries)
        if active_only:
            stmt = stmt.where(RiskFreeRateSeries.is_active == True)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def create_rate_series(self, series: RiskFreeRateSeries) -> RiskFreeRateSeries:
        self.session.add(series)
        await self.session.commit()
        await self.session.refresh(series)
        return series

    # 2. Rate Observations
    async def get_rate_observations(
        self, series_id: str, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> List[RiskFreeRateObservation]:
        stmt = select(RiskFreeRateObservation).where(RiskFreeRateObservation.series_id == series_id)
        if start_date:
            stmt = stmt.where(RiskFreeRateObservation.rate_date >= start_date)
        if end_date:
            stmt = stmt.where(RiskFreeRateObservation.rate_date <= end_date)
        stmt = stmt.order_by(RiskFreeRateObservation.rate_date.asc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def add_rate_observation(self, obs: RiskFreeRateObservation) -> RiskFreeRateObservation:
        self.session.add(obs)
        await self.session.commit()
        await self.session.refresh(obs)
        return obs

    # 3. Results Persistence
    async def save_sharpe_result(self, result: SharpeRatioResult) -> SharpeRatioResult:
        self.session.add(result)
        await self.session.commit()
        await self.session.refresh(result)
        return result

    async def save_sortino_result(self, result: SortinoRatioResult) -> SortinoRatioResult:
        self.session.add(result)
        await self.session.commit()
        await self.session.refresh(result)
        return result
