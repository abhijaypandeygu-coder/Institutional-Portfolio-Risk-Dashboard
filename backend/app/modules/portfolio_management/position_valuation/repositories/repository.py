"""Database repository for M05.03 - Position Valuation."""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.portfolio_management.position_management.models import PositionSide
from backend.app.modules.portfolio_management.position_valuation.models import (
    CostBasisLot,
    CostBasisAllocation,
    PositionValuation,
    PortfolioValuationSnapshot,
    LotStatus,
    ValuationStatus,
    AccountingMethod,
)


class ValuationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # -----------------------------------------------------------------------
    # COST BASIS LOTS
    # -----------------------------------------------------------------------
    async def create_lot(self, lot: CostBasisLot) -> CostBasisLot:
        self.session.add(lot)
        await self.session.flush()
        return lot

    async def get_lot_by_id(self, lot_id: str) -> Optional[CostBasisLot]:
        stmt = select(CostBasisLot).where(CostBasisLot.lot_id == lot_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_open_lots(
        self, portfolio_id: str, account_id: str, instrument_id: str, position_side: PositionSide
    ) -> List[CostBasisLot]:
        stmt = select(CostBasisLot).where(
            CostBasisLot.portfolio_id == portfolio_id,
            CostBasisLot.account_id == account_id,
            CostBasisLot.instrument_id == instrument_id,
            CostBasisLot.position_side == position_side,
            CostBasisLot.lot_status.in_([LotStatus.OPEN, LotStatus.PARTIALLY_CLOSED]),
            CostBasisLot.remaining_quantity > Decimal("0.0"),
        ).order_by(CostBasisLot.opening_effective_at.asc(), CostBasisLot.id.asc()) # FIFO by default
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_lots_for_portfolio(self, portfolio_id: str) -> List[CostBasisLot]:
        stmt = select(CostBasisLot).where(CostBasisLot.portfolio_id == portfolio_id).order_by(CostBasisLot.opening_effective_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # COST BASIS ALLOCATIONS (REALIZED P&L)
    # -----------------------------------------------------------------------
    async def create_allocation(self, alloc: CostBasisAllocation) -> CostBasisAllocation:
        self.session.add(alloc)
        await self.session.flush()
        return alloc

    async def list_allocations(
        self,
        portfolio_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        account_id: Optional[str] = None,
        instrument_id: Optional[str] = None,
    ) -> List[CostBasisAllocation]:
        stmt = select(CostBasisAllocation).where(CostBasisAllocation.portfolio_id == portfolio_id)
        if start_date:
            stmt = stmt.where(CostBasisAllocation.effective_at >= start_date)
        if end_date:
            stmt = stmt.where(CostBasisAllocation.effective_at <= end_date)
        if account_id:
            stmt = stmt.where(CostBasisAllocation.account_id == account_id)
        if instrument_id:
            stmt = stmt.where(CostBasisAllocation.instrument_id == instrument_id)
        stmt = stmt.order_by(CostBasisAllocation.effective_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # POSITION VALUATIONS
    # -----------------------------------------------------------------------
    async def save_position_valuation(self, val: PositionValuation) -> PositionValuation:
        self.session.add(val)
        await self.session.flush()
        return val

    async def list_position_valuations(
        self, portfolio_id: str, calculation_id: Optional[str] = None
    ) -> List[PositionValuation]:
        stmt = select(PositionValuation).where(PositionValuation.portfolio_id == portfolio_id)
        if calculation_id:
            stmt = stmt.where(PositionValuation.calculation_id == calculation_id)
        stmt = stmt.order_by(PositionValuation.effective_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_position_valuation(self, portfolio_id: str, instrument_id: str) -> Optional[PositionValuation]:
        stmt = select(PositionValuation).where(
            PositionValuation.portfolio_id == portfolio_id,
            PositionValuation.instrument_id == instrument_id,
        ).order_by(PositionValuation.effective_at.desc(), PositionValuation.id.desc())
        result = await self.session.execute(stmt)
        return result.scalars().first()

    # -----------------------------------------------------------------------
    # PORTFOLIO VALUATION SNAPSHOTS
    # -----------------------------------------------------------------------
    async def save_portfolio_snapshot(self, snap: PortfolioValuationSnapshot) -> PortfolioValuationSnapshot:
        self.session.add(snap)
        await self.session.flush()
        return snap

    async def get_latest_portfolio_snapshot(self, portfolio_id: str) -> Optional[PortfolioValuationSnapshot]:
        stmt = select(PortfolioValuationSnapshot).where(
            PortfolioValuationSnapshot.portfolio_id == portfolio_id
        ).order_by(PortfolioValuationSnapshot.valuation_timestamp.desc(), PortfolioValuationSnapshot.id.desc())
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_portfolio_snapshots(self, portfolio_id: str) -> List[PortfolioValuationSnapshot]:
        stmt = select(PortfolioValuationSnapshot).where(
            PortfolioValuationSnapshot.portfolio_id == portfolio_id
        ).order_by(PortfolioValuationSnapshot.valuation_timestamp.desc(), PortfolioValuationSnapshot.id.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
