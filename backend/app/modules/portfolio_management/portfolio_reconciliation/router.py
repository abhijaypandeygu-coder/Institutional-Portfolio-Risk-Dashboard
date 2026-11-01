"""FastAPI Router for M05.06 Portfolio Reconciliation."""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.portfolio_management.portfolio_reconciliation.schemas import (
    ProviderCreate,
    ProviderResponse,
    StatementImportCreate,
    StatementImportResponse,
    ReconciliationRunCreate,
    ReconciliationRunResponse,
    ReconciliationBreakResponse,
    BreakNoteCreate,
    BreakNoteResponse,
    BreakAssignRequest,
    BreakResolveRequest,
)
from backend.app.modules.portfolio_management.portfolio_reconciliation.services.service import (
    PortfolioReconciliationService,
)
from backend.app.modules.portfolio_management.portfolio_reconciliation.models import (
    BreakStatus,
    BreakSeverity,
    ReconciliationProvider,
)

router = APIRouter(prefix="/api/v1/reconciliation", tags=["M05.06 Portfolio Reconciliation"])


# ---------------------------------------------------------------------------
# PROVIDERS
# ---------------------------------------------------------------------------

@router.post("/providers", response_model=ProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(
    payload: ProviderCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register an external provider (broker, custodian, fund admin)."""
    svc = PortfolioReconciliationService(db)
    existing = await svc.repo.get_provider_by_code(payload.provider_code)
    if existing:
        return existing
    provider = ReconciliationProvider(
        provider_id=f"prv_{payload.provider_code.lower()}",
        provider_name=payload.provider_name,
        provider_type=payload.provider_type,
        provider_code=payload.provider_code.upper(),
    )
    return await svc.repo.create_provider(provider)


@router.get("/providers", response_model=List[ProviderResponse])
async def list_providers(
    db: AsyncSession = Depends(get_db),
):
    """List active reconciliation providers."""
    svc = PortfolioReconciliationService(db)
    return await svc.repo.list_providers()


# ---------------------------------------------------------------------------
# STATEMENT IMPORTS
# ---------------------------------------------------------------------------

@router.post("/statements/import", response_model=StatementImportResponse, status_code=status.HTTP_201_CREATED)
async def import_statement(
    payload: StatementImportCreate,
    db: AsyncSession = Depends(get_db),
):
    """Intake, hash, validate, and normalize an external statement dataset."""
    svc = PortfolioReconciliationService(db)
    return await svc.import_statement(payload)


@router.get("/statements/{statement_id}", response_model=StatementImportResponse)
async def get_statement(
    statement_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve imported statement metadata and records summary."""
    svc = PortfolioReconciliationService(db)
    stmt = await svc.repo.get_statement_import_by_id(statement_id)
    if not stmt:
        raise HTTPException(status_code=404, detail=f"Statement {statement_id} not found")
    return stmt


# ---------------------------------------------------------------------------
# RECONCILIATION RUNS
# ---------------------------------------------------------------------------

@router.post("/runs", response_model=ReconciliationRunResponse, status_code=status.HTTP_201_CREATED)
async def execute_reconciliation_run(
    payload: ReconciliationRunCreate,
    db: AsyncSession = Depends(get_db),
):
    """Execute reconciliation comparing external statements with authoritative internal books."""
    svc = PortfolioReconciliationService(db)
    return await svc.run_reconciliation(payload)


@router.get("/runs/{run_id}", response_model=ReconciliationRunResponse)
async def get_run_details(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve reconciliation run results and break summary."""
    svc = PortfolioReconciliationService(db)
    run = await svc.repo.get_run_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Reconciliation run {run_id} not found")
    return run


# ---------------------------------------------------------------------------
# BREAK MANAGEMENT & WORKFLOW
# ---------------------------------------------------------------------------

@router.get("/breaks", response_model=List[ReconciliationBreakResponse])
async def list_breaks(
    portfolio_id: str = Query(..., description="Target portfolio ID"),
    account_id: Optional[str] = Query(None),
    status_filter: Optional[BreakStatus] = Query(None, alias="status"),
    severity: Optional[BreakSeverity] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Query reconciliation breaks with filtering."""
    svc = PortfolioReconciliationService(db)
    return await svc.repo.list_breaks(
        portfolio_id=portfolio_id,
        account_id=account_id,
        status=status_filter,
        severity=severity,
    )


@router.get("/breaks/{break_id}", response_model=ReconciliationBreakResponse)
async def get_break_details(
    break_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full break details including investigation notes and status."""
    svc = PortfolioReconciliationService(db)
    b = await svc.repo.get_break_by_id(break_id)
    if not b:
        raise HTTPException(status_code=404, detail=f"Break {break_id} not found")
    return b


@router.post("/breaks/{break_id}/assign", response_model=ReconciliationBreakResponse)
async def assign_break(
    break_id: str,
    payload: BreakAssignRequest,
    db: AsyncSession = Depends(get_db),
):
    """Assign investigation responsibility for a reconciliation break."""
    svc = PortfolioReconciliationService(db)
    try:
        return await svc.assign_break(break_id, payload.assigned_to)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/breaks/{break_id}/notes", response_model=BreakNoteResponse, status_code=status.HTTP_201_CREATED)
async def add_investigation_note(
    break_id: str,
    payload: BreakNoteCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add an investigation note to a reconciliation break."""
    svc = PortfolioReconciliationService(db)
    try:
        return await svc.add_investigation_note(break_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/breaks/{break_id}/resolve", response_model=ReconciliationBreakResponse)
async def resolve_break(
    break_id: str,
    payload: BreakResolveRequest,
    db: AsyncSession = Depends(get_db),
):
    """Resolve and close a reconciliation break with root-cause classification."""
    svc = PortfolioReconciliationService(db)
    try:
        return await svc.resolve_break(break_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/breaks/{break_id}/reopen", response_model=ReconciliationBreakResponse)
async def reopen_break(
    break_id: str,
    reason: str = Query("New statement evidence received"),
    db: AsyncSession = Depends(get_db),
):
    """Reopen a previously resolved or closed break upon new evidence."""
    svc = PortfolioReconciliationService(db)
    try:
        return await svc.reopen_break(break_id, reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

