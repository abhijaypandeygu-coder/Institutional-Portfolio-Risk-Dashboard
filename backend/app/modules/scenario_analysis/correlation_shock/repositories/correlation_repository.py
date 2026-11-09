"""
M10.05 Correlation Shock SQLAlchemy Repository.
"""
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.scenario_analysis.correlation_shock.models import (
    CorrelationShockScenario,
    CorrelationShockScenarioVersion,
    CorrelationShockScopeMember,
    CorrelationShockPairRule,
    CorrelationShockExecution,
    CorrelationShockMatrixDiagnostic,
    CorrelationShockRepair,
    CorrelationShockRiskResult,
    CorrelationShockRiskContribution,
    CorrelationShockAuditLog,
    ScenarioStatus,
    ExecutionStatus,
)


class CorrelationShockRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_scenario(self, scenario: CorrelationShockScenario) -> CorrelationShockScenario:
        self.session.add(scenario)
        await self.session.flush()
        return scenario

    async def get_scenario_by_id(self, scenario_id: str) -> Optional[CorrelationShockScenario]:
        stmt = (
            select(CorrelationShockScenario)
            .options(
                selectinload(CorrelationShockScenario.versions)
                .selectinload(CorrelationShockScenarioVersion.scope_members),
                selectinload(CorrelationShockScenario.versions)
                .selectinload(CorrelationShockScenarioVersion.pair_rules),
            )
            .where(CorrelationShockScenario.id == scenario_id)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_scenario_by_code(self, scenario_code: str) -> Optional[CorrelationShockScenario]:
        stmt = (
            select(CorrelationShockScenario)
            .options(
                selectinload(CorrelationShockScenario.versions)
                .selectinload(CorrelationShockScenarioVersion.scope_members),
                selectinload(CorrelationShockScenario.versions)
                .selectinload(CorrelationShockScenarioVersion.pair_rules),
            )
            .where(CorrelationShockScenario.scenario_code == scenario_code)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_scenarios(
        self, portfolio_id: Optional[str] = None, status: Optional[ScenarioStatus] = None
    ) -> List[CorrelationShockScenario]:
        stmt = select(CorrelationShockScenario).options(
            selectinload(CorrelationShockScenario.versions)
        ).order_by(desc(CorrelationShockScenario.created_at))
        if portfolio_id:
            stmt = stmt.where(CorrelationShockScenario.portfolio_id == portfolio_id)
        if status:
            stmt = stmt.where(CorrelationShockScenario.status == status)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def create_scenario_version(
        self, version: CorrelationShockScenarioVersion
    ) -> CorrelationShockScenarioVersion:
        self.session.add(version)
        await self.session.flush()
        return version

    async def get_latest_version(self, scenario_id: str) -> Optional[CorrelationShockScenarioVersion]:
        stmt = (
            select(CorrelationShockScenarioVersion)
            .options(
                selectinload(CorrelationShockScenarioVersion.scope_members),
                selectinload(CorrelationShockScenarioVersion.pair_rules),
            )
            .where(CorrelationShockScenarioVersion.scenario_id == scenario_id)
            .order_by(desc(CorrelationShockScenarioVersion.version_number))
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def create_execution(self, execution: CorrelationShockExecution) -> CorrelationShockExecution:
        self.session.add(execution)
        await self.session.flush()
        return execution

    async def get_execution_by_id(self, execution_id: str) -> Optional[CorrelationShockExecution]:
        stmt = (
            select(CorrelationShockExecution)
            .options(
                selectinload(CorrelationShockExecution.diagnostics),
                selectinload(CorrelationShockExecution.repairs),
                selectinload(CorrelationShockExecution.risk_results),
                selectinload(CorrelationShockExecution.risk_contributions),
                selectinload(CorrelationShockExecution.audit_logs),
            )
            .where(CorrelationShockExecution.id == execution_id)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_executions(
        self, scenario_version_id: Optional[str] = None, portfolio_id: Optional[str] = None
    ) -> List[CorrelationShockExecution]:
        stmt = select(CorrelationShockExecution).order_by(desc(CorrelationShockExecution.started_at))
        if scenario_version_id:
            stmt = stmt.where(CorrelationShockExecution.scenario_version_id == scenario_version_id)
        if portfolio_id:
            stmt = stmt.where(CorrelationShockExecution.portfolio_id == portfolio_id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def log_audit_event(
        self, execution_id: Optional[str], event_type: str, payload: Dict[str, Any], actor_id: str = "system"
    ) -> CorrelationShockAuditLog:
        log = CorrelationShockAuditLog(
            execution_id=execution_id,
            event_type=event_type,
            actor_id=actor_id,
            event_payload=payload,
        )
        self.session.add(log)
        await self.session.flush()
        return log
