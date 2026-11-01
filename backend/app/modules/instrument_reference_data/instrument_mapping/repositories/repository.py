from datetime import date
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from backend.app.modules.instrument_reference_data.instrument_mapping.models import (
    IdentifierNamespace,
    ExternalIdentifierMapping,
    MappingConflictRecord,
    MappingStatus
)


class InstrumentMappingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_namespace(self, namespace_code: str) -> Optional[IdentifierNamespace]:
        stmt = select(IdentifierNamespace).where(IdentifierNamespace.namespace_code == namespace_code)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def add_namespace(self, ns: IdentifierNamespace) -> IdentifierNamespace:
        self.session.add(ns)
        await self.session.flush()
        return ns

    async def list_namespaces(self) -> List[IdentifierNamespace]:
        stmt = select(IdentifierNamespace).order_by(IdentifierNamespace.namespace_code.asc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_mapping_by_id(self, mapping_id: str) -> Optional[ExternalIdentifierMapping]:
        stmt = select(ExternalIdentifierMapping).where(ExternalIdentifierMapping.mapping_id == mapping_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def add_mapping(self, mapping: ExternalIdentifierMapping) -> ExternalIdentifierMapping:
        self.session.add(mapping)
        await self.session.flush()
        return mapping

    async def find_candidates(
        self,
        namespace_code: str,
        normalized_identifier: str,
        as_of_date: date,
        exchange_code: Optional[str] = None
    ) -> List[ExternalIdentifierMapping]:
        stmt = (
            select(ExternalIdentifierMapping)
            .where(
                ExternalIdentifierMapping.namespace_code == namespace_code,
                ExternalIdentifierMapping.external_identifier_normalized == normalized_identifier,
                ExternalIdentifierMapping.effective_from <= as_of_date,
                or_(
                    ExternalIdentifierMapping.effective_to.is_(None),
                    ExternalIdentifierMapping.effective_to >= as_of_date
                )
            )
        )
        if exchange_code:
            stmt = stmt.where(
                or_(
                    ExternalIdentifierMapping.exchange_code.is_(None),
                    ExternalIdentifierMapping.exchange_code == exchange_code.upper()
                )
            )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def add_conflict(self, conflict: MappingConflictRecord) -> MappingConflictRecord:
        self.session.add(conflict)
        await self.session.flush()
        return conflict
