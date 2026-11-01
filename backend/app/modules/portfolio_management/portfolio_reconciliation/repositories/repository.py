"""SQLAlchemy 2.0 Repository for M05.06 Portfolio Reconciliation."""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Tuple
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.portfolio_management.portfolio_reconciliation.models import (
    ReconciliationProvider,
    StatementImport,
    ExternalPositionRecord,
    ExternalTransactionRecord,
    ExternalCashRecord,
    ReconciliationRun,
    ReconciliationBreak,
    ReconciliationNote,
    BreakStatus,
    BreakSeverity,
    BreakCategory,
    ImportStatus,
)


class PortfolioReconciliationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # -----------------------------------------------------------------------
    # PROVIDERS
    # -----------------------------------------------------------------------
    async def create_provider(self, provider: ReconciliationProvider) -> ReconciliationProvider:
        self.session.add(provider)
        await self.session.flush()
        return provider

    async def get_provider_by_code(self, provider_code: str) -> Optional[ReconciliationProvider]:
        stmt = select(ReconciliationProvider).where(ReconciliationProvider.provider_code == provider_code)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_providers(self) -> List[ReconciliationProvider]:
        stmt = select(ReconciliationProvider).where(ReconciliationProvider.is_active == True)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # STATEMENT IMPORTS
    # -----------------------------------------------------------------------
    async def create_statement_import(self, statement: StatementImport) -> StatementImport:
        self.session.add(statement)
        await self.session.flush()
        return statement

    async def get_statement_import_by_id(self, statement_id: str) -> Optional[StatementImport]:
        stmt = (
            select(StatementImport)
            .options(
                selectinload(StatementImport.positions),
                selectinload(StatementImport.transactions),
                selectinload(StatementImport.cash_records),
            )
            .where(StatementImport.statement_id == statement_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_statement_by_hash(self, file_hash: str) -> Optional[StatementImport]:
        stmt = select(StatementImport).where(StatementImport.file_hash == file_hash)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    # -----------------------------------------------------------------------
    # EXTERNAL RECORDS
    # -----------------------------------------------------------------------
    async def list_external_positions(self, statement_id: str) -> List[ExternalPositionRecord]:
        stmt = select(ExternalPositionRecord).where(ExternalPositionRecord.statement_id == statement_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_external_transactions(self, statement_id: str) -> List[ExternalTransactionRecord]:
        stmt = select(ExternalTransactionRecord).where(ExternalTransactionRecord.statement_id == statement_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_external_cash_records(self, statement_id: str) -> List[ExternalCashRecord]:
        stmt = select(ExternalCashRecord).where(ExternalCashRecord.statement_id == statement_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # RECONCILIATION RUNS
    # -----------------------------------------------------------------------
    async def create_reconciliation_run(self, run: ReconciliationRun) -> ReconciliationRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_run_by_id(self, run_id: str) -> Optional[ReconciliationRun]:
        stmt = (
            select(ReconciliationRun)
            .options(selectinload(ReconciliationRun.breaks).selectinload(ReconciliationBreak.notes))
            .where(ReconciliationRun.run_id == run_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_runs(self, portfolio_id: str, account_id: Optional[str] = None) -> List[ReconciliationRun]:
        conditions = [ReconciliationRun.portfolio_id == portfolio_id]
        if account_id:
            conditions.append(ReconciliationRun.account_id == account_id)
        stmt = select(ReconciliationRun).where(and_(*conditions)).order_by(ReconciliationRun.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # BREAKS & WORKFLOW
    # -----------------------------------------------------------------------
    async def create_break(self, break_obj: ReconciliationBreak) -> ReconciliationBreak:
        self.session.add(break_obj)
        await self.session.flush()
        return break_obj

    async def get_break_by_id(self, break_id: str) -> Optional[ReconciliationBreak]:
        stmt = (
            select(ReconciliationBreak)
            .options(selectinload(ReconciliationBreak.notes))
            .where(ReconciliationBreak.break_id == break_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_breaks(
        self,
        portfolio_id: str,
        account_id: Optional[str] = None,
        status: Optional[BreakStatus] = None,
        severity: Optional[BreakSeverity] = None,
    ) -> List[ReconciliationBreak]:
        conditions = [ReconciliationBreak.portfolio_id == portfolio_id]
        if account_id:
            conditions.append(ReconciliationBreak.account_id == account_id)
        if status:
            conditions.append(ReconciliationBreak.break_status == status)
        if severity:
            conditions.append(ReconciliationBreak.severity == severity)
        stmt = (
            select(ReconciliationBreak)
            .options(selectinload(ReconciliationBreak.notes))
            .where(and_(*conditions))
            .order_by(ReconciliationBreak.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add_note(self, note: ReconciliationNote) -> ReconciliationNote:
        self.session.add(note)
        await self.session.flush()
        return note

