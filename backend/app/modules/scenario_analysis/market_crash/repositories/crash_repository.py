"""
Market Crash Simulation Repository (M10.03).
Async database queries and transactions for:
- Scenarios & scenario versions
- Benchmark shocks
- Mapping rules & mapping results
- Sensitivity snapshots
- Nonlinear parameters
- Simulation runs, position results, summaries, attributions, warnings, and audit logs
"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from ..models.crash_models import (
    MarketCrashScenario,
    MarketCrashScenarioVersion,
    MarketCrashBenchmarkShock,
    MarketCrashMappingRule,
    MarketCrashMappingResult,
    MarketCrashSensitivitySnapshot,
    MarketCrashNonlinearParameter,
    MarketCrashSimulationRun,
    MarketCrashPositionResult,
    MarketCrashSummaryResult,
    MarketCrashAttributionResult,
    MarketCrashWarning,
    MarketCrashAuditLog
)


class MarketCrashRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ----------------------------------------------------
    # Scenarios & Versions
    # ----------------------------------------------------
    async def create_scenario(self, scenario: MarketCrashScenario) -> MarketCrashScenario:
        self.db.add(scenario)
        await self.db.flush()
        return scenario

    async def get_scenario(self, scenario_id: str) -> Optional[MarketCrashScenario]:
        stmt = (
            select(MarketCrashScenario)
            .where(MarketCrashScenario.id == scenario_id)
            .options(
                selectinload(MarketCrashScenario.versions).selectinload(MarketCrashScenarioVersion.benchmark_shocks),
                selectinload(MarketCrashScenario.versions).selectinload(MarketCrashScenarioVersion.nonlinear_parameters)
            )
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_scenarios(
        self,
        category: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[MarketCrashScenario]:
        stmt = select(MarketCrashScenario).order_by(desc(MarketCrashScenario.created_at)).limit(limit)
        if category:
            stmt = stmt.where(MarketCrashScenario.category == category)
        if portfolio_id:
            stmt = stmt.where(MarketCrashScenario.portfolio_id == portfolio_id)
        if status:
            stmt = stmt.where(MarketCrashScenario.status == status)
        
        stmt = stmt.options(
            selectinload(MarketCrashScenario.versions).selectinload(MarketCrashScenarioVersion.benchmark_shocks),
            selectinload(MarketCrashScenario.versions).selectinload(MarketCrashScenarioVersion.nonlinear_parameters)
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def create_scenario_version(self, version: MarketCrashScenarioVersion) -> MarketCrashScenarioVersion:
        self.db.add(version)
        await self.db.flush()
        return version

    # ----------------------------------------------------
    # Simulation Runs
    # ----------------------------------------------------
    async def create_simulation_run(self, run: MarketCrashSimulationRun) -> MarketCrashSimulationRun:
        self.db.add(run)
        await self.db.flush()
        return run

    async def get_simulation_run(self, run_id: str) -> Optional[MarketCrashSimulationRun]:
        stmt = (
            select(MarketCrashSimulationRun)
            .where(MarketCrashSimulationRun.id == run_id)
            .options(
                selectinload(MarketCrashSimulationRun.position_results),
                selectinload(MarketCrashSimulationRun.summary_results),
                selectinload(MarketCrashSimulationRun.attribution_results),
                selectinload(MarketCrashSimulationRun.warnings)
            )
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_simulation_runs(
        self,
        portfolio_id: Optional[str] = None,
        scenario_id: Optional[str] = None,
        limit: int = 50
    ) -> List[MarketCrashSimulationRun]:
        stmt = select(MarketCrashSimulationRun).order_by(desc(MarketCrashSimulationRun.started_at)).limit(limit)
        if portfolio_id:
            stmt = stmt.where(MarketCrashSimulationRun.portfolio_id == portfolio_id)
        if scenario_id:
            stmt = stmt.where(MarketCrashSimulationRun.scenario_id == scenario_id)
        
        stmt = stmt.options(
            selectinload(MarketCrashSimulationRun.summary_results),
            selectinload(MarketCrashSimulationRun.warnings)
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_run_details(
        self,
        mappings: List[MarketCrashMappingResult],
        sensitivities: List[MarketCrashSensitivitySnapshot],
        positions: List[MarketCrashPositionResult],
        summary: MarketCrashSummaryResult,
        attributions: List[MarketCrashAttributionResult],
        warnings: List[MarketCrashWarning],
        audit_log: MarketCrashAuditLog
    ) -> None:
        for m in mappings:
            self.db.add(m)
        for s in sensitivities:
            self.db.add(s)
        for p in positions:
            self.db.add(p)
        self.db.add(summary)
        for a in attributions:
            self.db.add(a)
        for w in warnings:
            self.db.add(w)
        self.db.add(audit_log)
        await self.db.commit()
