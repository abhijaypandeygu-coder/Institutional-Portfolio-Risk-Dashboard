"""
Pydantic schemas for M13.02 — Risk Overview.

Defines presentation-layer standard metric contracts, methodology descriptors,
historical trend points, comparisons, and consolidated dashboard response payloads
for Value at Risk (VaR), Expected Shortfall (ES), Volatility, and Drawdown.
Strictly follows Part B Section 10 & 14: authoritative risk calculations reside in M07.
"""

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class MetricState(str, Enum):
    VALID = "VALID"
    STALE = "STALE"
    INCOMPLETE = "INCOMPLETE"
    INVALID = "INVALID"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    PENDING = "PENDING"
    ERROR = "ERROR"


class MetricUnit(str, Enum):
    CURRENCY = "CURRENCY"
    PERCENTAGE = "PERCENTAGE"
    RATIO = "RATIO"
    DAYS = "DAYS"
    COUNT = "COUNT"


class VaRMethodologyType(str, Enum):
    HISTORICAL_SIMULATION = "HISTORICAL_SIMULATION"
    PARAMETRIC = "PARAMETRIC"
    MONTE_CARLO = "MONTE_CARLO"


class VolatilityType(str, Enum):
    REALIZED = "REALIZED"
    FORECAST = "FORECAST"


# ---------------------------------------------------------------------------
# Methodology Panels Metadata
# ---------------------------------------------------------------------------

