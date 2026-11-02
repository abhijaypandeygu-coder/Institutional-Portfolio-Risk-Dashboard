"""
M07.10 Risk Forecasting Database Repository.
Data access layer for forecast configurations, runs, step results, evaluations, and comparisons.
"""
from datetime import date
from typing import List, Optional
from sqlalchemy import select, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.market_risk.risk_forecasting.models import (
    RiskForecastConfiguration,
    RiskForecastCalculationRun,
    VolatilityForecastResult,
    RiskForecastEvaluationResult,
    RiskForecastModelComparison,
    RiskForecastMonitoringEvent,
    ForecastCalculationScope,
    ForecastModelType,
)


class RiskForecastingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_calculation_run(
        self, run: RiskForecastCalculationRun
    ) -> RiskForecastCalculationRun:
        """Persist a new calculation run along with its forecast step results."""
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def get_calculation_run(
        self, calculation_id: str
    ) -> Optional[RiskForecastCalculationRun]:
        """Retrieve calculation run with steps and evaluations loaded."""
        stmt = (
            select(RiskForecastCalculationRun)
            .where(RiskForecastCalculationRun.calculation_id == calculation_id)
            .options(
                selectinload(RiskForecastCalculationRun.step_results),
                selectinload(RiskForecastCalculationRun.evaluations),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_latest_run_for_entity(
        self,
        scope: ForecastCalculationScope,
        entity_id: str,
        model_name: Optional[ForecastModelType] = None,
        as_of: Optional[date] = None,
    ) -> Optional[RiskForecastCalculationRun]:
        """Fetch the most recent forecast for an entity."""
        stmt = (
            select(RiskForecastCalculationRun)
            .where(
                and_(
                    RiskForecastCalculationRun.scope == scope,
                    RiskForecastCalculationRun.entity_id == entity_id,
                )
            )
        )
        if model_name:
            stmt = stmt.where(RiskForecastCalculationRun.model_name == model_name)
        if as_of:
            stmt = stmt.where(RiskForecastCalculationRun.forecast_origin <= as_of)

        stmt = stmt.order_by(
            desc(RiskForecastCalculationRun.forecast_origin),
            desc(RiskForecastCalculationRun.created_at),
        ).options(
            selectinload(RiskForecastCalculationRun.step_results),
            selectinload(RiskForecastCalculationRun.evaluations),
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_runs_for_entity(
        self,
        scope: ForecastCalculationScope,
        entity_id: str,
        model_name: Optional[ForecastModelType] = None,
        limit: int = 50,
    ) -> List[RiskForecastCalculationRun]:
        """List historical forecasts for charting rolling predictions."""
        stmt = (
            select(RiskForecastCalculationRun)
            .where(
                and_(
                    RiskForecastCalculationRun.scope == scope,
                    RiskForecastCalculationRun.entity_id == entity_id,
                )
            )
        )
        if model_name:
            stmt = stmt.where(RiskForecastCalculationRun.model_name == model_name)

        stmt = stmt.order_by(desc(RiskForecastCalculationRun.forecast_origin)).limit(limit).options(
            selectinload(RiskForecastCalculationRun.step_results)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def save_evaluation(
        self, eval_res: RiskForecastEvaluationResult
    ) -> RiskForecastEvaluationResult:
        """Persist a forecast evaluation result."""
        self.session.add(eval_res)
        await self.session.commit()
        await self.session.refresh(eval_res)
        return eval_res

    async def save_comparison(
        self, comp: RiskForecastModelComparison
    ) -> RiskForecastModelComparison:
        """Persist model comparison results."""
        self.session.add(comp)
        await self.session.commit()
        await self.session.refresh(comp)
        return comp

    async def save_monitoring_event(
        self, event: RiskForecastMonitoringEvent
    ) -> RiskForecastMonitoringEvent:
        """Persist a monitoring risk alert."""
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def list_monitoring_events(
        self, entity_id: Optional[str] = None, limit: int = 50
    ) -> List[RiskForecastMonitoringEvent]:
        """Retrieve recent monitoring events."""
        stmt = select(RiskForecastMonitoringEvent)
        if entity_id:
            stmt = stmt.where(RiskForecastMonitoringEvent.entity_id == entity_id)
        stmt = stmt.order_by(desc(RiskForecastMonitoringEvent.detected_at)).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
