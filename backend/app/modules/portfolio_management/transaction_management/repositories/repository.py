"""SQLAlchemy 2.0 Repository for M05.05 Transaction Management."""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Tuple
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.portfolio_management.transaction_management.models import (
    Transaction,
    TransactionType,
    TradeSide,
    PositionEffect,
    TransactionStatus,
    TradeExecution,
    ExecutionStatus,
    TransactionLifecycleEvent,
    TransactionFee,
    TransactionTransfer,
    TransactionTransferLeg,
    TransactionAdjustment,
    AdjustmentApprovalStatus,
    TransactionCorrection,
    TransactionSettlement,
    TransactionOutbox,
    OutboxDeliveryStatus,
)


class TransactionManagementRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # -----------------------------------------------------------------------
    # TRANSACTIONS
    # -----------------------------------------------------------------------
    async def create_transaction(self, tx: Transaction) -> Transaction:
        self.session.add(tx)
        await self.session.flush()
        return tx

    async def get_transaction_by_id(self, transaction_id: str) -> Optional[Transaction]:
        stmt = select(Transaction).where(Transaction.transaction_id == transaction_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_transactions(
        self,
        portfolio_id: str,
        account_id: Optional[str] = None,
        instrument_id: Optional[str] = None,
        transaction_type: Optional[TransactionType] = None,
        status: Optional[TransactionStatus] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> List[Transaction]:
        conditions = [Transaction.portfolio_id == portfolio_id]
        if account_id:
            conditions.append(Transaction.account_id == account_id)
        if instrument_id:
            conditions.append(Transaction.instrument_id == instrument_id)
        if transaction_type:
            conditions.append(Transaction.transaction_type == transaction_type)
        if status:
            conditions.append(Transaction.status == status)
        if date_from:
            conditions.append(Transaction.trade_date >= date_from)
        if date_to:
            conditions.append(Transaction.trade_date <= date_to)

        stmt = select(Transaction).where(and_(*conditions)).order_by(Transaction.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # EXECUTIONS
    # -----------------------------------------------------------------------
    async def create_execution(self, execution: TradeExecution) -> TradeExecution:
        self.session.add(execution)
        await self.session.flush()
        return execution

    async def get_execution_by_id(self, execution_id: str) -> Optional[TradeExecution]:
        stmt = select(TradeExecution).where(TradeExecution.execution_id == execution_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_execution_by_external_id(
        self, source_system: str, external_execution_id: str
    ) -> Optional[TradeExecution]:
        stmt = select(TradeExecution).where(
            TradeExecution.source_system == source_system,
            TradeExecution.external_execution_id == external_execution_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_executions_for_transaction(self, transaction_id: str) -> List[TradeExecution]:
        stmt = (
            select(TradeExecution)
            .where(TradeExecution.transaction_id == transaction_id)
            .order_by(TradeExecution.execution_timestamp.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # LIFECYCLE EVENTS
    # -----------------------------------------------------------------------
    async def add_lifecycle_event(self, event: TransactionLifecycleEvent) -> TransactionLifecycleEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_lifecycle_events(self, transaction_id: str) -> List[TransactionLifecycleEvent]:
        stmt = (
            select(TransactionLifecycleEvent)
            .where(TransactionLifecycleEvent.transaction_id == transaction_id)
            .order_by(TransactionLifecycleEvent.effective_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # FEES
    # -----------------------------------------------------------------------
    async def create_fee(self, fee: TransactionFee) -> TransactionFee:
        self.session.add(fee)
        await self.session.flush()
        return fee

    async def list_fees(self, transaction_id: str) -> List[TransactionFee]:
        stmt = select(TransactionFee).where(TransactionFee.transaction_id == transaction_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # TRANSFERS
    # -----------------------------------------------------------------------
    async def create_transfer(self, transfer: TransactionTransfer) -> TransactionTransfer:
        self.session.add(transfer)
        await self.session.flush()
        return transfer

    async def get_transfer_by_id(self, transfer_id: str) -> Optional[TransactionTransfer]:
        stmt = select(TransactionTransfer).where(TransactionTransfer.transfer_id == transfer_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_transfers(self, portfolio_id: str) -> List[TransactionTransfer]:
        stmt = (
            select(TransactionTransfer)
            .where(TransactionTransfer.portfolio_id == portfolio_id)
            .order_by(TransactionTransfer.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # ADJUSTMENTS
    # -----------------------------------------------------------------------
    async def create_adjustment(self, adj: TransactionAdjustment) -> TransactionAdjustment:
        self.session.add(adj)
        await self.session.flush()
        return adj

    async def get_adjustment_by_id(self, adjustment_id: str) -> Optional[TransactionAdjustment]:
        stmt = select(TransactionAdjustment).where(TransactionAdjustment.adjustment_id == adjustment_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_adjustments(self, portfolio_id: str) -> List[TransactionAdjustment]:
        stmt = (
            select(TransactionAdjustment)
            .where(TransactionAdjustment.portfolio_id == portfolio_id)
            .order_by(TransactionAdjustment.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # CORRECTIONS
    # -----------------------------------------------------------------------
    async def create_correction(self, corr: TransactionCorrection) -> TransactionCorrection:
        self.session.add(corr)
        await self.session.flush()
        return corr

    # -----------------------------------------------------------------------
    # OUTBOX
    # -----------------------------------------------------------------------
    async def create_outbox_event(self, outbox: TransactionOutbox) -> TransactionOutbox:
        self.session.add(outbox)
        await self.session.flush()
        return outbox

    async def list_outbox_events_for_aggregate(self, aggregate_id: str) -> List[TransactionOutbox]:
        stmt = (
            select(TransactionOutbox)
            .where(TransactionOutbox.aggregate_id == aggregate_id)
            .order_by(TransactionOutbox.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

