"""Tests for M05.06 Portfolio Reconciliation."""
import pytest
from datetime import datetime, date
from decimal import Decimal

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.modules.portfolio_management.portfolio_reconciliation.services.service import (
    PortfolioReconciliationService,
)
from backend.app.modules.portfolio_management.portfolio_reconciliation.models import (
    StatementType,
    ReconciliationType,
    ReconciliationRunStatus,
    BreakCategory,
    BreakStatus,
    BreakSeverity,
    ResolutionType,
)
from backend.app.modules.portfolio_management.portfolio_reconciliation.schemas import (
    StatementImportCreate,
    ExternalPositionItem,
    ExternalCashItem,
    ReconciliationRunCreate,
    BreakNoteCreate,
    BreakAssignRequest,
    BreakResolveRequest,
)

# Integrations to establish internal state
from backend.app.modules.portfolio_management.position_management.services.service import (
    PositionManagementService,
)
from backend.app.modules.portfolio_management.position_management.schemas import PositionEventRegisterRequest
from backend.app.modules.portfolio_management.position_management.models import PositionEventType
from backend.app.modules.portfolio_management.cash_management.services.service import (
    CashManagementService,
)
from backend.app.modules.portfolio_management.cash_management.schemas import DepositCreate


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_statement_import_and_deduplication():
    """Test importing external broker statement and verifying duplicate hash detection."""
    async with AsyncSessionLocal() as session:
        svc = PortfolioReconciliationService(session)
        port_id = "PORT_REC_01"
        acc_id = "ACC_01"

        dto = StatementImportCreate(
            provider_code="INTERACTIVE_BROKERS",
            statement_type=StatementType.POSITION,
            portfolio_id=port_id,
            account_id=acc_id,
            as_of_date=date(2026, 11, 1),
            file_name="ibkr_positions_20261101.csv",
            positions=[
                ExternalPositionItem(external_symbol="AAPL", quantity=Decimal("100.000000")),
                ExternalPositionItem(external_symbol="MSFT", quantity=Decimal("200.000000")),
            ],
        )
        stmt1 = await svc.import_statement(dto)
        assert stmt1.total_records == 2
        assert stmt1.valid_records == 2

        # Re-import identical statement -> should detect duplicate hash and return existing
        stmt2 = await svc.import_statement(dto)
        assert stmt2.statement_id == stmt1.statement_id


@pytest.mark.asyncio
async def test_position_reconciliation_exact_match_and_mismatch_breaks():
    """Test position reconciliation detecting exact matches, quantity mismatches, and missing positions."""
    async with AsyncSessionLocal() as session:
        svc = PortfolioReconciliationService(session)
        pos_svc = PositionManagementService(session)
        port_id = "PORT_REC_02"
        acc_id = "ACC_01"

        # 1. Establish internal position state: 100 shares of AAPL, 50 shares of GOOG
        await pos_svc.apply_position_event(
            PositionEventRegisterRequest(
                portfolio_id=port_id,
                account_id=acc_id,
                instrument_id="AAPL",
                event_type=PositionEventType.TRADE_BUY,
                signed_quantity_delta=Decimal("100.000000"),
                settled_quantity_delta=Decimal("100.000000"),
                effective_timestamp=datetime.utcnow(),
                idempotency_key="pos_evt_aapl_100",
            )
        )
        await pos_svc.apply_position_event(
            PositionEventRegisterRequest(
                portfolio_id=port_id,
                account_id=acc_id,
                instrument_id="GOOG",
                event_type=PositionEventType.TRADE_BUY,
                signed_quantity_delta=Decimal("50.000000"),
                settled_quantity_delta=Decimal("50.000000"),
                effective_timestamp=datetime.utcnow(),
                idempotency_key="pos_evt_goog_50",
            )
        )

        # 2. External statement:
        # - AAPL: 100 shares (Exact match)
        # - GOOG: 45 shares (Quantity mismatch: -5 shares)
        # - TSLA: 30 shares (Missing internal position)
        stmt = await svc.import_statement(
            StatementImportCreate(
                provider_code="CITADEL_CUSTODY",
                statement_type=StatementType.POSITION,
                portfolio_id=port_id,
                account_id=acc_id,
                as_of_date=date(2026, 11, 1),
                file_name="citadel_positions.csv",
                positions=[
                    ExternalPositionItem(external_symbol="AAPL", quantity=Decimal("100.000000")),
                    ExternalPositionItem(external_symbol="GOOG", quantity=Decimal("45.000000")),
                    ExternalPositionItem(external_symbol="TSLA", quantity=Decimal("30.000000")),
                ],
            )
        )

        # 3. Run Position Reconciliation
        run = await svc.run_reconciliation(
            ReconciliationRunCreate(
                portfolio_id=port_id,
                account_id=acc_id,
                provider_code="CITADEL_CUSTODY",
                reconciliation_type=ReconciliationType.POSITION,
                as_of_date=date(2026, 11, 1),
                statement_id=stmt.statement_id,
            )
        )
        assert run.status == ReconciliationRunStatus.COMPLETED_WITH_BREAKS
        assert run.matched_records == 1  # AAPL matched
        assert run.break_count == 2      # GOOG mismatch + TSLA missing internal

        # Inspect Breaks
        breaks = await svc.repo.list_breaks(port_id, acc_id)
        assert len(breaks) == 2
        goog_break = next(b for b in breaks if b.instrument_id == "GOOG")
        tsla_break = next(b for b in breaks if b.instrument_id == "TSLA")

        assert goog_break.break_category == BreakCategory.QUANTITY_MISMATCH
        assert goog_break.difference_value == Decimal("-5.000000")  # External (45) - Internal (50) = -5

        assert tsla_break.break_category == BreakCategory.MISSING_INTERNAL_POSITION
        assert tsla_break.difference_value == Decimal("30.000000")


