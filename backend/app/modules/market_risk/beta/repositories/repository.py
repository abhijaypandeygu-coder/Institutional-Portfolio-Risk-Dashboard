"""
M07.07 Portfolio Beta Database Repository.
"""
from typing import List, Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_risk.beta.models import (
    BenchmarkReference,
    BetaConfiguration,
    BetaCalculationRun,
    SecurityBetaResult,
    PortfolioBetaResult,
)


class BetaRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # Benchmarks
    async def get_benchmark_by_id(self, benchmark_id: str) -> Optional[BenchmarkReference]:
        stmt = select(BenchmarkReference).where(BenchmarkReference.id == benchmark_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_benchmark_by_code(self, code: str) -> Optional[BenchmarkReference]:
        stmt = select(BenchmarkReference).where(BenchmarkReference.benchmark_code == code)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_benchmarks(self, market: Optional[str] = None, active_only: bool = True) -> List[BenchmarkReference]:
        stmt = select(BenchmarkReference)
        if active_only:
            stmt = stmt.where(BenchmarkReference.is_active == True)
        if market:
            stmt = stmt.where(BenchmarkReference.market == market)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def list_active_benchmarks(self) -> List[BenchmarkReference]:
        return await self.list_benchmarks(active_only=True)

    async def create_benchmark(self, benchmark: BenchmarkReference) -> BenchmarkReference:
        self.session.add(benchmark)
        await self.session.commit()
        await self.session.refresh(benchmark)
        return benchmark

    # Configurations
    async def get_config_by_name(self, name: str) -> Optional[BetaConfiguration]:
        stmt = select(BetaConfiguration).where(BetaConfiguration.config_name == name)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_configs(self, active_only: bool = True) -> List[BetaConfiguration]:
        stmt = select(BetaConfiguration)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def list_active_configs(self) -> List[BetaConfiguration]:
        return await self.list_configs(active_only=True)

    async def save_config(self, config: BetaConfiguration) -> BetaConfiguration:
        self.session.add(config)
        await self.session.commit()
        await self.session.refresh(config)
        return config

    async def create_config(self, config: BetaConfiguration) -> BetaConfiguration:
        return await self.save_config(config)

    # Calculation Runs & Results
    async def create_calculation_run(self, run: BetaCalculationRun) -> BetaCalculationRun:
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def save_security_beta(self, result: SecurityBetaResult) -> SecurityBetaResult:
        self.session.add(result)
        await self.session.commit()
        await self.session.refresh(result)
        return result

    async def save_portfolio_beta(self, result: PortfolioBetaResult) -> PortfolioBetaResult:
        self.session.add(result)
        await self.session.commit()
        await self.session.refresh(result)
        return result

    async def get_latest_security_beta(
        self,
        instrument_id: str,
        benchmark_id: str,
        lookback_days: int,
    ) -> Optional[SecurityBetaResult]:
        stmt = (
            select(SecurityBetaResult)
            .where(
                SecurityBetaResult.instrument_id == instrument_id,
                SecurityBetaResult.benchmark_id == benchmark_id,
                SecurityBetaResult.lookback_days == lookback_days,
            )
            .order_by(desc(SecurityBetaResult.as_of_date))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()
