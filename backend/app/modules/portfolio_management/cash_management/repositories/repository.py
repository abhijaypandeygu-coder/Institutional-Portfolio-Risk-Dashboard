"""SQLAlchemy 2.0 Repository for M05.04 Cash Management."""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Tuple
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.portfolio_management.cash_management.models import (
    CashAccount,
    CashAccountStatus,
    CashAccountType,
    CashJournal,
    CashJournalLine,
    CashMovement,
    CashMovementStatus,
    CashMovementType,
    CashReservation,
    CashReservationStatus,
    CashReservationEvent,
    CashCommitment,
    CommitmentStatus,
    CommitmentType,
    CashRestriction,
    CashRestrictionStatus,
    CashBalanceSnapshot,
    CashTransferGroup,
    CashReconciliationRun,
    CashPolicy,
    AvailableCashStatus,
)


class CashManagementRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # -----------------------------------------------------------------------
    # CASH ACCOUNTS
    # -----------------------------------------------------------------------
    async def create_cash_account(self, cash_account: CashAccount) -> CashAccount:
        self.session.add(cash_account)
        await self.session.flush()
        return cash_account

    async def get_cash_account_by_id(self, cash_account_id: str) -> Optional[CashAccount]:
        stmt = select(CashAccount).where(CashAccount.cash_account_id == cash_account_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_cash_account(
        self,
        portfolio_id: str,
        account_id: str,
        currency: str,
        cash_account_type: CashAccountType = CashAccountType.TRADING,
    ) -> Optional[CashAccount]:
        stmt = select(CashAccount).where(
            CashAccount.portfolio_id == portfolio_id,
            CashAccount.account_id == account_id,
            CashAccount.currency == currency,
            CashAccount.cash_account_type == cash_account_type,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_cash_accounts_by_portfolio(self, portfolio_id: str) -> List[CashAccount]:
        stmt = select(CashAccount).where(CashAccount.portfolio_id == portfolio_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_cash_accounts_by_account(self, portfolio_id: str, account_id: str) -> List[CashAccount]:
        stmt = select(CashAccount).where(
            CashAccount.portfolio_id == portfolio_id,
            CashAccount.account_id == account_id,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # CASH MOVEMENTS
    # -----------------------------------------------------------------------
    async def create_movement(self, movement: CashMovement) -> CashMovement:
        self.session.add(movement)
        await self.session.flush()
        return movement

    async def get_movement_by_id(self, movement_id: str) -> Optional[CashMovement]:
        stmt = select(CashMovement).where(CashMovement.movement_id == movement_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_movement_by_idempotency_key(self, idempotency_key: str) -> Optional[CashMovement]:
        stmt = select(CashMovement).where(CashMovement.idempotency_key == idempotency_key)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_movements(
        self,
        portfolio_id: str,
        account_id: Optional[str] = None,
        currency: Optional[str] = None,
        movement_type: Optional[CashMovementType] = None,
        status: Optional[CashMovementStatus] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[CashMovement]:
        conditions = [CashMovement.portfolio_id == portfolio_id]
        if account_id:
            conditions.append(CashMovement.account_id == account_id)
        if currency:
            conditions.append(CashMovement.currency == currency)
        if movement_type:
            conditions.append(CashMovement.movement_type == movement_type)
        if status:
            conditions.append(CashMovement.status == status)
        if date_from:
            conditions.append(CashMovement.effective_at >= date_from)
        if date_to:
            conditions.append(CashMovement.effective_at <= date_to)

        stmt = select(CashMovement).where(and_(*conditions)).order_by(CashMovement.effective_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # CASH JOURNALS
    # -----------------------------------------------------------------------
    async def create_journal(self, journal: CashJournal) -> CashJournal:
        self.session.add(journal)
        await self.session.flush()
        return journal

    async def get_journal_by_idempotency_key(self, idempotency_key: str) -> Optional[CashJournal]:
        stmt = select(CashJournal).where(CashJournal.idempotency_key == idempotency_key)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    # -----------------------------------------------------------------------
    # CASH RESERVATIONS
    # -----------------------------------------------------------------------
    async def create_reservation(self, reservation: CashReservation) -> CashReservation:
        self.session.add(reservation)
        await self.session.flush()
        return reservation

    async def get_reservation_by_id(self, reservation_id: str) -> Optional[CashReservation]:
        stmt = select(CashReservation).where(CashReservation.reservation_id == reservation_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_reservation_by_idempotency_key(self, idempotency_key: str) -> Optional[CashReservation]:
        stmt = select(CashReservation).where(CashReservation.idempotency_key == idempotency_key)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_active_reservations(
        self,
        portfolio_id: str,
        account_id: str,
        currency: str,
    ) -> List[CashReservation]:
        stmt = select(CashReservation).where(
            CashReservation.portfolio_id == portfolio_id,
            CashReservation.account_id == account_id,
            CashReservation.currency == currency,
            CashReservation.status.in_([CashReservationStatus.ACTIVE, CashReservationStatus.PARTIALLY_RELEASED]),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add_reservation_event(self, event: CashReservationEvent) -> CashReservationEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    # -----------------------------------------------------------------------
    # RESTRICTIONS & COMMITMENTS
    # -----------------------------------------------------------------------
    async def create_restriction(self, restriction: CashRestriction) -> CashRestriction:
        self.session.add(restriction)
        await self.session.flush()
        return restriction

    async def list_active_restrictions(
        self,
        portfolio_id: str,
        account_id: str,
        currency: str,
    ) -> List[CashRestriction]:
        stmt = select(CashRestriction).where(
            CashRestriction.portfolio_id == portfolio_id,
            CashRestriction.account_id == account_id,
            CashRestriction.currency == currency,
            CashRestriction.status == CashRestrictionStatus.ACTIVE,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_commitment(self, commitment: CashCommitment) -> CashCommitment:
        self.session.add(commitment)
        await self.session.flush()
        return commitment

    async def list_active_commitments(
        self,
        portfolio_id: str,
        account_id: str,
        currency: str,
        commitment_type: Optional[CommitmentType] = None,
    ) -> List[CashCommitment]:
        conditions = [
            CashCommitment.portfolio_id == portfolio_id,
            CashCommitment.account_id == account_id,
            CashCommitment.currency == currency,
            CashCommitment.status.in_([CommitmentStatus.EXPECTED, CommitmentStatus.SCHEDULED, CommitmentStatus.DUE]),
        ]
        if commitment_type:
            conditions.append(CashCommitment.commitment_type == commitment_type)

        stmt = select(CashCommitment).where(and_(*conditions))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # SNAPSHOTS & RECONCILIATION
    # -----------------------------------------------------------------------
    async def create_snapshot(self, snapshot: CashBalanceSnapshot) -> CashBalanceSnapshot:
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot

    async def get_latest_snapshot(
        self,
        portfolio_id: str,
        account_id: str,
        currency: str,
    ) -> Optional[CashBalanceSnapshot]:
        stmt = (
            select(CashBalanceSnapshot)
            .where(
                CashBalanceSnapshot.portfolio_id == portfolio_id,
                CashBalanceSnapshot.account_id == account_id,
                CashBalanceSnapshot.currency == currency,
            )
            .order_by(CashBalanceSnapshot.calculated_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_transfer_group(self, transfer: CashTransferGroup) -> CashTransferGroup:
        self.session.add(transfer)
        await self.session.flush()
        return transfer

    async def get_transfer_group(self, transfer_id: str) -> Optional[CashTransferGroup]:
        stmt = select(CashTransferGroup).where(CashTransferGroup.transfer_id == transfer_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_reconciliation_run(self, run: CashReconciliationRun) -> CashReconciliationRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_policy(self, portfolio_id: str) -> Optional[CashPolicy]:
        stmt = select(CashPolicy).where(CashPolicy.portfolio_id == portfolio_id, CashPolicy.is_active == True)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_policy(self, policy: CashPolicy) -> CashPolicy:
        self.session.add(policy)
        await self.session.flush()
        return policy

