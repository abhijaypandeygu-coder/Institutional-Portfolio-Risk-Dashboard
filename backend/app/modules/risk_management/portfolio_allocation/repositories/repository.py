"""
Repository layer for M06.07 Portfolio Allocation.
"""

from typing import Optional, List
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.risk_management.portfolio_allocation.models import (
    PortfolioAllocationResult,
    PortfolioAllocationComponent,
    PortfolioAllocationTarget,
    PortfolioAllocationDrift,
    PortfolioAllocationComparison,
    AllocationGroupingDimension,
    AllocationViewType,
)


class PortfolioAllocationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_result(self, result: PortfolioAllocationResult) -> PortfolioAllocationResult:
        self.session.add(result)
        await self.session.flush()
        return result

    async def get_result_by_id(self, result_id: str) -> Optional[PortfolioAllocationResult]:
        stmt = (
            select(PortfolioAllocationResult)
            .where(PortfolioAllocationResult.result_id == result_id)
            .options(selectinload(PortfolioAllocationResult.components))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_latest_result(
        self,
        portfolio_id: Optional[str] = None,
        portfolio_group_id: Optional[str] = None,
        grouping_dimension: Optional[AllocationGroupingDimension] = None,
        allocation_view_type: Optional[AllocationViewType] = None,
    ) -> Optional[PortfolioAllocationResult]:
        stmt = select(PortfolioAllocationResult)
        if portfolio_id:
            stmt = stmt.where(PortfolioAllocationResult.portfolio_id == portfolio_id)
        if portfolio_group_id:
            stmt = stmt.where(PortfolioAllocationResult.portfolio_group_id == portfolio_group_id)
        if grouping_dimension:
            stmt = stmt.where(PortfolioAllocationResult.grouping_dimension == grouping_dimension)
        if allocation_view_type:
            stmt = stmt.where(PortfolioAllocationResult.allocation_view_type == allocation_view_type)

        stmt = stmt.order_by(desc(PortfolioAllocationResult.calculated_at)).options(
            selectinload(PortfolioAllocationResult.components)
        ).limit(1)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_target(self, target: PortfolioAllocationTarget) -> PortfolioAllocationTarget:
        self.session.add(target)
        await self.session.flush()
        return target

    async def list_active_targets(
        self,
        portfolio_id: Optional[str] = None,
        portfolio_group_id: Optional[str] = None,
        grouping_dimension: Optional[AllocationGroupingDimension] = None,
    ) -> List[PortfolioAllocationTarget]:
        stmt = select(PortfolioAllocationTarget).where(PortfolioAllocationTarget.is_active.is_(True))
        if portfolio_id:
            stmt = stmt.where(
                (PortfolioAllocationTarget.portfolio_id == portfolio_id) | (PortfolioAllocationTarget.portfolio_id.is_(None))
            )
        if portfolio_group_id:
            stmt = stmt.where(
                (PortfolioAllocationTarget.portfolio_group_id == portfolio_group_id) | (PortfolioAllocationTarget.portfolio_group_id.is_(None))
            )
        if grouping_dimension:
            stmt = stmt.where(PortfolioAllocationTarget.grouping_dimension == grouping_dimension)

        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def create_drifts(self, drifts: List[PortfolioAllocationDrift]) -> List[PortfolioAllocationDrift]:
        self.session.add_all(drifts)
        await self.session.flush()
        return drifts

    async def list_drifts_by_result(self, result_id: str) -> List[PortfolioAllocationDrift]:
        stmt = (
            select(PortfolioAllocationDrift)
            .where(PortfolioAllocationDrift.result_id == result_id)
            .order_by(desc(PortfolioAllocationDrift.absolute_drift_pp))
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def create_comparison(self, comp: PortfolioAllocationComparison) -> PortfolioAllocationComparison:
        self.session.add(comp)
        await self.session.flush()
        return comp

