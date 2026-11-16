"""
M10.06 Liquidity Stress Testing SQLAlchemy Repository.
"""
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.scenario_analysis.liquidity_stress.models import (
    LiquidityStressScenario,
    LiquidityStressConfiguration,
    LiquidityStressInstrumentOverride,
    LiquidityStressRun,
    LiquidityStressMarketSnapshot,
    LiquidityStressDepthLevel,
    LiquidityStressPositionResult,
    LiquidityStressHorizonResult,
    LiquidityStressCostAttribution,
    LiquidityStressAuditEvent,
    ScenarioStatus,
    RunStatus,
)


class LiquidityStressRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_scenario(self, scenario: LiquidityStressScenario) -> LiquidityStressScenario:
        self.session.add(scenario)
        await self.session.flush()
        return scenario

    async def get_scenario_by_id(self, scenario_id: str) -> Optional[LiquidityStressScenario]:
        stmt = (
            select(LiquidityStressScenario)
            .options(
                selectinload(LiquidityStressScenario.configurations),
                selectinload(LiquidityStressScenario.overrides),
            )
            .where(LiquidityStressScenario.id == scenario_id)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_scenario_by_code(self, scenario_code: str) -> Optional[LiquidityStressScenario]:
        stmt = (
            select(LiquidityStressScenario)
            .options(
                selectinload(LiquidityStressScenario.configurations),
                selectinload(LiquidityStressScenario.overrides),
            )
            .where(LiquidityStressScenario.scenario_code == scenario_code)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_scenarios(
        self, status: Optional[ScenarioStatus] = None
    ) -> List[LiquidityStressScenario]:
        stmt = select(LiquidityStressScenario).options(
            selectinload(LiquidityStressScenario.configurations)
        ).order_by(desc(LiquidityStressScenario.created_at))
        if status:
            stmt = stmt.where(LiquidityStressScenario.status == status)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def create_configuration(
        self, config: LiquidityStressConfiguration
    ) -> LiquidityStressConfiguration:
        self.session.add(config)
        await self.session.flush()
        return config

    async def get_latest_configuration(
        self, scenario_id: str
    ) -> Optional[LiquidityStressConfiguration]:
        stmt = (
            select(LiquidityStressConfiguration)
            .where(LiquidityStressConfiguration.scenario_id == scenario_id)
            .order_by(desc(LiquidityStressConfiguration.version_number))
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def create_run(self, run: LiquidityStressRun) -> LiquidityStressRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_run_by_id(self, run_id: str) -> Optional[LiquidityStressRun]:
        stmt = (
            select(LiquidityStressRun)
            .options(
                selectinload(LiquidityStressRun.market_snapshots).selectinload(LiquidityStressMarketSnapshot.depth_levels),
                selectinload(LiquidityStressRun.position_results),
                selectinload(LiquidityStressRun.horizon_results),
                selectinload(LiquidityStressRun.cost_attributions),
                selectinload(LiquidityStressRun.audit_events),
            )
            .where(LiquidityStressRun.id == run_id)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_runs_by_portfolio(
        self, portfolio_id: str
    ) -> List[LiquidityStressRun]:
        stmt = (
            select(LiquidityStressRun)
            .where(LiquidityStressRun.portfolio_id == portfolio_id)
            .order_by(desc(LiquidityStressRun.started_at))
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def log_audit_event(
        self, run_id: str, event_type: str, description: str, payload: Optional[Dict[str, Any]] = None, user_id: str = "system"
    ) -> LiquidityStressAuditEvent:
        log = LiquidityStressAuditEvent(
            run_id=run_id,
            event_type=event_type,
            event_description=description,
            user_id=user_id,
            event_metadata=payload or {},
        )
        self.session.add(log)
        await self.session.flush()
        return log
