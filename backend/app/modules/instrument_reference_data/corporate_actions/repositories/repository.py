from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.app.modules.instrument_reference_data.corporate_actions.models import (
    CorporateAction,
    CorporateActionInstrument,
    CorporateActionVersion,
    CorporateActionDividend,
    CorporateActionRatio,
    CorporateActionMerger,
    CorporateActionAdjustmentRun,
    CorporateActionAdjustmentLineage
)


class CorporateActionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, event_id: str) -> Optional[CorporateAction]:
        stmt = (
            select(CorporateAction)
            .where(CorporateAction.event_id == event_id)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_by_instrument(
        self,
        instrument_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[CorporateAction]:
        stmt = (
            select(CorporateAction)
            .where(CorporateAction.primary_instrument_id == instrument_id)
            .order_by(CorporateAction.effective_date.asc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def add_action(self, action: CorporateAction) -> CorporateAction:
        self.session.add(action)
        await self.session.flush()
        return action

    async def add_version(self, version: CorporateActionVersion) -> CorporateActionVersion:
        self.session.add(version)
        await self.session.flush()
        return version

    async def add_instrument_link(self, link: CorporateActionInstrument) -> CorporateActionInstrument:
        self.session.add(link)
        await self.session.flush()
        return link

    async def add_adjustment_run(self, run: CorporateActionAdjustmentRun) -> CorporateActionAdjustmentRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def add_lineage(self, lineage: CorporateActionAdjustmentLineage) -> CorporateActionAdjustmentLineage:
        self.session.add(lineage)
        await self.session.flush()
        return lineage

    async def get_adjustment_run(self, run_id: str) -> Optional[CorporateActionAdjustmentRun]:
        stmt = select(CorporateActionAdjustmentRun).where(CorporateActionAdjustmentRun.run_id == run_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()
