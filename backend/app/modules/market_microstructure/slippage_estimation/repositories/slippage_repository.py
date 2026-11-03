"""
Repository layer for M09.05 Slippage Estimation.
"""

from typing import List, Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_microstructure.slippage_estimation.models.slippage_models import (
    SlippageBenchmarkConfig,
    SlippageExecutionSummary,
    SlippageFillAttribution,
    SlippageOpportunityCost,
    SlippageCalibrationObservation,
    SlippageCalibrationRun,
)


class SlippageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_benchmark_config(self, config_code: str) -> Optional[SlippageBenchmarkConfig]:
        stmt = (
            select(SlippageBenchmarkConfig)
            .where(
                SlippageBenchmarkConfig.config_code == config_code,
                SlippageBenchmarkConfig.is_active == True,
            )
            .order_by(desc(SlippageBenchmarkConfig.version))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_benchmark_config(self, config: SlippageBenchmarkConfig) -> SlippageBenchmarkConfig:
        self.session.add(config)
        await self.session.flush()
        return config

    async def save_execution_summary(self, summary: SlippageExecutionSummary) -> SlippageExecutionSummary:
        self.session.add(summary)
        await self.session.flush()
        return summary

    async def get_execution_summary(self, order_id: str) -> Optional[SlippageExecutionSummary]:
        stmt = (
            select(SlippageExecutionSummary)
            .where(SlippageExecutionSummary.order_id == order_id)
            .order_by(desc(SlippageExecutionSummary.created_at))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def save_fill_attributions(
        self, attributions: List[SlippageFillAttribution]
    ) -> List[SlippageFillAttribution]:
        self.session.add_all(attributions)
        await self.session.flush()
        return attributions

    async def get_fill_attributions(self, order_id: str) -> List[SlippageFillAttribution]:
        stmt = (
            select(SlippageFillAttribution)
            .where(SlippageFillAttribution.order_id == order_id)
            .order_by(SlippageFillAttribution.fill_timestamp)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def save_opportunity_cost(self, cost: SlippageOpportunityCost) -> SlippageOpportunityCost:
        existing = await self.get_opportunity_cost(cost.order_id)
        if existing:
            existing.unfilled_quantity = cost.unfilled_quantity
            existing.benchmark_price = cost.benchmark_price
            existing.terminal_price = cost.terminal_price
            existing.terminal_timestamp = cost.terminal_timestamp
            existing.terminal_price_source = cost.terminal_price_source
            existing.opportunity_cost_price_units = cost.opportunity_cost_price_units
            existing.opportunity_cost_bps = cost.opportunity_cost_bps
            existing.opportunity_cost_monetary_amount = cost.opportunity_cost_monetary_amount
            existing.implementation_shortfall_monetary_amount = cost.implementation_shortfall_monetary_amount
            await self.session.flush()
            return existing
        self.session.add(cost)
        await self.session.flush()
        return cost

    async def get_opportunity_cost(self, order_id: str) -> Optional[SlippageOpportunityCost]:
        stmt = select(SlippageOpportunityCost).where(SlippageOpportunityCost.order_id == order_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def save_calibration_run(
        self, run: SlippageCalibrationRun, observations: List[SlippageCalibrationObservation]
    ) -> SlippageCalibrationRun:
        self.session.add(run)
        self.session.add_all(observations)
        await self.session.flush()
        return run

    async def get_calibration_run(self, run_code: str) -> Optional[SlippageCalibrationRun]:
        stmt = select(SlippageCalibrationRun).where(SlippageCalibrationRun.run_code == run_code)
        result = await self.session.execute(stmt)
        return result.scalars().first()

