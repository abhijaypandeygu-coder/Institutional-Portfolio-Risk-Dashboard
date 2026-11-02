"""
M07.05 Correlation Analysis Database Repository.
"""
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_risk.correlation.models import (
    CorrelationConfiguration,
    CorrelationCalculationRun,
    CorrelationPairResult,
    RollingCorrelationResult,
    CorrelationMatrixMetadata,
    CorrelationMatrixTransformation,
    CorrelationRegimeEvent,
    CorrelationRegimeStatus,
)


class CorrelationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_config_by_name(self, name: str) -> Optional[CorrelationConfiguration]:
        stmt = select(CorrelationConfiguration).where(CorrelationConfiguration.config_name == name)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_active_configs(self) -> List[CorrelationConfiguration]:
        stmt = select(CorrelationConfiguration).where(CorrelationConfiguration.is_active == True)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def create_config(self, config: CorrelationConfiguration) -> CorrelationConfiguration:
        self.session.add(config)
        await self.session.commit()
        await self.session.refresh(config)
        return config

    async def create_calculation_run(self, run: CorrelationCalculationRun) -> CorrelationCalculationRun:
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def save_pair_results(self, results: List[CorrelationPairResult]) -> None:
        self.session.add_all(results)
        await self.session.commit()

    async def get_latest_pair_result(
        self,
        asset_a_id: str,
        asset_b_id: str,
        lookback_days: int,
    ) -> Optional[CorrelationPairResult]:
        # Sort canonically to match index
        a_id, b_id = (asset_a_id, asset_b_id) if asset_a_id <= asset_b_id else (asset_b_id, asset_a_id)
        stmt = (
            select(CorrelationPairResult)
            .where(
                CorrelationPairResult.asset_a_id == a_id,
                CorrelationPairResult.asset_b_id == b_id,
                CorrelationPairResult.lookback_days == lookback_days,
            )
            .order_by(desc(CorrelationPairResult.as_of_date))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def save_matrix(self, matrix: CorrelationMatrixMetadata) -> CorrelationMatrixMetadata:
        self.session.add(matrix)
        await self.session.commit()
        await self.session.refresh(matrix)
        return matrix

    async def get_matrix_by_id(self, matrix_id: str) -> Optional[CorrelationMatrixMetadata]:
        stmt = select(CorrelationMatrixMetadata).where(CorrelationMatrixMetadata.id == matrix_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_latest_portfolio_matrix(
        self,
        portfolio_id: str,
        lookback_days: int,
    ) -> Optional[CorrelationMatrixMetadata]:
        stmt = (
            select(CorrelationMatrixMetadata)
            .where(
                CorrelationMatrixMetadata.portfolio_id == portfolio_id,
                CorrelationMatrixMetadata.lookback_days == lookback_days,
            )
            .order_by(desc(CorrelationMatrixMetadata.as_of_date))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def save_transformation(
        self, transformation: CorrelationMatrixTransformation
    ) -> CorrelationMatrixTransformation:
        self.session.add(transformation)
        await self.session.commit()
        await self.session.refresh(transformation)
        return transformation

    async def save_regime_events(self, events: List[CorrelationRegimeEvent]) -> None:
        self.session.add_all(events)
        await self.session.commit()

    async def list_regime_events(
        self,
        portfolio_id: Optional[str] = None,
        status: Optional[CorrelationRegimeStatus] = None,
        limit: int = 50,
    ) -> List[CorrelationRegimeEvent]:
        stmt = select(CorrelationRegimeEvent)
        if portfolio_id:
            stmt = stmt.where(CorrelationRegimeEvent.portfolio_id == portfolio_id)
        if status:
            stmt = stmt.where(CorrelationRegimeEvent.status == status)
        stmt = stmt.order_by(desc(CorrelationRegimeEvent.detected_at)).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def list_pairs_for_portfolio(
        self,
        portfolio_id: str,
        as_of_date: datetime,
        lookback_days: int,
    ) -> List[CorrelationPairResult]:
        stmt = (
            select(CorrelationPairResult)
            .where(
                CorrelationPairResult.portfolio_id == portfolio_id,
                CorrelationPairResult.as_of_date == as_of_date,
                CorrelationPairResult.lookback_days == lookback_days,
            )
            .order_by(desc(CorrelationPairResult.correlation_coefficient))
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

