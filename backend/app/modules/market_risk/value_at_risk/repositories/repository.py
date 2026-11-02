"""
Module M07.02: Value at Risk Repository.
Transaction-managed persistence for VaR configs, calculation results,
risk contributions, scenarios, and diagnostics.
"""
from datetime import datetime, date
from typing import List, Optional
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_risk.value_at_risk.models import (
    VaRModelConfig,
    VaRResult,
    VaRRiskContribution,
    VaRHistoricalScenario,
    VaRCalculationDiagnostic,
    VaRMethodology,
)


class VaRRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # Configs
    async def create_config(self, config: VaRModelConfig) -> VaRModelConfig:
        self.session.add(config)
        await self.session.commit()
        await self.session.refresh(config)
        return config

    async def get_config(self, config_id: str) -> Optional[VaRModelConfig]:
        stmt = select(VaRModelConfig).where(VaRModelConfig.config_id == config_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_configs(
        self, portfolio_id: Optional[str] = None
    ) -> List[VaRModelConfig]:
        stmt = select(VaRModelConfig).where(VaRModelConfig.is_active == True)
        if portfolio_id:
            stmt = stmt.where(VaRModelConfig.portfolio_id == portfolio_id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # Results
    async def save_var_result(
        self, result: VaRResult, contributions: Optional[List[VaRRiskContribution]] = None
    ) -> VaRResult:
        self.session.add(result)
        if contributions:
            self.session.add_all(contributions)
        await self.session.commit()
        await self.session.refresh(result)
        return result

    async def get_var_result(self, result_id: str) -> Optional[VaRResult]:
        stmt = select(VaRResult).where(VaRResult.result_id == result_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_latest_var_result(
        self,
        portfolio_id: str,
        methodology: Optional[VaRMethodology] = None,
    ) -> Optional[VaRResult]:
        stmt = select(VaRResult).where(VaRResult.portfolio_id == portfolio_id)
        if methodology:
            stmt = stmt.where(VaRResult.methodology == methodology)
        stmt = stmt.order_by(desc(VaRResult.calculated_at)).limit(1)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_var_results_history(
        self,
        portfolio_id: str,
        methodology: Optional[VaRMethodology] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        limit: int = 100,
    ) -> List[VaRResult]:
        stmt = select(VaRResult).where(VaRResult.portfolio_id == portfolio_id)
        if methodology:
            stmt = stmt.where(VaRResult.methodology == methodology)
        if from_date:
            stmt = stmt.where(VaRResult.as_of_date >= from_date)
        if to_date:
            stmt = stmt.where(VaRResult.as_of_date <= to_date)
        stmt = stmt.order_by(VaRResult.calculated_at.asc()).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # Contributions
    async def get_contributions_for_result(
        self, result_id: str
    ) -> List[VaRRiskContribution]:
        stmt = select(VaRRiskContribution).where(VaRRiskContribution.result_id == result_id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # Diagnostics
    async def record_diagnostic(
        self, diag: VaRCalculationDiagnostic
    ) -> VaRCalculationDiagnostic:
        self.session.add(diag)
        await self.session.commit()
        return diag

    async def list_diagnostics(
        self, result_id: Optional[str] = None, portfolio_id: Optional[str] = None
    ) -> List[VaRCalculationDiagnostic]:
        stmt = select(VaRCalculationDiagnostic).order_by(desc(VaRCalculationDiagnostic.created_at))
        if result_id:
            stmt = stmt.where(VaRCalculationDiagnostic.result_id == result_id)
        if portfolio_id:
            stmt = stmt.where(VaRCalculationDiagnostic.portfolio_id == portfolio_id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
