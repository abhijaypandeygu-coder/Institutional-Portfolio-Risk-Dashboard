"""Database repository for M05.02 - Position Management."""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.portfolio_management.position_management.models import (
    PositionBook,
    PositionEvent,
    PositionSnapshot,
    PortfolioPositionAggregate,
    PositionBorrowMetadata,
    PositionTransfer,
    PositionReconciliationRecord,
    PositionSide,
    PositionStatus,
    PositionEventStatus,
    TransferStatus,
    ReconciliationStatus,
)


class PositionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # -----------------------------------------------------------------------
    # POSITION BOOKS
    # -----------------------------------------------------------------------
    async def create_position_book(self, book: PositionBook) -> PositionBook:
        self.session.add(book)
        await self.session.flush()
        return book

    async def get_book_by_id(self, position_id: str) -> Optional[PositionBook]:
        stmt = select(PositionBook).where(PositionBook.position_id == position_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_book_by_identity(
        self, portfolio_id: str, account_id: str, instrument_id: str, listing_id: Optional[str] = None
    ) -> Optional[PositionBook]:
        stmt = select(PositionBook).where(
            PositionBook.portfolio_id == portfolio_id,
            PositionBook.account_id == account_id,
            PositionBook.instrument_id == instrument_id,
            PositionBook.listing_id == listing_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_books_by_portfolio(self, portfolio_id: str) -> List[PositionBook]:
        stmt = select(PositionBook).where(PositionBook.portfolio_id == portfolio_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_books_by_account(self, account_id: str) -> List[PositionBook]:
        stmt = select(PositionBook).where(PositionBook.account_id == account_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # EVENTS
    # -----------------------------------------------------------------------
    async def get_event_by_idempotency_key(self, idempotency_key: str) -> Optional[PositionEvent]:
        stmt = select(PositionEvent).where(PositionEvent.idempotency_key == idempotency_key)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def add_event(self, event: PositionEvent) -> PositionEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_events_for_position(self, position_id: str) -> List[PositionEvent]:
        stmt = select(PositionEvent).where(
            PositionEvent.position_id == position_id,
            PositionEvent.event_status == PositionEventStatus.APPLIED,
        ).order_by(PositionEvent.effective_timestamp.asc(), PositionEvent.event_sequence.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # SNAPSHOTS
    # -----------------------------------------------------------------------
    async def save_snapshot(self, snapshot: PositionSnapshot) -> PositionSnapshot:
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot

    async def get_latest_snapshot(self, position_id: str) -> Optional[PositionSnapshot]:
        stmt = select(PositionSnapshot).where(
            PositionSnapshot.position_id == position_id
        ).order_by(PositionSnapshot.snapshot_version.desc())
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_snapshot_as_of(self, position_id: str, as_of_dt: datetime) -> Optional[PositionSnapshot]:
        stmt = select(PositionSnapshot).where(
            PositionSnapshot.position_id == position_id,
            PositionSnapshot.effective_timestamp <= as_of_dt,
        ).order_by(PositionSnapshot.effective_timestamp.desc(), PositionSnapshot.snapshot_version.desc())
        result = await self.session.execute(stmt)
        return result.scalars().first()

    # -----------------------------------------------------------------------
    # PORTFOLIO AGGREGATES
    # -----------------------------------------------------------------------
    async def save_aggregate(self, agg: PortfolioPositionAggregate) -> PortfolioPositionAggregate:
        self.session.add(agg)
        await self.session.flush()
        return agg

    async def list_aggregates_for_portfolio(self, portfolio_id: str) -> List[PortfolioPositionAggregate]:
        stmt = select(PortfolioPositionAggregate).where(
            PortfolioPositionAggregate.portfolio_id == portfolio_id
        ).order_by(PortfolioPositionAggregate.id.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # BORROW METADATA
    # -----------------------------------------------------------------------
    async def add_borrow_metadata(self, borrow: PositionBorrowMetadata) -> PositionBorrowMetadata:
        self.session.add(borrow)
        await self.session.flush()
        return borrow

    async def get_borrow_by_position(self, position_id: str) -> Optional[PositionBorrowMetadata]:
        stmt = select(PositionBorrowMetadata).where(
            PositionBorrowMetadata.position_id == position_id
        ).order_by(PositionBorrowMetadata.recorded_at.desc())
        result = await self.session.execute(stmt)
        return result.scalars().first()

    # -----------------------------------------------------------------------
    # TRANSFERS
    # -----------------------------------------------------------------------
    async def create_transfer(self, transfer: PositionTransfer) -> PositionTransfer:
        self.session.add(transfer)
        await self.session.flush()
        return transfer

    async def get_transfer_by_id(self, transfer_id: str) -> Optional[PositionTransfer]:
        stmt = select(PositionTransfer).where(PositionTransfer.transfer_id == transfer_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    # -----------------------------------------------------------------------
    # RECONCILIATION
    # -----------------------------------------------------------------------
    async def create_reconciliation(self, rec: PositionReconciliationRecord) -> PositionReconciliationRecord:
        self.session.add(rec)
        await self.session.flush()
        return rec

    async def get_reconciliation_by_id(self, reconciliation_id: str) -> Optional[PositionReconciliationRecord]:
        stmt = select(PositionReconciliationRecord).where(
            PositionReconciliationRecord.reconciliation_id == reconciliation_id
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_reconciliations(self, portfolio_id: Optional[str] = None) -> List[PositionReconciliationRecord]:
        stmt = select(PositionReconciliationRecord)
        if portfolio_id:
            stmt = stmt.where(PositionReconciliationRecord.portfolio_id == portfolio_id)
        stmt = stmt.order_by(PositionReconciliationRecord.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
