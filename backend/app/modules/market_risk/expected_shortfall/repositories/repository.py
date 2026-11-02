"""
Module M07.03: Expected Shortfall Repository.
Provides database access for:
- Configurations
- ES Execution Results
- Tail Observations
- Tail Diagnostics
- Tail Contributions
- Historical Trend Tracking
"""
from datetime import date
from typing import List, Optional
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_risk.expected_shortfall.models import (
    ExpectedShortfallConfig,
    ExpectedShortfallResult,
    ESTailObservation,
    ESDiagnostic,
    ESContribution,
    ESHistory,
    ESMethodology,
)


class ExpectedShortfallRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_config(self, config: ExpectedShortfallConfig) -> ExpectedShortfallConfig:
        self.session.add(config)
        await self.session.flush()
        return config

    async def get_config_by_id(self, config_id: str) -> Optional[ExpectedShortfallConfig]:
        stmt = select(ExpectedShortfallConfig).where(ExpectedShortfallConfig.config_id == config_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_configs(self, portfolio_id: Optional[str] = None) -> List[ExpectedShortfallConfig]:
        stmt = select(ExpectedShortfallConfig).where(ExpectedShortfallConfig.is_active == True)
        if portfolio_id:
            stmt = stmt.where(
                (ExpectedShortfallConfig.portfolio_id == portfolio_id)
                | (ExpectedShortfallConfig.portfolio_id.is_(None))
            )
        stmt = stmt.order_by(desc(ExpectedShortfallConfig.created_at))
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def save_es_result(
        self,
        result: ExpectedShortfallResult,
        tail_observations: Optional[List[ESTailObservation]] = None,
        contributions: Optional[List[ESContribution]] = None,
        diagnostics: Optional[List[ESDiagnostic]] = None,
    ) -> ExpectedShortfallResult:
        self.session.add(result)
        await self.session.flush()

        if tail_observations:
            for obs in tail_observations:
                obs.result_id = result.result_id
                self.session.add(obs)

        if contributions:
            for c in contributions:
                c.result_id = result.result_id
                self.session.add(c)

        if diagnostics:
            for d in diagnostics:
                d.result_id = result.result_id
                self.session.add(d)

        await self.session.flush()
        return result

    async def get_result_by_id(self, result_id: str) -> Optional[ExpectedShortfallResult]:
        stmt = select(ExpectedShortfallResult).where(ExpectedShortfallResult.result_id == result_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_latest_result(
        self, portfolio_id: str, methodology: Optional[ESMethodology] = None
    ) -> Optional[ExpectedShortfallResult]:
        stmt = select(ExpectedShortfallResult).where(ExpectedShortfallResult.portfolio_id == portfolio_id)
        if methodology:
            stmt = stmt.where(ExpectedShortfallResult.methodology == methodology)
        stmt = stmt.order_by(desc(ExpectedShortfallResult.calculated_at)).limit(1)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_tail_observations(self, result_id: str) -> List[ESTailObservation]:
        stmt = (
            select(ESTailObservation)
            .where(ESTailObservation.result_id == result_id)
            .order_by(desc(ESTailObservation.portfolio_loss))
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_contributions(self, result_id: str) -> List[ESContribution]:
        stmt = (
            select(ESContribution)
            .where(ESContribution.result_id == result_id)
            .order_by(desc(ESContribution.contribution_amount))
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_diagnostics(self, result_id: str) -> List[ESDiagnostic]:
        stmt = select(ESDiagnostic).where(ESDiagnostic.result_id == result_id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def record_history_point(self, point: ESHistory) -> ESHistory:
        self.session.add(point)
        await self.session.flush()
        return point

    async def get_history_points(
        self, portfolio_id: str, methodology: Optional[str] = None, limit: int = 30
    ) -> List[ESHistory]:
        stmt = select(ESHistory).where(ESHistory.portfolio_id == portfolio_id)
        if methodology:
            stmt = stmt.where(ESHistory.methodology == methodology)
        stmt = stmt.order_by(desc(ESHistory.as_of_date)).limit(limit)
        res = await self.session.execute(stmt)
        points = list(res.scalars().all())
        points.reverse()  # Return in chronological order
        return points

