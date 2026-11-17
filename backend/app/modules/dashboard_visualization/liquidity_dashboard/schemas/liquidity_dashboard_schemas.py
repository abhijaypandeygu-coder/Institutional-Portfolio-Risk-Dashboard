"""
Pydantic schemas for M13.06 — Liquidity Dashboard.

Provides robust institutional data contracts for:
1. Spread visualization (absolute, relative, bps, quotes, historical trend)
2. Order-book depth visualization (ladders, cumulative depth, imbalance)
3. Composite liquidity scoring & component breakdowns
4. Position liquidation modeling (partial & full, long vs short, cost bps, horizon)
5. Portfolio-level liquidity summaries & concentration
6. Preferences, Saved Views, and Investigation Workflows
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# ---------------------------------------------------------------------------
# 1. Spread Schemas
# ---------------------------------------------------------------------------
class CurrentQuoteItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    symbol: str
    best_bid: Optional[Decimal] = None
    best_ask: Optional[Decimal] = None
    mid_price: Optional[Decimal] = None
    spread_abs: Optional[Decimal] = None
    spread_rel: Optional[Decimal] = None
    spread_bps: Optional[Decimal] = None
    spread_in_ticks: Optional[Decimal] = None
    tick_size: Optional[Decimal] = None
    quote_condition: str = "NORMAL"  # NORMAL, WIDE, LOCKED, CROSSED, ONE_SIDED, STALE, UNAVAILABLE
    bid_timestamp: Optional[datetime] = None
    ask_timestamp: Optional[datetime] = None
    observation_timestamp: Optional[datetime] = None
    venue: Optional[str] = "PRIMARY"


class HistoricalSpreadPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    spread_bps: Optional[Decimal] = None
    spread_abs: Optional[Decimal] = None
    relative_spread: Optional[Decimal] = None
    is_anomaly: bool = False


class InstrumentSpreadDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    symbol: str
    current_quote: CurrentQuoteItem
    avg_spread_bps_30d: Optional[Decimal] = None
    min_spread_bps_30d: Optional[Decimal] = None
    max_spread_bps_30d: Optional[Decimal] = None
    spread_percentile: Optional[Decimal] = None
    historical_series: List[HistoricalSpreadPoint] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 2. Order Book Depth Schemas
# ---------------------------------------------------------------------------
class DepthLevelItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    level_index: int  # 1 to N
    price: Decimal
    quantity: Decimal
    notional: Decimal
    distance_bps: Decimal
    order_count: Optional[int] = None


class OrderBookDepthLadder(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    symbol: str
    snapshot_timestamp: datetime
    bids: List[DepthLevelItem] = Field(default_factory=list)
    asks: List[DepthLevelItem] = Field(default_factory=list)
    total_bid_quantity: Decimal = Decimal("0")
    total_ask_quantity: Decimal = Decimal("0")
    total_bid_notional: Decimal = Decimal("0")
    total_ask_notional: Decimal = Decimal("0")
    cumulative_bid_notional: List[Decimal] = Field(default_factory=list)
    cumulative_ask_notional: List[Decimal] = Field(default_factory=list)
    depth_imbalance: Optional[Decimal] = None  # (Bid - Ask) / (Bid + Ask) [-1.0, +1.0]
    imbalance_status: str = "NEUTRAL"  # BID_HEAVY, ASK_HEAVY, NEUTRAL, BALANCED
    is_stale: bool = False


# ---------------------------------------------------------------------------
# 3. Liquidity Score Schemas
# ---------------------------------------------------------------------------
class ScoreComponentBreakdown(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str  # spread, depth, turnover, impact, slippage, resilience
    score: Decimal  # 0 to 100
    weight: Decimal  # e.g. 0.25
    weighted_score: Decimal
    raw_metric_value: Optional[Decimal] = None
    raw_metric_unit: Optional[str] = None
    status: str = "NORMAL"  # HEALTHY, ADEQUATE, WARNING, CRITICAL


class InstrumentLiquidityScore(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    symbol: str
    composite_score: Decimal  # 0 to 100
    liquidity_bucket: str  # TIER_1_HIGH, TIER_2_MODERATE, TIER_3_LOW, TIER_4_ILLIQUID
    rank: Optional[int] = None
    components: List[ScoreComponentBreakdown] = Field(default_factory=list)
    adv_shares_20d: Optional[Decimal] = None
    adtv_usd_20d: Optional[Decimal] = None
    turnover_ratio: Optional[Decimal] = None
    data_quality_coverage: Optional[Decimal] = None
    calculated_at: datetime


# ---------------------------------------------------------------------------
# 4. Liquidation Estimates Schemas
# ---------------------------------------------------------------------------
class TargetLiquidationScenario(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_percentage: Decimal  # 0.10, 0.25, 0.50, 0.75, 0.90, 1.00
    shares_to_liquidate: Decimal
    notional_value: Decimal
    liquidation_direction: str  # SELL (long liquidation) or BUY (short covering)
    order_type_assumed: str = "PASSIVE_AGGRESSIVE_HYBRID"
    participation_rate: Decimal  # e.g. 0.10 (10% of ADV)
    
    # Cost decomposition
    spread_cost_bps: Decimal
    market_impact_cost_bps: Decimal
    slippage_cost_bps: Decimal
    total_cost_bps: Decimal
    total_cost_usd: Decimal
    
    # Horizon & Execution details
    estimated_duration_minutes: Decimal
    estimated_trading_days: Decimal
    capacity_exhaustion_pct: Decimal
    risk_haircut_bps: Optional[Decimal] = None


class InstrumentLiquidationProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    symbol: str
    current_position_shares: Decimal
    current_position_notional: Decimal
    position_direction: str  # LONG, SHORT, FLAT
    liquidation_direction: str  # SELL (for LONG), BUY (for SHORT), NONE
    base_participation_rate: Decimal
    scenarios: List[TargetLiquidationScenario] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 5. Portfolio Liquidity Overview Schemas
# ---------------------------------------------------------------------------
class HoldingLiquiditySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    symbol: str
    sector: Optional[str] = "Unknown"
    position_shares: Decimal
    position_notional: Decimal
    weight_pct: Decimal
    position_direction: str
    
    spread_bps: Optional[Decimal] = None
    quote_condition: str = "NORMAL"
    composite_score: Optional[Decimal] = None
    liquidity_bucket: str = "TIER_2_MODERATE"
    depth_imbalance: Optional[Decimal] = None
    
    # 100% liquidation cost & days
    full_liquidation_cost_bps: Optional[Decimal] = None
    full_liquidation_cost_usd: Optional[Decimal] = None
    full_liquidation_days: Optional[Decimal] = None


class PortfolioLiquidityDashboardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str
    as_of_date: datetime
    total_nav: Decimal
    holdings_count: int
    
    # Aggregated metrics
    weighted_composite_score: Decimal
    weighted_spread_bps: Decimal
    total_full_liquidation_cost_usd: Decimal
    portfolio_liquidation_cost_bps: Decimal
    max_days_to_liquidate: Decimal
    
    # Concentration & Warning indicators
    low_liquidity_capital_pct: Decimal  # % in Tier 3/4
    locked_or_crossed_instruments_count: int
    severe_imbalance_count: int
    
    holdings: List[HoldingLiquiditySummary] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 6. Preferences, Saved Views, and Investigation Schemas
# ---------------------------------------------------------------------------
class PreferenceCreateRequest(BaseModel):
    dashboard_name: Optional[str] = "Default Liquidity Dashboard"
    default_portfolio_id: Optional[str] = None
    spread_unit: Optional[str] = "BPS"
    depth_levels_count: Optional[int] = 5
    default_lookback_days: Optional[int] = 30
    default_participation_rate: Optional[Decimal] = Decimal("0.10")
    default_liquidation_scenario: Optional[str] = "MODERATE"
    default_target_percentage: Optional[Decimal] = Decimal("1.00")
    display_configuration: Optional[Dict[str, Any]] = None


class PreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    dashboard_name: str
    default_portfolio_id: Optional[str]
    spread_unit: str
    depth_levels_count: int
    default_lookback_days: int
    default_participation_rate: Decimal
    default_liquidation_scenario: str
    default_target_percentage: Decimal
    display_configuration: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class SavedViewCreateRequest(BaseModel):
    view_name: str
    description: Optional[str] = None
    portfolio_id: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    selected_instrument_ids: Optional[List[str]] = None
    is_public: Optional[bool] = False


class SavedViewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    view_name: str
    description: Optional[str]
    portfolio_id: Optional[str]
    filters: Dict[str, Any]
    selected_instrument_ids: List[str]
    is_public: bool
    created_at: datetime
    updated_at: datetime


class InvestigationCreateRequest(BaseModel):
    portfolio_id: Optional[str] = None
    instrument_id: str
    investigation_type: str
    severity: Optional[str] = "MEDIUM"
    title: str
    notes: str
    metrics_snapshot: Optional[Dict[str, Any]] = None


class InvestigationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    portfolio_id: Optional[str]
    instrument_id: str
    investigation_type: str
    severity: str
    status: str
    title: str
    notes: str
    metrics_snapshot: Optional[Dict[str, Any]]
    resolved_at: Optional[datetime]
    resolved_by: Optional[str]
    created_at: datetime
    updated_at: datetime
