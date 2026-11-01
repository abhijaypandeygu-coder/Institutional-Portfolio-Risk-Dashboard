"""FastAPI Router for M05.04 Cash Management."""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.portfolio_management.cash_management.schemas import (
    CashAccountCreate,
    CashAccountResponse,
    CashBalanceResponse,
    AvailableCashExplanation,
    DepositCreate,
    WithdrawalCreate,
    CashMovementResponse,
    CashReservationCreate,
    CashReservationRelease,
    CashReservationAdjust,
    CashReservationResponse,
    CashTransferCreate,
    CashTransferResponse,
    CashReconciliationRunCreate,
    CashReconciliationResponse,
)
from backend.app.modules.portfolio_management.cash_management.services.service import CashManagementService
from backend.app.modules.portfolio_management.cash_management.models import (
    CashMovementType,
    CashMovementStatus,
)

router = APIRouter(prefix="/api/v1/portfolios/{portfolio_id}/cash", tags=["M05.04 Cash Management"])


# ---------------------------------------------------------------------------
# CASH BALANCES & AVAILABILITY
# ---------------------------------------------------------------------------

@router.get("/balances", response_model=List[CashBalanceResponse])
async def get_portfolio_cash_balances(
    portfolio_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all current cash balances across accounts and currencies for a portfolio."""
    svc = CashManagementService(db)
    accounts = await svc.repo.list_cash_accounts_by_portfolio(portfolio_id)
    balances = []
    for acc in accounts:
        snp = await svc.repo.get_latest_snapshot(portfolio_id, acc.account_id, acc.currency)
        if not snp:
            snp = await svc.calculate_and_snapshot_balances(portfolio_id, acc.account_id, acc.currency)
        balances.append(snp)
    return balances


@router.get("/accounts/{account_id}/balances", response_model=List[CashBalanceResponse])
async def get_account_cash_balances(
    portfolio_id: str,
    account_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve currency-specific cash balances for a selected account."""
    svc = CashManagementService(db)
    accounts = await svc.repo.list_cash_accounts_by_account(portfolio_id, account_id)
    balances = []
    for acc in accounts:
        snp = await svc.repo.get_latest_snapshot(portfolio_id, account_id, acc.currency)
        if not snp:
            snp = await svc.calculate_and_snapshot_balances(portfolio_id, account_id, acc.currency)
        balances.append(snp)
    return balances


@router.get("/available", response_model=AvailableCashExplanation)
async def get_available_cash(
    portfolio_id: str,
    account_id: str = Query(..., description="Account identifier"),
    currency: str = Query("USD", description="Currency code (e.g. 'USD', 'INR')"),
    db: AsyncSession = Depends(get_db),
):
    """Calculate and explain available cash according to portfolio policy."""
    svc = CashManagementService(db)
    return await svc.calculate_available_cash(portfolio_id, account_id, currency.upper())


# ---------------------------------------------------------------------------
# DEPOSITS & WITHDRAWALS
# ---------------------------------------------------------------------------

@router.post("/deposits", response_model=CashMovementResponse, status_code=status.HTTP_201_CREATED)
async def create_deposit(
    portfolio_id: str,
    payload: DepositCreate,
    db: AsyncSession = Depends(get_db),
):
    """Process an authorized cash deposit."""
    if payload.portfolio_id != portfolio_id:
        raise HTTPException(status_code=400, detail="Portfolio ID mismatch")
    svc = CashManagementService(db)
    try:
        return await svc.process_deposit(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/withdrawals", response_model=CashMovementResponse, status_code=status.HTTP_201_CREATED)
async def create_withdrawal(
    portfolio_id: str,
    payload: WithdrawalCreate,
    db: AsyncSession = Depends(get_db),
):
    """Process an authorized cash withdrawal subject to available cash."""
    if payload.portfolio_id != portfolio_id:
        raise HTTPException(status_code=400, detail="Portfolio ID mismatch")
    svc = CashManagementService(db)
    try:
        return await svc.process_withdrawal(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# CASH MOVEMENTS
# ---------------------------------------------------------------------------

@router.get("/movements", response_model=List[CashMovementResponse])
async def list_movements(
    portfolio_id: str,
    account_id: Optional[str] = Query(None),
    currency: Optional[str] = Query(None),
    movement_type: Optional[CashMovementType] = Query(None),
    status_filter: Optional[CashMovementStatus] = Query(None, alias="status"),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Query historical cash movement ledger."""
    svc = CashManagementService(db)
    return await svc.repo.list_movements(
        portfolio_id=portfolio_id,
        account_id=account_id,
        currency=currency.upper() if currency else None,
        movement_type=movement_type,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
    )


# ---------------------------------------------------------------------------
# CASH RESERVATIONS
# ---------------------------------------------------------------------------

@router.post("/reservations", response_model=CashReservationResponse, status_code=status.HTTP_201_CREATED)
async def create_reservation(
    portfolio_id: str,
    payload: CashReservationCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a cash reservation against available cash."""
    if payload.portfolio_id != portfolio_id:
        raise HTTPException(status_code=400, detail="Portfolio ID mismatch")
    svc = CashManagementService(db)
    try:
        return await svc.create_reservation(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reservations/{reservation_id}/release", response_model=CashReservationResponse)
async def release_reservation(
    portfolio_id: str,
    reservation_id: str,
    payload: CashReservationRelease,
    db: AsyncSession = Depends(get_db),
):
    """Release all or part of an active cash reservation."""
    svc = CashManagementService(db)
    try:
        return await svc.release_reservation(
            reservation_id=reservation_id,
            release_amount=payload.release_amount,
            reason=payload.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reservations/{reservation_id}/adjust", response_model=CashReservationResponse)
async def adjust_reservation(
    portfolio_id: str,
    reservation_id: str,
    payload: CashReservationAdjust,
    db: AsyncSession = Depends(get_db),
):
    """Adjust an existing cash reservation amount."""
    svc = CashManagementService(db)
    try:
        return await svc.adjust_reservation(
            reservation_id=reservation_id,
            new_reserved_amount=payload.new_reserved_amount,
            reason=payload.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# TRANSFERS
# ---------------------------------------------------------------------------

@router.post("/transfers", response_model=CashTransferResponse, status_code=status.HTTP_201_CREATED)
async def create_transfer(
    portfolio_id: str,
    payload: CashTransferCreate,
    db: AsyncSession = Depends(get_db),
):
    """Execute an internal or cross-currency cash transfer."""
    if payload.source_portfolio_id != portfolio_id:
        raise HTTPException(status_code=400, detail="Source portfolio ID mismatch")
    svc = CashManagementService(db)
    try:
        return await svc.process_transfer(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# RECONCILIATION
# ---------------------------------------------------------------------------

@router.post("/reconciliation/run", response_model=CashReconciliationResponse)
async def run_reconciliation(
    portfolio_id: str,
    payload: CashReconciliationRunCreate,
    db: AsyncSession = Depends(get_db),
):
    """Run cash balance reconciliation against an external statement."""
    if payload.portfolio_id != portfolio_id:
        raise HTTPException(status_code=400, detail="Portfolio ID mismatch")
    svc = CashManagementService(db)
    return await svc.run_reconciliation(payload)