@pytest.mark.asyncio
async def test_cash_reconciliation_balance_mismatch():
    """Test cash reconciliation comparing external cash closing balance with internal cash ledger."""
    async with AsyncSessionLocal() as session:
        svc = PortfolioReconciliationService(session)
        cash_svc = CashManagementService(session)
        port_id = "PORT_REC_03"
        acc_id = "ACC_01"

        # 1. Establish internal cash balance: 500,000 INR
        await cash_svc.process_deposit(
            DepositCreate(
                portfolio_id=port_id,
                account_id=acc_id,
                currency="INR",
                amount=Decimal("500000.000000"),
            )
        )

        # 2. External bank statement reports 498,000 INR (-2000 INR break)
        stmt = await svc.import_statement(
            StatementImportCreate(
                provider_code="HDFC_BANK",
                statement_type=StatementType.CASH,
                portfolio_id=port_id,
                account_id=acc_id,
                as_of_date=date(2026, 11, 1),
                file_name="hdfc_statement.csv",
                cash_records=[
                    ExternalCashItem(currency="INR", closing_balance=Decimal("498000.000000")),
                ],
            )
        )

        # 3. Run Cash Reconciliation
        run = await svc.run_reconciliation(
            ReconciliationRunCreate(
                portfolio_id=port_id,
                account_id=acc_id,
                provider_code="HDFC_BANK",
                reconciliation_type=ReconciliationType.CASH,
                as_of_date=date(2026, 11, 1),
                statement_id=stmt.statement_id,
            )
        )
        assert run.status == ReconciliationRunStatus.COMPLETED_WITH_BREAKS
        assert run.break_count == 1

        breaks = await svc.repo.list_breaks(port_id, acc_id)
        cash_break = breaks[0]
        assert cash_break.break_category == BreakCategory.CASH_BALANCE_MISMATCH
        assert cash_break.difference_value == Decimal("-2000.000000")
        assert cash_break.difference_unit == "INR"


@pytest.mark.asyncio
async def test_break_investigation_and_resolution_workflow():
    """Test assigning break, adding investigation notes, resolving with root-cause classification, and reopening."""
    async with AsyncSessionLocal() as session:
        svc = PortfolioReconciliationService(session)
        port_id = "PORT_REC_04"
        acc_id = "ACC_01"

        # 1. Ingest statement that generates a position break
        stmt = await svc.import_statement(
            StatementImportCreate(
                provider_code="MORGAN_STANLEY",
                statement_type=StatementType.POSITION,
                portfolio_id=port_id,
                account_id=acc_id,
                as_of_date=date(2026, 11, 1),
                file_name="ms_statement.csv",
                positions=[
                    ExternalPositionItem(external_symbol="NVDA", quantity=Decimal("200.000000")),
                ],
            )
        )
        run = await svc.run_reconciliation(
            ReconciliationRunCreate(
                portfolio_id=port_id,
                account_id=acc_id,
                provider_code="MORGAN_STANLEY",
                reconciliation_type=ReconciliationType.POSITION,
                as_of_date=date(2026, 11, 1),
                statement_id=stmt.statement_id,
            )
        )
        breaks = await svc.repo.list_breaks(port_id, acc_id)
        target_break = breaks[0]
        assert target_break.break_status == BreakStatus.OPEN

        # 2. Assign Break
        assigned_b = await svc.assign_break(target_break.break_id, assigned_to="ALICE_ANALYST")
        assert assigned_b.break_status == BreakStatus.ASSIGNED
        assert assigned_b.assigned_to == "ALICE_ANALYST"

        # 3. Add Investigation Note
        note = await svc.add_investigation_note(
            target_break.break_id,
            BreakNoteCreate(
                author_id="ALICE_ANALYST",
                note_content="Confirmed with broker: T+1 trade execution was confirmed post internal cutoff.",
            ),
        )
        assert note.note_content.startswith("Confirmed with broker")
        b_after_note = await svc.repo.get_break_by_id(target_break.break_id)
        assert b_after_note.break_status == BreakStatus.INVESTIGATING

        # 4. Resolve Break
        resolved_b = await svc.resolve_break(
            target_break.break_id,
            BreakResolveRequest(
                resolution_type=ResolutionType.TIMING_DIFFERENCE,
                resolution_explanation="Accepted as legitimate statement cutoff timing difference.",
                root_cause="TRADE_SETTLEMENT_TIMING",
            ),
        )
        assert resolved_b.break_status == BreakStatus.RESOLVED
        assert resolved_b.resolution_type == ResolutionType.TIMING_DIFFERENCE
        assert resolved_b.resolved_at is not None

        # 5. Reopen Break upon new evidence
        reopened_b = await svc.reopen_break(target_break.break_id, reason="Broker revised trade date")
        assert reopened_b.break_status == BreakStatus.REOPENED
        assert reopened_b.resolved_at is None
