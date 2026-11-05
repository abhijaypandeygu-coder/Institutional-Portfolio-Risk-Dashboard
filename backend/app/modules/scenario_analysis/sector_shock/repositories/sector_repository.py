"""
Sector Shock Repository (M10.04).
Async database queries and transactions for:
- Scenarios & scenario versions
- Group shock definitions
- Membership snapshots
- Spillover relationships & versions
- Simulation runs, positions, groups, attributions, warnings, and audit logs
"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from ..models.sector_models import (
    SectorShockScenario,
    SectorShockScenarioVersion,
    SectorShockGroupDefinition,
    SectorShockMembershipSnapshot,
    SectorSpilloverRelationship,
    SectorSpilloverRelationshipVersion,
    SectorShockMappingResult,
    SectorShockSimulationRun,
    SectorShockPositionResult,
    SectorShockGroupResult,
    SectorShockAttributionResult,
    SectorShockWarning,
    SectorShockAuditLog
)


class SectorShockRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ----------------------------------------------------
    # Scenarios & Versions
    # ----------------------------------------------------
    async def create_scenario(self, scenario: SectorShockScenario) -> SectorShockScenario:
        self.db.add(scenario)
        await self.db.flush()
        return scenario

    async def get_scenario(self, scenario_id: str) -> Optional[SectorShockScenario]:
        stmt = (
            select(SectorShockScenario)
            .where(SectorShockScenario.id == scenario_id)
            .options(
                selectinload(SectorShockScenario.versions).selectinload(SectorShockScenarioVersion.group_definitions)
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
    ) -> List[SectorShockScenario]:
        stmt = select(SectorShockScenario).order_by(desc(SectorShockScenario.created_at)).limit(limit)
        if category:
            stmt = stmt.where(SectorShockScenario.category == category)
        if portfolio_id:
            stmt = stmt.where(SectorShockScenario.portfolio_id == portfolio_id)
        if status:
            stmt = stmt.where(SectorShockScenario.status == status)
        
        stmt = stmt.options(
            selectinload(SectorShockScenario.versions).selectinload(SectorShockScenarioVersion.group_definitions)
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def create_scenario_version(self, version: SectorShockScenarioVersion) -> SectorShockScenarioVersion:
        self.db.add(version)
        await self.db.flush()
        return version

    # ----------------------------------------------------
    # Spillover Relationships
    # ----------------------------------------------------
    async def create_spillover_relationship(self, rel: SectorSpilloverRelationship) -> SectorSpilloverRelationship:
        self.db.add(rel)
        await self.db.flush()
        return rel

    async def list_spillover_relationships(self, limit: int = 100) -> List[SectorSpilloverRelationship]:
        stmt = select(SectorSpilloverRelationship).order_by(desc(SectorSpilloverRelationship.created_at)).limit(limit)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    # ----------------------------------------------------
    # Simulation Runs
    # ----------------------------------------------------
    async def create_simulation_run(self, run: SectorShockSimulationRun) -> SectorShockSimulationRun:
        self.db.add(run)
        await self.db.flush()
        return run

    async def get_simulation_run(self, run_id: str) -> Optional[SectorShockSimulationRun]:
        stmt = (
            select(SectorShockSimulationRun)
            .where(SectorShockSimulationRun.id == run_id)
            .options(
                selectinload(SectorShockSimulationRun.position_results),
                selectinload(SectorShockSimulationRun.group_results),
                selectinload(SectorShockSimulationRun.attribution_results),
                selectinload(SectorShockSimulationRun.warnings)
            )
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def save_run_details(
        self,
        snapshots: List[SectorShockMembershipSnapshot],
        mappings: List[SectorShockMappingResult],
        positions: List[SectorShockPositionResult],
        groups: List[SectorShockGroupResult],
        attributions: List[SectorShockAttributionResult],
        warnings: List[SectorShockWarning],
        audit_log: SectorShockAuditLog
    ) -> None:
        for s in snapshots:
            self.db.add(s)
        for m in mappings:
            self.db.add(m)
        for p in positions:
            self.db.add(p)
        for g in groups:
            self.db.add(g)
        for a in attributions:
            self.db.add(a)
        for w in warnings:
            self.db.add(w)
        self.db.add(audit_log)
        await self.db.commit()
