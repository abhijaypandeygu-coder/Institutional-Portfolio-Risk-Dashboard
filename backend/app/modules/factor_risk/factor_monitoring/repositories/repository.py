"""
SQLAlchemy 2.x Async Repository for M08.08 Factor Monitoring.
"""

from datetime import date, datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_, or_, desc, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.factor_risk.factor_monitoring.models import (
    FactorMonitoringConfig,
    FactorExposureTarget,
    FactorExposureTargetComponent,
    FactorThresholdPolicy,
    FactorMonitoringRun,
    FactorExposureDriftResult,
    FactorConcentrationResult,
    FactorThresholdEvaluation,
    FactorMonitoringBreach,
    FactorMonitoringEvent,
    BreachStatus,
    BreachSeverity,
    ThresholdMetricType,
)


class FactorMonitoringRepository:
    """Encapsulates all database operations for M08.08 Factor Monitoring."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # -------------------------------------------------------------------------
    # 1. Monitoring Configs
    # -------------------------------------------------------------------------

    async def create_monitoring_config(self, config: FactorMonitoringConfig) -> FactorMonitoringConfig:
        self.session.add(config)
        await self.session.flush()
        await self.session.refresh(config)
        return config

    async def get_monitoring_config_by_id(self, config_id: str) -> Optional[FactorMonitoringConfig]:
        stmt = select(FactorMonitoringConfig).where(FactorMonitoringConfig.config_id == config_id)
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_monitoring_config_by_code(self, config_code: str) -> Optional[FactorMonitoringConfig]:
        stmt = select(FactorMonitoringConfig).where(FactorMonitoringConfig.config_code == config_code)
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_monitoring_configs(self, limit: int = 50) -> List[FactorMonitoringConfig]:
        stmt = select(FactorMonitoringConfig).order_by(FactorMonitoringConfig.created_at.desc()).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # -------------------------------------------------------------------------
    # 2. Exposure Targets
    # -------------------------------------------------------------------------

    async def create_exposure_target(self, target: FactorExposureTarget) -> FactorExposureTarget:
        self.session.add(target)
        await self.session.flush()
        await self.session.refresh(target)
        return target

    async def get_exposure_target_by_id(self, target_id: str) -> Optional[FactorExposureTarget]:
        stmt = (
            select(FactorExposureTarget)
            .options(selectinload(FactorExposureTarget.components))
            .where(FactorExposureTarget.target_id == target_id)
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_active_target_for_portfolio(
        self,
        portfolio_id: str,
        factor_model_version_id: str,
        as_of_date: date,
    ) -> Optional[FactorExposureTarget]:
        stmt = (
            select(FactorExposureTarget)
            .options(selectinload(FactorExposureTarget.components))
            .where(
                and_(
                    FactorExposureTarget.portfolio_id == portfolio_id,
                    FactorExposureTarget.factor_model_version_id == factor_model_version_id,
                    FactorExposureTarget.effective_from <= as_of_date,
                    or_(
                        FactorExposureTarget.effective_to.is_(None),
                        FactorExposureTarget.effective_to >= as_of_date,
                    ),
                    FactorExposureTarget.is_approved.is_(True),
                )
            )
            .order_by(FactorExposureTarget.effective_from.desc())
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_exposure_targets(self, portfolio_id: Optional[str] = None) -> List[FactorExposureTarget]:
        stmt = select(FactorExposureTarget).options(selectinload(FactorExposureTarget.components))
        if portfolio_id:
            stmt = stmt.where(FactorExposureTarget.portfolio_id == portfolio_id)
        stmt = stmt.order_by(FactorExposureTarget.created_at.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # -------------------------------------------------------------------------
    # 3. Threshold Policies
    # -------------------------------------------------------------------------

    async def create_threshold_policy(self, policy: FactorThresholdPolicy) -> FactorThresholdPolicy:
        self.session.add(policy)
        await self.session.flush()
        await self.session.refresh(policy)
        return policy

    async def get_threshold_policy_by_id(self, policy_id: str) -> Optional[FactorThresholdPolicy]:
        stmt = select(FactorThresholdPolicy).where(FactorThresholdPolicy.policy_id == policy_id)
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_active_policies_for_portfolio(
        self,
        portfolio_id: str,
    ) -> List[FactorThresholdPolicy]:
        """Resolves active policies applicable to this portfolio or global fallback."""
        stmt = (
            select(FactorThresholdPolicy)
            .where(
                and_(
                    FactorThresholdPolicy.is_active.is_(True),
                    or_(
                        FactorThresholdPolicy.portfolio_id == portfolio_id,
                        FactorThresholdPolicy.portfolio_id.is_(None),
                    ),
                )
            )
            .order_by(FactorThresholdPolicy.policy_precedence.asc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def list_all_threshold_policies(self) -> List[FactorThresholdPolicy]:
        stmt = select(FactorThresholdPolicy).order_by(FactorThresholdPolicy.policy_precedence.asc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # -------------------------------------------------------------------------
    # 4. Monitoring Runs
    # -------------------------------------------------------------------------

    async def create_monitoring_run(self, run: FactorMonitoringRun) -> FactorMonitoringRun:
        self.session.add(run)
        await self.session.flush()
        await self.session.refresh(run)
        return run

    async def get_monitoring_run_by_id(self, run_id: str) -> Optional[FactorMonitoringRun]:
        stmt = (
            select(FactorMonitoringRun)
            .options(
                selectinload(FactorMonitoringRun.drifts),
                selectinload(FactorMonitoringRun.evaluations),
            )
            .where(FactorMonitoringRun.run_id == run_id)
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_latest_monitoring_run(
        self,
        portfolio_id: str,
        as_of_date: Optional[date] = None,
    ) -> Optional[FactorMonitoringRun]:
        stmt = (
            select(FactorMonitoringRun)
            .options(
                selectinload(FactorMonitoringRun.drifts),
                selectinload(FactorMonitoringRun.evaluations),
            )
            .where(FactorMonitoringRun.portfolio_id == portfolio_id)
        )
        if as_of_date:
            stmt = stmt.where(FactorMonitoringRun.as_of_date <= as_of_date)
        stmt = stmt.order_by(FactorMonitoringRun.as_of_date.desc(), FactorMonitoringRun.created_at.desc())
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_monitoring_runs_for_portfolio(
        self,
        portfolio_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100,
    ) -> List[FactorMonitoringRun]:
        stmt = (
            select(FactorMonitoringRun)
            .options(
                selectinload(FactorMonitoringRun.drifts),
                selectinload(FactorMonitoringRun.evaluations),
            )
            .where(FactorMonitoringRun.portfolio_id == portfolio_id)
        )
        if start_date:
            stmt = stmt.where(FactorMonitoringRun.as_of_date >= start_date)
        if end_date:
            stmt = stmt.where(FactorMonitoringRun.as_of_date <= end_date)
        stmt = stmt.order_by(FactorMonitoringRun.as_of_date.desc()).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # -------------------------------------------------------------------------
    # 5. Concentration & Drift Results
    # -------------------------------------------------------------------------

    async def create_concentration_result(self, conc: FactorConcentrationResult) -> FactorConcentrationResult:
        self.session.add(conc)
        await self.session.flush()
        await self.session.refresh(conc)
        return conc

    async def get_concentration_result_by_run_id(self, run_id: str) -> Optional[FactorConcentrationResult]:
        stmt = select(FactorConcentrationResult).where(FactorConcentrationResult.run_id == run_id)
        res = await self.session.execute(stmt)
        return res.scalars().first()

    # -------------------------------------------------------------------------
    # 6. Breach Lifecycle
    # -------------------------------------------------------------------------

    async def get_active_breach(
        self,
        portfolio_id: str,
        policy_id: str,
        factor_code: Optional[str] = None,
    ) -> Optional[FactorMonitoringBreach]:
        stmt = select(FactorMonitoringBreach).where(
            and_(
                FactorMonitoringBreach.portfolio_id == portfolio_id,
                FactorMonitoringBreach.policy_id == policy_id,
                FactorMonitoringBreach.factor_code == factor_code,
                FactorMonitoringBreach.breach_status.in_([BreachStatus.ACTIVE, BreachStatus.ACKNOWLEDGED, BreachStatus.RECOVERY_PENDING]),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def create_or_update_breach(self, breach: FactorMonitoringBreach) -> FactorMonitoringBreach:
        self.session.add(breach)
        await self.session.flush()
        await self.session.refresh(breach)
        return breach

    async def list_active_breaches(
        self,
        portfolio_id: Optional[str] = None,
        severity: Optional[BreachSeverity] = None,
    ) -> List[FactorMonitoringBreach]:
        stmt = select(FactorMonitoringBreach).where(
            FactorMonitoringBreach.breach_status.in_([BreachStatus.ACTIVE, BreachStatus.ACKNOWLEDGED, BreachStatus.RECOVERY_PENDING])
        )
        if portfolio_id:
            stmt = stmt.where(FactorMonitoringBreach.portfolio_id == portfolio_id)
        if severity:
            stmt = stmt.where(FactorMonitoringBreach.severity == severity)
        stmt = stmt.order_by(FactorMonitoringBreach.first_detected_at.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_breach_by_id(self, breach_id: str) -> Optional[FactorMonitoringBreach]:
        stmt = select(FactorMonitoringBreach).where(FactorMonitoringBreach.breach_id == breach_id)
        res = await self.session.execute(stmt)
        return res.scalars().first()

    # -------------------------------------------------------------------------
    # 7. Events
    # -------------------------------------------------------------------------

    async def create_monitoring_event(self, event: FactorMonitoringEvent) -> FactorMonitoringEvent:
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def list_events_for_run(self, run_id: str) -> List[FactorMonitoringEvent]:
        stmt = select(FactorMonitoringEvent).where(FactorMonitoringEvent.run_id == run_id).order_by(FactorMonitoringEvent.created_at.asc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

