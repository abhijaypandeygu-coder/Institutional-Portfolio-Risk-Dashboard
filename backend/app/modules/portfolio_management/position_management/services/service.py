"""Service layer for M05.02 - Position Management."""
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
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
    PositionEventType,
    PositionEventStatus,
    TransferStatus,
    BorrowStatus,
    ReconciliationStatus,
)
from backend.app.modules.portfolio_management.position_management.schemas import (
    PositionBookRegisterRequest,
    PositionEventRegisterRequest,
    PositionBorrowRegisterRequest,
    PositionTransferCreateRequest,
    PositionReconciliationSubmitRequest,
)
from backend.app.modules.portfolio_management.position_management.repositories.repository import PositionRepository


class PositionManagementService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PositionRepository(session)

    # -----------------------------------------------------------------------
    # 1. POSITION BOOK REGISTRATION
    # -----------------------------------------------------------------------
    async def get_or_create_position_book(self, req: PositionBookRegisterRequest) -> PositionBook:
        existing = await self.repo.get_book_by_identity(
            portfolio_id=req.portfolio_id,
            account_id=req.account_id,
            instrument_id=req.instrument_id,
            listing_id=req.listing_id,
        )
        if existing:
            return existing

        pos_id = f"POS_{uuid.uuid4().hex[:12].upper()}"
        book = PositionBook(
            position_id=pos_id,
            portfolio_id=req.portfolio_id,
            account_id=req.account_id,
            instrument_id=req.instrument_id,
            listing_id=req.listing_id,
            sleeve_id=req.sleeve_id,
            position_side=PositionSide.FLAT,
            position_status=PositionStatus.OPEN,
            current_snapshot_version=1,
        )
        book = await self.repo.create_position_book(book)

        # Initial zero snapshot
        init_snap = PositionSnapshot(
            snapshot_id=f"SNAP_{uuid.uuid4().hex[:10].upper()}",
            position_id=pos_id,
            portfolio_id=req.portfolio_id,
            account_id=req.account_id,
            instrument_id=req.instrument_id,
            listing_id=req.listing_id,
            position_side=PositionSide.FLAT,
            gross_long_quantity=Decimal("0.0"),
            gross_short_quantity=Decimal("0.0"),
            net_signed_quantity=Decimal("0.0"),
            settled_quantity=Decimal("0.0"),
            unsettled_quantity=Decimal("0.0"),
            economic_quantity=Decimal("0.0"),
            available_quantity=Decimal("0.0"),
            effective_timestamp=datetime.utcnow(),
            snapshot_version=1,
        )
        await self.repo.save_snapshot(init_snap)
        await self.session.commit()
        await self.session.refresh(book)
        return book

    # -----------------------------------------------------------------------
    # 2. EVENT INGESTION & QUANTITY APPLICATION
    # -----------------------------------------------------------------------
    async def apply_position_event(self, req: PositionEventRegisterRequest) -> PositionSnapshot:
        # Idempotency check
        existing_event = await self.repo.get_event_by_idempotency_key(req.idempotency_key)
        if existing_event:
            # Idempotent return of current latest snapshot
            latest = await self.repo.get_latest_snapshot(existing_event.position_id)
            if latest:
                return latest

        # Ensure Position Book exists
        book = await self.get_or_create_position_book(
            PositionBookRegisterRequest(
                portfolio_id=req.portfolio_id,
                account_id=req.account_id,
                instrument_id=req.instrument_id,
                listing_id=req.listing_id,
            )
        )

        effective_ts = req.effective_timestamp or datetime.utcnow()
        event_id = f"EVT_{uuid.uuid4().hex[:12].upper()}"

        # Fetch current latest snapshot
        current_snap = await self.repo.get_latest_snapshot(book.position_id)
        prev_net = current_snap.net_signed_quantity if current_snap else Decimal("0.0")
        prev_settled = current_snap.settled_quantity if current_snap else Decimal("0.0")
        prev_unsettled = current_snap.unsettled_quantity if current_snap else Decimal("0.0")

        # Compute new quantities based on event type
        new_net = prev_net + req.signed_quantity_delta
        
        # If settlement event: moves between unsettled and settled without changing net economic quantity
        if req.event_type == PositionEventType.SETTLEMENT:
            new_settled = prev_settled + req.settled_quantity_delta
            new_unsettled = prev_unsettled + req.unsettled_quantity_delta
            new_net = prev_net # Net economic stays identical
        else:
            # Trade or transfer: update settled or unsettled deltas
            new_settled = prev_settled + (req.settled_quantity_delta or Decimal("0.0"))
            new_unsettled = prev_unsettled + (req.unsettled_quantity_delta or Decimal("0.0"))

        # Gross Long and Short separation
        if new_net > 0:
            new_side = PositionSide.LONG
            gross_long = new_net
            gross_short = Decimal("0.0")
        elif new_net < 0:
            new_side = PositionSide.SHORT
            gross_long = Decimal("0.0")
            gross_short = abs(new_net)
        else:
            new_side = PositionSide.FLAT
            gross_long = Decimal("0.0")
            gross_short = Decimal("0.0")

        # Economic quantity = settled + unsettled
        economic_qty = new_settled + new_unsettled if (new_settled or new_unsettled) else new_net

        # Create immutable event record
        event = PositionEvent(
            position_event_id=event_id,
            position_id=book.position_id,
            portfolio_id=req.portfolio_id,
            account_id=req.account_id,
            instrument_id=req.instrument_id,
            listing_id=req.listing_id,
            event_type=req.event_type,
            event_status=PositionEventStatus.APPLIED,
            signed_quantity_delta=req.signed_quantity_delta,
            settled_quantity_delta=req.settled_quantity_delta or Decimal("0.0"),
            unsettled_quantity_delta=req.unsettled_quantity_delta or Decimal("0.0"),
            effective_timestamp=effective_ts,
            source_system=req.source_system,
            source_event_id=req.source_event_id,
            transaction_reference=req.transaction_reference,
            corporate_action_reference=req.corporate_action_reference,
            transfer_reference=req.transfer_reference,
            idempotency_key=req.idempotency_key,
            reason=req.reason,
        )
        await self.repo.add_event(event)

        # Update Book state
        book.position_side = new_side
        book.current_snapshot_version += 1
        if new_side == PositionSide.FLAT:
            book.position_status = PositionStatus.CLOSED
        else:
            book.position_status = PositionStatus.ACTIVE

        # Save new snapshot projection
        new_snap = PositionSnapshot(
            snapshot_id=f"SNAP_{uuid.uuid4().hex[:10].upper()}",
            position_id=book.position_id,
            portfolio_id=req.portfolio_id,
            account_id=req.account_id,
            instrument_id=req.instrument_id,
            listing_id=req.listing_id,
            position_side=new_side,
            gross_long_quantity=gross_long,
            gross_short_quantity=gross_short,
            net_signed_quantity=new_net,
            settled_quantity=new_settled,
            unsettled_quantity=new_unsettled,
            economic_quantity=economic_qty,
            available_quantity=new_settled if new_side == PositionSide.LONG else Decimal("0.0"),
            effective_timestamp=effective_ts,
            last_applied_event_id=event_id,
            snapshot_version=book.current_snapshot_version,
        )
        new_snap = await self.repo.save_snapshot(new_snap)

        # Update Portfolio-Level Aggregate
        await self._refresh_portfolio_aggregate(req.portfolio_id, req.instrument_id, req.listing_id, effective_ts)

        await self.session.commit()
        await self.session.refresh(new_snap)
        return new_snap

    # -----------------------------------------------------------------------
    # 3. TRANSFERS
    # -----------------------------------------------------------------------
    async def process_transfer(self, req: PositionTransferCreateRequest) -> PositionTransfer:
        transfer_id = f"TRF_{uuid.uuid4().hex[:10].upper()}"
        effective_ts = req.effective_timestamp or datetime.utcnow()

        transfer = PositionTransfer(
            transfer_id=transfer_id,
            source_portfolio_id=req.source_portfolio_id,
            source_account_id=req.source_account_id,
            destination_portfolio_id=req.destination_portfolio_id,
            destination_account_id=req.destination_account_id,
            instrument_id=req.instrument_id,
            listing_id=req.listing_id,
            quantity=req.quantity,
            transfer_status=TransferStatus.COMPLETED,
            source_confirmed=True,
            destination_confirmed=True,
            effective_timestamp=effective_ts,
            transfer_reason=req.transfer_reason,
        )
        transfer = await self.repo.create_transfer(transfer)

        # Outbound Leg: negative quantity delta
        await self.apply_position_event(
            PositionEventRegisterRequest(
                portfolio_id=req.source_portfolio_id,
                account_id=req.source_account_id,
                instrument_id=req.instrument_id,
                listing_id=req.listing_id,
                event_type=PositionEventType.TRANSFER_OUT,
                signed_quantity_delta=-req.quantity,
                settled_quantity_delta=-req.quantity,
                effective_timestamp=effective_ts,
                transfer_reference=transfer_id,
                idempotency_key=f"IDEMP_TRF_OUT_{transfer_id}",
                reason=f"Transfer to {req.destination_account_id}",
            )
        )

        # Inbound Leg: positive quantity delta
        await self.apply_position_event(
            PositionEventRegisterRequest(
                portfolio_id=req.destination_portfolio_id,
                account_id=req.destination_account_id,
                instrument_id=req.instrument_id,
                listing_id=req.listing_id,
                event_type=PositionEventType.TRANSFER_IN,
                signed_quantity_delta=req.quantity,
                settled_quantity_delta=req.quantity,
                effective_timestamp=effective_ts,
                transfer_reference=transfer_id,
                idempotency_key=f"IDEMP_TRF_IN_{transfer_id}",
                reason=f"Transfer from {req.source_account_id}",
            )
        )

        await self.session.commit()
        await self.session.refresh(transfer)
        return transfer

    # -----------------------------------------------------------------------
    # 4. BORROW METADATA FOR SHORT POSITIONS
    # -----------------------------------------------------------------------
    async def register_borrow_metadata(
        self, position_id: str, req: PositionBorrowRegisterRequest
    ) -> PositionBorrowMetadata:
        book = await self.repo.get_book_by_id(position_id)
        if not book:
            raise ValueError(f"Position '{position_id}' not found.")

        borrow_id = f"BRW_{uuid.uuid4().hex[:10].upper()}"
        borrow = PositionBorrowMetadata(
            borrow_id=borrow_id,
            position_id=position_id,
            lender_reference=req.lender_reference,
            locate_reference=req.locate_reference,
            borrowed_quantity=req.borrowed_quantity,
            borrow_rate_annual_pct=req.borrow_rate_annual_pct,
            borrow_status=req.borrow_status,
            effective_date=req.effective_date,
            recall_date=req.recall_date,
        )
        borrow = await self.repo.add_borrow_metadata(borrow)
        await self.session.commit()
        await self.session.refresh(borrow)
        return borrow

    # -----------------------------------------------------------------------
    # 5. RECONCILIATION
    # -----------------------------------------------------------------------
    async def submit_reconciliation(
        self, req: PositionReconciliationSubmitRequest
    ) -> PositionReconciliationRecord:
        book = await self.repo.get_book_by_identity(
            portfolio_id=req.portfolio_id,
            account_id=req.account_id,
            instrument_id=req.instrument_id,
        )
        internal_qty = Decimal("0.0")
        pos_id = book.position_id if book else f"UNKNOWN_{req.account_id}_{req.instrument_id}"
        if book:
            snap = await self.repo.get_latest_snapshot(book.position_id)
            if snap:
                internal_qty = snap.net_signed_quantity

        diff = internal_qty - req.external_quantity
        status = ReconciliationStatus.MATCHED if diff == Decimal("0.0") else ReconciliationStatus.QUANTITY_MISMATCH

        rec_id = f"REC_{uuid.uuid4().hex[:10].upper()}"
        rec = PositionReconciliationRecord(
            reconciliation_id=rec_id,
            position_id=pos_id,
            portfolio_id=req.portfolio_id,
            account_id=req.account_id,
            instrument_id=req.instrument_id,
            internal_quantity=internal_qty,
            external_quantity=req.external_quantity,
            difference_quantity=diff,
            reconciliation_status=status,
            source_name=req.source_name,
            as_of_date=req.as_of_date,
        )
        rec = await self.repo.create_reconciliation(rec)
        await self.session.commit()
        await self.session.refresh(rec)
        return rec

    # -----------------------------------------------------------------------
    # 6. HISTORICAL REBUILD
    # -----------------------------------------------------------------------
    async def rebuild_position_history(self, position_id: str) -> PositionSnapshot:
        """
        Reconstructs position snapshots deterministically from the immutable event ledger.
        """
        book = await self.repo.get_book_by_id(position_id)
        if not book:
            raise ValueError(f"Position '{position_id}' not found.")

        events = await self.repo.list_events_for_position(position_id)
        
        running_net = Decimal("0.0")
        running_settled = Decimal("0.0")
        running_unsettled = Decimal("0.0")

        latest_snap = None
        for evt in events:
            if evt.event_type == PositionEventType.SETTLEMENT:
                running_settled += evt.settled_quantity_delta
                running_unsettled += evt.unsettled_quantity_delta
            else:
                running_net += evt.signed_quantity_delta
                running_settled += evt.settled_quantity_delta
                running_unsettled += evt.unsettled_quantity_delta

            if running_net > 0:
                side = PositionSide.LONG
                gross_long = running_net
                gross_short = Decimal("0.0")
            elif running_net < 0:
                side = PositionSide.SHORT
                gross_long = Decimal("0.0")
                gross_short = abs(running_net)
            else:
                side = PositionSide.FLAT
                gross_long = Decimal("0.0")
                gross_short = Decimal("0.0")

            book.current_snapshot_version += 1
            latest_snap = PositionSnapshot(
                snapshot_id=f"SNAP_RB_{uuid.uuid4().hex[:10].upper()}",
                position_id=position_id,
                portfolio_id=book.portfolio_id,
                account_id=book.account_id,
                instrument_id=book.instrument_id,
                listing_id=book.listing_id,
                position_side=side,
                gross_long_quantity=gross_long,
                gross_short_quantity=gross_short,
                net_signed_quantity=running_net,
                settled_quantity=running_settled,
                unsettled_quantity=running_unsettled,
                economic_quantity=running_settled + running_unsettled if (running_settled or running_unsettled) else running_net,
                available_quantity=running_settled if side == PositionSide.LONG else Decimal("0.0"),
                effective_timestamp=evt.effective_timestamp,
                last_applied_event_id=evt.position_event_id,
                snapshot_version=book.current_snapshot_version,
            )
            await self.repo.save_snapshot(latest_snap)

        await self.session.commit()
        return latest_snap

    # -----------------------------------------------------------------------
    # INTERNAL HELPERS
    # -----------------------------------------------------------------------
    async def _refresh_portfolio_aggregate(
        self, portfolio_id: str, instrument_id: str, listing_id: Optional[str], effective_ts: datetime
    ):
        books = await self.repo.list_books_by_portfolio(portfolio_id)
        matching_books = [
            b for b in books if b.instrument_id == instrument_id and b.listing_id == listing_id
        ]

        total_gross_long = Decimal("0.0")
        total_gross_short = Decimal("0.0")
        total_net = Decimal("0.0")
        total_settled = Decimal("0.0")
        total_unsettled = Decimal("0.0")

        contributing_accounts = 0
        for b in matching_books:
            snap = await self.repo.get_latest_snapshot(b.position_id)
            if snap:
                contributing_accounts += 1
                total_gross_long += snap.gross_long_quantity
                total_gross_short += snap.gross_short_quantity
                total_net += snap.net_signed_quantity
                total_settled += snap.settled_quantity
                total_unsettled += snap.unsettled_quantity

        agg = PortfolioPositionAggregate(
            aggregate_id=f"AGG_{uuid.uuid4().hex[:10].upper()}",
            portfolio_id=portfolio_id,
            instrument_id=instrument_id,
            listing_id=listing_id,
            gross_long_quantity=total_gross_long,
            gross_short_quantity=total_gross_short,
            net_signed_quantity=total_net,
            settled_quantity=total_settled,
            unsettled_quantity=total_unsettled,
            available_quantity=total_settled,
            contributing_account_count=contributing_accounts,
            effective_timestamp=effective_ts,
        )
        await self.repo.save_aggregate(agg)

