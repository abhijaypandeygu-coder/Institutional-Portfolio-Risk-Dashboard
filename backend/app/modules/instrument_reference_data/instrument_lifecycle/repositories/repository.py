from datetime import date, datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from backend.app.modules.instrument_reference_data.instrument_lifecycle.models import (
    ListingLifecycleRecord,
    ListingLifecycleEvent,
    SuspensionEvent,
    ResumptionEvent,
    DelistingEvent
)
from backend.app.modules.instrument_reference_data.instrument_lifecycle.state_machine.transitions import ListingLifecycleStatus


class InstrumentLifecycleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_listing_record(self, listing_id: str) -> Optional[ListingLifecycleRecord]:
        stmt = select(ListingLifecycleRecord).where(ListingLifecycleRecord.listing_id == listing_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_by_instrument(self, instrument_id: str) -> List[ListingLifecycleRecord]:
        stmt = (
            select(ListingLifecycleRecord)
            .where(ListingLifecycleRecord.instrument_id == instrument_id)
            .order_by(ListingLifecycleRecord.created_at.asc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def add_listing_record(self, record: ListingLifecycleRecord) -> ListingLifecycleRecord:
        self.session.add(record)
        await self.session.flush()
        return record

    async def add_event(self, event: ListingLifecycleEvent) -> ListingLifecycleEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    async def add_suspension(self, susp: SuspensionEvent) -> SuspensionEvent:
        self.session.add(susp)
        await self.session.flush()
        return susp

    async def add_resumption(self, resump: ResumptionEvent) -> ResumptionEvent:
        self.session.add(resump)
        await self.session.flush()
        return resump

    async def add_delisting(self, delist: DelistingEvent) -> DelistingEvent:
        self.session.add(delist)
        await self.session.flush()
        return delist

    async def list_events_by_listing(self, listing_id: str) -> List[ListingLifecycleEvent]:
        stmt = (
            select(ListingLifecycleEvent)
            .where(ListingLifecycleEvent.listing_id == listing_id)
            .order_by(ListingLifecycleEvent.effective_date.asc(), ListingLifecycleEvent.recorded_at.asc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_historical_status_as_of(
        self,
        listing_id: str,
        as_of_date: date,
        recorded_as_of: Optional[datetime] = None
    ) -> Optional[ListingLifecycleStatus]:
        stmt = (
            select(ListingLifecycleEvent)
            .where(
                ListingLifecycleEvent.listing_id == listing_id,
                ListingLifecycleEvent.effective_date <= as_of_date
            )
        )
        if recorded_as_of:
            stmt = stmt.where(ListingLifecycleEvent.recorded_at <= recorded_as_of)
        
        stmt = stmt.order_by(
            ListingLifecycleEvent.effective_date.desc(),
            ListingLifecycleEvent.recorded_at.desc()
        )
        res = await self.session.execute(stmt)
        latest_event = res.scalars().first()
        return latest_event.new_status if latest_event else None

