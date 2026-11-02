"""
M08.03 Factor Sensitivity Repository Layer.
Handles database access for model configs, window configs, estimation runs,
coefficients, model diagnostics, stability profiles, and structural break tests.
"""
from datetime import date
from typing import Optional, List
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.factor_risk.factor_sensitivity.models import (
    FactorSensitivityModelConfig,
    FactorSensitivityWindowConfig,
    FactorSensitivityRun,
    FactorSensitivityCoefficient,
    FactorSensitivityModelDiagnostics,
    FactorSensitivityStability,
    FactorSensitivityBreakTest,
    TargetType,
)


class FactorSensitivityRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # =========================================================================
    # 1. Model & Window Configs
    # =========================================================================

    async def get_config_by_id(self, config_id: str) -> Optional[FactorSensitivityModelConfig]:
        stmt = (
            select(FactorSensitivityModelConfig)
            .options(selectinload(FactorSensitivityModelConfig.window_configs))
            .where(FactorSensitivityModelConfig.config_id == config_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_config_by_code(self, config_code: str) -> Optional[FactorSensitivityModelConfig]:
        stmt = (
            select(FactorSensitivityModelConfig)
            .options(selectinload(FactorSensitivityModelConfig.window_configs))
            .where(FactorSensitivityModelConfig.config_code == config_code)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_config_by_hash(self, config_hash: str) -> Optional[FactorSensitivityModelConfig]:
        stmt = (
            select(FactorSensitivityModelConfig)
            .options(selectinload(FactorSensitivityModelConfig.window_configs))
            .where(FactorSensitivityModelConfig.config_hash == config_hash)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_configs(self) -> List[FactorSensitivityModelConfig]:
        stmt = (
            select(FactorSensitivityModelConfig)
            .options(selectinload(FactorSensitivityModelConfig.window_configs))
            .order_by(FactorSensitivityModelConfig.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def save_config(self, config: FactorSensitivityModelConfig) -> FactorSensitivityModelConfig:
        self.session.add(config)
        await self.session.flush()
        return config

    # =========================================================================
    # 2. Estimation Runs & Coefficients
    # =========================================================================

    async def save_run(self, run: FactorSensitivityRun) -> FactorSensitivityRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_run_by_id(self, run_id: str) -> Optional[FactorSensitivityRun]:
        stmt = (
            select(FactorSensitivityRun)
            .options(
                selectinload(FactorSensitivityRun.coefficients),
                selectinload(FactorSensitivityRun.diagnostics),
            )
            .where(FactorSensitivityRun.run_id == run_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_latest_run_for_target(
        self,
        target_type: TargetType,
        target_id: str,
        as_of_date: Optional[date] = None,
        config_id: Optional[str] = None,
    ) -> Optional[FactorSensitivityRun]:
        filters = [
            FactorSensitivityRun.target_type == target_type,
            FactorSensitivityRun.target_id == target_id,
        ]
        if as_of_date is not None:
            filters.append(FactorSensitivityRun.as_of_date <= as_of_date)
        if config_id is not None:
            filters.append(FactorSensitivityRun.config_id == config_id)

        stmt = (
            select(FactorSensitivityRun)
            .options(
                selectinload(FactorSensitivityRun.coefficients),
                selectinload(FactorSensitivityRun.diagnostics),
            )
            .where(and_(*filters))
            .order_by(desc(FactorSensitivityRun.as_of_date), desc(FactorSensitivityRun.created_at if hasattr(FactorSensitivityRun, "created_at") else FactorSensitivityRun.started_at))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_coefficients_history(
        self,
        target_type: TargetType,
        target_id: str,
        factor_code: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[FactorSensitivityCoefficient]:
        filters = [
            FactorSensitivityRun.target_type == target_type,
            FactorSensitivityRun.target_id == target_id,
        ]
        if start_date is not None:
            filters.append(FactorSensitivityRun.as_of_date >= start_date)
        if end_date is not None:
            filters.append(FactorSensitivityRun.as_of_date <= end_date)
        if factor_code is not None:
            filters.append(FactorSensitivityCoefficient.factor_code == factor_code)

        stmt = (
            select(FactorSensitivityCoefficient)
            .join(FactorSensitivityRun, FactorSensitivityCoefficient.run_id == FactorSensitivityRun.run_id)
            .where(and_(*filters))
            .order_by(FactorSensitivityRun.as_of_date.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # =========================================================================
    # 3. Stability & Break Tests
    # =========================================================================

    async def save_stability(self, stability: FactorSensitivityStability) -> FactorSensitivityStability:
        self.session.add(stability)
        await self.session.flush()
        return stability

    async def get_stability_by_id(self, stability_id: str) -> Optional[FactorSensitivityStability]:
        stmt = (
            select(FactorSensitivityStability)
            .options(selectinload(FactorSensitivityStability.break_tests))
            .where(FactorSensitivityStability.stability_id == stability_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_latest_stability_for_factor(
        self,
        target_type: TargetType,
        target_id: str,
        factor_code: str,
    ) -> Optional[FactorSensitivityStability]:
        stmt = (
            select(FactorSensitivityStability)
            .options(selectinload(FactorSensitivityStability.break_tests))
            .where(
                and_(
                    FactorSensitivityStability.target_type == target_type,
                    FactorSensitivityStability.target_id == target_id,
                    FactorSensitivityStability.factor_code == factor_code,
                )
            )
            .order_by(desc(FactorSensitivityStability.analysis_end), desc(FactorSensitivityStability.created_at))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_stabilities_for_target(
        self,
        target_type: TargetType,
        target_id: str,
    ) -> List[FactorSensitivityStability]:
        stmt = (
            select(FactorSensitivityStability)
            .options(selectinload(FactorSensitivityStability.break_tests))
            .where(
                and_(
                    FactorSensitivityStability.target_type == target_type,
                    FactorSensitivityStability.target_id == target_id,
                )
            )
            .order_by(FactorSensitivityStability.factor_code.asc(), desc(FactorSensitivityStability.analysis_end))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def save_break_test(self, break_test: FactorSensitivityBreakTest) -> FactorSensitivityBreakTest:
        self.session.add(break_test)
        await self.session.flush()
        return break_test
