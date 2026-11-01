"""
Repository layer for M06.06 Concentration Analytics.
"""

from typing import Optional, List
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.risk_management.concentration_analytics.models import (
    ConcentrationResult,
    ConcentrationContributor,
    ConcentrationComparison,
    ConcentrationPolicy,
    ConcentrationGroupingDimension,
    ConcentrationExposureBasis,
)


class ConcentrationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_result(self, result: ConcentrationResult) -> ConcentrationResult:
        self.session.add(result)
        await self.session.flush()
        return result

    async def get_result_by_id(self, result_id: str) -> Optional[ConcentrationResult]:
        stmt = (
            select(ConcentrationResult)
            .where(ConcentrationResult.result_id == result_id)
            .options(selectinload(ConcentrationResult.contributors))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_latest_result(
        self,
        portfolio_id: Optional[str] = None,
        portfolio_group_id: Optional[str] = None,
        grouping_dimension: Optional[ConcentrationGroupingDimension] = None,
        exposure_basis: Optional[ConcentrationExposureBasis] = None,
    ) -> Optional[ConcentrationResult]:
        stmt = select(ConcentrationResult)
        if portfolio_id:
            stmt = stmt.where(ConcentrationResult.portfolio_id == portfolio_id)
        if portfolio_group_id:
            stmt = stmt.where(ConcentrationResult.portfolio_group_id == portfolio_group_id)
        if grouping_dimension:
            stmt = stmt.where(ConcentrationResult.grouping_dimension == grouping_dimension)
        if exposure_basis:
            stmt = stmt.where(ConcentrationResult.exposure_basis == exposure_basis)

        stmt = stmt.order_by(desc(ConcentrationResult.calculated_at)).options(
            selectinload(ConcentrationResult.contributors)
        ).limit(1)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_results(
        self,
        portfolio_id: Optional[str] = None,
        portfolio_group_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[ConcentrationResult]:
        stmt = select(ConcentrationResult)
        if portfolio_id:
            stmt = stmt.where(ConcentrationResult.portfolio_id == portfolio_id)
        if portfolio_group_id:
            stmt = stmt.where(ConcentrationResult.portfolio_group_id == portfolio_group_id)
        stmt = stmt.order_by(desc(ConcentrationResult.calculated_at)).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def create_comparison(self, comparison: ConcentrationComparison) -> ConcentrationComparison:
        self.session.add(comparison)
        await self.session.flush()
        return comparison

    async def get_comparison_by_id(self, comparison_id: str) -> Optional[ConcentrationComparison]:
        stmt = select(ConcentrationComparison).where(ConcentrationComparison.comparison_id == comparison_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_policy(self, policy: ConcentrationPolicy) -> ConcentrationPolicy:
        self.session.add(policy)
        await self.session.flush()
        return policy

    async def get_active_policy(
        self,
        portfolio_id: Optional[str] = None,
        portfolio_group_id: Optional[str] = None,
        grouping_dimension: Optional[ConcentrationGroupingDimension] = None,
        exposure_basis: Optional[ConcentrationExposureBasis] = None,
    ) -> Optional[ConcentrationPolicy]:
        stmt = select(ConcentrationPolicy).where(ConcentrationPolicy.is_active.is_(True))
        if portfolio_id:
            stmt = stmt.where(
                (ConcentrationPolicy.portfolio_id == portfolio_id) | (ConcentrationPolicy.portfolio_id.is_(None))
            )
        if portfolio_group_id:
            stmt = stmt.where(
                (ConcentrationPolicy.portfolio_group_id == portfolio_group_id) | (ConcentrationPolicy.portfolio_group_id.is_(None))
            )
        if grouping_dimension:
            stmt = stmt.where(ConcentrationPolicy.grouping_dimension == grouping_dimension)
        if exposure_basis:
            stmt = stmt.where(ConcentrationPolicy.exposure_basis == exposure_basis)

        stmt = stmt.order_by(desc(ConcentrationPolicy.created_at)).limit(1)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

