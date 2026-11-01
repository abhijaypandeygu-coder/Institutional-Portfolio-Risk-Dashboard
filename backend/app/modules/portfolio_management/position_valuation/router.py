"""REST API Router for M05.03 - Position Valuation."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.portfolio_management.position_valuation.schemas import (
    PositionValuationResponse,
    PortfolioValuationSnapshotResponse,
    CostBasisLotResponse,
    CostBasisAllocationResponse,
    RunValuationRequest,
)
from backend.app.modules.portfolio_management.position_valuation.services.service import PositionValuationService

router = APIRouter(prefix="/valuations", tags=["Position Valuation"])


# ---------------------------------------------------------------------------
# 1. RUN VALUATION
# ---------------------------------------------------------------------------
@router.post("/run", response_model=PortfolioValuationSnapshotResponse, status_code=status.HTTP_201_CREATED)
async def run_valuation(payload: RunValuationRequest, db: AsyncSession = Depends(get_db)):
    service = PositionValuationService(db)
    try:
        return await service.run_portfolio_valuation(
            portfolio_id=payload.portfolio_id,
            as_of_dt=payload.valuation_date,
            provided_marks=payload.mark_prices,
            provided_fx_rates=payload.fx_rates_to_base,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ---------------------------------------------------------------------------
# 2. POSITION VALUATIONS RETRIEVAL
# ---------------------------------------------------------------------------
@router.get("/portfolios/{portfolio_id}/positions", response_model=List[PositionValuationResponse])
async def list_position_valuations(
    portfolio_id: str, calculation_id: Optional[str] = None, db: AsyncSession = Depends(get_db)
):
    service = PositionValuationService(db)
    return await service.repo.list_position_valuations(portfolio_id, calculation_id)


@router.get("/portfolios/{portfolio_id}/positions/{instrument_id}", response_model=PositionValuationResponse)
async def get_latest_instrument_valuation(
    portfolio_id: str, instrument_id: str, db: AsyncSession = Depends(get_db)
):
    service = PositionValuationService(db)
    val = await service.repo.get_latest_position_valuation(portfolio_id, instrument_id)
    if not val:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No valuation found for instrument '{instrument_id}' in portfolio '{portfolio_id}'.",
        )
    return val


# ---------------------------------------------------------------------------
# 3. PORTFOLIO SUMMARY & SNAPSHOTS
# ---------------------------------------------------------------------------
@router.get("/portfolios/{portfolio_id}/summary", response_model=PortfolioValuationSnapshotResponse)
async def get_latest_portfolio_summary(portfolio_id: str, db: AsyncSession = Depends(get_db)):
    service = PositionValuationService(db)
    snap = await service.repo.get_latest_portfolio_snapshot(portfolio_id)
    if not snap:
        # Run valuation on demand if no snapshot exists yet
        snap = await service.run_portfolio_valuation(portfolio_id)
    return snap


@router.get("/portfolios/{portfolio_id}/history", response_model=List[PortfolioValuationSnapshotResponse])
async def list_portfolio_valuation_history(portfolio_id: str, db: AsyncSession = Depends(get_db)):
    service = PositionValuationService(db)
    return await service.repo.list_portfolio_snapshots(portfolio_id)


# ---------------------------------------------------------------------------
# 4. REALIZED P&L
# ---------------------------------------------------------------------------
@router.get("/portfolios/{portfolio_id}/realized-pnl", response_model=List[CostBasisAllocationResponse])
async def list_realized_pnl_allocations(
    portfolio_id: str,
    period_start: Optional[datetime] = None,
    period_end: Optional[datetime] = None,
    account_id: Optional[str] = None,
    instrument_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    service = PositionValuationService(db)
    return await service.repo.list_allocations(
        portfolio_id=portfolio_id,
        start_date=period_start,
        end_date=period_end,
        account_id=account_id,
        instrument_id=instrument_id,
    )


# ---------------------------------------------------------------------------
# 5. COST BASIS LOTS
# ---------------------------------------------------------------------------
@router.get("/portfolios/{portfolio_id}/lots", response_model=List[CostBasisLotResponse])
async def list_portfolio_cost_basis_lots(portfolio_id: str, db: AsyncSession = Depends(get_db)):
    service = PositionValuationService(db)
    return await service.repo.list_lots_for_portfolio(portfolio_id)
