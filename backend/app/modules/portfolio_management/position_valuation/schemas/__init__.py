"""Pydantic 2.x Schemas for M05.03 - Position Valuation."""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

from backend.app.modules.portfolio_management.position_management.models import PositionSide
from backend.app.modules.portfolio_management.position_valuation.models import (
    ValuationStatus,
    MarkPriceType,
    AccountingMethod,
    LotStatus,
)


class PositionValuationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    valuation_id: str
    calculation_id: str
    portfolio_id: str
    account_id: str
    instrument_id: str
    listing_id: Optional[str] = None
    position_side: PositionSide
    signed_quantity: Decimal
    mark_price: Decimal
    mark_price_type: MarkPriceType
    price_currency: str
    fx_rate_to_base: Decimal
    signed_market_value_native: Decimal
    signed_market_value_base: Decimal
    signed_cost_basis_native: Decimal
    signed_cost_basis_base: Decimal
    unrealized_pnl_native: Decimal
    unrealized_pnl_base: Decimal
    unrealized_pnl_pct: Optional[Decimal] = None
    valuation_status: ValuationStatus
    effective_at: datetime
    calculated_at: datetime


class PortfolioValuationSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    snapshot_id: str
    calculation_id: str
    portfolio_id: str
    base_currency: str
    gross_long_market_value: Decimal
    gross_short_market_value: Decimal
    net_market_value: Decimal
    total_cost_basis: Decimal
    total_unrealized_pnl: Decimal
    realized_pnl_period: Decimal
    valued_position_count: int
    unavailable_position_count: int
    valuation_status: ValuationStatus
    valuation_timestamp: datetime
    created_at: datetime


class CostBasisLotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    lot_id: str
    portfolio_id: str
    account_id: str
    instrument_id: str
    listing_id: Optional[str] = None
    position_side: PositionSide
    opening_position_event_id: Optional[str] = None
    opening_effective_at: datetime
    original_quantity: Decimal
    remaining_quantity: Decimal
    original_unit_price: Decimal
    original_consideration: Decimal
    currency: str
    original_fx_rate: Decimal
    remaining_basis_native: Decimal
    remaining_basis_base: Decimal
    accounting_method: AccountingMethod
    lot_status: LotStatus
    created_at: datetime


class CostBasisAllocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    allocation_id: str
    portfolio_id: str
    account_id: str
    instrument_id: str
    closing_position_event_id: str
    opening_lot_id: Optional[str] = None
    position_side: PositionSide
    closed_quantity: Decimal
    allocated_opening_basis_native: Decimal
    allocated_opening_basis_base: Decimal
    closing_consideration_native: Decimal
    closing_consideration_base: Decimal
    realized_pnl_native: Decimal
    realized_pnl_base: Decimal
    currency: str
    effective_at: datetime
    created_at: datetime


class RunValuationRequest(BaseModel):
    portfolio_id: str = Field(..., min_length=3, max_length=64)
    valuation_date: Optional[datetime] = None
    mark_prices: Optional[dict] = Field(None, description="Optional map of instrument_id -> Decimal mark price")
    fx_rates_to_base: Optional[dict] = Field(None, description="Optional map of currency -> Decimal FX rate to base")
