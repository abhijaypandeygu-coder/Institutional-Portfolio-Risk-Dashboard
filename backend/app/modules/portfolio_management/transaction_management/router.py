"""FastAPI Router for M05.05 Transaction Management."""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.portfolio_management.transaction_management.schemas import (
    TransactionCreate,
    TransactionResponse,
    TradeExecutionCreate,
    TradeExecutionResponse,
    TransactionFeeCreate,
    TransactionFeeResponse,
    SecurityTransferCreate,
    CashTransferCreate,
    TransferResponse,
    AdjustmentCreate,
    AdjustmentResponse,
    ExecutionCorrectionCreate,
    LifecycleEventResponse,
    OutboxDeliveryStatusResponse,
)
from backend.app.modules.portfolio_management.transaction_management.services.service import TransactionManagementService
from backend.app.modules.portfolio_management.transaction_management.models import (
    TransactionType,
    TransactionStatus,
)

router = APIRouter(prefix="/api/v1/portfolios/{portfolio_id}/transactions", tags=["M05.05 Transaction Management"])


# ---------------------------------------------------------------------------
# TRANSACTIONS
# ---------------------------------------------------------------------------

@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    portfolio_id: str,
    payload: TransactionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Capture a new logical transaction or parent order."""
    if payload.portfolio_id != portfolio_id:
        raise HTTPException(status_code=400, detail="Portfolio ID mismatch")
    svc = TransactionManagementService(db)
    return await svc.create_transaction(payload)


@router.get("", response_model=List[TransactionResponse])
async def list_transactions(
    portfolio_id: str,
    account_id: Optional[str] = Query(None),
    instrument_id: Optional[str] = Query(None),
    transaction_type: Optional[TransactionType] = Query(None),
    status_filter: Optional[TransactionStatus] = Query(None, alias="status"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List transactions with filtering."""
    svc = TransactionManagementService(db)
    return await svc.repo.list_transactions(
        portfolio_id=portfolio_id,
        account_id=account_id,
        instrument_id=instrument_id,
        transaction_type=transaction_type,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    portfolio_id: str,
    transaction_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve transaction details by ID."""
    svc = TransactionManagementService(db)
    tx = await svc.repo.get_transaction_by_id(transaction_id)
    if not tx or tx.portfolio_id != portfolio_id:
        raise HTTPException(status_code=404, detail=f"Transaction {transaction_id} not found")
    return tx


# ---------------------------------------------------------------------------
# EXECUTIONS
# ---------------------------------------------------------------------------

@router.post("/{transaction_id}/executions", response_model=TradeExecutionResponse, status_code=status.HTTP_201_CREATED)
async def record_execution(
    portfolio_id: str,
    transaction_id: str,
    payload: TradeExecutionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Record an individual execution fill for a transaction."""
    svc = TransactionManagementService(db)
    tx = await svc.repo.get_transaction_by_id(transaction_id)
    if not tx or tx.portfolio_id != portfolio_id:
        raise HTTPException(status_code=404, detail=f"Transaction {transaction_id} not found")
    try:
        return await svc.record_execution(transaction_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{transaction_id}/executions", response_model=List[TradeExecutionResponse])
async def list_executions(
    portfolio_id: str,
    transaction_id: str,
    db: AsyncSession = Depends(get_db),
):
    """List all individual execution fills for a transaction."""
    svc = TransactionManagementService(db)
    return await svc.repo.list_executions_for_transaction(transaction_id)


# ---------------------------------------------------------------------------
# CANCELLATION & CORRECTIONS
# ---------------------------------------------------------------------------

@router.post("/{transaction_id}/cancel", response_model=TransactionResponse)
async def cancel_transaction(
    portfolio_id: str,
    transaction_id: str,
    reason: str = Query("Client cancel request"),
    db: AsyncSession = Depends(get_db),
):
    """Cancel unexecuted remainder of transaction while preserving existing fills."""
    svc = TransactionManagementService(db)
    try:
        return await svc.cancel_transaction(transaction_id, reason=reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{transaction_id}/corrections", response_model=TradeExecutionResponse)
async def correct_execution(
    portfolio_id: str,
    transaction_id: str,
    payload: ExecutionCorrectionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Submit a correction for an existing execution."""
    svc = TransactionManagementService(db)
    try:
        return await svc.correct_execution(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# TRANSFERS
# ---------------------------------------------------------------------------

@router.post("/security-transfers", response_model=TransferResponse, status_code=status.HTTP_201_CREATED)
async def process_security_transfer(
    portfolio_id: str,
    payload: SecurityTransferCreate,
    db: AsyncSession = Depends(get_db),
):
    """Record an inbound, outbound, or internal security transfer."""
    if payload.source_portfolio_id != portfolio_id and payload.destination_portfolio_id != portfolio_id:
        raise HTTPException(status_code=400, detail="Portfolio ID mismatch")
    svc = TransactionManagementService(db)
    return await svc.process_security_transfer(payload)


# ---------------------------------------------------------------------------
# ADJUSTMENTS
# ---------------------------------------------------------------------------

@router.post("/adjustments", response_model=AdjustmentResponse, status_code=status.HTTP_201_CREATED)
async def create_adjustment(
    portfolio_id: str,
    payload: AdjustmentCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a controlled manual adjustment request."""
    if payload.portfolio_id != portfolio_id:
        raise HTTPException(status_code=400, detail="Portfolio ID mismatch")
    svc = TransactionManagementService(db)
    return await svc.create_adjustment_request(payload)


@router.post("/adjustments/{adjustment_id}/approve", response_model=AdjustmentResponse)
async def approve_adjustment(
    portfolio_id: str,
    adjustment_id: str,
    approver: str = Query("SUPERVISOR"),
    db: AsyncSession = Depends(get_db),
):
    """Approve a controlled adjustment request under separation of duties."""
    svc = TransactionManagementService(db)
    try:
        return await svc.approve_adjustment(adjustment_id, approver=approver)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# LIFECYCLE & DELIVERY STATUS
# ---------------------------------------------------------------------------

@router.get("/{transaction_id}/lifecycle", response_model=List[LifecycleEventResponse])
async def get_lifecycle_history(
    portfolio_id: str,
    transaction_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve complete audit lifecycle history for a transaction."""
    svc = TransactionManagementService(db)
    return await svc.repo.list_lifecycle_events(transaction_id)


@router.get("/{transaction_id}/delivery-status", response_model=List[OutboxDeliveryStatusResponse])
async def get_delivery_status(
    portfolio_id: str,
    transaction_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Query downstream event delivery status for a transaction."""
    svc = TransactionManagementService(db)
    return await svc.repo.list_outbox_events_for_aggregate(transaction_id)
