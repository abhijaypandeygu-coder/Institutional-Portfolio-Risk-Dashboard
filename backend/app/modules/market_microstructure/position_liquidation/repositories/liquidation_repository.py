"""
Repository layer for M09.07 Position Liquidation.
"""

from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_microstructure.position_liquidation.models.liquidation_models import (
    PositionLiquidationPlan,
    PositionLiquidationTarget,
    PositionLiquidationScheduleItem,
    PositionLiquidationHorizonResult,
    PositionLiquidationCostResult,
    PositionLiquidationCalibrationRun,
    PortfolioLiquidationSummary,
)


class PositionLiquidationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_plan_by_id(self, plan_id: str) -> Optional[PositionLiquidationPlan]:
        stmt = (
            select(PositionLiquidationPlan)
            .options(
                selectinload(PositionLiquidationPlan.targets),
                selectinload(PositionLiquidationPlan.schedules),
                selectinload(PositionLiquidationPlan.horizon_results),
                selectinload(PositionLiquidationPlan.cost_results),
            )
            .where(PositionLiquidationPlan.plan_id == plan_id)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_plans_for_position(self, position_id: str) -> List[PositionLiquidationPlan]:
        stmt = (
            select(PositionLiquidationPlan)
            .options(
                selectinload(PositionLiquidationPlan.targets),
                selectinload(PositionLiquidationPlan.horizon_results),
                selectinload(PositionLiquidationPlan.cost_results),
            )
            .where(PositionLiquidationPlan.position_id == position_id)
            .order_by(PositionLiquidationPlan.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def save_plan(self, plan: PositionLiquidationPlan) -> PositionLiquidationPlan:
        self.session.add(plan)
        await self.session.flush()
        return plan

    async def save_calibration_run(self, run: PositionLiquidationCalibrationRun) -> PositionLiquidationCalibrationRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_calibration_run(self, calibration_id: str) -> Optional[PositionLiquidationCalibrationRun]:
        stmt = select(PositionLiquidationCalibrationRun).where(
            PositionLiquidationCalibrationRun.calibration_id == calibration_id
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_calibration_runs(self) -> List[PositionLiquidationCalibrationRun]:
        stmt = select(PositionLiquidationCalibrationRun).order_by(
            PositionLiquidationCalibrationRun.created_at.desc()
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def save_portfolio_summary(self, summary: PortfolioLiquidationSummary) -> PortfolioLiquidationSummary:
        self.session.add(summary)
        await self.session.flush()
        return summary

