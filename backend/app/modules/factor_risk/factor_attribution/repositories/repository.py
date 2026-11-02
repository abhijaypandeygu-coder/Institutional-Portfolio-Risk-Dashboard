"""
M08.04 Factor Attribution Repository Layer.
Handles database access for attribution configs, return attribution runs,
risk attribution runs, covariance snapshots, and reconciliation records.
"""
from datetime import date
from typing import Optional, List
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.factor_risk.factor_attribution.models import (
    FactorAttributionConfig,
    FactorReturnAttributionRun,
    FactorReturnAttributionComponent,
    FactorRiskAttributionRun,
    FactorRiskAttributionComponent,
    FactorAttributionCovarianceSnapshot,
    FactorAttributionReconciliation,
)


class FactorAttributionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # =========================================================================
    # 1. Configs
    # =========================================================================

    async def get_config_by_id(self, config_id: str) -> Optional[FactorAttributionConfig]:
        stmt = select(FactorAttributionConfig).where(FactorAttributionConfig.config_id == config_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_config_by_code(self, config_code: str) -> Optional[FactorAttributionConfig]:
        stmt = select(FactorAttributionConfig).where(FactorAttributionConfig.config_code == config_code)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_configs(self) -> List[FactorAttributionConfig]:
        stmt = select(FactorAttributionConfig).order_by(FactorAttributionConfig.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def save_config(self, config: FactorAttributionConfig) -> FactorAttributionConfig:
        self.session.add(config)
        await self.session.flush()
        return config

    # =========================================================================
    # 2. Return Attribution Runs
    # =========================================================================

    async def save_return_run(self, run: FactorReturnAttributionRun) -> FactorReturnAttributionRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_return_run_by_id(self, run_id: str) -> Optional[FactorReturnAttributionRun]:
        stmt = (
            select(FactorReturnAttributionRun)
            .options(
                selectinload(FactorReturnAttributionRun.components),
                selectinload(FactorReturnAttributionRun.reconciliation),
            )
            .where(FactorReturnAttributionRun.run_id == run_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_return_runs_for_portfolio(
        self,
        portfolio_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[FactorReturnAttributionRun]:
        filters = [FactorReturnAttributionRun.portfolio_id == portfolio_id]
        if start_date:
            filters.append(FactorReturnAttributionRun.period_start >= start_date)
        if end_date:
            filters.append(FactorReturnAttributionRun.period_end <= end_date)

        stmt = (
            select(FactorReturnAttributionRun)
            .options(
                selectinload(FactorReturnAttributionRun.components),
                selectinload(FactorReturnAttributionRun.reconciliation),
            )
            .where(and_(*filters))
            .order_by(desc(FactorReturnAttributionRun.period_end))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # =========================================================================
    # 3. Covariance Snapshots
    # =========================================================================

    async def save_covariance_snapshot(
        self, snapshot: FactorAttributionCovarianceSnapshot
    ) -> FactorAttributionCovarianceSnapshot:
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot

    async def get_covariance_snapshot_by_id(
        self, snapshot_id: str
    ) -> Optional[FactorAttributionCovarianceSnapshot]:
        stmt = select(FactorAttributionCovarianceSnapshot).where(
            FactorAttributionCovarianceSnapshot.snapshot_id == snapshot_id
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_latest_covariance_snapshot(
        self,
        factor_model_version_id: str,
        as_of_date: date,
    ) -> Optional[FactorAttributionCovarianceSnapshot]:
        stmt = (
            select(FactorAttributionCovarianceSnapshot)
            .where(
                and_(
                    FactorAttributionCovarianceSnapshot.factor_model_version_id == factor_model_version_id,
                    FactorAttributionCovarianceSnapshot.estimation_window_end <= as_of_date,
                )
            )
            .order_by(desc(FactorAttributionCovarianceSnapshot.estimation_window_end), desc(FactorAttributionCovarianceSnapshot.created_at))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    # =========================================================================
    # 4. Risk Attribution Runs
    # =========================================================================

    async def save_risk_run(self, run: FactorRiskAttributionRun) -> FactorRiskAttributionRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_risk_run_by_id(self, run_id: str) -> Optional[FactorRiskAttributionRun]:
        stmt = (
            select(FactorRiskAttributionRun)
            .options(
                selectinload(FactorRiskAttributionRun.components),
                selectinload(FactorRiskAttributionRun.reconciliation),
            )
            .where(FactorRiskAttributionRun.run_id == run_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_risk_runs_for_portfolio(
        self,
        portfolio_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[FactorRiskAttributionRun]:
        filters = [FactorRiskAttributionRun.portfolio_id == portfolio_id]
        if start_date:
            filters.append(FactorRiskAttributionRun.as_of_date >= start_date)
        if end_date:
            filters.append(FactorRiskAttributionRun.as_of_date <= end_date)

        stmt = (
            select(FactorRiskAttributionRun)
            .options(
                selectinload(FactorRiskAttributionRun.components),
                selectinload(FactorRiskAttributionRun.reconciliation),
            )
            .where(and_(*filters))
            .order_by(desc(FactorRiskAttributionRun.as_of_date))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # =========================================================================
    # 5. Reconciliation Records
    # =========================================================================

    async def save_reconciliation(
        self, reconciliation: FactorAttributionReconciliation
    ) -> FactorAttributionReconciliation:
        self.session.add(reconciliation)
        await self.session.flush()
        return reconciliation

    async def get_reconciliation_by_run_id(
        self, run_id: str
    ) -> Optional[FactorAttributionReconciliation]:
        stmt = select(FactorAttributionReconciliation).where(
            (FactorAttributionReconciliation.return_run_id == run_id)
            | (FactorAttributionReconciliation.risk_run_id == run_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

