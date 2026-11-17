"""
Pydantic contracts and data models for M14.01 — Daily Risk Reports.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class ReportGenerationStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class OverallControlStatus(str, Enum):
    CLEAR = "CLEAR"
    WARNINGS_PRESENT = "WARNINGS_PRESENT"
    BREACHES_PRESENT = "BREACHES_PRESENT"
    CRITICAL_BREACHES_PRESENT = "CRITICAL_BREACHES_PRESENT"
    EMERGENCY_BREACHES_PRESENT = "EMERGENCY_BREACHES_PRESENT"
    DATA_INCOMPLETE = "DATA_INCOMPLETE"
    CONTROL_STATUS_UNAVAILABLE = "CONTROL_STATUS_UNAVAILABLE"


class OverallFreshnessStatus(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    DELAYED = "DELAYED"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class BreachSeverity(str, Enum):
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


class BreachLifecycleStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    MITIGATED = "MITIGATED"
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"


# -----------------------------------------------------------------------------
# 1. Configuration Contracts
# -----------------------------------------------------------------------------
class ReportMetricInclusionConfig(BaseModel):
    include_nav_and_pnl: bool = True
    include_exposure: bool = True
    include_var: bool = True
    include_expected_shortfall: bool = True
    include_volatility: bool = True
    include_drawdown: bool = True
    include_limit_breaches: bool = True
    include_freshness_manifest: bool = True
    include_methodology_manifest: bool = True


class ReportFreshnessPolicy(BaseModel):
    max_portfolio_data_age_hours: int = 24
    max_market_data_age_hours: int = 24
    max_risk_calc_age_hours: int = 24
    allow_stale_with_warning: bool = True


class ReportScheduleConfig(BaseModel):
    is_scheduled: bool = False
    schedule_cron: Optional[str] = None # E.g., '0 18 * * 1-5'
    timezone: str = "UTC"


class DailyReportConfigurationCreate(BaseModel):
    portfolio_id: str = Field(..., description="Target portfolio canonical ID")
    configuration_name: str = Field(..., min_length=1, max_length=128)
    reporting_calendar: str = Field("NSE_INDIA", description="NSE_INDIA, NYSE_US, GLOBAL")
    reporting_currency: str = Field("USD", min_length=3, max_length=8)
    valuation_cutoff_policy: str = Field("EOD_CLOSE", description="EOD_CLOSE, INTRADAY_SNAPSHOT")
    metric_inclusion_config: ReportMetricInclusionConfig = Field(default_factory=ReportMetricInclusionConfig)
    freshness_policy: ReportFreshnessPolicy = Field(default_factory=ReportFreshnessPolicy)
    schedule_config: ReportScheduleConfig = Field(default_factory=ReportScheduleConfig)


class DailyReportConfigurationUpdate(BaseModel):
    configuration_name: Optional[str] = None
    reporting_calendar: Optional[str] = None
    reporting_currency: Optional[str] = None
    valuation_cutoff_policy: Optional[str] = None
    metric_inclusion_config: Optional[ReportMetricInclusionConfig] = None
    freshness_policy: Optional[ReportFreshnessPolicy] = None
    schedule_config: Optional[ReportScheduleConfig] = None
    is_active: Optional[bool] = None


class DailyReportConfigurationResponse(BaseModel):
    id: str
    portfolio_id: str
    configuration_name: str
    reporting_calendar: str
    reporting_currency: str
    valuation_cutoff_policy: str
    report_template_version: str
    metric_inclusion_config: ReportMetricInclusionConfig
    freshness_policy: ReportFreshnessPolicy
    schedule_config: ReportScheduleConfig
    configuration_version: int
    is_active: bool
    created_by: str
    created_at: datetime
    updated_at: datetime


# -----------------------------------------------------------------------------
# 2. Structured Report Data Contracts
# -----------------------------------------------------------------------------
class ReportPortfolioContext(BaseModel):
    portfolio_id: str
    portfolio_name: str
    base_currency: str
    reporting_calendar: str
    session_context: str


class ReportPortfolioSummaryData(BaseModel):
    nav: Optional[float] = None
    market_value: Optional[float] = None
    cash_balance: Optional[float] = None
    realized_pnl: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    total_pnl: Optional[float] = None
    gross_exposure: Optional[float] = None
    net_exposure: Optional[float] = None
    long_exposure: Optional[float] = None
    short_exposure: Optional[float] = None
    invested_capital: Optional[float] = None
    cash_allocation_pct: Optional[float] = None
    currency: str = "USD"
    valuation_timestamp: Optional[datetime] = None
    valuation_completeness: str = "COMPLETE" # COMPLETE, PARTIAL, UNAVAILABLE
    source_snapshot_id: Optional[str] = None
    valuation_version: Optional[int] = None


class ReportVaRMetric(BaseModel):
    value: Optional[float] = None
    confidence_level: Optional[float] = None
    horizon_days: Optional[int] = None
    methodology: Optional[str] = None # HISTORICAL, PARAMETRIC, MONTE_CARLO
    currency: Optional[str] = None
    status: str = "FRESH" # FRESH, STALE, UNAVAILABLE


class ReportESMetric(BaseModel):
    value: Optional[float] = None
    confidence_level: Optional[float] = None
    horizon_days: Optional[int] = None
    methodology: Optional[str] = None
    tail_observation_count: Optional[int] = None
    currency: Optional[str] = None
    status: str = "FRESH"


class ReportVolatilityMetric(BaseModel):
    value: Optional[float] = None
    return_frequency: Optional[str] = None # DAILY, WEEKLY
    annualization_factor: Optional[float] = None
    lookback_window: Optional[int] = None
    designation: Optional[str] = None # HISTORICAL, FORECAST
    status: str = "FRESH"


class ReportDrawdownMetric(BaseModel):
    current_drawdown: Optional[float] = None
    maximum_drawdown: Optional[float] = None
    peak_date: Optional[date] = None
    trough_date: Optional[date] = None
    recovery_status: Optional[str] = None
    status: str = "FRESH"


class ReportRiskMetricsData(BaseModel):
    var: ReportVaRMetric = Field(default_factory=ReportVaRMetric)
    expected_shortfall: ReportESMetric = Field(default_factory=ReportESMetric)
    volatility: ReportVolatilityMetric = Field(default_factory=ReportVolatilityMetric)
    drawdown: ReportDrawdownMetric = Field(default_factory=ReportDrawdownMetric)
    calculated_at: Optional[datetime] = None
    model_versions: Dict[str, str] = Field(default_factory=dict)


class ReportLimitItem(BaseModel):
    limit_id: str
    limit_type: str # PORTFOLIO, POSITION, SECTOR, LIQUIDITY
    target_entity: str
    configured_threshold: float
    observed_value: float
    utilization_pct: Optional[float] = None
    severity: BreachSeverity
    lifecycle_status: BreachLifecycleStatus
    detected_at: datetime
    acknowledged_at: Optional[datetime] = None
    assigned_owner: Optional[str] = None
    evaluation_id: Optional[str] = None


class ReportControlStatusData(BaseModel):
    overall_status: OverallControlStatus
    total_active_warnings: int = 0
    total_active_breaches: int = 0
    total_critical_breaches: int = 0
    total_emergency_breaches: int = 0
    warnings: List[ReportLimitItem] = Field(default_factory=list)
    breaches: List[ReportLimitItem] = Field(default_factory=list)


class ReportSourceFreshnessItem(BaseModel):
    source_category: str # PORTFOLIO_VALUATION, MARKET_DATA, RISK_CALCULATIONS, LIMIT_CHECKS
    source_module: str
    source_id: Optional[str] = None
    latest_event_at: Optional[datetime] = None
    observed_age_hours: Optional[float] = None
    quality_status: str # FRESH, STALE, UNAVAILABLE


class ReportFreshnessData(BaseModel):
    overall_status: OverallFreshnessStatus
    items: List[ReportSourceFreshnessItem] = Field(default_factory=list)


# Complete Canonical Structured Daily Report
class CanonicalDailyRiskReport(BaseModel):
    report_id: str
    report_type: str = "DAILY_RISK_REPORT"
    report_schema_version: str = "1.0"
    report_version: int = 1
    portfolio: ReportPortfolioContext
    reporting_date: date
    valuation_timestamp: datetime
    generated_at: datetime
    reporting_timezone: str
    portfolio_summary: ReportPortfolioSummaryData
    risk_metrics: ReportRiskMetricsData
    control_status: ReportControlStatusData
    freshness: ReportFreshnessData
    methodology_manifest: Dict[str, str] = Field(default_factory=dict)
    source_manifest: Dict[str, str] = Field(default_factory=dict)


# -----------------------------------------------------------------------------
# 3. Report Run, Archive & Execution Contracts
# -----------------------------------------------------------------------------
class DailyReportGenerateRequest(BaseModel):
    portfolio_id: str
    report_date: date
    configuration_id: Optional[str] = None
    force_regeneration: bool = False
    regeneration_reason: Optional[str] = None


class DailyReportRunResponse(BaseModel):
    id: str
    report_configuration_id: str
    portfolio_id: str
    report_date: date
    valuation_timestamp: datetime
    generated_at: datetime
    generation_status: ReportGenerationStatus
    overall_control_status: OverallControlStatus
    overall_freshness_status: OverallFreshnessStatus
    report_version: int
    report_schema_version: str
    template_version: str
    idempotency_key: str
    error_summary: Optional[str] = None
    created_by: str


class DailyReportArtifactResponse(BaseModel):
    id: str
    report_run_id: str
    artifact_type: str # PDF, HTML, CSV
    storage_reference: str
    content_hash: str
    content_type: str
    file_size_bytes: int
    generated_at: datetime


class DailyReportVersionResponse(BaseModel):
    id: str
    portfolio_id: str
    report_date: date
    report_run_id: str
    version_number: int
    supersedes_version_id: Optional[str] = None
    version_reason: Optional[str] = None
    created_at: datetime
    created_by: str


class DailyReportIntegrityVerificationResponse(BaseModel):
    report_run_id: str
    is_valid: bool
    verified_at: datetime
    artifacts_verified: List[Dict[str, Any]]
    verification_notes: str
