"""Tests for M05.04 Cash Management."""
import pytest
from datetime import datetime, date
from decimal import Decimal
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.modules.portfolio_management.cash_management.services.service import CashManagementService
from backend.app.modules.portfolio_management.cash_management.models import (
    CashMovementType,
    CashReservationType,
    CashReservationStatus,
    CashPolicy,
    CashRestriction,
    CashRestrictionType,
    CashRestrictionStatus,
    CashCommitment,
    CommitmentType,
    CommitmentStatus,
)
from backend.app.modules.portfolio_management.cash_management.schemas import (
    DepositCreate,
    WithdrawalCreate,
    CashReservationCreate,
    CashReservationRelease,
    CashReservationAdjust,
    CashTransferCreate,
    CashReconciliationRunCreate,
)


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_cash_deposit_withdrawal_and_settled_balance():
    """Test deposit increases settled balance, withdrawal decreases settled balance."""
    async with AsyncSessionLocal() as session:
        svc = CashManagementService(session)
        port_id = "PORT_CASH_01"
        acc_id = "ACC_01"
        curr = "USD"

        # 1. Deposit 50,000 USD
        dep = DepositCreate(
            portfolio_id=port_id,
            account_id=acc_id,
            currency=curr,
            amount=Decimal("50000.000000"),
            source_reference="WIRE_DEP_101",
        )
        mov_dep = await svc.process_deposit(dep)
        assert mov_dep.signed_amount == Decimal("50000.000000")
        assert mov_dep.net_amount == Decimal("50000.000000")

        # 2. Check balance
        avail = await svc.calculate_available_cash(port_id, acc_id, curr)
        assert avail.settled_balance == Decimal("50000.000000")
        assert avail.final_available_cash == Decimal("50000.000000")

        # 3. Withdraw 10,000 USD
        wth = WithdrawalCreate(
            portfolio_id=port_id,
            account_id=acc_id,
            currency=curr,
            amount=Decimal("10000.000000"),
            destination_reference="WIRE_WTH_102",
        )
        mov_wth = await svc.process_withdrawal(wth)
        assert mov_wth.signed_amount == Decimal("-10000.000000")

        # 4. Check balance after withdrawal
        avail_after = await svc.calculate_available_cash(port_id, acc_id, curr)
        assert avail_after.settled_balance == Decimal("40000.000000")
        assert avail_after.final_available_cash == Decimal("40000.000000")


@pytest.mark.asyncio
async def test_available_cash_with_reservations_and_restrictions():
    """Test conservative available cash calculation deducting reservations, restrictions, and buffers."""
    async with AsyncSessionLocal() as session:
        svc = CashManagementService(session)
        port_id = "PORT_CASH_02"
        acc_id = "ACC_01"
        curr = "INR"

        # 1. Set policy with 10,000 minimum cash buffer
        policy = CashPolicy(
            policy_id="POL_01",
            portfolio_id=port_id,
            policy_name="Conservative INR Policy",
            minimum_cash_buffer=Decimal("10000.000000"),
            allow_unsettled_receivables=False,
            allow_credit_facility=False,
        )
        await svc.repo.create_policy(policy)

        # 2. Deposit 500,000 INR
        await svc.process_deposit(
            DepositCreate(
                portfolio_id=port_id,
                account_id=acc_id,
                currency=curr,
                amount=Decimal("500000.000000"),
            )
        )

        # 3. Active Reservation of 80,000 INR
        res_dto = CashReservationCreate(
            portfolio_id=port_id,
            account_id=acc_id,
            currency=curr,
            reservation_type=CashReservationType.OPEN_ORDER,
            reserved_amount=Decimal("80000.000000"),
            reason="Limit buy order earmark",
        )
        res = await svc.create_reservation(res_dto)
        assert res.remaining_amount == Decimal("80000.000000")

        # 4. Add Restriction of 20,000 INR (e.g. margin pledge hold)
        cash_acc = await svc.get_or_create_cash_account(port_id, acc_id, curr)
        restriction = CashRestriction(
            restriction_id="REST_01",
            cash_account_id=cash_acc.cash_account_id,
            portfolio_id=port_id,
            account_id=acc_id,
            currency=curr,
            restricted_amount=Decimal("20000.000000"),
            restriction_type=CashRestrictionType.PLEDGED,
            reason="Collateral margin lock",
            status=CashRestrictionStatus.ACTIVE,
        )
        await svc.repo.create_restriction(restriction)

        # 5. Calculate available cash
        # Available Cash = 500,000 - 80,000 (res) - 20,000 (rest) - 10,000 (buffer) = 390,000
        avail = await svc.calculate_available_cash(port_id, acc_id, curr)
        assert avail.settled_balance == Decimal("500000.000000")
        assert avail.active_reservations == Decimal("80000.000000")
        assert avail.restricted_cash == Decimal("20000.000000")
        assert avail.minimum_cash_buffer == Decimal("10000.000000")
        assert avail.final_available_cash == Decimal("390000.000000")


