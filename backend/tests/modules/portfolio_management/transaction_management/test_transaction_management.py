"""Tests for M05.05 Transaction Management."""
import pytest
from datetime import datetime, date
from decimal import Decimal

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.modules.portfolio_management.transaction_management.services.service import TransactionManagementService
from backend.app.modules.portfolio_management.transaction_management.models import (
    TransactionStatus,
    TradeSide,
    PositionEffect,
    ExecutionStatus,
    TransferDirection,
    TransferStatus,
    AdjustmentCategory,
    AdjustmentApprovalStatus,
)
from backend.app.modules.portfolio_management.transaction_management.schemas import (
    TransactionCreate,
    TradeExecutionCreate,
    SecurityTransferCreate,
    AdjustmentCreate,
    ExecutionCorrectionCreate,
)


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_multiple_executions_and_average_price_aggregation():
    """Test capturing logical trade with multiple execution fills, computing weighted average price without losing fills."""
    async with AsyncSessionLocal() as session:
        svc = TransactionManagementService(session)
        port_id = "PORT_TX_01"
        acc_id = "ACC_01"

        # 1. Register logical BUY transaction for 100 shares of RELIANCE
        tx_dto = TransactionCreate(
            portfolio_id=port_id,
            account_id=acc_id,
            instrument_id="INST_RELIANCE",
            trade_side=TradeSide.BUY,
            position_effect=PositionEffect.OPEN_LONG,
            transaction_currency="INR",
            requested_quantity=Decimal("100.000000"),
            source_system="ORDER_ROUTER",
            external_order_reference="ORD_1001",
        )
        tx = await svc.create_transaction(tx_dto)
        assert tx.status == TransactionStatus.PENDING
        assert tx.remaining_quantity == Decimal("100.000000")

        # 2. Fill 1: 30 shares at 500 INR
        exec1 = await svc.record_execution(
            tx.transaction_id,
            TradeExecutionCreate(
                executed_quantity=Decimal("30.000000"),
                execution_price=Decimal("500.000000"),
                execution_currency="INR",
                external_execution_id="FILL_01",
            ),
        )
        assert exec1.executed_quantity == Decimal("30.000000")

        # 3. Fill 2: 20 shares at 502 INR
        exec2 = await svc.record_execution(
            tx.transaction_id,
            TradeExecutionCreate(
                executed_quantity=Decimal("20.000000"),
                execution_price=Decimal("502.000000"),
                execution_currency="INR",
                external_execution_id="FILL_02",
            ),
        )

        # 4. Fill 3: 50 shares at 501 INR (completes remaining)
        exec3 = await svc.record_execution(
            tx.transaction_id,
            TradeExecutionCreate(
                executed_quantity=Decimal("50.000000"),
                execution_price=Decimal("501.000000"),
                execution_currency="INR",
                external_execution_id="FILL_03",
            ),
        )

        # 5. Verify Transaction Aggregation:
        # Total Quantity = 30 + 20 + 50 = 100
        # Total Gross = 30*500 (15,000) + 20*502 (10,040) + 50*501 (25,050) = 50,090 INR
        # Average Price = 50,090 / 100 = 500.90 INR
        updated_tx = await svc.repo.get_transaction_by_id(tx.transaction_id)
        assert updated_tx.executed_quantity == Decimal("100.000000")
        assert updated_tx.remaining_quantity == Decimal("0.000000")
        assert updated_tx.aggregate_gross_consideration == Decimal("50090.000000")
        assert updated_tx.average_execution_price == Decimal("500.900000")
        assert updated_tx.status == TransactionStatus.FILLED

        # Verify all 3 individual executions remain preserved in history
        all_execs = await svc.repo.list_executions_for_transaction(tx.transaction_id)
        assert len(all_execs) == 3

        # Verify Outbox events published to Position (M05.02) and Cash (M05.04)
        outbox = await svc.repo.list_outbox_events_for_aggregate(tx.transaction_id)
        assert len(outbox) == 6  # 3 fills * 2 events each (position + cash)


@pytest.mark.asyncio
async def test_partial_fill_cancellation_preserves_executed_quantity():
    """Test cancelling partially filled order cancels unexecuted remainder while preserving fills."""
    async with AsyncSessionLocal() as session:
        svc = TransactionManagementService(session)
        port_id = "PORT_TX_02"
        acc_id = "ACC_01"

        # 1. Register 100 share order
        tx = await svc.create_transaction(
            TransactionCreate(
                portfolio_id=port_id,
                account_id=acc_id,
                instrument_id="INST_AAPL",
                trade_side=TradeSide.BUY,
                position_effect=PositionEffect.OPEN_LONG,
                transaction_currency="USD",
                requested_quantity=Decimal("100.000000"),
            )
        )

        # 2. Fill 40 shares
        await svc.record_execution(
            tx.transaction_id,
            TradeExecutionCreate(
                executed_quantity=Decimal("40.000000"),
                execution_price=Decimal("150.000000"),
                execution_currency="USD",
                external_execution_id="FILL_AAPL_40",
            ),
        )

        # 3. Cancel remaining 60 shares
        cancelled_tx = await svc.cancel_transaction(tx.transaction_id, reason="User cancelled remaining")
        assert cancelled_tx.executed_quantity == Decimal("40.000000")
        assert cancelled_tx.remaining_quantity == Decimal("0.000000")
        assert cancelled_tx.cancelled_quantity == Decimal("60.000000")
        assert cancelled_tx.status == TransactionStatus.PARTIALLY_FILLED_CANCELLED

        # Executions remain preserved
        execs = await svc.repo.list_executions_for_transaction(tx.transaction_id)
        assert len(execs) == 1
        assert execs[0].executed_quantity == Decimal("40.000000")


