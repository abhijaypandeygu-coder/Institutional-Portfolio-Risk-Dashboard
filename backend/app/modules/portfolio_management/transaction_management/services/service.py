"""Service layer for M05.05 Transaction Management."""
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
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
    AdjustmentCategory,
    AdjustmentApprovalStatus,
    TransactionCorrection,
    TransactionSettlement,
    TransactionOutbox,
    OutboxDeliveryStatus,
    TransferStatus,
    SettlementStatus,
)
from backend.app.modules.portfolio_management.transaction_management.schemas import (
    TransactionCreate,
    TradeExecutionCreate,
    TransactionFeeCreate,
    SecurityTransferCreate,
    CashTransferCreate,
    AdjustmentCreate,
    ExecutionCorrectionCreate,
)
from backend.app.modules.portfolio_management.transaction_management.repositories.repository import (
    TransactionManagementRepository,
)


class TransactionManagementService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = TransactionManagementRepository(session)

    # -----------------------------------------------------------------------
    # 1. TRANSACTION CAPTURE
    # -----------------------------------------------------------------------
    async def create_transaction(self, dto: TransactionCreate) -> Transaction:
        tx_id = f"tx_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()
        req_qty = Decimal(str(dto.requested_quantity))

        tx = Transaction(
            transaction_id=tx_id,
            portfolio_id=dto.portfolio_id,
            account_id=dto.account_id,
            instrument_id=dto.instrument_id,
            listing_id=dto.listing_id,
            transaction_type=dto.transaction_type,
            trade_side=dto.trade_side,
            position_effect=dto.position_effect,
            transaction_currency=dto.transaction_currency.upper(),
            requested_quantity=req_qty,
            executed_quantity=Decimal("0.000000"),
            remaining_quantity=req_qty,
            cancelled_quantity=Decimal("0.000000"),
            trade_date=date.today(),
            expected_settlement_date=dto.expected_settlement_date,
            status=TransactionStatus.PENDING,
            source_system=dto.source_system,
            external_order_reference=dto.external_order_reference,
            external_trade_reference=dto.external_trade_reference,
            created_at=now,
            updated_at=now,
        )
        await self.repo.create_transaction(tx)

        # Record initial lifecycle event
        await self.repo.add_lifecycle_event(
            TransactionLifecycleEvent(
                transaction_id=tx_id,
                previous_status="NONE",
                new_status=TransactionStatus.PENDING.value,
                event_type="ORDER_CAPTURED",
                source_system=dto.source_system,
                reason="Transaction registered",
                effective_at=now,
                recorded_at=now,
            )
        )
        return tx

    # -----------------------------------------------------------------------
    # 2. EXECUTION CAPTURE & AGGREGATION
    # -----------------------------------------------------------------------
    async def record_execution(self, transaction_id: str, dto: TradeExecutionCreate) -> TradeExecution:
        tx = await self.repo.get_transaction_by_id(transaction_id)
        if not tx:
            raise ValueError(f"Transaction {transaction_id} not found")

        # Idempotency check on external_execution_id
        if dto.external_execution_id:
            existing = await self.repo.get_execution_by_external_id(
                dto.source_system, dto.external_execution_id
            )
            if existing:
                return existing

        now = datetime.utcnow()
        exec_qty = Decimal(str(dto.executed_quantity))
        exec_price = Decimal(str(dto.execution_price))
        gross = exec_qty * exec_price

        exec_id = f"exec_{uuid.uuid4().hex[:12]}"
        execution = TradeExecution(
            execution_id=exec_id,
            transaction_id=transaction_id,
            portfolio_id=tx.portfolio_id,
            account_id=tx.account_id,
            instrument_id=tx.instrument_id or "UNKNOWN",
            listing_id=tx.listing_id,
            trade_side=tx.trade_side or TradeSide.BUY,
            position_effect=tx.position_effect,
            executed_quantity=exec_qty,
            execution_price=exec_price,
            execution_currency=dto.execution_currency.upper(),
            gross_consideration=gross,
            execution_timestamp=dto.execution_timestamp or now,
            trade_date=date.today(),
            source_system=dto.source_system,
            external_execution_id=dto.external_execution_id,
            broker_reference=dto.broker_reference,
            source_sequence=dto.source_sequence,
            execution_status=ExecutionStatus.CONFIRMED,
            created_at=now,
        )
        await self.repo.create_execution(execution)

        # Update Transaction Aggregates
        prev_status = tx.status
        all_execs = await self.repo.list_executions_for_transaction(transaction_id)
        total_qty = sum((e.executed_quantity for e in all_execs if e.execution_status == ExecutionStatus.CONFIRMED), Decimal("0.000000"))
        total_gross = sum((e.gross_consideration for e in all_execs if e.execution_status == ExecutionStatus.CONFIRMED), Decimal("0.000000"))
        avg_price = (total_gross / total_qty) if total_qty > 0 else Decimal("0.000000")

        tx.executed_quantity = total_qty
        tx.remaining_quantity = max(tx.requested_quantity - total_qty, Decimal("0.000000"))
        tx.aggregate_gross_consideration = total_gross
        tx.average_execution_price = avg_price
        tx.aggregate_net_consideration = (
            (total_gross + tx.aggregate_fees)
            if tx.trade_side == TradeSide.BUY
            else (total_gross - tx.aggregate_fees)
        )
        if not tx.first_execution_at:
            tx.first_execution_at = execution.execution_timestamp
        tx.last_execution_at = execution.execution_timestamp

        # Lifecycle update: FILLED or PARTIALLY_FILLED
        if tx.remaining_quantity == 0 and tx.requested_quantity > 0:
            tx.status = TransactionStatus.FILLED
        else:
            tx.status = TransactionStatus.PARTIALLY_FILLED

        if tx.status != prev_status:
            await self.repo.add_lifecycle_event(
                TransactionLifecycleEvent(
                    transaction_id=transaction_id,
                    previous_status=prev_status.value,
                    new_status=tx.status.value,
                    event_type="FILL_RECORDED",
                    source_system=dto.source_system,
                    reason=f"Execution of {exec_qty} units recorded",
                    effective_at=now,
                    recorded_at=now,
                )
            )

        # 3. Publish Downstream Outbox Events atomically
        # Position Event (M05.02)
        signed_qty = exec_qty if tx.trade_side == TradeSide.BUY else -exec_qty
        pos_payload = {
            "transaction_id": transaction_id,
            "execution_id": exec_id,
            "portfolio_id": tx.portfolio_id,
            "account_id": tx.account_id,
            "instrument_id": tx.instrument_id,
            "listing_id": tx.listing_id,
            "trade_side": tx.trade_side.value if tx.trade_side else "BUY",
            "executed_quantity": str(exec_qty),
            "signed_quantity": str(signed_qty),
            "execution_price": str(exec_price),
            "currency": dto.execution_currency.upper(),
            "execution_timestamp": execution.execution_timestamp.isoformat(),
        }
        await self.repo.create_outbox_event(
            TransactionOutbox(
                outbox_id=f"obx_pos_{uuid.uuid4().hex[:12]}",
                aggregate_type="TRANSACTION",
                aggregate_id=transaction_id,
                event_type="POSITION_EFFECT",
                destination_module="M05.02_POSITION",
                payload=pos_payload,
                idempotency_key=f"pos_{exec_id}",
                delivery_status=OutboxDeliveryStatus.DELIVERED,  # Simulating immediate direct outbox delivery
                delivered_at=now,
            )
        )

        # Cash Event (M05.04)
        cash_signed_amount = -gross if tx.trade_side == TradeSide.BUY else gross
        cash_payload = {
            "transaction_id": transaction_id,
            "execution_id": exec_id,
            "portfolio_id": tx.portfolio_id,
            "account_id": tx.account_id,
            "trade_side": tx.trade_side.value if tx.trade_side else "BUY",
            "gross_consideration": str(gross),
            "signed_amount": str(cash_signed_amount),
            "currency": dto.execution_currency.upper(),
            "execution_timestamp": execution.execution_timestamp.isoformat(),
        }
        await self.repo.create_outbox_event(
            TransactionOutbox(
                outbox_id=f"obx_csh_{uuid.uuid4().hex[:12]}",
                aggregate_type="TRANSACTION",
                aggregate_id=transaction_id,
                event_type="CASH_EFFECT",
                destination_module="M05.04_CASH",
                payload=cash_payload,
                idempotency_key=f"csh_{exec_id}",
                delivery_status=OutboxDeliveryStatus.DELIVERED,
                delivered_at=now,
            )
        )

        return execution

    # -----------------------------------------------------------------------
    # 3. CANCELLATION (Partial remainder cancellation preserves fills)
    # -----------------------------------------------------------------------
    async def cancel_transaction(self, transaction_id: str, reason: str = "Client order cancel") -> Transaction:
        tx = await self.repo.get_transaction_by_id(transaction_id)
        if not tx:
            raise ValueError(f"Transaction {transaction_id} not found")

        now = datetime.utcnow()
        prev_status = tx.status

        if tx.executed_quantity > 0:
            tx.cancelled_quantity = tx.remaining_quantity
            tx.remaining_quantity = Decimal("0.000000")
            tx.status = TransactionStatus.PARTIALLY_FILLED_CANCELLED
        else:
            tx.cancelled_quantity = tx.requested_quantity
            tx.remaining_quantity = Decimal("0.000000")
            tx.status = TransactionStatus.CANCELLED

        await self.repo.add_lifecycle_event(
            TransactionLifecycleEvent(
                transaction_id=transaction_id,
                previous_status=prev_status.value,
                new_status=tx.status.value,
                event_type="ORDER_CANCELLED",
                source_system="USER",
                reason=reason,
                effective_at=now,
                recorded_at=now,
            )
        )
        return tx

    # -----------------------------------------------------------------------
    # 4. TRANSFERS (Security & Cash)
    # -----------------------------------------------------------------------
    async def process_security_transfer(self, dto: SecurityTransferCreate) -> TransactionTransfer:
        transfer_id = f"trf_sec_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()
        qty = Decimal(str(dto.quantity))

        transfer = TransactionTransfer(
            transfer_id=transfer_id,
            portfolio_id=dto.source_portfolio_id,
            source_account_id=dto.source_account_id,
            destination_account_id=dto.destination_account_id,
            transfer_type="SECURITY",
            transfer_direction=dto.transfer_direction,
            instrument_id=dto.instrument_id,
            listing_id=dto.listing_id,
            quantity=qty,
            status=TransferStatus.COMPLETED,
            external_transfer_reference=dto.external_transfer_reference,
            reason=dto.reason,
            effective_at=now,
            completed_at=now,
        )

        # Linked Legs: Outbound from source, Inbound to destination
        legs = [
            TransactionTransferLeg(
                transfer_id=transfer_id,
                leg_type="SECURITY",
                direction="DEBIT",
                portfolio_id=dto.source_portfolio_id,
                account_id=dto.source_account_id,
                instrument_id=dto.instrument_id,
                quantity=qty,
            ),
            TransactionTransferLeg(
                transfer_id=transfer_id,
                leg_type="SECURITY",
                direction="CREDIT",
                portfolio_id=dto.destination_portfolio_id,
                account_id=dto.destination_account_id,
                instrument_id=dto.instrument_id,
                quantity=qty,
            ),
        ]
        transfer.legs = legs
        await self.repo.create_transfer(transfer)

        # Publish Position Outbox Event
        await self.repo.create_outbox_event(
            TransactionOutbox(
                outbox_id=f"obx_trf_{uuid.uuid4().hex[:12]}",
                aggregate_type="TRANSFER",
                aggregate_id=transfer_id,
                event_type="POSITION_TRANSFER",
                destination_module="M05.02_POSITION",
                payload={
                    "transfer_id": transfer_id,
                    "instrument_id": dto.instrument_id,
                    "quantity": str(qty),
                    "source_account": dto.source_account_id,
                    "destination_account": dto.destination_account_id,
                },
                idempotency_key=f"trf_{transfer_id}",
                delivery_status=OutboxDeliveryStatus.DELIVERED,
                delivered_at=now,
            )
        )
        return transfer

    # -----------------------------------------------------------------------
    # 5. CONTROLLED MANUAL ADJUSTMENTS
    # -----------------------------------------------------------------------
    async def create_adjustment_request(self, dto: AdjustmentCreate) -> TransactionAdjustment:
        adj_id = f"adj_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()

        adj = TransactionAdjustment(
            adjustment_id=adj_id,
            portfolio_id=dto.portfolio_id,
            account_id=dto.account_id,
            instrument_id=dto.instrument_id,
            transaction_id=dto.transaction_id,
            adjustment_type=dto.adjustment_type,
            reason=dto.reason,
            original_value=dto.original_value,
            proposed_value=dto.proposed_value,
            adjustment_amount=Decimal(str(dto.adjustment_amount)),
            currency=dto.currency,
            supporting_evidence_reference=dto.supporting_evidence_reference,
            requested_by=dto.requested_by,
            requested_at=now,
            approval_status=AdjustmentApprovalStatus.PENDING_APPROVAL,
            downstream_posting_status="PENDING",
        )
        return await self.repo.create_adjustment(adj)

    async def approve_adjustment(
        self, adjustment_id: str, approver: str = "SUPERVISOR"
    ) -> TransactionAdjustment:
        adj = await self.repo.get_adjustment_by_id(adjustment_id)
        if not adj:
            raise ValueError(f"Adjustment {adjustment_id} not found")

        # Separation of duties: requester cannot self-approve
        if adj.requested_by == approver:
            raise ValueError("Separation of duties violation: requester cannot approve own adjustment")

        now = datetime.utcnow()
        adj.approval_status = AdjustmentApprovalStatus.APPROVED
        adj.approved_by = approver
        adj.approved_at = now
        adj.downstream_posting_status = "POSTED"

        # Publish Outbox event to appropriate downstream module
        dest_mod = (
            "M05.04_CASH" if adj.adjustment_type == AdjustmentCategory.CASH_BALANCE else "M05.02_POSITION"
        )
        await self.repo.create_outbox_event(
            TransactionOutbox(
                outbox_id=f"obx_adj_{uuid.uuid4().hex[:12]}",
                aggregate_type="ADJUSTMENT",
                aggregate_id=adjustment_id,
                event_type="MANUAL_ADJUSTMENT",
                destination_module=dest_mod,
                payload={
                    "adjustment_id": adjustment_id,
                    "adjustment_type": adj.adjustment_type.value,
                    "amount": str(adj.adjustment_amount),
                    "reason": adj.reason,
                    "approver": approver,
                },
                idempotency_key=f"adj_{adjustment_id}",
                delivery_status=OutboxDeliveryStatus.DELIVERED,
                delivered_at=now,
            )
        )
        return adj

    # -----------------------------------------------------------------------
    # 6. CORRECTIONS & TRADE BUSTS
    # -----------------------------------------------------------------------
    async def correct_execution(self, dto: ExecutionCorrectionCreate) -> TradeExecution:
        orig = await self.repo.get_execution_by_id(dto.execution_id)
        if not orig:
            raise ValueError(f"Execution {dto.execution_id} not found")

        now = datetime.utcnow()
        old_vals = {
            "executed_quantity": str(orig.executed_quantity),
            "execution_price": str(orig.execution_price),
            "gross_consideration": str(orig.gross_consideration),
            "execution_status": orig.execution_status.value,
        }

        # Mark original execution as CORRECTED
        orig.execution_status = ExecutionStatus.CORRECTED

        # Create replacement execution preserving lineage
        new_qty = Decimal(str(dto.new_quantity)) if dto.new_quantity else orig.executed_quantity
        new_price = Decimal(str(dto.new_price)) if dto.new_price else orig.execution_price
        new_gross = new_qty * new_price

        new_exec_id = f"exec_{uuid.uuid4().hex[:12]}"
        replacement = TradeExecution(
            execution_id=new_exec_id,
            transaction_id=orig.transaction_id,
            portfolio_id=orig.portfolio_id,
            account_id=orig.account_id,
            instrument_id=orig.instrument_id,
            listing_id=orig.listing_id,
            trade_side=orig.trade_side,
            position_effect=orig.position_effect,
            executed_quantity=new_qty,
            execution_price=new_price,
            execution_currency=orig.execution_currency,
            gross_consideration=new_gross,
            execution_timestamp=orig.execution_timestamp,
            trade_date=orig.trade_date,
            source_system=dto.source_system,
            execution_status=ExecutionStatus.CONFIRMED,
            correction_version=orig.correction_version + 1,
            supersedes_execution_id=orig.execution_id,
            created_at=now,
        )
        await self.repo.create_execution(replacement)

        # Record Correction audit record
        corr_id = f"corr_{uuid.uuid4().hex[:12]}"
        new_vals = {
            "executed_quantity": str(new_qty),
            "execution_price": str(new_price),
            "gross_consideration": str(new_gross),
            "replacement_execution_id": new_exec_id,
        }
        await self.repo.create_correction(
            TransactionCorrection(
                correction_id=corr_id,
                original_transaction_id=orig.transaction_id,
                original_execution_id=orig.execution_id,
                correction_type="AMENDMENT",
                correction_reason=dto.reason,
                old_values=old_vals,
                new_values=new_vals,
                source_system=dto.source_system,
                effective_at=now,
            )
        )

        # Recalculate transaction aggregate
        tx = await self.repo.get_transaction_by_id(orig.transaction_id)
        if tx:
            all_execs = await self.repo.list_executions_for_transaction(orig.transaction_id)
            total_qty = sum((e.executed_quantity for e in all_execs if e.execution_status == ExecutionStatus.CONFIRMED), Decimal("0.000000"))
            total_gross = sum((e.gross_consideration for e in all_execs if e.execution_status == ExecutionStatus.CONFIRMED), Decimal("0.000000"))
            tx.executed_quantity = total_qty
            tx.aggregate_gross_consideration = total_gross
            tx.average_execution_price = (total_gross / total_qty) if total_qty > 0 else Decimal("0.000000")
            tx.status = TransactionStatus.CORRECTED

        return replacement
