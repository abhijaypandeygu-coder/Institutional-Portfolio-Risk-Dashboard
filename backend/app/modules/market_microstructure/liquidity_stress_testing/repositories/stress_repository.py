"""
Repository layer for M09.06 Liquidity Stress Testing.
"""

from typing import List, Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_microstructure.liquidity_stress_testing.models.stress_models import (
    LiquidityStressConfig,
    LiquidityStressScenarioRun,
    LiquidityStressMonitoringSnapshot,
)


class LiquidityStressRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_config_by_code(self, scenario_code: str) -> Optional[LiquidityStressConfig]:
        stmt = (
            select(LiquidityStressConfig)
            .where(
                LiquidityStressConfig.scenario_code == scenario_code,
                LiquidityStressConfig.is_active == True,
            )
            .order_by(desc(LiquidityStressConfig.version))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_config(self, config: LiquidityStressConfig) -> LiquidityStressConfig:
        self.session.add(config)
        await self.session.flush()
        return config

    async def list_configs(self) -> List[LiquidityStressConfig]:
        stmt = (
            select(LiquidityStressConfig)
            .where(LiquidityStressConfig.is_active == True)
            .order_by(LiquidityStressConfig.scenario_code)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def save_scenario_run(self, run: LiquidityStressScenarioRun) -> LiquidityStressScenarioRun:
        existing = await self.get_scenario_run(run.run_id)
        if existing:
            existing.baseline_spread = run.baseline_spread
            existing.stressed_spread = run.stressed_spread
            existing.baseline_visible_depth = run.baseline_visible_depth
            existing.stressed_visible_depth = run.stressed_visible_depth
            existing.baseline_duration_intervals = run.baseline_duration_intervals
            existing.stressed_duration_intervals = run.stressed_duration_intervals
            existing.duration_increase_intervals = run.duration_increase_intervals
            existing.liquidation_status = run.liquidation_status
            existing.stressed_fillable_quantity = run.stressed_fillable_quantity
            existing.stressed_residual_quantity = run.stressed_residual_quantity
            existing.baseline_total_cost = run.baseline_total_cost
            existing.stressed_total_cost = run.stressed_total_cost
            existing.cost_escalation_monetary = run.cost_escalation_monetary
            existing.cost_escalation_pct = run.cost_escalation_pct
            existing.cost_escalation_bps = run.cost_escalation_bps
            await self.session.flush()
            return existing

        self.session.add(run)
        await self.session.flush()
        return run

    async def get_scenario_run(self, run_id: str) -> Optional[LiquidityStressScenarioRun]:
        stmt = select(LiquidityStressScenarioRun).where(LiquidityStressScenarioRun.run_id == run_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def save_monitoring_snapshot(
        self, snapshot: LiquidityStressMonitoringSnapshot
    ) -> LiquidityStressMonitoringSnapshot:
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot

    async def get_latest_monitoring(
        self, instrument_id: str
    ) -> Optional[LiquidityStressMonitoringSnapshot]:
        stmt = (
            select(LiquidityStressMonitoringSnapshot)
            .where(LiquidityStressMonitoringSnapshot.instrument_id == instrument_id)
            .order_by(desc(LiquidityStressMonitoringSnapshot.monitoring_timestamp))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

