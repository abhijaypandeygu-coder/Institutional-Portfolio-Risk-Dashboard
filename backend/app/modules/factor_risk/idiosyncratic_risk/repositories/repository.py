"""
Repository layer for M08.06 Idiosyncratic Risk.
"""

from typing import List, Optional
from datetime import date
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.factor_risk.idiosyncratic_risk.models import (
    ResidualRiskConfig,
    ResidualVolatilityRun,
    ResidualCovarianceSnapshot,
    PortfolioIdiosyncraticRiskRun,
    SecurityResidualRiskContribution,
    IssuerResidualRiskContribution,
    ResidualDiagnosticRun,
    ResidualOutlierRecord,
)


class IdiosyncraticRiskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---------------------------------------------------------
    # Residual Risk Config
    # ---------------------------------------------------------
    async def create_config(self, config: ResidualRiskConfig) -> ResidualRiskConfig:
        self.session.add(config)
        await self.session.commit()
        await self.session.refresh(config)
        return config

    async def get_config_by_id(self, config_id: str) -> Optional[ResidualRiskConfig]:
        stmt = select(ResidualRiskConfig).where(ResidualRiskConfig.config_id == config_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_config_by_code(self, config_code: str) -> Optional[ResidualRiskConfig]:
        stmt = select(ResidualRiskConfig).where(ResidualRiskConfig.config_code == config_code)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_config_by_hash(self, config_hash: str) -> Optional[ResidualRiskConfig]:
        stmt = select(ResidualRiskConfig).where(ResidualRiskConfig.config_hash == config_hash)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_configs(self, limit: int = 50) -> List[ResidualRiskConfig]:
        stmt = select(ResidualRiskConfig).order_by(desc(ResidualRiskConfig.created_at)).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # ---------------------------------------------------------
    # Residual Volatility Runs
    # ---------------------------------------------------------
    async def save_residual_volatility_run(self, run: ResidualVolatilityRun) -> ResidualVolatilityRun:
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def get_residual_volatility_run(
        self,
        config_id: str,
        instrument_id: str,
        as_of_date: date,
    ) -> Optional[ResidualVolatilityRun]:
        stmt = select(ResidualVolatilityRun).where(
            and_(
                ResidualVolatilityRun.config_id == config_id,
                ResidualVolatilityRun.instrument_id == instrument_id,
                ResidualVolatilityRun.as_of_date == as_of_date,
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    # ---------------------------------------------------------
    # Residual Covariance Snapshots
    # ---------------------------------------------------------
    async def save_covariance_snapshot(self, snapshot: ResidualCovarianceSnapshot) -> ResidualCovarianceSnapshot:
        self.session.add(snapshot)
        await self.session.commit()
        await self.session.refresh(snapshot)
        return snapshot

    async def get_covariance_snapshot(
        self,
        factor_model_version_id: str,
        as_of_date: date,
        dimension: int,
    ) -> Optional[ResidualCovarianceSnapshot]:
        stmt = select(ResidualCovarianceSnapshot).where(
            and_(
                ResidualCovarianceSnapshot.factor_model_version_id == factor_model_version_id,
                ResidualCovarianceSnapshot.as_of_date == as_of_date,
                ResidualCovarianceSnapshot.dimension == dimension,
            )
        ).order_by(desc(ResidualCovarianceSnapshot.created_at))
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    # ---------------------------------------------------------
    # Portfolio Idiosyncratic Runs
    # ---------------------------------------------------------
    async def save_portfolio_run(
        self,
        run: PortfolioIdiosyncraticRiskRun,
        security_contribs: List[SecurityResidualRiskContribution],
        issuer_contribs: List[IssuerResidualRiskContribution],
    ) -> PortfolioIdiosyncraticRiskRun:
        self.session.add(run)
        await self.session.flush()

        for sc in security_contribs:
            sc.run_id = run.run_id
            self.session.add(sc)

        for ic in issuer_contribs:
            ic.run_id = run.run_id
            self.session.add(ic)

        await self.session.commit()
        await self.session.refresh(run)
        return await self.get_portfolio_run_by_run_id(run.run_id)

    async def get_portfolio_run_by_run_id(self, run_id: str) -> Optional[PortfolioIdiosyncraticRiskRun]:
        stmt = (
            select(PortfolioIdiosyncraticRiskRun)
            .options(
                selectinload(PortfolioIdiosyncraticRiskRun.security_contributions),
                selectinload(PortfolioIdiosyncraticRiskRun.issuer_contributions),
            )
            .where(PortfolioIdiosyncraticRiskRun.run_id == run_id)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    # ---------------------------------------------------------
    # Residual Diagnostics
    # ---------------------------------------------------------
    async def save_diagnostic_run(
        self,
        diag: ResidualDiagnosticRun,
        outliers: List[ResidualOutlierRecord],
    ) -> ResidualDiagnosticRun:
        self.session.add(diag)
        await self.session.flush()

        for out in outliers:
            out.diagnostic_run_id = diag.diagnostic_run_id
            self.session.add(out)

        await self.session.commit()
        await self.session.refresh(diag)
        return await self.get_diagnostic_run_by_run_id(diag.diagnostic_run_id)

    async def get_diagnostic_run_by_run_id(self, diag_run_id: str) -> Optional[ResidualDiagnosticRun]:
        stmt = (
            select(ResidualDiagnosticRun)
            .options(selectinload(ResidualDiagnosticRun.outliers))
            .where(ResidualDiagnosticRun.diagnostic_run_id == diag_run_id)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()