@pytest.mark.asyncio
async def test_security_transfer_linked_legs_and_outbox():
    """Test internal security transfer creates linked debit/credit legs and outbox events."""
    async with AsyncSessionLocal() as session:
        svc = TransactionManagementService(session)
        port_id = "PORT_TX_03"

        trf_dto = SecurityTransferCreate(
            source_portfolio_id=port_id,
            source_account_id="ACC_DESK_A",
            destination_portfolio_id=port_id,
            destination_account_id="ACC_DESK_B",
            instrument_id="INST_MSFT",
            quantity=Decimal("500.000000"),
            transfer_direction=TransferDirection.INTERNAL,
            reason="Internal desk inventory rebalance",
        )
        trf = await svc.process_security_transfer(trf_dto)
        assert trf.status == TransferStatus.COMPLETED
        assert trf.quantity == Decimal("500.000000")
        assert len(trf.legs) == 2

        # Check linked debit/credit legs
        debit_leg = next(l for l in trf.legs if l.direction == "DEBIT")
        credit_leg = next(l for l in trf.legs if l.direction == "CREDIT")
        assert debit_leg.account_id == "ACC_DESK_A"
        assert credit_leg.account_id == "ACC_DESK_B"
        assert debit_leg.quantity == Decimal("500.000000")

        # Check outbox publication
        outbox = await svc.repo.list_outbox_events_for_aggregate(trf.transfer_id)
        assert len(outbox) == 1
        assert outbox[0].event_type == "POSITION_TRANSFER"


@pytest.mark.asyncio
async def test_controlled_adjustment_separation_of_duties_and_correction_lineage():
    """Test manual adjustment workflow enforces separation of duties and execution corrections preserve lineage."""
    async with AsyncSessionLocal() as session:
        svc = TransactionManagementService(session)
        port_id = "PORT_TX_04"
        acc_id = "ACC_01"

        # 1. Submit Adjustment Request
        adj_dto = AdjustmentCreate(
            portfolio_id=port_id,
            account_id=acc_id,
            adjustment_type=AdjustmentCategory.SECURITY_QUANTITY,
            reason="Corporate reconciliation discrepancy",
            original_value="100",
            proposed_value="105",
            adjustment_amount=Decimal("5.000000"),
            requested_by="TRADER_JANE",
        )
        adj = await svc.create_adjustment_request(adj_dto)
        assert adj.approval_status == AdjustmentApprovalStatus.PENDING_APPROVAL

        # 2. Separation of duties check: Trader Jane cannot approve own adjustment
        with pytest.raises(ValueError, match="Separation of duties violation"):
            await svc.approve_adjustment(adj.adjustment_id, approver="TRADER_JANE")

        # 3. Authorized supervisor approves
        approved_adj = await svc.approve_adjustment(adj.adjustment_id, approver="RISK_MANAGER_BOB")
        assert approved_adj.approval_status == AdjustmentApprovalStatus.APPROVED
        assert approved_adj.approved_by == "RISK_MANAGER_BOB"

        # 4. Execution Correction Test: Price amendment preserves original fill
        tx = await svc.create_transaction(
            TransactionCreate(
                portfolio_id=port_id,
                account_id=acc_id,
                instrument_id="INST_INFY",
                trade_side=TradeSide.BUY,
                transaction_currency="INR",
                requested_quantity=Decimal("50.000000"),
            )
        )
        fill = await svc.record_execution(
            tx.transaction_id,
            TradeExecutionCreate(
                executed_quantity=Decimal("50.000000"),
                execution_price=Decimal("1400.000000"),
                execution_currency="INR",
                external_execution_id="FILL_INFY_01",
            ),
        )

        # Correct fill price from 1400 to 1395
        corr_dto = ExecutionCorrectionCreate(
            execution_id=fill.execution_id,
            new_price=Decimal("1395.000000"),
            reason="Broker price amendment notice",
        )
        replacement = await svc.correct_execution(corr_dto)
        assert replacement.execution_price == Decimal("1395.000000")
        assert replacement.supersedes_execution_id == fill.execution_id

        # Verify original fill is marked CORRECTED and not deleted
        orig_fill = await svc.repo.get_execution_by_id(fill.execution_id)
        assert orig_fill.execution_status == ExecutionStatus.CORRECTED
