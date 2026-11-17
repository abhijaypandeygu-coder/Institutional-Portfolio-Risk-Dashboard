"""
Pydantic schemas for M13.03 — Exposure Dashboard.

Defines presentation-layer contracts for:
1. Sector Allocation (M06.03, M04.02)
2. Instrument Allocation & Ranked Holdings (M06.04, M04.01)
3. Portfolio Capital Allocation & Cash Composition (M06.07, M05.03, M05.04)
4. Hierarchical Drill-Down (Portfolio -> Sector -> Industry -> Security)

Strictly adheres to Part B Section 3: NO financial calculations are duplicated here.
"""

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class PositionSideFilter(str, Enum):
    ALL = "ALL"
    LONG = "LONG"
    SHORT = "SHORT"


class HierarchyLevel(str, Enum):
    PORTFOLIO = "PORTFOLIO"
    SECTOR = "SECTOR"
    INDUSTRY = "INDUSTRY"
    INSTRUMENT = "INSTRUMENT"


# ---------------------------------------------------------------------------
# M13.03.01 — Sector Allocation Models
# ---------------------------------------------------------------------------

class SectorAllocationRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sector_id: str
    sector_name: str
    classification_scheme: str = Field("GICS", description="Classification standard (e.g. GICS, ICB)")
    reporting_currency: str
    net_market_value: Decimal
    long_market_value: Decimal
    short_market_value: Decimal
    gross_market_value: Decimal
    nav_weight_pct: Optional[Decimal] = Field(None, description="Sector net NAV weight percentage (e.g. 25.00 for 25%)")
    gross_weight_pct: Optional[Decimal] = Field(None, description="Sector gross exposure percentage of NAV")
    instrument_count: int
    is_unclassified: bool = False
    data_quality_status: str = "FRESH"


class SectorAllocationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str
    as_of: datetime
    reporting_currency: str
    total_sectors_count: int
    total_long_exposure: Decimal
    total_short_exposure: Decimal
    total_net_exposure: Decimal
    total_gross_exposure: Decimal
    unclassified_exposure: Optional[Decimal] = None
    sectors: List[SectorAllocationRow] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# M13.03.02 — Instrument Allocation Models
# ---------------------------------------------------------------------------

class RankedHoldingItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rank: int
    instrument_id: str
    symbol: str
    instrument_name: str
    exchange_code: str
    position_side: str = Field(..., description="LONG or SHORT")
    quantity: Decimal
    mark_price: Decimal
    price_currency: str
    market_value: Decimal = Field(..., description="Signed market value native/base")
    absolute_market_value: Decimal = Field(..., description="Absolute market value magnitude")
    nav_weight_pct: Optional[Decimal] = Field(None, description="NAV weight percentage")
    gross_weight_pct: Optional[Decimal] = Field(None, description="Gross weight percentage")
    sector_name: Optional[str] = None
    industry_name: Optional[str] = None
    valuation_timestamp: datetime
    valuation_status: str = "FRESH"


class InstrumentAllocationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str
    as_of: datetime
    reporting_currency: str
    total_instruments_count: int
    long_instruments_count: int
    short_instruments_count: int
    total_long_market_value: Decimal
    total_short_market_value: Decimal
    total_net_market_value: Decimal
    total_gross_market_value: Decimal
    top_long_holdings: List[RankedHoldingItem] = Field(default_factory=list)
    top_short_holdings: List[RankedHoldingItem] = Field(default_factory=list)
    all_ranked_holdings: List[RankedHoldingItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# M13.03.03 — Portfolio Capital & Cash Allocation Models
# ---------------------------------------------------------------------------

class CashBalanceDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account_id: str
    currency: str
    settled_balance: Decimal
    available_balance: Decimal
    restricted_balance: Decimal
    base_equivalent: Decimal
    fx_rate_to_base: Decimal = Decimal("1.0")


class PortfolioAllocationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str
    as_of: datetime
    reporting_currency: str
    total_nav: Decimal
    total_long_position_value: Decimal
    total_short_position_value: Decimal
    net_position_value: Decimal
    gross_position_exposure: Decimal
    total_cash_value: Decimal
    available_cash_value: Decimal
    restricted_cash_value: Decimal
    invested_nav_weight_pct: Decimal
    cash_nav_weight_pct: Decimal
    gross_exposure_to_nav_ratio: Decimal
    reconciliation_residual: Decimal = Decimal("0.0")
    reconciliation_status: str = "RECONCILED"
    cash_balances: List[CashBalanceDetail] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# M13.03.04 — Drill-Down & Hierarchy Models
# ---------------------------------------------------------------------------

class HierarchyBreadcrumb(BaseModel):
    level: HierarchyLevel
    id: str
    name: str


class ExposureDrillDownResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str
    as_of: datetime
    current_level: HierarchyLevel
    breadcrumbs: List[HierarchyBreadcrumb] = Field(default_factory=list)
    reporting_currency: str
    level_name: str
    market_value: Decimal
    nav_weight_pct: Optional[Decimal] = None
    long_exposure: Decimal
    short_exposure: Decimal
    net_exposure: Decimal
    gross_exposure: Decimal
    sub_items: List[Dict[str, Any]] = Field(default_factory=list)
    holdings: List[RankedHoldingItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Consolidated Exposure Dashboard Response
# ---------------------------------------------------------------------------

class ConsolidatedExposureDashboardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str
    portfolio_name: str
    base_currency: str
    as_of: datetime
    generated_at: datetime

    # Summary Cards & Components
    allocation_summary: PortfolioAllocationSummary
    sector_summary: SectorAllocationSummary
    instrument_summary: InstrumentAllocationSummary

    # Data Quality & Freshness Context
    overall_quality_status: str = "FRESH"
    valuation_timestamp: datetime
    snapshot_id: Optional[str] = None
    data_quality_notes: List[str] = Field(default_factory=list)
