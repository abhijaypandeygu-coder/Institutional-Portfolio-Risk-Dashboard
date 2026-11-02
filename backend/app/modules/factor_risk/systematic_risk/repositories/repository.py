"""
M08.05 Systematic Risk Repository Layer.
Handles asynchronous persistence and queries for:
- Risk configurations
- Covariance snapshots
- Systematic risk runs, instrument details, and portfolio details
- Scenario configurations, shocks, and execution results
- Model coverage records
"""
from datetime import date
from typing import List, Optional
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.factor_risk.systematic_risk.models import (
    FactorRiskConfig,
    FactorCovarianceSnapshot,
    SystematicRiskRun,
    InstrumentSystematicRisk,
    PortfolioSystematicRisk,
    FactorScenarioConfig,
    FactorScenarioShock,
    FactorScenarioRun,
    FactorScenarioComponent,
    FactorModelCoverageRecord,
    CovarianceMethod,
    SystematicTargetType,
)


class SystematicRiskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # =========================================================================
    # 1. RISK CONFIGS
    # =========================================================================

    async def save_config(self, config: FactorRiskConfig) -> FactorRiskConfig:
        self.session.add(config)
        await self.session.flush()
        return config

    async def get_config_by_id(self, config_id: str) -> Optional[FactorRiskConfig]:
        stmt = select(FactorRiskConfig).where(FactorRiskConfig.config_id == config_id)
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_config_by_code(self, code: str) -> Optional[FactorRiskConfig]:
        stmt = select(FactorRiskConfig).where(FactorRiskConfig.config_code == code)
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_configs(self) -> List[FactorRiskConfig]:
        stmt = select(FactorRiskConfig).order_by(FactorRiskConfig.created_at.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # =========================================================================
    # 2. FACTOR COVARIANCE SNAPSHOTS
    # =========================================================================

    async def save_covariance_snapshot(self, snapshot: FactorCovarianceSnapshot) -> FactorCovarianceSnapshot:
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot

    async def get_covariance_snapshot_by_id(self, snapshot_id: str) -> Optional[FactorCovarianceSnapshot]:
        stmt = select(FactorCovarianceSnapshot).where(FactorCovarianceSnapshot.snapshot_id == snapshot_id)
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_latest_covariance_snapshot(
        self,
        factor_model_version_id: str,
        as_of_date: date,
        covariance_method: CovarianceMethod,
    ) -> Optional[FactorCovarianceSnapshot]:
        stmt = (
            select(FactorCovarianceSnapshot)
            .where(
                and_(
                    FactorCovarianceSnapshot.factor_model_version_id == factor_model_version_id,
                    FactorCovarianceSnapshot.estimation_window_end <= as_of_date,
                    FactorCovarianceSnapshot.covariance_method == covariance_method,
                )
            )
            .order_by(desc(FactorCovarianceSnapshot.estimation_window_end))
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    # =========================================================================
    # 3. SYSTEMATIC RISK RUNS
    # =========================================================================

    async def save_run(self, run: SystematicRiskRun) -> SystematicRiskRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_run_by_id(self, run_id: str) -> Optional[SystematicRiskRun]:
        stmt = select(SystematicRiskRun).where(SystematicRiskRun.run_id == run_id)
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_instrument_risk_by_run_id(self, run_id: str) -> Optional[InstrumentSystematicRisk]:
        stmt = select(InstrumentSystematicRisk).where(InstrumentSystematicRisk.run_id == run_id)
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_portfolio_risk_by_run_id(self, run_id: str) -> Optional[PortfolioSystematicRisk]:
        stmt = select(PortfolioSystematicRisk).where(PortfolioSystematicRisk.run_id == run_id)
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_latest_risk_run(
        self,
        target_type: SystematicTargetType,
        target_id: str,
        as_of_date: date,
    ) -> Optional[SystematicRiskRun]:
        stmt = (
            select(SystematicRiskRun)
            .where(
                and_(
                    SystematicRiskRun.target_type == target_type,
                    SystematicRiskRun.target_id == target_id,
                    SystematicRiskRun.as_of_date <= as_of_date,
                )
            )
            .order_by(desc(SystematicRiskRun.as_of_date), desc(SystematicRiskRun.id))
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    # =========================================================================
    # 4. SCENARIO CONFIGS & RUNS
    # =========================================================================

    async def save_scenario_config(self, config: FactorScenarioConfig) -> FactorScenarioConfig:
        self.session.add(config)
        await self.session.flush()
        return config

    async def get_scenario_config_by_id(self, scenario_id: str) -> Optional[FactorScenarioConfig]:
        stmt = (
            select(FactorScenarioConfig)
            .options(selectinload(FactorScenarioConfig.shocks))
            .where(FactorScenarioConfig.scenario_id == scenario_id)
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_scenario_configs(self) -> List[FactorScenarioConfig]:
        stmt = select(FactorScenarioConfig).options(selectinload(FactorScenarioConfig.shocks)).order_by(FactorScenarioConfig.created_at.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def save_scenario_run(self, run: FactorScenarioRun) -> FactorScenarioRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_scenario_run_by_id(self, run_id: str) -> Optional[FactorScenarioRun]:
        stmt = (
            select(FactorScenarioRun)
            .options(selectinload(FactorScenarioRun.components))
            .where(FactorScenarioRun.run_id == run_id)
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    # =========================================================================
    # 5. MODEL COVERAGE RECORDS
    # =========================================================================

    async def save_coverage_record(self, record: FactorModelCoverageRecord) -> FactorModelCoverageRecord:
        self.session.add(record)
        await self.session.flush()
        return record

    async def list_coverage_records(self, portfolio_id: str, as_of_date: date) -> List[FactorModelCoverageRecord]:
        stmt = (
            select(FactorModelCoverageRecord)
            .where(
                and_(
                    FactorModelCoverageRecord.portfolio_id == portfolio_id,
                    FactorModelCoverageRecord.as_of_date == as_of_date,
                )
            )
            .order_by(FactorModelCoverageRecord.absolute_market_value.desc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

