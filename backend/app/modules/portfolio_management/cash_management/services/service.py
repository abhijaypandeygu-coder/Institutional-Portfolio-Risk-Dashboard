"""Service layer for M05.04 Cash Management."""
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
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
    TransferStatus,
    ReconciliationStatus,
)
from backend.app.modules.portfolio_management.cash_management.schemas import (
    CashAccountCreate,
    DepositCreate,
    WithdrawalCreate,
    CashReservationCreate,
    CashReservationRelease,
    CashReservationAdjust,
    CashTransferCreate,
    CashReconciliationRunCreate,
    AvailableCashExplanation,
)
from backend.app.modules.portfolio_management.cash_management.repositories.repository import (
    CashManagementRepository,
)


class CashManagementService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CashManagementRepository(session)

    # -----------------------------------------------------------------------
    # 1. CASH ACCOUNTS
    # -----------------------------------------------------------------------
    async def get_or_create_cash_account(
        self,
        portfolio_id: str,
        account_id: str,
        currency: str,
        cash_account_type: CashAccountType = CashAccountType.TRADING,
        description: Optional[str] = None,
    ) -> CashAccount:
        acc = await self.repo.get_cash_account(
            portfolio_id=portfolio_id,
            account_id=account_id,
            currency=currency.upper(),
            cash_account_type=cash_account_type,
        )
        if acc:
            return acc

        cash_account_id = f"csh_acc_{uuid.uuid4().hex[:12]}"
        acc = CashAccount(
            cash_account_id=cash_account_id,
            portfolio_id=portfolio_id,
            account_id=account_id,
            currency=currency.upper(),
            cash_account_type=cash_account_type,
            status=CashAccountStatus.ACTIVE,
            description=description or f"Cash account for {account_id} in {currency}",
        )
        return await self.repo.create_cash_account(acc)

    # -----------------------------------------------------------------------
    # 2. DOUBLE-ENTRY JOURNAL POSTING & MOVEMENTS
    # -----------------------------------------------------------------------
    async def post_cash_movement_with_journal(
        self,
        portfolio_id: str,
        account_id: str,
        currency: str,
        movement_type: CashMovementType,
        signed_amount: Decimal,
        gross_amount: Decimal,
        fees_amount: Decimal = Decimal("0.000000"),
        tax_amount: Decimal = Decimal("0.000000"),
        source_system: str = "INTERNAL",
        source_event_id: Optional[str] = None,
        external_reference: Optional[str] = None,
        related_instrument_id: Optional[str] = None,
        related_trade_id: Optional[str] = None,
        related_corporate_action_id: Optional[str] = None,
        transfer_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        effective_at: Optional[datetime] = None,
        settlement_at: Optional[datetime] = None,
    ) -> Tuple[CashMovement, CashJournal]:
        """
        Atomically records an immutable CashMovement and creates a balanced CashJournal.
        Debit increases cash asset account, Credit decreases cash asset account.
        """
        curr = currency.upper()
        if idempotency_key:
            existing_mov = await self.repo.get_movement_by_idempotency_key(idempotency_key)
            if existing_mov:
                # Idempotent return
                return existing_mov, None

        # Verify or create subledger cash account
        cash_account = await self.get_or_create_cash_account(portfolio_id, account_id, curr)

        now = datetime.utcnow()
        eff_at = effective_at or now
        settle_at = settlement_at or eff_at

        # Verify Net Amount
        # For inflow: net = gross - fees - tax
        # For outflow: net = gross + fees + tax (in magnitude)
        net_amount = abs(signed_amount)

        movement_id = f"mov_{uuid.uuid4().hex[:12]}"
        journal_id = f"csh_jrn_{uuid.uuid4().hex[:12]}"

        movement = CashMovement(
            movement_id=movement_id,
            cash_account_id=cash_account.cash_account_id,
            portfolio_id=portfolio_id,
            account_id=account_id,
            movement_type=movement_type,
            signed_amount=signed_amount,
            currency=curr,
            gross_amount=gross_amount,
            fees_amount=fees_amount,
            tax_amount=tax_amount,
            net_amount=net_amount,
            effective_at=eff_at,
            settlement_at=settle_at,
            posted_at=now,
            status=CashMovementStatus.SETTLED,
            source_system=source_system,
            source_event_id=source_event_id,
            external_reference=external_reference,
            related_instrument_id=related_instrument_id,
            related_trade_id=related_trade_id,
            related_corporate_action_id=related_corporate_action_id,
            transfer_id=transfer_id,
            idempotency_key=idempotency_key,
        )
        await self.repo.create_movement(movement)

        # Build balanced double-entry lines
        # Cash Asset Code: 1000-CASH
        # Counterparty/Clearing Code based on movement type
        lines = []
        if signed_amount > 0:
            # Cash Inflow: Debit Cash Asset, Credit Funding/Income/Clearing
            lines.append(
                CashJournalLine(
                    journal_id=journal_id,
                    line_number=1,
                    ledger_account_code="1000-CASH",
                    debit_amount=net_amount,
                    credit_amount=Decimal("0.000000"),
                    currency=curr,
                    description=f"{movement_type.value} cash receipt",
                )
            )
            lines.append(
                CashJournalLine(
                    journal_id=journal_id,
                    line_number=2,
                    ledger_account_code=f"2000-CLEARING-{movement_type.value}",
                    debit_amount=Decimal("0.000000"),
                    credit_amount=net_amount,
                    currency=curr,
                    description=f"{movement_type.value} funding source",
                )
            )
        else:
            # Cash Outflow: Debit Expense/Clearing, Credit Cash Asset
            lines.append(
                CashJournalLine(
                    journal_id=journal_id,
                    line_number=1,
                    ledger_account_code=f"2000-CLEARING-{movement_type.value}",
                    debit_amount=net_amount,
                    credit_amount=Decimal("0.000000"),
                    currency=curr,
                    description=f"{movement_type.value} application",
                )
            )
            lines.append(
                CashJournalLine(
                    journal_id=journal_id,
                    line_number=2,
                    ledger_account_code="1000-CASH",
                    debit_amount=Decimal("0.000000"),
                    credit_amount=net_amount,
                    currency=curr,
                    description=f"{movement_type.value} cash disbursement",
                )
            )

        journal = CashJournal(
            journal_id=journal_id,
            journal_type=movement_type.value,
            portfolio_id=portfolio_id,
            cash_account_id=cash_account.cash_account_id,
            currency=curr,
            source_movement_id=movement_id,
            source_event_id=source_event_id,
            idempotency_key=f"jrn_{idempotency_key}" if idempotency_key else None,
            effective_at=eff_at,
            posted_at=now,
            status="POSTED",
            lines=lines,
        )
        await self.repo.create_journal(journal)

        # Trigger balance snapshot recalculation
        await self.calculate_and_snapshot_balances(portfolio_id, account_id, curr)

        return movement, journal

    # -----------------------------------------------------------------------
    # 3. DEPOSIT & WITHDRAWAL
    # -----------------------------------------------------------------------
    async def process_deposit(self, dto: DepositCreate) -> CashMovement:
        amt = Decimal(str(dto.amount))
        movement, _ = await self.post_cash_movement_with_journal(
            portfolio_id=dto.portfolio_id,
            account_id=dto.account_id,
            currency=dto.currency,
            movement_type=CashMovementType.DEPOSIT,
            signed_amount=amt,
            gross_amount=amt,
            source_system="EXTERNAL_FUNDING",
            external_reference=dto.source_reference,
            idempotency_key=dto.idempotency_key,
        )
        return movement

    async def process_withdrawal(self, dto: WithdrawalCreate) -> CashMovement:
        amt = Decimal(str(dto.amount))
        # Check availability
        avail = await self.calculate_available_cash(dto.portfolio_id, dto.account_id, dto.currency)
        if avail.final_available_cash < amt:
            raise ValueError(
                f"Insufficient available cash for withdrawal. Requested: {amt} {dto.currency}, Available: {avail.final_available_cash} {dto.currency}"
            )

        movement, _ = await self.post_cash_movement_with_journal(
            portfolio_id=dto.portfolio_id,
            account_id=dto.account_id,
            currency=dto.currency,
            movement_type=CashMovementType.WITHDRAWAL,
            signed_amount=-amt,
            gross_amount=amt,
            source_system="EXTERNAL_DISBURSEMENT",
            external_reference=dto.destination_reference,
            idempotency_key=dto.idempotency_key,
        )
        return movement

    # -----------------------------------------------------------------------
    # 4. RESERVATIONS & COMMITTED CASH LIFECYCLE
    # -----------------------------------------------------------------------
    async def create_reservation(self, dto: CashReservationCreate) -> CashReservation:
        curr = dto.currency.upper()
        if dto.idempotency_key:
            existing = await self.repo.get_reservation_by_idempotency_key(dto.idempotency_key)
            if existing:
                return existing

        amt = Decimal(str(dto.reserved_amount))
        # Validate current available cash
        avail = await self.calculate_available_cash(dto.portfolio_id, dto.account_id, curr)
        if avail.final_available_cash < amt:
            raise ValueError(
                f"Insufficient available cash to create reservation. Required: {amt} {curr}, Available: {avail.final_available_cash} {curr}"
            )

        cash_account = await self.get_or_create_cash_account(dto.portfolio_id, dto.account_id, curr)
        res_id = f"csh_res_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()

        reservation = CashReservation(
            reservation_id=res_id,
            cash_account_id=cash_account.cash_account_id,
            portfolio_id=dto.portfolio_id,
            account_id=dto.account_id,
            currency=curr,
            reservation_type=dto.reservation_type,
            reserved_amount=amt,
            remaining_amount=amt,
            source_commitment_id=dto.source_commitment_id,
            source_order_id=dto.source_order_id,
            source_trade_id=dto.source_trade_id,
            status=CashReservationStatus.ACTIVE,
            reason=dto.reason,
            idempotency_key=dto.idempotency_key,
            created_at=now,
            effective_at=now,
            expires_at=dto.expires_at,
        )
        await self.repo.create_reservation(reservation)

        event = CashReservationEvent(
            reservation_id=res_id,
            event_type="CREATED",
            amount=amt,
            previous_remaining_amount=Decimal("0.000000"),
            new_remaining_amount=amt,
            reason=dto.reason or "Reservation created",
            effective_at=now,
        )
        await self.repo.add_reservation_event(event)

        # Invalidate/refresh balance snapshot
        await self.calculate_and_snapshot_balances(dto.portfolio_id, dto.account_id, curr)
        return reservation

    async def release_reservation(
        self,
        reservation_id: str,
        release_amount: Optional[Decimal] = None,
        reason: Optional[str] = "Reservation released",
    ) -> CashReservation:
        res = await self.repo.get_reservation_by_id(reservation_id)
        if not res:
            raise ValueError(f"Reservation {reservation_id} not found")

        if res.status in [CashReservationStatus.RELEASED, CashReservationStatus.CANCELLED, CashReservationStatus.SETTLED]:
            return res

        now = datetime.utcnow()
        prev_remaining = res.remaining_amount
        if release_amount is None or release_amount >= prev_remaining:
            # Full release
            amount_released = prev_remaining
            new_remaining = Decimal("0.000000")
            res.status = CashReservationStatus.RELEASED
            res.released_at = now
        else:
            amount_released = Decimal(str(release_amount))
            new_remaining = prev_remaining - amount_released
            res.status = CashReservationStatus.PARTIALLY_RELEASED

        res.remaining_amount = new_remaining

        event = CashReservationEvent(
            reservation_id=reservation_id,
            event_type="RELEASED" if res.status == CashReservationStatus.RELEASED else "PARTIALLY_RELEASED",
            amount=amount_released,
            previous_remaining_amount=prev_remaining,
            new_remaining_amount=new_remaining,
            reason=reason,
            effective_at=now,
        )
        await self.repo.add_reservation_event(event)

        await self.calculate_and_snapshot_balances(res.portfolio_id, res.account_id, res.currency)
        return res

    async def adjust_reservation(
        self,
        reservation_id: str,
        new_reserved_amount: Decimal,
        reason: Optional[str] = "Reservation adjusted",
    ) -> CashReservation:
        res = await self.repo.get_reservation_by_id(reservation_id)
        if not res:
            raise ValueError(f"Reservation {reservation_id} not found")

        now = datetime.utcnow()
        prev_remaining = res.remaining_amount
        new_rem = Decimal(str(new_reserved_amount))

        res.remaining_amount = new_rem
        if new_rem == 0:
            res.status = CashReservationStatus.RELEASED
            res.released_at = now
        else:
            res.status = CashReservationStatus.PARTIALLY_RELEASED

        event = CashReservationEvent(
            reservation_id=reservation_id,
            event_type="ADJUSTED",
            amount=new_rem - prev_remaining,
            previous_remaining_amount=prev_remaining,
            new_remaining_amount=new_rem,
            reason=reason,
            effective_at=now,
        )
        await self.repo.add_reservation_event(event)

        await self.calculate_and_snapshot_balances(res.portfolio_id, res.account_id, res.currency)
        return res

    # -----------------------------------------------------------------------
    # 5. ATOMIC SETTLEMENT CONVERSION (Double-Counting Prevention)
    # -----------------------------------------------------------------------
    async def settle_trade_obligation(
        self,
        portfolio_id: str,
        account_id: str,
        currency: str,
        trade_id: str,
        settled_cash_amount: Decimal,  # Negative for buy settlement, Positive for sell settlement
        reservation_id: Optional[str] = None,
        commitment_id: Optional[str] = None,
        source_event_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> CashMovement:
        """
        Executes atomic settlement:
        1. Posts actual settled cash movement & journal entries.
        2. Releases associated reservation cleanly so the payable/commitment is not double-counted.
        3. Updates commitment status to SETTLED.
        """
        curr = currency.upper()
        if idempotency_key:
            existing_mov = await self.repo.get_movement_by_idempotency_key(idempotency_key)
            if existing_mov:
                return existing_mov

        mtype = (
            CashMovementType.TRADE_SETTLEMENT_DEBIT
            if settled_cash_amount < 0
            else CashMovementType.TRADE_SETTLEMENT_CREDIT
        )

        # 1. Post settled cash movement
        mov, _ = await self.post_cash_movement_with_journal(
            portfolio_id=portfolio_id,
            account_id=account_id,
            currency=curr,
            movement_type=mtype,
            signed_amount=settled_cash_amount,
            gross_amount=abs(settled_cash_amount),
            source_system="TRADE_SETTLEMENT",
            source_event_id=source_event_id or f"evt_settle_{trade_id}",
            related_trade_id=trade_id,
            idempotency_key=idempotency_key,
        )

        # 2. Release reservation if present
        if reservation_id:
            res = await self.repo.get_reservation_by_id(reservation_id)
            if res and res.status in [CashReservationStatus.ACTIVE, CashReservationStatus.PARTIALLY_RELEASED]:
                now = datetime.utcnow()
                prev_rem = res.remaining_amount
                res.status = CashReservationStatus.SETTLED
                res.remaining_amount = Decimal("0.000000")
                res.released_at = now
                event = CashReservationEvent(
                    reservation_id=reservation_id,
                    event_type="SETTLED",
                    amount=prev_rem,
                    previous_remaining_amount=prev_rem,
                    new_remaining_amount=Decimal("0.000000"),
                    reason=f"Settled via trade {trade_id}",
                    effective_at=now,
                )
                await self.repo.add_reservation_event(event)

        # 3. Resolve commitment if present
        if commitment_id:
            cm = await self.session.execute(
                select(CashCommitment).where(CashCommitment.commitment_id == commitment_id)
            )
            comm = cm.scalars().first()
            if comm:
                comm.status = CommitmentStatus.SETTLED
                comm.actual_settlement_at = datetime.utcnow()
                comm.outstanding_amount = Decimal("0.000000")

        # Recalculate balance snapshot
        await self.calculate_and_snapshot_balances(portfolio_id, account_id, curr)
        return mov

    # -----------------------------------------------------------------------
    # 6. AVAILABLE CASH CALCULATION & EXPLANATION
    # -----------------------------------------------------------------------
    async def calculate_available_cash(
        self,
        portfolio_id: str,
        account_id: str,
        currency: str,
    ) -> AvailableCashExplanation:
        """
        Available Cash = Settled Cash
                       + Eligible Unsettled Receivables
                       + Eligible Credit
                       - Active Cash Reservations
                       - Restricted Cash Deduction
                       - Minimum Cash Buffer
                       - Other Unreserved Payable Deductions
        """
        curr = currency.upper()

        # 1. Fetch Policy
        policy = await self.repo.get_policy(portfolio_id)
        allow_receivables = policy.allow_unsettled_receivables if policy else False
        allow_credit = policy.allow_credit_facility if policy else False
        credit_limit = policy.credit_facility_limit if policy else Decimal("0.000000")
        min_buffer = policy.minimum_cash_buffer if policy else Decimal("0.000000")
        policy_ver = policy.version if policy else 1

        # 2. Sum Settled Cash Movements
        movs = await self.repo.list_movements(
            portfolio_id=portfolio_id,
            account_id=account_id,
            currency=curr,
            status=CashMovementStatus.SETTLED,
        )
        settled_balance = sum((m.signed_amount for m in movs), Decimal("0.000000"))

        # 3. Active Reservations
        res_list = await self.repo.list_active_reservations(portfolio_id, account_id, curr)
        active_reservations = sum((r.remaining_amount for r in res_list), Decimal("0.000000"))

        # 4. Active Restrictions
        rest_list = await self.repo.list_active_restrictions(portfolio_id, account_id, curr)
        restricted_cash = sum((r.restricted_amount for r in rest_list), Decimal("0.000000"))

        # 5. Commitments (Receivables and Unreserved Payables)
        receivables = await self.repo.list_active_commitments(
            portfolio_id, account_id, curr, commitment_type=CommitmentType.RECEIVABLE
        )
        total_receivables = sum((c.outstanding_amount for c in receivables), Decimal("0.000000"))
        eligible_receivables = total_receivables if allow_receivables else Decimal("0.000000")

        # Unreserved payables: only deduct payables that DO NOT have an active reservation (prevents double counting)
        active_res_comm_ids = {r.source_commitment_id for r in res_list if r.source_commitment_id}
        payables = await self.repo.list_active_commitments(
            portfolio_id, account_id, curr, commitment_type=CommitmentType.PAYABLE
        )
        unreserved_payables = Decimal("0.000000")
        for p in payables:
            if p.commitment_id not in active_res_comm_ids and p.source_event_id not in active_res_comm_ids:
                unreserved_payables += p.outstanding_amount

        eligible_credit = credit_limit if allow_credit else Decimal("0.000000")

        # Core formula execution
        avail_cash = (
            settled_balance
            + eligible_receivables
            + eligible_credit
            - active_reservations
            - restricted_cash
            - min_buffer
            - unreserved_payables
        )

        # Status
        status = AvailableCashStatus.AVAILABLE
        reasons = []
        if avail_cash < 0:
            status = AvailableCashStatus.NEGATIVE_AVAILABLE_CASH
            reasons.append("Obligations and reservations exceed available cash.")
        elif avail_cash < Decimal("1000.000000"):
            status = AvailableCashStatus.LOW_AVAILABLE_CASH
            reasons.append("Available cash is below standard warning threshold.")

        if restricted_cash > 0:
            reasons.append(f"Restricted holds applied: {restricted_cash} {curr}")

        return AvailableCashExplanation(
            portfolio_id=portfolio_id,
            account_id=account_id,
            currency=curr,
            settled_balance=settled_balance,
            eligible_unsettled_receivables=eligible_receivables,
            eligible_credit=eligible_credit,
            active_reservations=active_reservations,
            restricted_cash=restricted_cash,
            minimum_cash_buffer=min_buffer,
            unreserved_payable_deductions=unreserved_payables,
            final_available_cash=avail_cash,
            availability_status=status,
            policy_version=policy_ver,
            calculation_timestamp=datetime.utcnow(),
            reasons=reasons,
        )

    async def calculate_and_snapshot_balances(
        self,
        portfolio_id: str,
        account_id: str,
        currency: str,
    ) -> CashBalanceSnapshot:
        curr = currency.upper()
        cash_account = await self.get_or_create_cash_account(portfolio_id, account_id, curr)
        explanation = await self.calculate_available_cash(portfolio_id, account_id, curr)

        # Compute total unsettled receivables and payables for snapshot
        receivables = await self.repo.list_active_commitments(
            portfolio_id, account_id, curr, commitment_type=CommitmentType.RECEIVABLE
        )
        total_rec = sum((c.outstanding_amount for c in receivables), Decimal("0.000000"))

        payables = await self.repo.list_active_commitments(
            portfolio_id, account_id, curr, commitment_type=CommitmentType.PAYABLE
        )
        total_pay = sum((c.outstanding_amount for c in payables), Decimal("0.000000"))

        now = datetime.utcnow()
        snapshot_id = f"csh_snp_{uuid.uuid4().hex[:12]}"
        snapshot = CashBalanceSnapshot(
            snapshot_id=snapshot_id,
            cash_account_id=cash_account.cash_account_id,
            portfolio_id=portfolio_id,
            account_id=account_id,
            currency=curr,
            settled_balance=explanation.settled_balance,
            unsettled_receivables=total_rec,
            unsettled_payables=total_pay,
            reserved_cash=explanation.active_reservations,
            restricted_cash=explanation.restricted_cash,
            eligible_credit=explanation.eligible_credit,
            minimum_cash_buffer=explanation.minimum_cash_buffer,
            available_cash=explanation.final_available_cash,
            availability_status=explanation.availability_status,
            effective_at=now,
            calculated_at=now,
            policy_version=explanation.policy_version,
        )
        return await self.repo.create_snapshot(snapshot)

    # -----------------------------------------------------------------------
    # 7. TRANSFERS (Internal & Cross-Currency FX)
    # -----------------------------------------------------------------------
    async def process_transfer(self, dto: CashTransferCreate) -> CashTransferGroup:
        src_curr = dto.source_currency.upper()
        dest_curr = dto.destination_currency.upper()
        src_amt = Decimal(str(dto.source_amount))

        # Check source account availability
        avail = await self.calculate_available_cash(
            dto.source_portfolio_id, dto.source_account_id, src_curr
        )
        if avail.final_available_cash < src_amt + dto.fee_amount:
            raise ValueError(
                f"Insufficient funds for transfer. Available: {avail.final_available_cash} {src_curr}, Required: {src_amt + dto.fee_amount} {src_curr}"
            )

        transfer_id = f"csh_xfer_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()

        if src_curr == dest_curr:
            # Same currency transfer
            dest_amt = src_amt
            fx_rate = None
        else:
            # Cross-currency FX transfer
            if not dto.fx_rate or dto.fx_rate <= 0:
                raise ValueError("FX rate must be supplied for cross-currency transfers.")
            fx_rate = Decimal(str(dto.fx_rate))
            dest_amt = (
                Decimal(str(dto.destination_amount))
                if dto.destination_amount
                else (src_amt * fx_rate)
            )

        # 1. Debit Source Account
        await self.post_cash_movement_with_journal(
            portfolio_id=dto.source_portfolio_id,
            account_id=dto.source_account_id,
            currency=src_curr,
            movement_type=CashMovementType.INTERNAL_TRANSFER_OUT,
            signed_amount=-src_amt,
            gross_amount=src_amt,
            fees_amount=dto.fee_amount,
            source_system="INTERNAL_TRANSFER",
            transfer_id=transfer_id,
            source_event_id=f"xfer_{transfer_id}_out",
        )

        # 2. Credit Destination Account
        await self.post_cash_movement_with_journal(
            portfolio_id=dto.destination_portfolio_id,
            account_id=dto.destination_account_id,
            currency=dest_curr,
            movement_type=CashMovementType.INTERNAL_TRANSFER_IN,
            signed_amount=dest_amt,
            gross_amount=dest_amt,
            source_system="INTERNAL_TRANSFER",
            transfer_id=transfer_id,
            source_event_id=f"xfer_{transfer_id}_in",
        )

        # Fetch subledger accounts
        src_acc = await self.get_or_create_cash_account(dto.source_portfolio_id, dto.source_account_id, src_curr)
        dest_acc = await self.get_or_create_cash_account(dto.destination_portfolio_id, dto.destination_account_id, dest_curr)

        group = CashTransferGroup(
            transfer_id=transfer_id,
            source_cash_account_id=src_acc.cash_account_id,
            destination_cash_account_id=dest_acc.cash_account_id,
            source_portfolio_id=dto.source_portfolio_id,
            destination_portfolio_id=dto.destination_portfolio_id,
            source_currency=src_curr,
            destination_currency=dest_curr,
            source_amount=src_amt,
            destination_amount=dest_amt,
            fx_rate=fx_rate,
            fx_rate_reference=dto.fx_rate_reference,
            fee_amount=dto.fee_amount,
            status=TransferStatus.COMPLETED,
            source_reference=dto.source_reference,
            effective_at=now,
            settlement_at=now,
        )
        return await self.repo.create_transfer_group(group)

    # -----------------------------------------------------------------------
    # 8. RECONCILIATION
    # -----------------------------------------------------------------------
    async def run_reconciliation(self, dto: CashReconciliationRunCreate) -> CashReconciliationRun:
        curr = dto.currency.upper()
        cash_account = await self.get_or_create_cash_account(dto.portfolio_id, dto.account_id, curr)

        # Compute internal closing balance
        movs = await self.repo.list_movements(
            portfolio_id=dto.portfolio_id,
            account_id=dto.account_id,
            currency=curr,
            status=CashMovementStatus.SETTLED,
        )
        internal_balance = sum((m.signed_amount for m in movs), Decimal("0.000000"))
        ext_balance = Decimal(str(dto.external_closing_balance))
        diff = internal_balance - ext_balance

        status = ReconciliationStatus.MATCHED if diff == 0 else ReconciliationStatus.AMOUNT_MISMATCH

        run_id = f"csh_rec_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()
        run = CashReconciliationRun(
            run_id=run_id,
            portfolio_id=dto.portfolio_id,
            cash_account_id=cash_account.cash_account_id,
            currency=curr,
            statement_date=dto.statement_date,
            internal_closing_balance=internal_balance,
            external_closing_balance=ext_balance,
            difference=diff,
            status=status,
            source_statement_reference=dto.source_statement_reference,
            started_at=now,
            completed_at=now,
        )
        return await self.repo.create_reconciliation_run(run)
