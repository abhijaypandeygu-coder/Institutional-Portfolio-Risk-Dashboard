"""
Hypothetical Scenarios Repository (M10.02).
Provides database persistence and queries for templates, executions, positions, risk, and liquidity.
"""

from typing import List, Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.hypothetical_models import (
    HypotheticalScenarioTemplate,
    HypotheticalScenarioTemplateVersion,
    HypotheticalScenarioRun,
    HypotheticalScenarioPositionResult,
    HypotheticalScenarioRiskResult,
    HypotheticalScenarioLiquidityResult,
    HypotheticalScenarioWarning,
    HypotheticalScenarioAuditLog
)


class HypotheticalScenariosRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_template(self, template: HypotheticalScenarioTemplate) -> HypotheticalScenarioTemplate:
        self.db.add(template)
        await self.db.flush()
        return template

    async def get_template_by_id(self, template_id: str) -> Optional[HypotheticalScenarioTemplate]:
        stmt = select(HypotheticalScenarioTemplate).where(HypotheticalScenarioTemplate.id == template_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_template_by_code(self, template_code: str) -> Optional[HypotheticalScenarioTemplate]:
        stmt = select(HypotheticalScenarioTemplate).where(HypotheticalScenarioTemplate.template_code == template_code)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_templates(
        self,
        category: Optional[str] = None,
        author_id: Optional[str] = None,
        limit: int = 50
    ) -> List[HypotheticalScenarioTemplate]:
        stmt = select(HypotheticalScenarioTemplate)
        if category:
            stmt = stmt.where(HypotheticalScenarioTemplate.category == category)
        if author_id:
            stmt = stmt.where(HypotheticalScenarioTemplate.author_id == author_id)
        stmt = stmt.order_by(desc(HypotheticalScenarioTemplate.created_at)).limit(limit)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_template_version(self, ver: HypotheticalScenarioTemplateVersion) -> HypotheticalScenarioTemplateVersion:
        self.db.add(ver)
        await self.db.flush()
        return ver

    async def save_run(self, run: HypotheticalScenarioRun) -> HypotheticalScenarioRun:
        self.db.add(run)
        await self.db.flush()
        return run

    async def get_run_by_id(self, run_id: str) -> Optional[HypotheticalScenarioRun]:
        stmt = select(HypotheticalScenarioRun).where(HypotheticalScenarioRun.id == run_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def save_positions(self, positions: List[HypotheticalScenarioPositionResult]):
        self.db.add_all(positions)
        await self.db.flush()

    async def save_risk_results(self, risk_results: List[HypotheticalScenarioRiskResult]):
        self.db.add_all(risk_results)
        await self.db.flush()

    async def save_liquidity_results(self, liquidity_results: List[HypotheticalScenarioLiquidityResult]):
        self.db.add_all(liquidity_results)
        await self.db.flush()

    async def save_warnings(self, warnings: List[HypotheticalScenarioWarning]):
        self.db.add_all(warnings)
        await self.db.flush()

    async def save_audit_log(self, log: HypotheticalScenarioAuditLog) -> HypotheticalScenarioAuditLog:
        self.db.add(log)
        await self.db.flush()
        return log
