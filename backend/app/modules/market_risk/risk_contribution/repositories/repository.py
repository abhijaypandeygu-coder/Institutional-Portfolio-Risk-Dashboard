"""
M07.09 Risk Contribution Database Repository.
Handles CRUD and persistence operations for runs, holding contributions,
group attributions, and historical queries.
"""
from datetime import date
from typing import List, Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.market_risk.risk_contribution.models import (
    RiskContributionCalculationRun,
    HoldingRiskContributionResult,
    GroupRiskContributionResult,
    GroupingDimension,
)


class RiskContributionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_calculation_run(
        self, run: RiskContributionCalculationRun
    ) -> RiskContributionCalculationRun:
        """Persist a new calculation run along with its holding and group contributions."""
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def get_calculation_run(
        self, calculation_id: str
    ) -> Optional[RiskContributionCalculationRun]:
        """Fetch calculation run with holding and group contributions eagerly loaded."""
        stmt = (
            select(RiskContributionCalculationRun)
            .where(RiskContributionCalculationRun.calculation_id == calculation_id)
            .options(
                selectinload(RiskContributionCalculationRun.holding_contributions),
                selectinload(RiskContributionCalculationRun.group_contributions),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_latest_run_for_portfolio(
        self, portfolio_id: str, as_of_date: Optional[date] = None
    ) -> Optional[RiskContributionCalculationRun]:
        """Fetch the most recent calculation run for a portfolio."""
        stmt = (
            select(RiskContributionCalculationRun)
            .where(RiskContributionCalculationRun.portfolio_id == portfolio_id)
        )
        if as_of_date:
            stmt = stmt.where(RiskContributionCalculationRun.as_of_date <= as_of_date)
        
        stmt = (
            stmt.order_by(desc(RiskContributionCalculationRun.as_of_date), desc(RiskContributionCalculationRun.calculated_at))
            .options(
                selectinload(RiskContributionCalculationRun.holding_contributions),
                selectinload(RiskContributionCalculationRun.group_contributions),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_holding_contributions(
        self, calculation_id: str
    ) -> List[HoldingRiskContributionResult]:
        """Fetch holding-level contributions for a specific calculation run."""
        stmt = (
            select(HoldingRiskContributionResult)
            .where(HoldingRiskContributionResult.calculation_id == calculation_id)
            .order_by(desc(HoldingRiskContributionResult.component_risk_contribution))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_group_contributions(
        self, calculation_id: str, dimension: Optional[GroupingDimension] = None
    ) -> List[GroupRiskContributionResult]:
        """Fetch group-level contributions for a specific calculation run and optional dimension."""
        stmt = (
            select(GroupRiskContributionResult)
            .where(GroupRiskContributionResult.calculation_id == calculation_id)
        )
        if dimension:
            stmt = stmt.where(GroupRiskContributionResult.dimension == dimension)
        
        stmt = stmt.order_by(desc(GroupRiskContributionResult.component_risk_contribution))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
