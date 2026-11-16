"""
Asynchronous repository for M10.07 Monte Carlo Scenarios.
Handles database persistence, queries, updates, and audit trails.
"""

from typing import List, Optional
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.scenario_analysis.monte_carlo.models.monte_carlo_models import (
    MonteCarloScenario,
    MonteCarloSimulationRun,
    MonteCarloSimulationSummary,
    MonteCarloRiskMetric,
    MonteCarloInstrumentResult,
    MonteCarloAuditEvent,
)


class MonteCarloRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_scenario_by_id(self, scenario_id: str) -> Optional[MonteCarloScenario]:
        stmt = select(MonteCarloScenario).where(MonteCarloScenario.id == scenario_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_scenario_by_code(self, scenario_code: str) -> Optional[MonteCarloScenario]:
        stmt = select(MonteCarloScenario).where(MonteCarloScenario.scenario_code == scenario_code)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_scenarios(self, active_only: bool = True) -> List[MonteCarloScenario]:
        stmt = select(MonteCarloScenario)
        if active_only:
            stmt = stmt.where(MonteCarloScenario.is_active.is_(True))
        stmt = stmt.order_by(MonteCarloScenario.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_scenario(self, scenario: MonteCarloScenario) -> MonteCarloScenario:
        self.session.add(scenario)
        await self.session.flush()
        return scenario

    async def update_scenario(self, scenario: MonteCarloScenario) -> MonteCarloScenario:
        await self.session.flush()
        return scenario

    async def delete_scenario(self, scenario: MonteCarloScenario) -> None:
        await self.session.delete(scenario)
        await self.session.flush()

    async def create_simulation_run(self, run: MonteCarloSimulationRun) -> MonteCarloSimulationRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_simulation_run_by_id(self, run_id: str) -> Optional[MonteCarloSimulationRun]:
        stmt = (
            select(MonteCarloSimulationRun)
            .where(MonteCarloSimulationRun.id == run_id)
            .options(
                selectinload(MonteCarloSimulationRun.scenario),
                selectinload(MonteCarloSimulationRun.summary),
                selectinload(MonteCarloSimulationRun.risk_metrics),
                selectinload(MonteCarloSimulationRun.instrument_results),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_simulation_run_by_code(self, run_code: str) -> Optional[MonteCarloSimulationRun]:
        stmt = (
            select(MonteCarloSimulationRun)
            .where(MonteCarloSimulationRun.run_code == run_code)
            .options(
                selectinload(MonteCarloSimulationRun.scenario),
                selectinload(MonteCarloSimulationRun.summary),
                selectinload(MonteCarloSimulationRun.risk_metrics),
                selectinload(MonteCarloSimulationRun.instrument_results),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_runs_for_scenario(self, scenario_id: str, limit: int = 50) -> List[MonteCarloSimulationRun]:
        stmt = (
            select(MonteCarloSimulationRun)
            .where(MonteCarloSimulationRun.scenario_id == scenario_id)
            .order_by(MonteCarloSimulationRun.executed_at.desc())
            .limit(limit)
            .options(
                selectinload(MonteCarloSimulationRun.summary),
                selectinload(MonteCarloSimulationRun.risk_metrics),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def log_audit_event(
        self,
        action: str,
        actor: str = "system",
        details: Optional[dict] = None,
        run_id: Optional[str] = None
    ) -> MonteCarloAuditEvent:
        event = MonteCarloAuditEvent(
            action=action,
            actor=actor,
            details=details or {},
            run_id=run_id
        )
        self.session.add(event)
        await self.session.flush()
        return event

