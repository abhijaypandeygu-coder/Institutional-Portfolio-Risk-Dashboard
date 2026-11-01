"""REST API Router for M05.02 - Position Management."""
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.portfolio_management.position_management.schemas import (
    PositionBookRegisterRequest,
    PositionBookResponse,
    PositionEventRegisterRequest,
    PositionEventResponse,
    PositionSnapshotResponse,
    PortfolioPositionAggregateResponse,
    PositionBorrowRegisterRequest,
    PositionBorrowResponse,
    PositionTransferCreateRequest,
    PositionTransferResponse,
    PositionReconciliationSubmitRequest,
    PositionReconciliationResponse,
)
from backend.app.modules.portfolio_management.position_management.services.service import PositionManagementService

router = APIRouter(prefix="/positions", tags=["Position Management"])


# ---------------------------------------------------------------------------
# 1. POSITION BOOK REGISTRATION & RETRIEVAL
# ---------------------------------------------------------------------------
@router.post("", response_model=PositionBookResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=PositionBookResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def register_position_book(payload: PositionBookRegisterRequest, db: AsyncSession = Depends(get_db)):
    service = PositionManagementService(db)
    try:
        return await service.get_or_create_position_book(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{position_id}", response_model=PositionBookResponse)
async def get_position_book(position_id: str, db: AsyncSession = Depends(get_db)):
    service = PositionManagementService(db)
    book = await service.repo.get_book_by_id(position_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Position '{position_id}' not found.")
    return book


@router.get("/{position_id}/snapshot", response_model=PositionSnapshotResponse)
async def get_latest_position_snapshot(position_id: str, db: AsyncSession = Depends(get_db)):
    service = PositionManagementService(db)
    snap = await service.repo.get_latest_snapshot(position_id)
    if not snap:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No snapshot found for '{position_id}'.")
    return snap


@router.get("/{position_id}/snapshot/as-of", response_model=PositionSnapshotResponse)
async def get_snapshot_as_of(
    position_id: str, as_of_dt: datetime = Query(...), db: AsyncSession = Depends(get_db)
):
    service = PositionManagementService(db)
    snap = await service.repo.get_snapshot_as_of(position_id, as_of_dt)
    if not snap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No historical snapshot found for '{position_id}' as of {as_of_dt}.",
        )
    return snap


# ---------------------------------------------------------------------------
# 2. POSITION EVENT INGESTION & LEDGER
# ---------------------------------------------------------------------------
@router.post("/events", response_model=PositionSnapshotResponse, status_code=status.HTTP_201_CREATED)
async def apply_position_event(payload: PositionEventRegisterRequest, db: AsyncSession = Depends(get_db)):
    service = PositionManagementService(db)
    try:
        return await service.apply_position_event(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{position_id}/events", response_model=List[PositionEventResponse])
async def list_position_events(position_id: str, db: AsyncSession = Depends(get_db)):
    service = PositionManagementService(db)
    return await service.repo.list_events_for_position(position_id)


# ---------------------------------------------------------------------------
# 3. ACCOUNT & PORTFOLIO RETRIEVAL
# ---------------------------------------------------------------------------
@router.get("/accounts/{account_id}", response_model=List[PositionBookResponse])
async def list_account_positions(account_id: str, db: AsyncSession = Depends(get_db)):
    service = PositionManagementService(db)
    return await service.repo.list_books_by_account(account_id)


@router.get("/portfolios/{portfolio_id}", response_model=List[PositionBookResponse])
async def list_portfolio_positions(portfolio_id: str, db: AsyncSession = Depends(get_db)):
    service = PositionManagementService(db)
    return await service.repo.list_books_by_portfolio(portfolio_id)


@router.get("/portfolios/{portfolio_id}/aggregates", response_model=List[PortfolioPositionAggregateResponse])
async def list_portfolio_aggregates(portfolio_id: str, db: AsyncSession = Depends(get_db)):
    service = PositionManagementService(db)
    return await service.repo.list_aggregates_for_portfolio(portfolio_id)


# ---------------------------------------------------------------------------
# 4. TRANSFERS
# ---------------------------------------------------------------------------
@router.post("/transfers", response_model=PositionTransferResponse, status_code=status.HTTP_201_CREATED)
async def create_transfer(payload: PositionTransferCreateRequest, db: AsyncSession = Depends(get_db)):
    service = PositionManagementService(db)
    try:
        return await service.process_transfer(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ---------------------------------------------------------------------------
# 5. BORROW METADATA
# ---------------------------------------------------------------------------
@router.post("/{position_id}/borrow", response_model=PositionBorrowResponse, status_code=status.HTTP_201_CREATED)
async def register_borrow(
    position_id: str, payload: PositionBorrowRegisterRequest, db: AsyncSession = Depends(get_db)
):
    service = PositionManagementService(db)
    try:
        return await service.register_borrow_metadata(position_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{position_id}/borrow", response_model=PositionBorrowResponse)
async def get_borrow_metadata(position_id: str, db: AsyncSession = Depends(get_db)):
    service = PositionManagementService(db)
    borrow = await service.repo.get_borrow_by_position(position_id)
    if not borrow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No borrow metadata for '{position_id}'.")
    return borrow


# ---------------------------------------------------------------------------
# 6. RECONCILIATION
# ---------------------------------------------------------------------------
@router.post("/reconciliation", response_model=PositionReconciliationResponse, status_code=status.HTTP_201_CREATED)
async def submit_reconciliation(payload: PositionReconciliationSubmitRequest, db: AsyncSession = Depends(get_db)):
    service = PositionManagementService(db)
    return await service.submit_reconciliation(payload)


@router.get("/reconciliation", response_model=List[PositionReconciliationResponse])
async def list_reconciliations(portfolio_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    service = PositionManagementService(db)
    return await service.repo.list_reconciliations(portfolio_id)


# ---------------------------------------------------------------------------
# 7. DETERMINISTIC REBUILD
# ---------------------------------------------------------------------------
@router.post("/{position_id}/rebuild", response_model=PositionSnapshotResponse)
async def rebuild_position(position_id: str, db: AsyncSession = Depends(get_db)):
    service = PositionManagementService(db)
    try:
        return await service.rebuild_position_history(position_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
