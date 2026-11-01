"""Service layer for M05.06 Portfolio Reconciliation."""
import uuid
import hashlib
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.portfolio_management.portfolio_reconciliation.models import (
    ReconciliationProvider,
    StatementImport,
    ExternalPositionRecord,
    ExternalTransactionRecord,
    ExternalCashRecord,
    ReconciliationRun,
    ReconciliationBreak,
    ReconciliationNote,
    ProviderType,
    StatementType,
    ImportStatus,
    ReconciliationType,
    ReconciliationRunStatus,
    BreakCategory,
    BreakSeverity,
    BreakStatus,
    ResolutionType,
)
from backend.app.modules.portfolio_management.portfolio_reconciliation.schemas import (
    ProviderCreate,
    StatementImportCreate,
    ReconciliationRunCreate,
    BreakNoteCreate,
    BreakAssignRequest,
    BreakResolveRequest,
)
from backend.app.modules.portfolio_management.portfolio_reconciliation.repositories.repository import (
    PortfolioReconciliationRepository,
)

# Downstream Module Repositories for authoritative internal book retrieval
from backend.app.modules.portfolio_management.position_management.repositories.repository import (
    PositionRepository,
)
from backend.app.modules.portfolio_management.cash_management.repositories.repository import (
    CashManagementRepository,
)
from backend.app.modules.portfolio_management.transaction_management.repositories.repository import (
    TransactionManagementRepository,
)


class PortfolioReconciliationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PortfolioReconciliationRepository(session)
        self.pos_repo = PositionRepository(session)
        self.cash_repo = CashManagementRepository(session)
        self.tx_repo = TransactionManagementRepository(session)

    # -----------------------------------------------------------------------
    # 1. STATEMENT INTAKE & NORMALIZATION
    # -----------------------------------------------------------------------
    async def import_statement(self, dto: StatementImportCreate) -> StatementImport:
        now = datetime.utcnow()
        # Compute deterministic content hash for duplicate detection
        content_str = f"{dto.provider_code}:{dto.portfolio_id}:{dto.account_id}:{dto.statement_type.value}:{dto.as_of_date}:{dto.file_name}"
        file_hash = hashlib.sha256(content_str.encode("utf-8")).hexdigest()

        existing = await self.repo.get_statement_by_hash(file_hash)
        if existing:
            return existing

        statement_id = f"stmt_{uuid.uuid4().hex[:12]}"
        total_recs = 0
        valid_recs = 0

        pos_entities = []
        if dto.positions:
            for p in dto.positions:
                total_recs += 1
                pos_entities.append(
                    ExternalPositionRecord(
                        record_id=f"ext_pos_{uuid.uuid4().hex[:12]}",
                        statement_id=statement_id,
                        portfolio_id=dto.portfolio_id,
                        account_id=dto.account_id,
                        external_symbol=p.external_symbol,
                        resolved_instrument_id=p.external_symbol,  # In production resolved via M04.07
                        quantity=Decimal(str(p.quantity)),
                        position_side=p.position_side,
                        price=Decimal(str(p.price)) if p.price is not None else None,
                        market_value=Decimal(str(p.market_value)) if p.market_value is not None else None,
                        currency=p.currency.upper(),
                        as_of_date=dto.as_of_date,
                    )
                )
                valid_recs += 1

        tx_entities = []
        if dto.transactions:
            for t in dto.transactions:
                total_recs += 1
                tx_entities.append(
                    ExternalTransactionRecord(
                        record_id=f"ext_tx_{uuid.uuid4().hex[:12]}",
                        statement_id=statement_id,
                        portfolio_id=dto.portfolio_id,
                        account_id=dto.account_id,
                        external_trade_id=t.external_trade_id,
                        external_symbol=t.external_symbol,
                        resolved_instrument_id=t.external_symbol,
                        trade_side=t.trade_side.upper(),
                        quantity=Decimal(str(t.quantity)),
                        price=Decimal(str(t.price)),
                        gross_amount=Decimal(str(t.gross_amount)),
                        fees=Decimal(str(t.fees)),
                        currency=t.currency.upper(),
                        trade_date=t.trade_date,
                        settlement_date=t.settlement_date,
                    )
                )
                valid_recs += 1

        cash_entities = []
        if dto.cash_records:
            for c in dto.cash_records:
                total_recs += 1
                cash_entities.append(
                    ExternalCashRecord(
                        record_id=f"ext_csh_{uuid.uuid4().hex[:12]}",
                        statement_id=statement_id,
                        portfolio_id=dto.portfolio_id,
                        account_id=dto.account_id,
                        currency=c.currency.upper(),
                        closing_balance=Decimal(str(c.closing_balance)),
                        as_of_date=dto.as_of_date,
                    )
                )
                valid_recs += 1

        statement = StatementImport(
            statement_id=statement_id,
            provider_code=dto.provider_code,
            statement_type=dto.statement_type,
            portfolio_id=dto.portfolio_id,
            account_id=dto.account_id,
            as_of_date=dto.as_of_date,
            file_name=dto.file_name,
            file_hash=file_hash,
            import_status=ImportStatus.STAGED,
            total_records=total_recs,
            valid_records=valid_recs,
            invalid_records=0,
            created_at=now,
            completed_at=now,
            positions=pos_entities,
            transactions=tx_entities,
            cash_records=cash_entities,
        )
        return await self.repo.create_statement_import(statement)

    # -----------------------------------------------------------------------
    # 2. RECONCILIATION EXECUTION ENGINE
    # -----------------------------------------------------------------------
    async def run_reconciliation(self, dto: ReconciliationRunCreate) -> ReconciliationRun:
        now = datetime.utcnow()
        run_id = f"rec_run_{uuid.uuid4().hex[:12]}"

        # Retrieve Statement if provided
        statement = None
        if dto.statement_id:
            statement = await self.repo.get_statement_import_by_id(dto.statement_id)

        run = ReconciliationRun(
            run_id=run_id,
            portfolio_id=dto.portfolio_id,
            account_id=dto.account_id,
            provider_code=dto.provider_code,
            reconciliation_type=dto.reconciliation_type,
            as_of_date=dto.as_of_date,
            statement_id=dto.statement_id,
            status=ReconciliationRunStatus.MATCHING,
            started_at=now,
            created_at=now,
        )
        await self.repo.create_reconciliation_run(run)

        breaks: List[ReconciliationBreak] = []
        matched_cnt = 0
        unmatched_cnt = 0
        total_ext = 0
        total_int = 0

        # -------------------------------------------------------------------
        # A. POSITION RECONCILIATION
        # -------------------------------------------------------------------
        if dto.reconciliation_type in [ReconciliationType.POSITION, ReconciliationType.FULL_PORTFOLIO] and statement:
            # 1. External positions from statement
            ext_positions = await self.repo.list_external_positions(statement.statement_id)
            total_ext += len(ext_positions)

            # 2. Internal positions from M05.02
            int_books = await self.pos_repo.list_books_by_portfolio(dto.portfolio_id)
            int_pos_map: Dict[str, Decimal] = {}
            for pb in int_books:
                if pb.account_id == dto.account_id:
                    snp = await self.pos_repo.get_latest_snapshot(pb.position_id)
                    int_pos_map[pb.instrument_id] = snp.net_signed_quantity if snp else Decimal("0.000000")
            total_int += len(int_pos_map)

            # Match external against internal
            seen_internal_insts = set()
            for ep in ext_positions:
                inst_id = ep.resolved_instrument_id or ep.external_symbol
                seen_internal_insts.add(inst_id)
                if inst_id not in int_pos_map:
                    # Missing Internal Position break
                    unmatched_cnt += 1
                    breaks.append(
                        ReconciliationBreak(
                            break_id=f"brk_{uuid.uuid4().hex[:12]}",
                            run_id=run_id,
                            portfolio_id=dto.portfolio_id,
                            account_id=dto.account_id,
                            instrument_id=inst_id,
                            break_category=BreakCategory.MISSING_INTERNAL_POSITION,
                            severity=BreakSeverity.HIGH,
                            break_status=BreakStatus.OPEN,
                            internal_value="0",
                            external_value=str(ep.quantity),
                            difference_value=ep.quantity,
                            difference_unit="SHARES",
                        )
                    )
                else:
                    int_qty = int_pos_map[inst_id]
                    diff = ep.quantity - int_qty
                    if diff != 0:
                        unmatched_cnt += 1
                        breaks.append(
                            ReconciliationBreak(
                                break_id=f"brk_{uuid.uuid4().hex[:12]}",
                                run_id=run_id,
                                portfolio_id=dto.portfolio_id,
                                account_id=dto.account_id,
                                instrument_id=inst_id,
                                break_category=BreakCategory.QUANTITY_MISMATCH,
                                severity=BreakSeverity.HIGH,
                                break_status=BreakStatus.OPEN,
                                internal_value=str(int_qty),
                                external_value=str(ep.quantity),
                                difference_value=diff,
                                difference_unit="SHARES",
                            )
                        )
                    else:
                        matched_cnt += 1

            # Check for Missing External Positions
            for inst_id, int_qty in int_pos_map.items():
                if inst_id not in seen_internal_insts and int_qty != 0:
                    unmatched_cnt += 1
                    breaks.append(
                        ReconciliationBreak(
                            break_id=f"brk_{uuid.uuid4().hex[:12]}",
                            run_id=run_id,
                            portfolio_id=dto.portfolio_id,
                            account_id=dto.account_id,
                            instrument_id=inst_id,
                            break_category=BreakCategory.MISSING_EXTERNAL_POSITION,
                            severity=BreakSeverity.HIGH,
                            break_status=BreakStatus.OPEN,
                            internal_value=str(int_qty),
                            external_value="0",
                            difference_value=-int_qty,
                            difference_unit="SHARES",
                        )
                    )

        # -------------------------------------------------------------------
        # B. CASH RECONCILIATION
        # -------------------------------------------------------------------
        if dto.reconciliation_type in [ReconciliationType.CASH, ReconciliationType.FULL_PORTFOLIO] and statement:
            ext_cash_records = await self.repo.list_external_cash_records(statement.statement_id)
            for ec in ext_cash_records:
                total_ext += 1
                # Retrieve internal settled cash from M05.04
                csh_acc = await self.cash_repo.get_cash_account(dto.portfolio_id, dto.account_id, ec.currency)
                int_cash_balance = Decimal("0.000000")
                if csh_acc:
                    snp = await self.cash_repo.get_latest_snapshot(dto.portfolio_id, dto.account_id, ec.currency)
                    if snp:
                        int_cash_balance = snp.settled_balance

                diff = ec.closing_balance - int_cash_balance
                if diff != 0:
                    unmatched_cnt += 1
                    breaks.append(
                        ReconciliationBreak(
                            break_id=f"brk_{uuid.uuid4().hex[:12]}",
                            run_id=run_id,
                            portfolio_id=dto.portfolio_id,
                            account_id=dto.account_id,
                            instrument_id=None,
                            break_category=BreakCategory.CASH_BALANCE_MISMATCH,
                            severity=BreakSeverity.CRITICAL if abs(diff) > 1000 else BreakSeverity.MEDIUM,
                            break_status=BreakStatus.OPEN,
                            internal_value=str(int_cash_balance),
                            external_value=str(ec.closing_balance),
                            difference_value=diff,
                            difference_unit=ec.currency,
                        )
                    )
                else:
                    matched_cnt += 1

        # Save all breaks
        crit_count = 0
        for b in breaks:
            if b.severity == BreakSeverity.CRITICAL:
                crit_count += 1
            await self.repo.create_break(b)

        # Finalize run
        run.total_external_records = total_ext
        run.total_internal_records = total_int
        run.matched_records = matched_cnt
        run.unmatched_records = unmatched_cnt
        run.break_count = len(breaks)
        run.critical_break_count = crit_count
        run.status = (
            ReconciliationRunStatus.COMPLETED
            if len(breaks) == 0
            else ReconciliationRunStatus.COMPLETED_WITH_BREAKS
        )
        run.completed_at = datetime.utcnow()
        return run

    # -----------------------------------------------------------------------
    # 3. BREAK ASSIGNMENT & RESOLUTION WORKFLOW
    # -----------------------------------------------------------------------
    async def assign_break(self, break_id: str, assigned_to: str) -> ReconciliationBreak:
        b = await self.repo.get_break_by_id(break_id)
        if not b:
            raise ValueError(f"Break {break_id} not found")
        b.assigned_to = assigned_to
        b.break_status = BreakStatus.ASSIGNED
        return b

    async def add_investigation_note(self, break_id: str, dto: BreakNoteCreate) -> ReconciliationNote:
        b = await self.repo.get_break_by_id(break_id)
        if not b:
            raise ValueError(f"Break {break_id} not found")
        b.break_status = BreakStatus.INVESTIGATING

        note = ReconciliationNote(
            note_id=f"not_{uuid.uuid4().hex[:12]}",
            break_id=break_id,
            author_id=dto.author_id,
            note_content=dto.note_content,
        )
        return await self.repo.add_note(note)

    async def resolve_break(self, break_id: str, dto: BreakResolveRequest) -> ReconciliationBreak:
        b = await self.repo.get_break_by_id(break_id)
        if not b:
            raise ValueError(f"Break {break_id} not found")

        now = datetime.utcnow()
        b.resolution_type = dto.resolution_type
        b.resolution_explanation = dto.resolution_explanation
        b.root_cause = dto.root_cause or dto.resolution_type.value
        b.break_status = BreakStatus.RESOLVED
        b.resolved_at = now
        b.closed_at = now
        return b

    async def reopen_break(self, break_id: str, reason: str = "New statement evidence received") -> ReconciliationBreak:
        b = await self.repo.get_break_by_id(break_id)
        if not b:
            raise ValueError(f"Break {break_id} not found")

        b.break_status = BreakStatus.REOPENED
        b.resolved_at = None
        b.closed_at = None

        await self.repo.add_note(
            ReconciliationNote(
                note_id=f"not_{uuid.uuid4().hex[:12]}",
                break_id=break_id,
                author_id="SYSTEM",
                note_content=f"Break reopened: {reason}",
            )
        )
        return b
