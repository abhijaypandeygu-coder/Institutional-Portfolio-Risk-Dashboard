"""
Repository layer for M10.09 Stress Loss Attribution.
Async SQLAlchemy operations for configurations, runs, position, sector, industry, factor, and interaction contributions.
"""

from typing import List, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.scenario_analysis.loss_attribution.models.attribution_models import (
    StressLossAttribution,
    StressLossAttributionRun,
    StressPositionContribution,
    StressSectorContribution,
    StressIndustryContribution,
    StressFactorContribution,
    StressInteractionEffect,
    StressLossAttributionAuditLog,
)


class StressLossAttributionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_attribution_by_id(self, attr_id: str) -> Optional[StressLossAttribution]:
        stmt = select(StressLossAttribution).where(StressLossAttribution.id == attr_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_attribution_by_code(self, attr_code: str) -> Optional[StressLossAttribution]:
        stmt = select(StressLossAttribution).where(StressLossAttribution.attribution_code == attr_code)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_attributions(self, portfolio_id: Optional[str] = None) -> List[StressLossAttribution]:
        stmt = select(StressLossAttribution).order_by(StressLossAttribution.created_at.desc())
        if portfolio_id:
            stmt = stmt.where(StressLossAttribution.portfolio_id == portfolio_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_attribution(self, attr: StressLossAttribution) -> StressLossAttribution:
        self.session.add(attr)
        await self.session.flush()
        return attr

    async def create_run(self, run: StressLossAttributionRun) -> StressLossAttributionRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_run_by_id(self, run_id: str) -> Optional[StressLossAttributionRun]:
        stmt = (
            select(StressLossAttributionRun)
            .where(StressLossAttributionRun.id == run_id)
            .options(
                selectinload(StressLossAttributionRun.position_contributions),
                selectinload(StressLossAttributionRun.sector_contributions),
                selectinload(StressLossAttributionRun.industry_contributions),
                selectinload(StressLossAttributionRun.factor_contributions),
                selectinload(StressLossAttributionRun.interaction_effects),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_run_by_code(self, run_code: str) -> Optional[StressLossAttributionRun]:
        stmt = (
            select(StressLossAttributionRun)
            .where(StressLossAttributionRun.run_code == run_code)
            .options(
                selectinload(StressLossAttributionRun.position_contributions),
                selectinload(StressLossAttributionRun.sector_contributions),
                selectinload(StressLossAttributionRun.industry_contributions),
                selectinload(StressLossAttributionRun.factor_contributions),
                selectinload(StressLossAttributionRun.interaction_effects),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def log_audit_event(
        self,
        attribution_id: str,
        event_type: str,
        actor: str = "system",
        details: Optional[dict] = None,
        attribution_run_id: Optional[str] = None
    ) -> StressLossAttributionAuditLog:
        event = StressLossAttributionAuditLog(
            attribution_id=attribution_id,
            attribution_run_id=attribution_run_id,
            event_type=event_type,
            actor=actor,
            details=details or {}
        )
        self.session.add(event)
        await self.session.flush()
        return event