@pytest.mark.asyncio
async def test_atomic_trade_settlement_and_double_counting_prevention():
    """Test trade settlement atomically posts cash debit and releases reservation to prevent double-counting."""
    async with AsyncSessionLocal() as session:
        svc = CashManagementService(session)
        port_id = "PORT_CASH_03"
        acc_id = "ACC_01"
        curr = "USD"

        # 1. Deposit 100,000 USD
        await svc.process_deposit(
            DepositCreate(
                portfolio_id=port_id,
                account_id=acc_id,
                currency=curr,
                amount=Decimal("100000.000000"),
            )
        )

        # 2. Buy trade executed -> Reserve 25,000 USD
        trade_id = "TRD_US_999"
        res = await svc.create_reservation(
            CashReservationCreate(
                portfolio_id=port_id,
                account_id=acc_id,
                currency=curr,
                reservation_type=CashReservationType.EXECUTED_UNSETTLED_TRADE,
                reserved_amount=Decimal("25000.000000"),
                source_trade_id=trade_id,
            )
        )
        # Prior to settlement: Available = 100,000 - 25,000 = 75,000
        avail_pre = await svc.calculate_available_cash(port_id, acc_id, curr)
        assert avail_pre.final_available_cash == Decimal("75000.000000")

        # 3. Settlement arrives (T+1): Settle obligation atomically
        settle_mov = await svc.settle_trade_obligation(
            portfolio_id=port_id,
            account_id=acc_id,
            currency=curr,
            trade_id=trade_id,
            settled_cash_amount=Decimal("-25000.000000"),
            reservation_id=res.reservation_id,
        )
        assert settle_mov.signed_amount == Decimal("-25000.000000")

        # 4. Check post-settlement:
        # Settled Cash = 100,000 - 25,000 = 75,000
        # Active Reservation = 0 (released)
        # Available Cash = 75,000 - 0 = 75,000 (NOT 50,000!)
        avail_post = await svc.calculate_available_cash(port_id, acc_id, curr)
        assert avail_post.settled_balance == Decimal("75000.000000")
        assert avail_post.active_reservations == Decimal("0.000000")
        assert avail_post.final_available_cash == Decimal("75000.000000")


@pytest.mark.asyncio
async def test_currency_isolation_and_cross_currency_transfer():
    """Test INR and USD accounts maintain independent ledgers and cross-currency FX transfer works correctly."""
    async with AsyncSessionLocal() as session:
        svc = CashManagementService(session)
        port_id = "PORT_CASH_04"
        acc_id = "ACC_GLOBAL"

        # 1. Deposit 1,000,000 INR and 10,000 USD in the same account
        await svc.process_deposit(
            DepositCreate(
                portfolio_id=port_id,
                account_id=acc_id,
                currency="INR",
                amount=Decimal("1000000.000000"),
            )
        )
        await svc.process_deposit(
            DepositCreate(
                portfolio_id=port_id,
                account_id=acc_id,
                currency="USD",
                amount=Decimal("10000.000000"),
            )
        )

        # 2. Check independent balances
        avail_inr = await svc.calculate_available_cash(port_id, acc_id, "INR")
        avail_usd = await svc.calculate_available_cash(port_id, acc_id, "USD")
        assert avail_inr.settled_balance == Decimal("1000000.000000")
        assert avail_usd.settled_balance == Decimal("10000.000000")

        # 3. Cross-Currency FX Transfer: Convert 5,000 USD to INR at FX 83.50 (destination = 417,500 INR)
        transfer_dto = CashTransferCreate(
            source_portfolio_id=port_id,
            source_account_id=acc_id,
            destination_portfolio_id=port_id,
            destination_account_id=acc_id,
            source_currency="USD",
            destination_currency="INR",
            source_amount=Decimal("5000.000000"),
            destination_amount=Decimal("417500.000000"),
            fx_rate=Decimal("83.500000"),
            fx_rate_reference="REUTERS_MID_83.50",
        )
        xfer = await svc.process_transfer(transfer_dto)
        assert xfer.destination_amount == Decimal("417500.000000")

        # 4. Check updated balances
        # USD: 10,000 - 5,000 = 5,000 USD
        # INR: 1,000,000 + 417,500 = 1,417,500 INR
        avail_inr_post = await svc.calculate_available_cash(port_id, acc_id, "INR")
        avail_usd_post = await svc.calculate_available_cash(port_id, acc_id, "USD")
        assert avail_usd_post.settled_balance == Decimal("5000.000000")
        assert avail_inr_post.settled_balance == Decimal("1417500.000000")
