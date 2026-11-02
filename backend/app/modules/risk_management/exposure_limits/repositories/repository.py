"""
Repository layer for M06.08 Exposure Limits.
"""

from typing import Optional, List
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_management.exposure_limits.models import (
    ExposureLimitConfig,
    ExposureLimitEvaluation,
    ExposureLimitBreachHistory,
    ExposureLimitCategory,
)


class ExposureLimitRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_limit_config(self, config: ExposureLimitConfig) -> ExposureLimitConfig:
        self.session.add(config)
        await self.session.flush()
        return config

    async def get_limit_config_by_id(self, limit_id: str) -> Optional[ExposureLimitConfig]:
        stmt = select(ExposureLimitConfig).where(ExposureLimitConfig.limit_id == limit_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_active_limit_configs(
        self,
        portfolio_id: Optional[str] = None,
        portfolio_group_id: Optional[str] = None,
        limit_category: Optional[ExposureLimitCategory] = None,
    ) -> List[ExposureLimitConfig]:
        stmt = select(ExposureLimitConfig).where(ExposureLimitConfig.is_active.is_(True))
        if portfolio_id:
            stmt = stmt.where(
                (ExposureLimitConfig.portfolio_id == portfolio_id) | (ExposureLimitConfig.portfolio_id.is_(None))
            )
        if portfolio_group_id:
            stmt = stmt.where(
                (ExposureLimitConfig.portfolio_group_id == portfolio_group_id) | (ExposureLimitConfig.portfolio_group_id.is_(None))
            )
        if limit_category:
            stmt = stmt.where(ExposureLimitConfig.limit_category == limit_category)

        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def create_evaluations(self, evals: List[ExposureLimitEvaluation]) -> List[ExposureLimitEvaluation]:
        self.session.add_all(evals)
        await self.session.flush()
        return evals

    async def get_latest_evaluation(self, limit_id: str) -> Optional[ExposureLimitEvaluation]:
        stmt = (
            select(ExposureLimitEvaluation)
            .where(ExposureLimitEvaluation.limit_id == limit_id)
            .order_by(desc(ExposureLimitEvaluation.evaluated_at))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_breach_event(self, event: ExposureLimitBreachHistory) -> ExposureLimitBreachHistory:
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_breach_history(
        self,
        portfolio_id: Optional[str] = None,
        limit_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[ExposureLimitBreachHistory]:
        stmt = select(ExposureLimitBreachHistory)
        if portfolio_id:
            stmt = stmt.where(ExposureLimitBreachHistory.portfolio_id == portfolio_id)
        if limit_id:
            stmt = stmt.where(ExposureLimitBreachHistory.limit_id == limit_id)
        stmt = stmt.order_by(desc(ExposureLimitBreachHistory.recorded_at)).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

