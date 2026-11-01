"""
Repositories for M04.01 Instrument Master.
Implements indexed queries, temporal effective-date filtering, and audit trail persistence.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, update, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.instrument_reference_data.instrument_master.models import (
    Instrument,
    InstrumentListing,
    InstrumentIdentifier,
    InstrumentSource,
    InstrumentAttributeHistory,
    InstrumentImportBatch,
    InstrumentImportRecord,
    InstrumentIdentityReview,
    InstrumentAuditEvent,
    utc_now,
)


class InstrumentRepository:
    """Repository handling database operations for Instrument Master."""

    @staticmethod
    async def create_audit_event(
        session: AsyncSession,
        action_type: str,
        new_state: str,
        actor_id: str,
        reason: str,
        instrument_id: Optional[str] = None,
        listing_id: Optional[str] = None,
        previous_state: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> InstrumentAuditEvent:
        event = InstrumentAuditEvent(
            instrument_id=instrument_id,
            listing_id=listing_id,
            action_type=action_type,
            previous_state=previous_state,
            new_state=new_state,
            actor_id=actor_id,
            reason=reason,
            metadata_snapshot=metadata,
        )
        session.add(event)
        return event

    @staticmethod
    async def get_by_instrument_id(
        session: AsyncSession, instrument_id: str
    ) -> Optional[Instrument]:
        stmt = select(Instrument).where(Instrument.instrument_id == instrument_id)
        return (await session.execute(stmt)).scalars().first()

    @staticmethod
    async def get_by_isin(
        session: AsyncSession, isin: str
    ) -> Optional[Instrument]:
        stmt = select(Instrument).where(Instrument.isin == isin)
        return (await session.execute(stmt)).scalars().first()

    @staticmethod
    async def list_instruments(
        session: AsyncSession,
        query: Optional[str] = None,
        instrument_type: Optional[str] = None,
        lifecycle_status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Instrument]:
        stmt = select(Instrument).order_by(desc(Instrument.created_at))
        if query:
            stmt = stmt.where(
                or_(
                    Instrument.canonical_name.ilike(f"%{query}%"),
                    Instrument.short_name.ilike(f"%{query}%"),
                    Instrument.issuer_name.ilike(f"%{query}%"),
                    Instrument.isin == query.upper(),
                )
            )
        if instrument_type:
            stmt = stmt.where(Instrument.instrument_type == instrument_type)
        if lifecycle_status:
            stmt = stmt.where(Instrument.lifecycle_status == lifecycle_status)
        stmt = stmt.limit(limit).offset(offset)
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    async def get_listings_for_instrument(
        session: AsyncSession, instrument_id: str, active_only: bool = True
    ) -> List[InstrumentListing]:
        stmt = select(InstrumentListing).where(InstrumentListing.instrument_id == instrument_id)
        if active_only:
            stmt = stmt.where(InstrumentListing.listing_status == "ACTIVE")
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    async def get_listing_by_id(
        session: AsyncSession, listing_id: str
    ) -> Optional[InstrumentListing]:
        stmt = select(InstrumentListing).where(InstrumentListing.listing_id == listing_id)
        return (await session.execute(stmt)).scalars().first()

    @staticmethod
    async def find_listing_by_symbol(
        session: AsyncSession, exchange_id: str, exchange_symbol: str
    ) -> Optional[InstrumentListing]:
        stmt = select(InstrumentListing).where(
            InstrumentListing.exchange_id == exchange_id,
            InstrumentListing.exchange_symbol == exchange_symbol,
            InstrumentListing.listing_status == "ACTIVE",
        )
        return (await session.execute(stmt)).scalars().first()

    @staticmethod
    async def find_listings_by_symbol_only(
        session: AsyncSession, exchange_symbol: str
    ) -> List[InstrumentListing]:
        stmt = select(InstrumentListing).where(
            InstrumentListing.exchange_symbol == exchange_symbol,
            InstrumentListing.listing_status == "ACTIVE",
        )
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    async def get_history(
        session: AsyncSession, instrument_id: str
    ) -> List[InstrumentAttributeHistory]:
        stmt = select(InstrumentAttributeHistory).where(
            InstrumentAttributeHistory.instrument_id == instrument_id
        ).order_by(desc(InstrumentAttributeHistory.recorded_at))
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    async def get_import_batch(
        session: AsyncSession, batch_reference: str
    ) -> Optional[InstrumentImportBatch]:
        stmt = select(InstrumentImportBatch).where(InstrumentImportBatch.batch_reference == batch_reference)
        return (await session.execute(stmt)).scalars().first()

    @staticmethod
    async def list_identity_reviews(
        session: AsyncSession, status: Optional[str] = None
    ) -> List[InstrumentIdentityReview]:
        stmt = select(InstrumentIdentityReview).order_by(desc(InstrumentIdentityReview.created_at))
        if status:
            stmt = stmt.where(InstrumentIdentityReview.review_status == status)
        return list((await session.execute(stmt)).scalars().all())
