"""
M08.01 Factor Definition Repository Layer.
Handles CRUD and persistence operations for factor definitions, versions,
characteristics, factor models, and pinned memberships.
"""
from datetime import date, datetime
from typing import List, Optional
from sqlalchemy import select, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.factor_risk.factor_definition.models import (
    FactorDefinition,
    FactorDefinitionVersion,
    FactorCharacteristic,
    FactorModel,
    FactorModelVersion,
    FactorModelMembership,
    FactorFamily,
    MarketScope,
    FactorLifecycleStatus,
)


class FactorDefinitionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_factor(self, factor: FactorDefinition) -> FactorDefinition:
        self.session.add(factor)
        await self.session.commit()
        return factor

    async def save_version(self, version: FactorDefinitionVersion) -> FactorDefinitionVersion:
        self.session.add(version)
        await self.session.commit()
        return version

    async def get_factor_by_id(self, factor_id: str) -> Optional[FactorDefinition]:
        stmt = (
            select(FactorDefinition)
            .where(FactorDefinition.factor_id == factor_id)
            .options(
                selectinload(FactorDefinition.versions).selectinload(FactorDefinitionVersion.characteristics)
            )
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_factor_by_code(self, factor_code: str) -> Optional[FactorDefinition]:
        stmt = (
            select(FactorDefinition)
            .where(FactorDefinition.factor_code == factor_code)
            .options(
                selectinload(FactorDefinition.versions).selectinload(FactorDefinitionVersion.characteristics)
            )
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_factors(
        self,
        family: Optional[FactorFamily] = None,
        market: Optional[MarketScope] = None,
        status: Optional[FactorLifecycleStatus] = None,
    ) -> List[FactorDefinition]:
        stmt = select(FactorDefinition).options(
            selectinload(FactorDefinition.versions).selectinload(FactorDefinitionVersion.characteristics)
        )
        if family:
            stmt = stmt.where(FactorDefinition.factor_family == family)
        if status:
            stmt = stmt.where(FactorDefinition.lifecycle_status == status)

        stmt = stmt.order_by(FactorDefinition.factor_code)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_version_by_id(self, version_id: str) -> Optional[FactorDefinitionVersion]:
        stmt = (
            select(FactorDefinitionVersion)
            .where(FactorDefinitionVersion.version_id == version_id)
            .options(selectinload(FactorDefinitionVersion.characteristics))
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_latest_approved_version(self, factor_id: str) -> Optional[FactorDefinitionVersion]:
        stmt = (
            select(FactorDefinitionVersion)
            .where(
                and_(
                    FactorDefinitionVersion.factor_id == factor_id,
                    FactorDefinitionVersion.approval_status.in_([
                        FactorLifecycleStatus.APPROVED,
                        FactorLifecycleStatus.ACTIVE,
                    ]),
                )
            )
            .order_by(desc(FactorDefinitionVersion.version_number))
            .options(selectinload(FactorDefinitionVersion.characteristics))
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    # Factor Model queries
    async def save_model(self, model: FactorModel) -> FactorModel:
        self.session.add(model)
        await self.session.commit()
        return model

    async def save_model_version(self, version: FactorModelVersion) -> FactorModelVersion:
        self.session.add(version)
        await self.session.commit()
        return version

    async def get_model_by_id(self, model_id: str) -> Optional[FactorModel]:
        stmt = (
            select(FactorModel)
            .where(FactorModel.model_id == model_id)
            .options(
                selectinload(FactorModel.model_versions).selectinload(FactorModelVersion.memberships)
            )
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_model_by_code(self, model_code: str) -> Optional[FactorModel]:
        stmt = (
            select(FactorModel)
            .where(FactorModel.model_code == model_code)
            .options(
                selectinload(FactorModel.model_versions).selectinload(FactorModelVersion.memberships)
            )
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_models(self) -> List[FactorModel]:
        stmt = select(FactorModel).options(
            selectinload(FactorModel.model_versions).selectinload(FactorModelVersion.memberships)
        ).order_by(FactorModel.model_code)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
