"""
M13.09 - Historical Analytics Pydantic Schemas.
Institutional data contracts for time series observations, risk trends, event overlays,
point-in-time state reconstruction, provenance manifests, version comparisons, and user preferences.
"""

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class HistoricalMode(str, Enum):
    AS_KNOWN_AT_TIME = "AS_KNOWN_AT_TIME"
    LATEST_RESTATED = "LATEST_RESTATED"
    EFFECTIVE_DATE = "EFFECTIVE_DATE"


class ConsistencyStatus(str, Enum):
    CONSISTENT = "CONSISTENT"
    PARTIALLY_CONSISTENT = "PARTIALLY_CONSISTENT"
    RESTATED = "RESTATED"
    INCOMPLETE = "INCOMPLETE"
    UNAVAILABLE = "UNAVAILABLE"


class ObservationFrequency(str, Enum):
    INTRADAY = "INTRADAY"
    HOURLY = "HOURLY"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


# -------------------------------------------------------------
# 1. Historical Observation Contracts
# -------------------------------------------------------------
class HistoricalDataPoint(BaseModel):
    """
    Standard observation contract preserving timestamps, values, units, quality, and origin.
    """
    observation_id: str
    portfolio_id: str
    metric_name: str
    effective_at: datetime
    known_at: datetime
    calculated_at: Optional[datetime] = None
    value: Optional[float] = None
    currency: Optional[str] = None
    unit: str
    frequency: str = "DAILY"
    source_module: str
    source_record_id: Optional[str] = None
    model_version: Optional[str] = None
    dataset_version: Optional[str] = None
    quality_status: str = "VALID"
    is_restated: bool = False
    metadata: Optional[Dict[str, Any]] = None


class HistoricalPortfolioValueResponse(BaseModel):
    portfolio_id: str
    metric: str
    currency: str
    frequency: str
    historical_mode: HistoricalMode
    start_time: datetime
    end_time: datetime
    observations: List[HistoricalDataPoint]
    summary_kpis: Dict[str, Any]
    downsampled: bool = False
    total_raw_observations: int = 0


class HistoricalPnLResponse(BaseModel):
    portfolio_id: str
    pnl_type: str # DAILY, CUMULATIVE, REALIZED, UNREALIZED
    currency: str
    frequency: str
    historical_mode: HistoricalMode
    observations: List[HistoricalDataPoint]
    summary_kpis: Dict[str, Any]


class HistoricalRiskTrendResponse(BaseModel):
    portfolio_id: str
    metric: str # VAR, ES, VOLATILITY, DRAWDOWN
    currency: Optional[str] = None
    unit: str
    frequency: str
    historical_mode: HistoricalMode
    observations: List[HistoricalDataPoint]
    summary_statistics: Dict[str, Any]


class HistoricalExposureResponse(BaseModel):
    portfolio_id: str
    exposure_type: str # GROSS, NET, LONG, SHORT
    currency: str
    unit: str
    observations: List[HistoricalDataPoint]
    summary_statistics: Dict[str, Any]


# -------------------------------------------------------------
# 2. Event Overlay Contracts
# -------------------------------------------------------------
class EventOverlayItem(BaseModel):
    event_id: str
    event_category: str # ALERT, BREACH, TRADE, CASH_MOVEMENT, SCENARIO, CORPORATE_ACTION
    event_title: str
    event_description: Optional[str] = None
    portfolio_id: Optional[str] = None
    instrument_id: Optional[str] = None
    occurrence_time: datetime
    detection_time: Optional[datetime] = None
    severity: Optional[str] = None
    priority_score: Optional[float] = None
    source_module: str
    source_record_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class HistoricalEventsResponse(BaseModel):
    portfolio_id: Optional[str] = None
    events: List[EventOverlayItem]
    total_count: int
    page: int
    page_size: int


# -------------------------------------------------------------
# 3. Point-in-Time Reconstruction & Provenance
# -------------------------------------------------------------
class PointInTimePositionHolding(BaseModel):
    instrument_id: str
    instrument_name: Optional[str] = None
    signed_quantity: float
    market_price: Optional[float] = None
    market_value_base: float
    cost_basis_base: float
    unrealized_pnl_base: float
    currency: str


class PointInTimeCashBalance(BaseModel):
    currency: str
    settled_cash: float
    available_cash: float
    available_cash_base: float


