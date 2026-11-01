"""SQLAlchemy 2.x Models for M05.03 - Position Valuation."""
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, List
from sqlalchemy import (
    String,
    Boolean,
    Integer,
    Numeric,
    DateTime,
    Date,
    ForeignKey,
    Text,
    Enum as SAEnum,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base
from backend.app.modules.portfolio_management.position_management.models import PositionSide


class ValuationStatus(str, Enum):
    VALUED = "VALUED"
    PARTIALLY_VALUED = "PARTIALLY_VALUED"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"
    INELIGIBLE = "INELIGIBLE"
    PENDING_FX = "PENDING_FX"
    CALCULATION_ERROR = "CALCULATION_ERROR"


class MarkPriceType(str, Enum):
    OFFICIAL_CLOSE = "OFFICIAL_CLOSE"
    PREVIOUS_CLOSE = "PREVIOUS_CLOSE"
    LAST_TRADED_PRICE = "LAST_TRADED_PRICE"
    MID_PRICE = "MID_PRICE"
    BID_PRICE = "BID_PRICE"
    ASK_PRICE = "ASK_PRICE"
    AUCTION_PRICE = "AUCTION_PRICE"
    SETTLEMENT_PRICE = "SETTLEMENT_PRICE"
    MANUAL_MARK = "MANUAL_MARK"


class AccountingMethod(str, Enum):
    FIFO = "FIFO"
    WEIGHTED_AVERAGE = "WEIGHTED_AVERAGE"
    SPECIFIC_IDENTIFICATION = "SPECIFIC_IDENTIFICATION"


class LotStatus(str, Enum):
    OPEN = "OPEN"
    PARTIALLY_CLOSED = "PARTIALLY_CLOSED"
    CLOSED = "CLOSED"


# ---------------------------------------------------------------------------
# 1. COST BASIS ACQUISITION LOTS
# ---------------------------------------------------------------------------
class CostBasisLot(Base):
    """
    Acquisition lot tracking for FIFO, Weighted Average, and Specific Identification.
    Supports both Long acquisition costs and Short opening proceeds basis.
    """
    __tablename__ = "m05_cost_basis_lots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lot_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    position_side: Mapped[PositionSide] = mapped_column(
        SAEnum(PositionSide, native_enum=False), nullable=False
    )
    
    opening_position_event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    opening_effective_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    
    # Quantities: stored as positive magnitude
    original_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    remaining_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    
    original_unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    original_consideration: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    
    # Base currency conversions
    original_fx_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1.0"), nullable=False)
    remaining_basis_native: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    remaining_basis_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    
    allocated_costs: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    accounting_method: Mapped[AccountingMethod] = mapped_column(
        SAEnum(AccountingMethod, native_enum=False), default=AccountingMethod.FIFO, nullable=False
    )
    lot_status: Mapped[LotStatus] = mapped_column(
        SAEnum(LotStatus, native_enum=False), default=LotStatus.OPEN, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    allocations: Mapped[List["CostBasisAllocation"]] = relationship(
        "CostBasisAllocation", back_populates="lot", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# 2. COST BASIS ALLOCATIONS (CLOSING REALIZATIONS)
# ---------------------------------------------------------------------------
class CostBasisAllocation(Base):
    """
    Allocates closing sales or covers against opening acquisition lots.
    """
    __tablename__ = "m05_cost_basis_allocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    allocation_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    closing_position_event_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    opening_lot_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("m05_cost_basis_lots.lot_id", ondelete="CASCADE"), nullable=True, index=True
    )
    position_side: Mapped[PositionSide] = mapped_column(
        SAEnum(PositionSide, native_enum=False), nullable=False
    )
    
    closed_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    allocated_opening_basis_native: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    allocated_opening_basis_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    
    closing_consideration_native: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    closing_consideration_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    
    realized_pnl_native: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    realized_pnl_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    lot: Mapped[Optional["CostBasisLot"]] = relationship("CostBasisLot", back_populates="allocations")


# ---------------------------------------------------------------------------
# 3. POSITION VALUATIONS (INDIVIDUAL HOLDINGS)
# ---------------------------------------------------------------------------
class PositionValuation(Base):
    """
    Authoritative calculated market value, cost basis, and unrealized P&L for a position.
    Strict signed conventions: Long is positive (+), Short is negative (-).
    """
    __tablename__ = "m05_position_valuations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    valuation_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    calculation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    position_side: Mapped[PositionSide] = mapped_column(
        SAEnum(PositionSide, native_enum=False), nullable=False
    )
    
    # Signed Quantity
    signed_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    
    # Mark Price
    mark_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    mark_price_type: Mapped[MarkPriceType] = mapped_column(
        SAEnum(MarkPriceType, native_enum=False), default=MarkPriceType.OFFICIAL_CLOSE, nullable=False
    )
    price_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    fx_rate_to_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1.0"), nullable=False)
    
    # Signed Market Value (+ for Long, - for Short)
    signed_market_value_native: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    signed_market_value_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    
    # Signed Cost Basis (+ for Long, - for Short)
    signed_cost_basis_native: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    signed_cost_basis_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    
    # Unrealized P&L = Signed Market Value - Signed Cost Basis
    unrealized_pnl_native: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unrealized_pnl_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unrealized_pnl_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    
    valuation_status: Mapped[ValuationStatus] = mapped_column(
        SAEnum(ValuationStatus, native_enum=False), default=ValuationStatus.VALUED, nullable=False
    )
    effective_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


# ---------------------------------------------------------------------------
# 4. PORTFOLIO VALUATION SNAPSHOTS (AGGREGATE)
# ---------------------------------------------------------------------------
class PortfolioValuationSnapshot(Base):
    """
    Portfolio-level aggregated valuation preserving gross long and gross short market values.
    """
    __tablename__ = "m05_portfolio_valuation_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    calculation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    
    # Gross & Net Market Values in Base Currency
    gross_long_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    gross_short_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    net_market_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    
    total_cost_basis: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    total_unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    realized_pnl_period: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0.0"), nullable=False)
    
    valued_position_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unavailable_position_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    valuation_status: Mapped[ValuationStatus] = mapped_column(
        SAEnum(ValuationStatus, native_enum=False), default=ValuationStatus.VALUED, nullable=False
    )
    valuation_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
