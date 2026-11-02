"""
M07.06 Covariance Analysis Database Repository.
"""
from typing import List, Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_risk.covariance.models import (
    CovarianceConfiguration,
    CovarianceCalculationRun,
    CovariancePairResult,
    RollingCovarianceResult,
    CovarianceMatrixMetadata,
    CovarianceMatrixTransformation,
    PortfolioCovarianceResult,
)


class CovarianceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_config_by_name(self, name: str) -> Optional[CovarianceConfiguration]:
        stmt = select(CovarianceConfiguration).where(CovarianceConfiguration.config_name == name)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_active_configs(self) -> List[CovarianceConfiguration]:
        stmt = select(CovarianceConfiguration).where(CovarianceConfiguration.is_active == True)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def create_config(self, config: CovarianceConfiguration) -> CovarianceConfiguration:
        self.session.add(config)
        await self.session.commit()
        await self.session.refresh(config)
        return config

    async def create_calculation_run(self, run: CovarianceCalculationRun) -> CovarianceCalculationRun:
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def save_pair_results(self, results: List[CovariancePairResult]) -> None:
        self.session.add_all(results)
        await self.session.commit()

    async def save_matrix(self, matrix: CovarianceMatrixMetadata) -> CovarianceMatrixMetadata:
        self.session.add(matrix)
        await self.session.commit()
        await self.session.refresh(matrix)
        return matrix

    async def get_matrix_by_id(self, matrix_id: str) -> Optional[CovarianceMatrixMetadata]:
        stmt = select(CovarianceMatrixMetadata).where(CovarianceMatrixMetadata.id == matrix_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_latest_portfolio_matrix(
        self,
        portfolio_id: str,
        lookback_days: int,
    ) -> Optional[CovarianceMatrixMetadata]:
        stmt = (
            select(CovarianceMatrixMetadata)
            .where(
                CovarianceMatrixMetadata.portfolio_id == portfolio_id,
                CovarianceMatrixMetadata.lookback_days == lookback_days,
            )
            .order_by(desc(CovarianceMatrixMetadata.as_of_date))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def save_transformation(
        self, transformation: CovarianceMatrixTransformation
    ) -> CovarianceMatrixTransformation:
        self.session.add(transformation)
        await self.session.commit()
        await self.session.refresh(transformation)
        return transformation

    async def save_portfolio_result(
        self, result: PortfolioCovarianceResult
    ) -> PortfolioCovarianceResult:
        self.session.add(result)
        await self.session.commit()
        await self.session.refresh(result)
        return result