class PointInTimeRiskMetrics(BaseModel):
    var_95_1d: Optional[float] = None
    var_99_1d: Optional[float] = None
    expected_shortfall: Optional[float] = None
    realized_volatility_annualized: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    gross_exposure_pct: Optional[float] = None
    net_exposure_pct: Optional[float] = None
    model_version: Optional[str] = None
    calculation_timestamp: Optional[datetime] = None


class ProvenanceManifestResponse(BaseModel):
    manifest_id: str
    portfolio_id: str
    selected_effective_at: datetime
    selected_knowledge_at: datetime
    historical_mode: HistoricalMode
    position_snapshot_id: Optional[str] = None
    valuation_record_id: Optional[str] = None
    risk_calculation_ids: List[str] = Field(default_factory=list)
    market_data_watermark: Optional[str] = None
    reference_data_version: Optional[str] = None
    model_versions: Dict[str, str] = Field(default_factory=dict)
    source_modules: List[str] = Field(default_factory=list)
    consistency_status: ConsistencyStatus
    consistency_notes: Optional[str] = None
    created_at: datetime


class PointInTimeStateResponse(BaseModel):
    portfolio_id: str
    effective_at: datetime
    known_at: datetime
    historical_mode: HistoricalMode
    base_currency: str
    total_nav_base: float
    total_market_value_base: float
    total_cash_value_base: float
    total_unrealized_pnl_base: float
    positions: List[PointInTimePositionHolding] = Field(default_factory=list)
    cash_balances: List[PointInTimeCashBalance] = Field(default_factory=list)
    risk_metrics: Optional[PointInTimeRiskMetrics] = None
    recent_events: List[EventOverlayItem] = Field(default_factory=list)
    manifest: ProvenanceManifestResponse


# -------------------------------------------------------------
# 4. Version Comparison
# -------------------------------------------------------------
class HistoricalVersionComparisonResponse(BaseModel):
    portfolio_id: str
    metric: str
    effective_at: datetime
    version_a_label: str
    version_a_value: Optional[float] = None
    version_a_timestamp: Optional[datetime] = None
    version_a_model_version: Optional[str] = None
    version_b_label: str
    version_b_value: Optional[float] = None
    version_b_timestamp: Optional[datetime] = None
    version_b_model_version: Optional[str] = None
    absolute_difference: Optional[float] = None
    percentage_difference: Optional[float] = None
    restatement_reason: Optional[str] = None
    is_compatible: bool = True
    compatibility_warning: Optional[str] = None


# -------------------------------------------------------------
# 5. Preferences & Saved Views
# -------------------------------------------------------------
class HistoricalPreferenceResponse(BaseModel):
    id: str
    user_id: str
    dashboard_name: str
    default_portfolio_id: Optional[str] = None
    default_lookback_days: int
    default_frequency: str
    default_historical_mode: str
    default_timezone: str
    enabled_event_overlays: List[str]
    downsample_threshold: int
    created_at: datetime
    updated_at: datetime


class HistoricalPreferenceUpdate(BaseModel):
    default_portfolio_id: Optional[str] = None
    default_lookback_days: Optional[int] = None
    default_frequency: Optional[str] = None
    default_historical_mode: Optional[str] = None
    default_timezone: Optional[str] = None
    enabled_event_overlays: Optional[List[str]] = None
    downsample_threshold: Optional[int] = None


class HistoricalSavedViewResponse(BaseModel):
    id: str
    user_id: str
    view_name: str
    description: Optional[str] = None
    portfolio_ids: List[str]
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    frequency: str
    historical_mode: str
    selected_metrics: List[str]
    event_overlay_filters: Optional[Dict[str, Any]] = None
    is_public: bool
    created_at: datetime
    updated_at: datetime


class HistoricalSavedViewCreate(BaseModel):
    view_name: str
    description: Optional[str] = None
    portfolio_ids: List[str]
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    frequency: str = "DAILY"
    historical_mode: str = "AS_KNOWN_AT_TIME"
    selected_metrics: List[str] = Field(default_factory=lambda: ["NAV", "DAILY_PNL", "VAR_99_1D"])
    event_overlay_filters: Optional[Dict[str, Any]] = None
    is_public: bool = False
