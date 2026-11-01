"""
M06.02 Net Exposure Database Repository.
Handles persistence and retrieval of Net Exposure policies, runs,
results, contributions, breakdowns, and threshold events.
"""

from typing import Optional, List
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_management.net_exposure.models import (
    NetExposurePolicy,
    NetExposureCalculationRun,
    NetExposureResult,
    NetExposureContribution,
    NetExposureBreakdown,
    DirectionalThresholdEvent,
)


class NetExposureRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_policy(self, policy: NetExposurePolicy) -> NetExposurePolicy:
        self.session.add(policy)
        await self.session.flush()
        return policy

    async def get_policy_by_id(self, policy_id: str) -> Optional[NetExposurePolicy]:
        stmt = select(NetExposurePolicy).where(NetExposurePolicy.id == policy_id)
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_active_policy(
        self, portfolio_id: Optional[str] = None, group_id: Optional[str] = None
    ) -> Optional[NetExposurePolicy]:
        stmt = select(NetExposurePolicy)
        if portfolio_id:
            stmt = stmt.where(NetExposurePolicy.portfolio_id == portfolio_id)
        elif group_id:
            stmt = stmt.where(NetExposurePolicy.group_id == group_id)
        else:
            stmt = stmt.where(and_(NetExposurePolicy.portfolio_id.is_(None), NetExposurePolicy.group_id.is_(None)))
        stmt = stmt.order_by(desc(NetExposurePolicy.created_at))
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def save_run(self, run: NetExposureCalculationRun) -> NetExposureCalculationRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_run_by_id(self, run_id: str) -> Optional[NetExposureCalculationRun]:
        stmt = select(NetExposureCalculationRun).where(NetExposureCalculationRun.id == run_id)
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_run_by_idempotency(self, key: str) -> Optional[NetExposureCalculationRun]:
        stmt = select(NetExposureCalculationRun).where(NetExposureCalculationRun.idempotency_key == key)
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def save_result(self, result: NetExposureResult) -> NetExposureResult:
        self.session.add(result)
        await self.session.flush()
        return result

    async def get_result_by_run_id(self, run_id: str) -> Optional[NetExposureResult]:
        stmt = select(NetExposureResult).where(NetExposureResult.calculation_run_id == run_id)
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def save_contributions(self, contributions: List[NetExposureContribution]) -> None:
        self.session.add_all(contributions)
        await self.session.flush()

    async def get_contributions(self, run_id: str) -> List[NetExposureContribution]:
        stmt = select(NetExposureContribution).where(NetExposureContribution.calculation_run_id == run_id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def save_breakdowns(self, breakdowns: List[NetExposureBreakdown]) -> None:
        self.session.add_all(breakdowns)
        await self.session.flush()

    async def get_breakdowns(self, run_id: str) -> List[NetExposureBreakdown]:
        stmt = select(NetExposureBreakdown).where(NetExposureBreakdown.calculation_run_id == run_id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def save_threshold_events(self, events: List[DirectionalThresholdEvent]) -> None:
        self.session.add_all(events)
        await self.session.flush()

    async def get_threshold_events(self, run_id: str) -> List[DirectionalThresholdEvent]:
        stmt = select(DirectionalThresholdEvent).where(DirectionalThresholdEvent.calculation_run_id == run_id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

