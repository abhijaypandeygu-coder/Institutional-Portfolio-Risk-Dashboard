"""
M06.01 Gross Exposure Repository.
Data access layer for exposure policies, calculation runs, results, contributions, and breakdowns.
"""

from datetime import datetime
from typing import Optional, List, Sequence
from sqlalchemy import select, and_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.modules.risk_management.gross_exposure.models import (
    ExposurePolicy,
    ExposureCalculationRun,
    ExposureResult,
    ExposureContribution,
    ExposureBreakdown,
    ExposureThresholdEvent,
)


class GrossExposureRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ==========================================
    # Policy Management
    # ==========================================

    async def create_policy(self, policy: ExposurePolicy) -> ExposurePolicy:
        self.session.add(policy)
        await self.session.flush()
        return policy

    async def get_effective_policy(
        self,
        portfolio_id: Optional[str] = None,
        group_id: Optional[str] = None,
        as_of: Optional[datetime] = None,
    ) -> Optional[ExposurePolicy]:
        as_of_time = as_of or datetime.utcnow()
        conditions = [
            ExposurePolicy.effective_from <= as_of_time,
            ExposurePolicy.approval_status == "APPROVED",
        ]
        if portfolio_id:
            conditions.append(ExposurePolicy.portfolio_id == portfolio_id)
        elif group_id:
            conditions.append(ExposurePolicy.group_id == group_id)

        stmt = (
            select(ExposurePolicy)
            .where(and_(*conditions))
            .order_by(desc(ExposurePolicy.policy_version))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    # ==========================================
    # Calculation Runs & Results
    # ==========================================

    async def create_calculation_run(self, run: ExposureCalculationRun) -> ExposureCalculationRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_calculation_run(self, run_id: str) -> Optional[ExposureCalculationRun]:
        stmt = select(ExposureCalculationRun).where(ExposureCalculationRun.id == run_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_latest_run_for_entity(
        self,
        portfolio_id: Optional[str] = None,
        group_id: Optional[str] = None,
    ) -> Optional[ExposureCalculationRun]:
        conditions = []
        if portfolio_id:
            conditions.append(ExposureCalculationRun.portfolio_id == portfolio_id)
        elif group_id:
            conditions.append(ExposureCalculationRun.group_id == group_id)

        stmt = (
            select(ExposureCalculationRun)
            .where(and_(*conditions))
            .order_by(desc(ExposureCalculationRun.effective_as_of), desc(ExposureCalculationRun.created_at))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_run_result(self, run_id: str) -> Optional[ExposureResult]:
        stmt = select(ExposureResult).where(ExposureResult.calculation_run_id == run_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_run_contributions(self, run_id: str) -> Sequence[ExposureContribution]:
        stmt = (
            select(ExposureContribution)
            .where(ExposureContribution.calculation_run_id == run_id)
            .order_by(asc(ExposureContribution.instrument_id))
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def get_run_breakdowns(self, run_id: str) -> Sequence[ExposureBreakdown]:
        stmt = (
            select(ExposureBreakdown)
            .where(ExposureBreakdown.calculation_run_id == run_id)
            .order_by(asc(ExposureBreakdown.breakdown_type), desc(ExposureBreakdown.gross_exposure))
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def get_run_threshold_events(self, run_id: str) -> Sequence[ExposureThresholdEvent]:
        stmt = select(ExposureThresholdEvent).where(ExposureThresholdEvent.calculation_run_id == run_id)
        res = await self.session.execute(stmt)
        return res.scalars().all()
