"""
Pydantic schemas for M13.01 — Portfolio Overview.
Defines standard metric response contracts, summary cards, and aggregated responses.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class StandardMetricValue(BaseModel):
    """
    Standard metric response contract established in M13 Section 10.
    """
    metric_code: str
    metric_name: str
    value: Optional[Decimal] = None
    value_display: str
    currency: Optional[str] = None
    unit: str = "CURRENCY"  # CURRENCY, PERCENTAGE, RATIO, COUNT
    as_of: datetime
    retrieved_at: datetime
    quality_status: str = "FRESH"  # FRESH, STALE, DELAYED, PARTIAL, MISSING, INVALID, NOT_AVAILABLE
    source_module: str
    calculation_basis: str
    is_negative: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PortfolioMetadataContext(BaseModel):
    portfolio_id: str
    portfolio_name: str
    portfolio_type: str
    base_currency: str
    status: str
    benchmark: Optional[str] = None
    strategy: Optional[str] = None
    owner: Optional[str] = None
    inception_date: Optional[datetime] = None


class DataFreshnessSummary(BaseModel):
    overall_status: str = "FRESH"  # FRESH, DELAYED, STALE, PARTIAL
    last_portfolio_snapshot_at: Optional[datetime] = None
    last_valuation_at: Optional[datetime] = None
    last_pnl_calculation_at: Optional[datetime] = None
    last_exposure_calculation_at: Optional[datetime] = None
    last_market_data_update_at: Optional[datetime] = None
    market_data_source: str = "ALPHA_VANTAGE_SIMULATOR"
    latency_seconds: Optional[float] = None
    is_stale: bool = False
    stale_reason: Optional[str] = None


class ExposureSummaryDetail(BaseModel):
    gross_exposure: StandardMetricValue
    net_exposure: StandardMetricValue
    long_exposure: StandardMetricValue
    short_exposure: StandardMetricValue
    gross_exposure_pct_nav: Optional[StandardMetricValue] = None
    net_exposure_pct_nav: Optional[StandardMetricValue] = None
    directional_status: str = "NET_LONG"  # NET_LONG, NET_SHORT, NEUTRAL, NOT_AVAILABLE
    directional_description: str


class NavTrendPoint(BaseModel):
    timestamp: datetime
    nav: Decimal
    currency: str


class PnlTrendPoint(BaseModel):
    timestamp: datetime
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal
    currency: str


class PortfolioOverviewResponse(BaseModel):
    """
    Complete consolidated response for M13.01 Portfolio Overview.
    Aggregates M05 (Valuation, P&L), M06 (Exposure), and M02/M03 (Freshness).
    """
    portfolio: PortfolioMetadataContext
    freshness: DataFreshnessSummary
    
    # Core Overview KPIs
    total_nav: StandardMetricValue
    intraday_pnl: StandardMetricValue
    intraday_pnl_pct: Optional[StandardMetricValue] = None
    unrealized_pnl: StandardMetricValue
    realized_pnl: StandardMetricValue
    total_pnl: StandardMetricValue
    
    # Exposures
    exposure: ExposureSummaryDetail
    
    # Historical Visualization Trends
    nav_trend: List[NavTrendPoint] = Field(default_factory=list)
    pnl_trend: List[PnlTrendPoint] = Field(default_factory=list)
    
    # Table Summary Rows
    summary_table_rows: List[StandardMetricValue] = Field(default_factory=list)
    
    generated_at: datetime
