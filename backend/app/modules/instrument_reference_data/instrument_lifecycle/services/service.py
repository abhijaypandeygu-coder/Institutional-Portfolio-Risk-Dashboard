import uuid
from datetime import date, datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.modules.instrument_reference_data.instrument_lifecycle.models import (
    ListingLifecycleRecord,
    ListingLifecycleEvent,
    SuspensionEvent,
    ResumptionEvent,
    DelistingEvent,
    VerificationStatus
)
from backend.app.modules.instrument_reference_data.instrument_lifecycle.schemas import (
    RegisterListingLifecycleRequest,
    RegisterSuspensionRequest,
    RegisterResumptionRequest,
    RegisterDelistingRequest,
    InstrumentLifecycleSummary,
    ListingLifecycleResponse
)
from backend.app.modules.instrument_reference_data.instrument_lifecycle.state_machine.transitions import (
    ListingLifecycleStatus,
    InstrumentLifecycleStatus,
    validate_listing_transition
)
from backend.app.modules.instrument_reference_data.instrument_lifecycle.repositories.repository import InstrumentLifecycleRepository
from backend.app.modules.instrument_reference_data.instrument_master.models import Instrument


class InstrumentLifecycleService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = InstrumentLifecycleRepository(session)

    async def register_listing_lifecycle(self, req: RegisterListingLifecycleRequest) -> ListingLifecycleRecord:
        # Validate instrument exists
        inst_res = await self.session.execute(
            select(Instrument).where(Instrument.instrument_id == req.instrument_id)
        )
        if not inst_res.scalar_one_or_none():
            raise ValueError(f"Instrument '{req.instrument_id}' does not exist in Instrument Master.")

        existing = await self.repo.get_listing_record(req.listing_id)
        if existing:
            raise ValueError(f"Listing lifecycle record '{req.listing_id}' already exists.")

        record = ListingLifecycleRecord(
            listing_id=req.listing_id,
            instrument_id=req.instrument_id,
            exchange_code=req.exchange_code.upper(),
            market_segment=req.market_segment.upper(),
            first_listing_date=req.first_listing_date,
            first_trading_date=req.first_trading_date,
            current_status=req.initial_status,
            status_as_of=datetime.utcnow()
        )
        await self.repo.add_listing_record(record)

        # Record initial event
        evt = ListingLifecycleEvent(
            event_id=f"EVT_{uuid.uuid4().hex[:12].upper()}",
            listing_id=req.listing_id,
            instrument_id=req.instrument_id,
            event_type="LISTING_INITIALIZATION",
            previous_status=ListingLifecycleStatus.UNKNOWN,
            new_status=req.initial_status,
            effective_date=req.first_trading_date or date.today(),
            reason="Initial listing lifecycle registration",
            source_name="OFFICIAL_REGISTRY"
        )
        await self.repo.add_event(evt)

        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def register_suspension(self, req: RegisterSuspensionRequest) -> SuspensionEvent:
        listing = await self.repo.get_listing_record(req.listing_id)
        if not listing:
            raise ValueError(f"Listing '{req.listing_id}' not found.")

        # Validate transition
        if not validate_listing_transition(listing.current_status, ListingLifecycleStatus.SUSPENDED):
            raise ValueError(
                f"Illegal status transition from '{listing.current_status.value}' to '{ListingLifecycleStatus.SUSPENDED.value}'"
            )

        susp = SuspensionEvent(
            suspension_id=req.suspension_id,
            listing_id=req.listing_id,
            suspension_type=req.suspension_type,
            effective_start_date=req.effective_start_date,
            expected_end_date=req.expected_end_date,
            is_open_ended=req.is_open_ended,
            reason=req.reason,
            source_reference=req.source_reference
        )
        await self.repo.add_suspension(susp)

        # Update listing status projection
        prev_status = listing.current_status
        listing.current_status = ListingLifecycleStatus.SUSPENDED
        listing.status_as_of = datetime.utcnow()

        # Add event
        evt = ListingLifecycleEvent(
            event_id=f"EVT_{uuid.uuid4().hex[:12].upper()}",
            listing_id=req.listing_id,
            instrument_id=listing.instrument_id,
            event_type="SUSPENSION",
            previous_status=prev_status,
            new_status=ListingLifecycleStatus.SUSPENDED,
            effective_date=req.effective_start_date,
            reason=req.reason,
            source_reference=req.source_reference
        )
        await self.repo.add_event(evt)

        await self.session.commit()
        await self.session.refresh(susp)
        return susp

    async def register_resumption(self, req: RegisterResumptionRequest) -> ResumptionEvent:
        listing = await self.repo.get_listing_record(req.listing_id)
        if not listing:
            raise ValueError(f"Listing '{req.listing_id}' not found.")

        if not validate_listing_transition(listing.current_status, ListingLifecycleStatus.ACTIVE):
            raise ValueError(
                f"Illegal status transition from '{listing.current_status.value}' to '{ListingLifecycleStatus.ACTIVE.value}'"
            )

        resump = ResumptionEvent(
            resumption_id=req.resumption_id,
            listing_id=req.listing_id,
            related_suspension_id=req.related_suspension_id,
            resumption_type=req.resumption_type,
            effective_resume_date=req.effective_resume_date,
            conditions=req.conditions,
            reason=req.reason
        )
        await self.repo.add_resumption(resump)

        prev_status = listing.current_status
        listing.current_status = ListingLifecycleStatus.ACTIVE
        listing.status_as_of = datetime.utcnow()

        evt = ListingLifecycleEvent(
            event_id=f"EVT_{uuid.uuid4().hex[:12].upper()}",
            listing_id=req.listing_id,
            instrument_id=listing.instrument_id,
            event_type="RESUMPTION",
            previous_status=prev_status,
            new_status=ListingLifecycleStatus.ACTIVE,
            effective_date=req.effective_resume_date,
            reason=req.reason
        )
        await self.repo.add_event(evt)

        await self.session.commit()
        await self.session.refresh(resump)
        return resump

    async def register_delisting(self, req: RegisterDelistingRequest) -> DelistingEvent:
        listing = await self.repo.get_listing_record(req.listing_id)
        if not listing:
            raise ValueError(f"Listing '{req.listing_id}' not found.")

        delist = DelistingEvent(
            delisting_id=req.delisting_id,
            listing_id=req.listing_id,
            delisting_type=req.delisting_type,
            announcement_date=req.announcement_date,
            last_trading_date=req.last_trading_date,
            effective_delisting_date=req.effective_delisting_date,
            reason=req.reason,
            successor_instrument_id=req.successor_instrument_id,
            source_reference=req.source_reference
        )
        await self.repo.add_delisting(delist)

        listing.last_trading_date = req.last_trading_date
        listing.effective_delisting_date = req.effective_delisting_date
        
        # Check if delisting is already effective or just announced
        today = date.today()
        new_status = ListingLifecycleStatus.DELISTED if today >= req.effective_delisting_date else ListingLifecycleStatus.DELISTING_ANNOUNCED

        prev_status = listing.current_status
        listing.current_status = new_status
        listing.status_as_of = datetime.utcnow()

        evt = ListingLifecycleEvent(
            event_id=f"EVT_{uuid.uuid4().hex[:12].upper()}",
            listing_id=req.listing_id,
            instrument_id=listing.instrument_id,
            event_type="DELISTING",
            previous_status=prev_status,
            new_status=new_status,
            effective_date=req.effective_delisting_date,
            reason=req.reason,
            source_reference=req.source_reference
        )
        await self.repo.add_event(evt)

        await self.session.commit()
        await self.session.refresh(delist)
        return delist

    async def get_instrument_summary(self, instrument_id: str) -> InstrumentLifecycleSummary:
        listings = await self.repo.list_by_instrument(instrument_id)
        
        total = len(listings)
        active_count = sum(1 for l in listings if l.current_status == ListingLifecycleStatus.ACTIVE)
        suspended_count = sum(1 for l in listings if l.current_status == ListingLifecycleStatus.SUSPENDED)
        delisted_count = sum(1 for l in listings if l.current_status == ListingLifecycleStatus.DELISTED)

        # Aggregation logic
        if total == 0:
            derived = InstrumentLifecycleStatus.UNKNOWN
        elif active_count == total:
            derived = InstrumentLifecycleStatus.ACTIVE
        elif active_count > 0:
            derived = InstrumentLifecycleStatus.PARTIALLY_TRADABLE
        elif suspended_count == total:
            derived = InstrumentLifecycleStatus.SUSPENDED_ALL_LISTINGS
        elif delisted_count == total:
            derived = InstrumentLifecycleStatus.RETIRED
        else:
            derived = InstrumentLifecycleStatus.UNKNOWN

        return InstrumentLifecycleSummary(
            instrument_id=instrument_id,
            derived_status=derived,
            total_listings=total,
            active_listings_count=active_count,
            suspended_listings_count=suspended_count,
            delisted_listings_count=delisted_count,
            listings=[ListingLifecycleResponse.model_validate(l) for l in listings]
        )

