"""
Repository layer for M10.08 Scenario Comparison.
Async SQLAlchemy operations for comparisons, members, runs, results, rankings, and audit logs.
"""

from typing import List, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.scenario_analysis.scenario_comparison.models.comparison_models import (
    ScenarioComparison,
    ScenarioComparisonMember,
    ScenarioComparisonRun,
    ScenarioComparisonMetricResult,
    ScenarioComparisonRanking,
    ScenarioComparisonSensitivity,
    ScenarioComparisonAttribution,
    ScenarioComparisonAuditLog,
)


class ScenarioComparisonRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_comparison_by_id(self, comp_id: str) -> Optional[ScenarioComparison]:
        stmt = (
            select(ScenarioComparison)
            .where(ScenarioComparison.id == comp_id)
            .options(selectinload(ScenarioComparison.members))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_comparison_by_code(self, comp_code: str) -> Optional[ScenarioComparison]:
        stmt = (
            select(ScenarioComparison)
            .where(ScenarioComparison.comparison_code == comp_code)
            .options(selectinload(ScenarioComparison.members))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_comparisons(self, portfolio_id: Optional[str] = None) -> List[ScenarioComparison]:
        stmt = (
            select(ScenarioComparison)
            .options(selectinload(ScenarioComparison.members))
            .order_by(ScenarioComparison.created_at.desc())
        )
        if portfolio_id:
            stmt = stmt.where(ScenarioComparison.portfolio_id == portfolio_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_comparison(self, comp: ScenarioComparison) -> ScenarioComparison:
        self.session.add(comp)
        await self.session.flush()
        return comp

    async def update_comparison(self, comp: ScenarioComparison) -> ScenarioComparison:
        await self.session.flush()
        return comp

    async def delete_comparison(self, comp: ScenarioComparison) -> None:
        await self.session.delete(comp)
        await self.session.flush()

    async def add_member(self, member: ScenarioComparisonMember) -> ScenarioComparisonMember:
        self.session.add(member)
        await self.session.flush()
        return member

    async def remove_member(self, member: ScenarioComparisonMember) -> None:
        await self.session.delete(member)
        await self.session.flush()

    async def get_member(self, member_id: str) -> Optional[ScenarioComparisonMember]:
        stmt = select(ScenarioComparisonMember).where(ScenarioComparisonMember.id == member_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_run(self, run: ScenarioComparisonRun) -> ScenarioComparisonRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_run_by_id(self, run_id: str) -> Optional[ScenarioComparisonRun]:
        stmt = (
            select(ScenarioComparisonRun)
            .where(ScenarioComparisonRun.id == run_id)
            .options(
                selectinload(ScenarioComparisonRun.metric_results),
                selectinload(ScenarioComparisonRun.rankings),
                selectinload(ScenarioComparisonRun.sensitivities),
                selectinload(ScenarioComparisonRun.attributions),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_run_by_code(self, run_code: str) -> Optional[ScenarioComparisonRun]:
        stmt = (
            select(ScenarioComparisonRun)
            .where(ScenarioComparisonRun.run_code == run_code)
            .options(
                selectinload(ScenarioComparisonRun.metric_results),
                selectinload(ScenarioComparisonRun.rankings),
                selectinload(ScenarioComparisonRun.sensitivities),
                selectinload(ScenarioComparisonRun.attributions),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_runs_for_comparison(self, comp_id: str) -> List[ScenarioComparisonRun]:
        stmt = (
            select(ScenarioComparisonRun)
            .where(ScenarioComparisonRun.comparison_id == comp_id)
            .order_by(ScenarioComparisonRun.started_at.desc())
            .options(
                selectinload(ScenarioComparisonRun.metric_results),
                selectinload(ScenarioComparisonRun.rankings),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def log_audit_event(
        self,
        comparison_id: str,
        event_type: str,
        actor: str = "system",
        details: Optional[dict] = None,
        comparison_run_id: Optional[str] = None
    ) -> ScenarioComparisonAuditLog:
        event = ScenarioComparisonAuditLog(
            comparison_id=comparison_id,
            comparison_run_id=comparison_run_id,
            event_type=event_type,
            actor=actor,
            details=details or {}
        )
        self.session.add(event)
        await self.session.flush()
        return event