class VaRMethodologyDetails(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    method: str = Field(..., description="Calculation method name")
    return_definition: str = Field("LOGARITHMIC", description="Return definition used")
    confidence_level: Decimal = Field(..., description="Confidence level (e.g. 0.99 for 99%)")
    horizon_days: int = Field(1, description="Holding horizon in trading days")
    horizon_label: str = Field("1 trading day", description="Readable horizon label")
    lookback_window: int = Field(..., description="Lookback window in days")
    observation_frequency: str = Field("DAILY", description="Return observation frequency")
    valuation_base_type: str = Field("PORTFOLIO_NAV", description="Valuation basis")
    distribution_assumption: Optional[str] = Field(None, description="Parametric distribution assumption")
    model_version: str = Field("1.0", description="M07 Model version")
    calculation_timestamp: datetime = Field(..., description="Timestamp of M07 calculation")
    assumptions_summary: str = Field(..., description="Summary of key model assumptions")


class ESMethodologyDetails(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    method: str = Field(..., description="Tail loss calculation method")
    confidence_level: Decimal = Field(..., description="Confidence level matching VaR")
    horizon_days: int = Field(1, description="Holding horizon in trading days")
    horizon_label: str = Field("1 trading day", description="Readable horizon label")
    tail_definition: str = Field("E[L | L >= VaR]", description="Tail expectation mathematical formulation")
    tail_weighting_method: str = Field("EQUAL_WEIGHTED", description="Weighting of tail observations")
    observation_frequency: str = Field("DAILY", description="Return frequency")
    estimation_window: int = Field(..., description="Lookback estimation window in days")
    model_version: str = Field("1.0", description="M07 Model version")
    calculation_timestamp: datetime = Field(..., description="Calculation timestamp")


class VolatilityMethodologyDetails(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    volatility_type: VolatilityType = Field(..., description="REALIZED or FORECAST")
    calculation_method: str = Field(..., description="Estimator or forecast model")
    return_frequency: str = Field("DAILY", description="Return frequency")
    lookback_window: int = Field(..., description="Lookback window in days")
    annualization_factor: Decimal = Field(..., description="Annualization factor (e.g. sqrt(252))")
    periods_per_year: int = Field(252, description="Trading periods per year")
    sample_count: int = Field(..., description="Sample observations count")
    model_version: str = Field("1.0", description="M07 Model version")
    calculation_timestamp: datetime = Field(..., description="Calculation timestamp")


class DrawdownMethodologyDetails(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    measurement_period: str = Field(..., description="Measurement window (e.g. 1_year, ytd)")
    valuation_frequency: str = Field("DAILY", description="Valuation observation frequency")
    high_water_mark_policy: str = Field("RUNNING_PEAK", description="HWM calculation policy")
    nav_basis: str = Field("NET_ASSET_VALUE", description="Underlying series basis")
    cash_flow_adjusted: bool = Field(True, description="Whether series is cash-flow adjusted")
    calculation_timestamp: datetime = Field(..., description="Calculation timestamp")


# ---------------------------------------------------------------------------
# Primary Risk Metric Cards
# ---------------------------------------------------------------------------

class VaRMetricCard(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metric_id: str = "VAR"
    value: Optional[Decimal] = Field(None, description="VaR monetary loss amount (positive loss convention)")
    value_display: Optional[str] = Field(None, description="Formatted monetary VaR display")
    currency: str = Field("USD", description="Reporting currency")
    percentage_of_nav: Optional[Decimal] = Field(None, description="VaR as % of NAV")
    percentage_display: Optional[str] = Field(None, description="Formatted percentage of NAV")
    confidence_level: Decimal = Field(Decimal("0.99"), description="Confidence level (e.g. 0.99 for 99%)")
    confidence_display: str = Field("99%", description="Formatted confidence level")
    horizon_days: int = Field(1, description="Horizon in trading days")
    horizon_display: str = Field("1 trading day", description="Readable horizon")
    methodology: str = Field("HISTORICAL_SIMULATION", description="Calculation methodology")
    status: MetricState = Field(MetricState.VALID, description="Metric state")
    calculation_timestamp: Optional[datetime] = Field(None, description="Calculation timestamp")
    data_quality_status: str = Field("FRESH", description="Data quality classification")
    source_module: str = Field("M07.02", description="Authoritative source engine")
    methodology_details: Optional[VaRMethodologyDetails] = None


class ExpectedShortfallMetricCard(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metric_id: str = "EXPECTED_SHORTFALL"
    value: Optional[Decimal] = Field(None, description="ES monetary loss amount (average modeled tail loss)")
    value_display: Optional[str] = Field(None, description="Formatted monetary ES display")
    currency: str = Field("USD", description="Reporting currency")
    percentage_of_nav: Optional[Decimal] = Field(None, description="ES as % of NAV")
    percentage_display: Optional[str] = Field(None, description="Formatted percentage of NAV")
    confidence_level: Decimal = Field(Decimal("0.99"), description="Confidence level matching VaR")
    confidence_display: str = Field("99%", description="Formatted confidence level")
    horizon_days: int = Field(1, description="Horizon in trading days")
    horizon_display: str = Field("1 trading day", description="Readable horizon")
    methodology: str = Field("HISTORICAL_SIMULATION", description="Calculation methodology")
    status: MetricState = Field(MetricState.VALID, description="Metric state")
    calculation_timestamp: Optional[datetime] = Field(None, description="Calculation timestamp")
    data_quality_status: str = Field("FRESH", description="Data quality classification")
    source_module: str = Field("M07.03", description="Authoritative source engine")
    methodology_details: Optional[ESMethodologyDetails] = None


class VolatilityMetricCard(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metric_id: str = "VOLATILITY"
    value: Optional[Decimal] = Field(None, description="Annualized volatility percentage (e.g. 18.40)")
    value_display: Optional[str] = Field(None, description="Formatted percentage display (18.40%)")
    volatility_type: VolatilityType = Field(VolatilityType.REALIZED, description="REALIZED or FORECAST")
    is_annualized: bool = Field(True, description="Whether volatility is annualized")
    lookback_window: int = Field(60, description="Lookback window in trading days")
    return_frequency: str = Field("DAILY", description="Return frequency")
    estimator: str = Field("SAMPLE_STD_DEV", description="Estimator or forecast model")
    status: MetricState = Field(MetricState.VALID, description="Metric state")
    calculation_timestamp: Optional[datetime] = Field(None, description="Calculation timestamp")
    data_quality_status: str = Field("FRESH", description="Data quality classification")
    source_module: str = Field("M07.01", description="Authoritative source engine")
    methodology_details: Optional[VolatilityMethodologyDetails] = None


class DrawdownMetricCard(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metric_id: str = "DRAWDOWN"
    current_drawdown_pct: Optional[Decimal] = Field(None, description="Current drawdown percentage (e.g. -2.40)")
    current_drawdown_display: Optional[str] = Field(None, description="Formatted current drawdown (-2.40%)")
    current_drawdown_amount: Optional[Decimal] = Field(None, description="Monetary drawdown amount")
    current_drawdown_amount_display: Optional[str] = Field(None, description="Formatted monetary drawdown")
    maximum_drawdown_pct: Optional[Decimal] = Field(None, description="Maximum drawdown percentage (e.g. -11.80)")
    maximum_drawdown_display: Optional[str] = Field(None, description="Formatted max drawdown (-11.80%)")
    maximum_drawdown_amount: Optional[Decimal] = Field(None, description="Monetary maximum drawdown")
    high_water_mark: Optional[Decimal] = Field(None, description="Running high water mark")
    peak_date: Optional[datetime] = Field(None, description="Peak date / start of drawdown")
    trough_date: Optional[datetime] = Field(None, description="Trough date")
    recovery_status: Optional[str] = Field("RECOVERING", description="Recovery status")
    measurement_period: str = Field("1_year", description="Selected measurement lookback")
    status: MetricState = Field(MetricState.VALID, description="Metric state")
    calculation_timestamp: Optional[datetime] = Field(None, description="Calculation timestamp")
    data_quality_status: str = Field("FRESH", description="Data quality classification")
    source_module: str = Field("M07.04", description="Authoritative source engine")
    methodology_details: Optional[DrawdownMethodologyDetails] = None


# ---------------------------------------------------------------------------
# Detailed Analysis, Comparisons & Time-Series
# ---------------------------------------------------------------------------

class VaRESComparisonItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str
    reporting_currency: str
    confidence_level: Decimal
    horizon_days: int
    var_monetary_amount: Optional[Decimal]
    var_percentage_of_nav: Optional[Decimal]
    es_monetary_amount: Optional[Decimal]
    es_percentage_of_nav: Optional[Decimal]
    tail_excess_amount: Optional[Decimal]
    tail_excess_pct: Optional[Decimal]
    es_to_var_ratio: Optional[Decimal]
    is_compatible: bool = Field(True, description="Whether VaR and ES configurations match")
    compatibility_note: Optional[str] = None


class HistoricalTrendPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    observation_date: date
    value: Decimal
    percentage: Optional[Decimal] = None
    currency: Optional[str] = None
    methodology: Optional[str] = None
    confidence_level: Optional[Decimal] = None
    horizon_days: Optional[int] = None
    status: MetricState = MetricState.VALID


class UnderwaterChartPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    observation_date: date
    portfolio_nav: Decimal
    high_water_mark: Decimal
    drawdown_pct: Decimal
    drawdown_amount: Decimal
    is_peak: bool = False
    is_trough: bool = False
    is_recovered: bool = False
    episode_id: Optional[str] = None


class DrawdownEpisodeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    episode_id: str
    peak_date: datetime
    trough_date: Optional[datetime] = None
    recovery_date: Optional[datetime] = None
    peak_value: Decimal
    trough_value: Optional[Decimal] = None
    max_decline_pct: Decimal
    underwater_duration_days: Optional[int] = None
    recovery_duration_days: Optional[int] = None
    status: str = Field("RECOVERING", description="RECOVERED, RECOVERING, or TROUGH_SEEKING")


class DataQualitySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    overall_status: MetricState = MetricState.VALID
    last_valuation_timestamp: Optional[datetime] = None
    last_risk_run_timestamp: Optional[datetime] = None
    stale_metrics: List[str] = Field(default_factory=list)
    failed_metrics: List[str] = Field(default_factory=list)
    quality_notes: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Consolidated Risk Overview Payload
# ---------------------------------------------------------------------------

class RiskOverviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str
    portfolio_name: str
    base_currency: str
    as_of: datetime
    generated_at: datetime
    valuation_nav: Optional[Decimal] = None

    # Primary KPI Cards
    var: VaRMetricCard
    expected_shortfall: ExpectedShortfallMetricCard
    volatility: VolatilityMetricCard
    drawdown: DrawdownMetricCard

    # Comparison & Diagnostics
    var_es_comparison: Optional[VaRESComparisonItem] = None
    quality_summary: DataQualitySummary

    # Available UI selectors
    available_confidence_levels: List[Decimal] = Field(
        default_factory=lambda: [Decimal("0.90"), Decimal("0.95"), Decimal("0.975"), Decimal("0.99"), Decimal("0.995")]
    )
    available_horizons_days: List[int] = Field(default_factory=lambda: [1, 5, 10])
    available_var_methodologies: List[str] = Field(
        default_factory=lambda: ["HISTORICAL_SIMULATION", "PARAMETRIC", "MONTE_CARLO"]
    )
    available_volatility_lookbacks: List[int] = Field(default_factory=lambda: [20, 60, 90, 252])
    available_drawdown_periods: List[str] = Field(
        default_factory=lambda: ["1_month", "3_months", "6_months", "1_year", "ytd", "all"]
    )


# ---------------------------------------------------------------------------
# Historical Response Payloads
# ---------------------------------------------------------------------------

class RiskHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str
    metric: str
    reporting_currency: str
    points: List[HistoricalTrendPoint] = Field(default_factory=list)
    underwater_points: Optional[List[UnderwaterChartPoint]] = None
    episodes: Optional[List[DrawdownEpisodeSummary]] = None
