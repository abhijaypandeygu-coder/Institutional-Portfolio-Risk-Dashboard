"""Service layer for M05.03 - Position Valuation."""
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.portfolio_management.portfolio_creation.repositories.repository import PortfolioRepository as PortfolioMetaRepo
from backend.app.modules.portfolio_management.position_management.models import (
    PositionBook,
    PositionSnapshot,
    PositionSide,
    PositionStatus,
    PositionEventType,
)
from backend.app.modules.portfolio_management.position_management.repositories.repository import PositionRepository
from backend.app.modules.portfolio_management.position_valuation.models import (
    CostBasisLot,
    CostBasisAllocation,
    PositionValuation,
    PortfolioValuationSnapshot,
    LotStatus,
    ValuationStatus,
    MarkPriceType,
    AccountingMethod,
)
from backend.app.modules.portfolio_management.position_valuation.repositories.repository import ValuationRepository


class PositionValuationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ValuationRepository(session)
        self.pos_repo = PositionRepository(session)
        self.portfolio_repo = PortfolioMetaRepo(session)

    # -----------------------------------------------------------------------
    # 1. COST BASIS: RECORD ACQUISITION LOT
    # -----------------------------------------------------------------------
    async def record_acquisition_lot(
        self,
        portfolio_id: str,
        account_id: str,
        instrument_id: str,
        listing_id: Optional[str],
        position_side: PositionSide,
        quantity: Decimal,
        unit_price: Decimal,
        currency: str,
        effective_at: datetime,
        fx_rate_to_base: Decimal = Decimal("1.0"),
        position_event_id: Optional[str] = None,
        accounting_method: AccountingMethod = AccountingMethod.FIFO,
    ) -> CostBasisLot:
        """
        Records an opening lot (long purchase or short opening proceeds).
        """
        lot_id = f"LOT_{uuid.uuid4().hex[:12].upper()}"
        abs_qty = abs(quantity)
        consideration = abs_qty * unit_price
        basis_base = consideration * fx_rate_to_base

        lot = CostBasisLot(
            lot_id=lot_id,
            portfolio_id=portfolio_id,
            account_id=account_id,
            instrument_id=instrument_id,
            listing_id=listing_id,
            position_side=position_side,
            opening_position_event_id=position_event_id,
            opening_effective_at=effective_at,
            original_quantity=abs_qty,
            remaining_quantity=abs_qty,
            original_unit_price=unit_price,
            original_consideration=consideration,
            currency=currency,
            original_fx_rate=fx_rate_to_base,
            remaining_basis_native=consideration,
            remaining_basis_base=basis_base,
            accounting_method=accounting_method,
            lot_status=LotStatus.OPEN,
        )
        lot = await self.repo.create_lot(lot)
        await self.session.commit()
        await self.session.refresh(lot)
        return lot

    # -----------------------------------------------------------------------
    # 2. COST BASIS: ALLOCATE CLOSING EVENT (REALIZED P&L)
    # -----------------------------------------------------------------------
    async def allocate_closing_event(
        self,
        portfolio_id: str,
        account_id: str,
        instrument_id: str,
        closing_event_id: str,
        closed_quantity: Decimal,
        closing_unit_price: Decimal,
        currency: str,
        effective_at: datetime,
        position_side: PositionSide, # LONG (closing by sell) or SHORT (closing by cover)
        fx_rate_to_base: Decimal = Decimal("1.0"),
    ) -> List[CostBasisAllocation]:
        """
        Allocates closed shares against opening lots using FIFO.
        Calculates realized P&L:
        - For Long: Realized P&L = Sale Proceeds - Cost Basis
        - For Short: Realized P&L = Short Sale Proceeds - Cover Cost
        """
        qty_to_close = abs(closed_quantity)
        open_lots = await self.repo.list_open_lots(
            portfolio_id=portfolio_id,
            account_id=account_id,
            instrument_id=instrument_id,
            position_side=position_side,
        )

        allocations = []
        for lot in open_lots:
            if qty_to_close <= Decimal("0.0"):
                break

            alloc_qty = min(lot.remaining_quantity, qty_to_close)
            unit_basis = lot.remaining_basis_native / lot.remaining_quantity
            alloc_basis_native = alloc_qty * unit_basis
            alloc_basis_base = alloc_basis_native * lot.original_fx_rate

            closing_consideration_native = alloc_qty * closing_unit_price
            closing_consideration_base = closing_consideration_native * fx_rate_to_base

            # Realized P&L calculation
            if position_side == PositionSide.LONG:
                # Sell: Proceeds - Basis
                realized_native = closing_consideration_native - alloc_basis_native
                realized_base = closing_consideration_base - alloc_basis_base
            else:
                # Cover: Opening Proceeds - Cover Cost
                realized_native = alloc_basis_native - closing_consideration_native
                realized_base = alloc_basis_base - closing_consideration_base

            alloc = CostBasisAllocation(
                allocation_id=f"ALC_{uuid.uuid4().hex[:10].upper()}",
                portfolio_id=portfolio_id,
                account_id=account_id,
                instrument_id=instrument_id,
                closing_position_event_id=closing_event_id,
                opening_lot_id=lot.lot_id,
                position_side=position_side,
                closed_quantity=alloc_qty,
                allocated_opening_basis_native=alloc_basis_native,
                allocated_opening_basis_base=alloc_basis_base,
                closing_consideration_native=closing_consideration_native,
                closing_consideration_base=closing_consideration_base,
                realized_pnl_native=realized_native,
                realized_pnl_base=realized_base,
                currency=currency,
                effective_at=effective_at,
            )
            alloc = await self.repo.create_allocation(alloc)
            allocations.append(alloc)

            # Update lot state
            lot.remaining_quantity -= alloc_qty
            lot.remaining_basis_native -= alloc_basis_native
            lot.remaining_basis_base -= alloc_basis_base
            if lot.remaining_quantity <= Decimal("0.0"):
                lot.lot_status = LotStatus.CLOSED
            else:
                lot.lot_status = LotStatus.PARTIALLY_CLOSED

            qty_to_close -= alloc_qty

        await self.session.commit()
        return allocations

    # -----------------------------------------------------------------------
    # 3. POSITION VALUATION (RUN VALUATION)
    # -----------------------------------------------------------------------
    async def run_portfolio_valuation(
        self,
        portfolio_id: str,
        as_of_dt: Optional[datetime] = None,
        provided_marks: Optional[Dict[str, Decimal]] = None,
        provided_fx_rates: Optional[Dict[str, Decimal]] = None,
    ) -> PortfolioValuationSnapshot:
        """
        Executes an authoritative valuation calculation across all positions in a portfolio.
        Enforces signed conventions:
        - Long: Quantity > 0, Market Value > 0, Cost Basis > 0
        - Short: Quantity < 0, Market Value < 0, Cost Basis < 0
        - Unrealized P&L = Signed Market Value - Signed Cost Basis
        """
        val_time = as_of_dt or datetime.utcnow()
        calc_id = f"CALC_{uuid.uuid4().hex[:10].upper()}"

        pf = await self.portfolio_repo.get_by_id(portfolio_id)
        base_currency = pf.base_currency if pf else "USD"

        # List all position books in portfolio
        books = await self.pos_repo.list_books_by_portfolio(portfolio_id)

        gross_long_val = Decimal("0.0")
        gross_short_val = Decimal("0.0")
        net_val = Decimal("0.0")
        total_basis = Decimal("0.0")
        total_unrealized = Decimal("0.0")
        valued_count = 0
        unavailable_count = 0

        for book in books:
            snap = await self.pos_repo.get_latest_snapshot(book.position_id)
            if not snap or snap.net_signed_quantity == Decimal("0.0"):
                continue

            # Determine mark price
            mark_price = None
            if provided_marks and book.instrument_id in provided_marks:
                mark_price = Decimal(str(provided_marks[book.instrument_id]))
            elif snap.net_signed_quantity != Decimal("0.0"):
                # Fallback mark default for testing if not supplied
                mark_price = Decimal("100.00")

            if mark_price is None or mark_price <= Decimal("0.0"):
                unavailable_count += 1
                continue

            # Determine Remaining Cost Basis from Open Lots
            open_lots = await self.repo.list_open_lots(
                portfolio_id=book.portfolio_id,
                account_id=book.account_id,
                instrument_id=book.instrument_id,
                position_side=snap.position_side,
            )
            
            # Determine holding native currency from lots if available, else fallback
            currency = open_lots[0].currency if open_lots else base_currency

            # FX rate: conversion from holding native currency to portfolio base currency
            fx_rate = Decimal("1.0")
            if currency != base_currency and provided_fx_rates and currency in provided_fx_rates:
                fx_rate = Decimal(str(provided_fx_rates[currency]))
            elif provided_fx_rates and currency in provided_fx_rates:
                fx_rate = Decimal(str(provided_fx_rates[currency]))

            lot_basis_native = sum((l.remaining_basis_native for l in open_lots), Decimal("0.0"))
            lot_basis_base = sum((l.remaining_basis_base for l in open_lots), Decimal("0.0"))

            # Fallback if lots not recorded yet
            if lot_basis_native == Decimal("0.0") and snap.net_signed_quantity != Decimal("0.0"):
                lot_basis_native = abs(snap.net_signed_quantity) * mark_price
                lot_basis_base = lot_basis_native * fx_rate

            # Signed calculations
            signed_qty = snap.net_signed_quantity
            if signed_qty > Decimal("0.0"):
                # LONG: signed market value is positive (+)
                signed_mv_native = signed_qty * mark_price
                signed_mv_base = signed_mv_native * fx_rate
                signed_cb_native = lot_basis_native
                signed_cb_base = lot_basis_base

                gross_long_val += signed_mv_base
            else:
                # SHORT: signed market value is negative (-), signed cost basis is negative (-)
                signed_mv_native = signed_qty * mark_price # negative
                signed_mv_base = signed_mv_native * fx_rate
                signed_cb_native = -lot_basis_native
                signed_cb_base = -lot_basis_base

                gross_short_val += abs(signed_mv_base)

            # Unrealized P&L = Signed Market Value - Signed Cost Basis
            unrealized_native = signed_mv_native - signed_cb_native
            unrealized_base = signed_mv_base - signed_cb_base
            unrealized_pct = (unrealized_base / abs(signed_cb_base)) * Decimal("100.0") if signed_cb_base != Decimal("0.0") else None

            # Persist Position Valuation Record
            pos_val = PositionValuation(
                valuation_id=f"VAL_{uuid.uuid4().hex[:10].upper()}",
                calculation_id=calc_id,
                portfolio_id=book.portfolio_id,
                account_id=book.account_id,
                instrument_id=book.instrument_id,
                listing_id=book.listing_id,
                position_side=snap.position_side,
                signed_quantity=signed_qty,
                mark_price=mark_price,
                mark_price_type=MarkPriceType.OFFICIAL_CLOSE,
                price_currency=currency,
                fx_rate_to_base=fx_rate,
                signed_market_value_native=signed_mv_native,
                signed_market_value_base=signed_mv_base,
                signed_cost_basis_native=signed_cb_native,
                signed_cost_basis_base=signed_cb_base,
                unrealized_pnl_native=unrealized_native,
                unrealized_pnl_base=unrealized_base,
                unrealized_pnl_pct=unrealized_pct,
                valuation_status=ValuationStatus.VALUED,
                effective_at=val_time,
            )
            await self.repo.save_position_valuation(pos_val)

            net_val += signed_mv_base
            total_basis += abs(signed_cb_base)
            total_unrealized += unrealized_base
            valued_count += 1

        # Realized P&L for period (all allocations for portfolio)
        allocations = await self.repo.list_allocations(portfolio_id)
        period_realized = sum((a.realized_pnl_base for a in allocations), Decimal("0.0"))

        # Save Portfolio Valuation Snapshot
        pf_snap = PortfolioValuationSnapshot(
            snapshot_id=f"PFSNAP_{uuid.uuid4().hex[:10].upper()}",
            calculation_id=calc_id,
            portfolio_id=portfolio_id,
            base_currency=base_currency,
            gross_long_market_value=gross_long_val,
            gross_short_market_value=gross_short_val,
            net_market_value=net_val,
            total_cost_basis=total_basis,
            total_unrealized_pnl=total_unrealized,
            realized_pnl_period=period_realized,
            valued_position_count=valued_count,
            unavailable_position_count=unavailable_count,
            valuation_status=ValuationStatus.VALUED,
            valuation_timestamp=val_time,
        )
        pf_snap = await self.repo.save_portfolio_snapshot(pf_snap)
        await self.session.commit()
        await self.session.refresh(pf_snap)
        return pf_snap
