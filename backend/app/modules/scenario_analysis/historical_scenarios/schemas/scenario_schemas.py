"""
Historical Scenarios Pydantic Schemas (M10.01).
Strict validation using Pydantic 2.x and ConfigDict.
"""

from pydantic import BaseModel, ConfigDict, Field
from decimal import Decimal
from typing import List, Optional, Dict, Any
from datetime import datetime


class HistoricalEventCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_code: str = Field(..., max_length=100)
    event_name: str = Field(..., max_length=150)
    description: Optional[str] = Field(None, max_length=255)
    category: str = Field(default="CRISIS", max_length=50)
    tags: Optional[str] = Field(None, max_length=255)
    global_scope: bool = Field(default=True)
    affected_regions: str = Field(default="GLOBAL", max_length=100)
    affected_markets: str = Field(default="ALL", max_length=100)
    start_date: datetime
    end_date: datetime
    reference_timezone: str = Field(default="UTC", max_length=50)
    primary_reference_index: Optional[str] = Field(None, max_length=50)
    event_narrative: Optional[str] = None
    data_coverage_status: str = Field(default="ADEQUATE", max_length=50)
    current_version: str = Field(default="1.0.0", max_length=20)


class HistoricalEventResponse(HistoricalEventCreate):
    id: str
    event_status: str
    created_at: datetime
    updated_at: datetime
    created_by: str


class HistoricalObservationInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: Optional[str] = None
    listing_id: Optional[str] = None
    factor_id: Optional[str] = None
    observation_date: datetime
    observation_timestamp: datetime
    reference_price: Optional[Decimal] = None
    adjusted_price: Optional[Decimal] = None
    return_value: Decimal
    return_type: str = Field(default="TOTAL_RETURN")
    currency: str = Field(default="USD")
    quality_status: str = Field(default="VALID")


class PortfolioPositionInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    listing_id: str
    signed_quantity: Decimal
    baseline_price: Decimal = Field(..., gt=0)
    currency: str = Field(default="USD")
    sector: Optional[str] = None
    factor_sensitivities: Optional[Dict[str, Decimal]] = None


class ReplayExecutionRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str
    event_id: str
    portfolio_snapshot_id: Optional[str] = None
    replay_mode: str = Field(default="CURRENT_PORTFOLIO") # CURRENT_PORTFOLIO, HISTORICAL_SNAPSHOT, ACTUAL_HISTORICAL_PERIOD
    return_definition: str = Field(default="TOTAL_RETURN")
    base_currency: str = Field(default="USD")
    missing_data_policy: str = Field(default="STRICT") # STRICT, EXCLUDE_UNMAPPED, APPROVED_PROXY_ONLY, PARTIAL
    valuation_baseline: str = Field(default="PRE_EVENT_CLOSE")
    baseline_nav: Decimal = Field(..., gt=0)
    positions: List[PortfolioPositionInput] = Field(..., min_length=1)
    
    # Optional mappings and overrides
    manual_proxy_mappings: Optional[Dict[str, str]] = None # instrument_id -> proxy_instrument_id
    manual_overrides: Optional[Dict[str, Decimal]] = None # instrument_id -> user_specified_return
    excluded_instrument_ids: Optional[List[str]] = None
    
    # Currency FX shocks for cross-currency holdings (currency -> fx_return)
    fx_shocks: Optional[Dict[str, Decimal]] = None
    include_daily_path: bool = Field(default=False)


class PositionReplayResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    listing_id: str
    signed_quantity: Decimal
    baseline_price: Decimal
    baseline_market_value: Decimal
    local_currency: str
    local_return: Decimal
    fx_return: Decimal
    base_currency_return: Decimal
    scenario_price: Decimal
    scenario_market_value: Decimal
    scenario_pnl: Decimal
    portfolio_weight: Decimal
    portfolio_contribution: Decimal
    mapping_method: str
    mapping_status: str
    quality_status: str
    is_excluded: bool = False
    exclusion_reason: Optional[str] = None


class ReplayWarningResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    warning_code: str
    severity: str # INFO, WARNING, HIGH, CRITICAL
    warning_category: str
    message: str
    details_json: Optional[str] = None


class ReplayPathPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    observation_date: datetime
    scenario_nav: Decimal
    scenario_pnl: Decimal
    scenario_return: Decimal


class ReplayRunSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    replay_id: str
    replay_code: str
    portfolio_id: str
    scenario_event_id: str
    replay_mode: str
    base_currency: str
    replay_status: str
    baseline_nav: Decimal
    scenario_nav: Decimal
    scenario_pnl: Decimal
    scenario_return: Decimal
    direct_coverage: Decimal
    proxy_coverage: Decimal
    factor_coverage: Decimal
    unmapped_coverage: Decimal
    included_count: int
    excluded_count: int
    warnings: List[ReplayWarningResponse]
    positions: List[PositionReplayResponse]
    daily_path: Optional[List[ReplayPathPoint]] = None
    caveat_summary: str


class HistoricalDifferenceReport(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    holdings_overlap_count: int
    new_holdings_count: int
    delisted_or_missing_holdings_count: int
    tested_top_holding: str
    historical_top_holding: Optional[str] = None
    sector_weight_differences: Dict[str, Decimal]
    mandatory_caveat: str
