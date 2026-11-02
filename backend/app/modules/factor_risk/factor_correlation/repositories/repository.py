"""
Repository layer for M08.07 Factor Correlation & Covariance Analytics.
"""

from typing import List, Optional
from datetime import date
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.factor_risk.factor_correlation.models import (
    FactorCorrelationConfig,
    FactorCorrelationRun,
    FactorCorrelationPair,
    FactorCorrelationMatrixSnapshot,
    FactorCovarianceConfig,
    FactorCovarianceSnapshot,
    RollingFactorCorrelation,
    FactorRegimeAlertConfig,
    FactorRegimeAlert,
    RegimeAlertStatus,
)


class FactorCorrelationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---------------------------------------------------------
    # Correlation Config
    # ---------------------------------------------------------
    async def create_correlation_config(self, config: FactorCorrelationConfig) -> FactorCorrelationConfig:
        self.session.add(config)
        await self.session.commit()
        await self.session.refresh(config)
        return config

    async def get_correlation_config_by_id(self, config_id: str) -> Optional[FactorCorrelationConfig]:
        stmt = select(FactorCorrelationConfig).where(FactorCorrelationConfig.config_id == config_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_correlation_config_by_code(self, config_code: str) -> Optional[FactorCorrelationConfig]:
        stmt = select(FactorCorrelationConfig).where(FactorCorrelationConfig.config_code == config_code)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_correlation_config_by_hash(self, config_hash: str) -> Optional[FactorCorrelationConfig]:
        stmt = select(FactorCorrelationConfig).where(FactorCorrelationConfig.config_hash == config_hash)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_correlation_configs(self, limit: int = 50) -> List[FactorCorrelationConfig]:
        stmt = select(FactorCorrelationConfig).order_by(desc(FactorCorrelationConfig.created_at)).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # ---------------------------------------------------------
    # Correlation Run & Matrix Snapshot
    # ---------------------------------------------------------
    async def save_correlation_run(
        self,
        run: FactorCorrelationRun,
        pairs: List[FactorCorrelationPair],
        matrix_snapshot: FactorCorrelationMatrixSnapshot,
    ) -> FactorCorrelationRun:
        self.session.add(run)
        await self.session.flush()

        for p in pairs:
            p.run_id = run.run_id
            self.session.add(p)

        matrix_snapshot.run_id = run.run_id
        self.session.add(matrix_snapshot)

        await self.session.commit()
        await self.session.refresh(run)
        return await self.get_correlation_run_by_id(run.run_id)

    async def get_correlation_run_by_id(self, run_id: str) -> Optional[FactorCorrelationRun]:
        stmt = (
            select(FactorCorrelationRun)
            .options(
                selectinload(FactorCorrelationRun.pairs),
                selectinload(FactorCorrelationRun.matrix_snapshot),
            )
            .where(FactorCorrelationRun.run_id == run_id)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_matrix_snapshot_by_id(self, matrix_id: str) -> Optional[FactorCorrelationMatrixSnapshot]:
        stmt = select(FactorCorrelationMatrixSnapshot).where(FactorCorrelationMatrixSnapshot.matrix_id == matrix_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    # ---------------------------------------------------------
    # Authoritative Factor Covariance Snapshots
    # ---------------------------------------------------------
    async def save_covariance_snapshot(self, snapshot: FactorCovarianceSnapshot) -> FactorCovarianceSnapshot:
        self.session.add(snapshot)
        await self.session.commit()
        await self.session.refresh(snapshot)
        return snapshot

    async def get_covariance_snapshot_by_id(self, snapshot_id: str) -> Optional[FactorCovarianceSnapshot]:
        stmt = select(FactorCovarianceSnapshot).where(FactorCovarianceSnapshot.snapshot_id == snapshot_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_latest_covariance_snapshot(
        self,
        factor_model_version_id: str,
        as_of_date: date,
        covariance_method: str = "SAMPLE",
    ) -> Optional[FactorCovarianceSnapshot]:
        stmt = (
            select(FactorCovarianceSnapshot)
            .where(
                and_(
                    FactorCovarianceSnapshot.factor_model_version_id == factor_model_version_id,
                    FactorCovarianceSnapshot.as_of_date <= as_of_date,
                    FactorCovarianceSnapshot.covariance_method == covariance_method,
                )
            )
            .order_by(desc(FactorCovarianceSnapshot.as_of_date))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    # ---------------------------------------------------------
    # Rolling Correlations
    # ---------------------------------------------------------
    async def save_rolling_correlation(self, record: RollingFactorCorrelation) -> RollingFactorCorrelation:
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def get_rolling_history(
        self,
        factor_model_version_id: str,
        factor_a_code: str,
        factor_b_code: str,
        start_date: date,
        end_date: date,
    ) -> List[RollingFactorCorrelation]:
        stmt = (
            select(RollingFactorCorrelation)
            .where(
                and_(
                    RollingFactorCorrelation.factor_model_version_id == factor_model_version_id,
                    RollingFactorCorrelation.factor_a_code == factor_a_code,
                    RollingFactorCorrelation.factor_b_code == factor_b_code,
                    RollingFactorCorrelation.as_of_date >= start_date,
                    RollingFactorCorrelation.as_of_date <= end_date,
                )
            )
            .order_by(RollingFactorCorrelation.as_of_date.asc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # ---------------------------------------------------------
    # Regime Alerts
    # ---------------------------------------------------------
    async def save_regime_alert(self, alert: FactorRegimeAlert) -> FactorRegimeAlert:
        self.session.add(alert)
        await self.session.commit()
        await self.session.refresh(alert)
        return alert

    async def get_active_regime_alerts(
        self,
        factor_model_version_id: str,
        as_of_date: date,
    ) -> List[FactorRegimeAlert]:
        stmt = (
            select(FactorRegimeAlert)
            .where(
                and_(
                    FactorRegimeAlert.factor_model_version_id == factor_model_version_id,
                    FactorRegimeAlert.as_of_date == as_of_date,
                    FactorRegimeAlert.status == RegimeAlertStatus.ACTIVE,
                )
            )
            .order_by(desc(FactorRegimeAlert.created_at))
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

