"""
Pydantic schemas for M14.02 — Portfolio Performance Reports.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from backend.app.modules.reporting_attribution_audit.portfolio_performance.models.performance_report_models import (
    ReportingPeriodType,
    ReportingFrequency,
    ReturnMethodology,
    CashFlowTimingPolicy,
    BenchmarkReturnType,
    BenchmarkCurrencyPolicy,
    PerformanceDataStatus,
    ReportGenerationStatus,
)


class PerformanceReportConfigCreate(BaseModel):
    portfolio_id: str
    configuration_name: str
    reporting_period_type: ReportingPeriodType = ReportingPeriodType.MONTHLY
    custom_start_date: Optional[date] = None
    custom_end_date: Optional[date] = None
    reporting_frequency: ReportingFrequency = ReportingFrequency.DAILY
    reporting_currency: str = "USD"
    return_methodology: ReturnMethodology = ReturnMethodology.TWR
    cash_flow_timing_policy: CashFlowTimingPolicy = CashFlowTimingPolicy.VALUATION_AT_FLOW_BOUNDARY
    benchmark_id: Optional[str] = None
    benchmark_return_type: BenchmarkReturnType = BenchmarkReturnType.TOTAL_RETURN
    benchmark_currency_policy: BenchmarkCurrencyPolicy = BenchmarkCurrencyPolicy.PORTFOLIO_REPORTING_CURRENCY
    pnl_breakdown_config: Dict[str, Any] = Field(default_factory=dict)
    data_completeness_policy: Dict[str, Any] = Field(default_factory=dict)
    template_version: str = "v1.0"


class PerformanceReportConfigUpdate(BaseModel):
    configuration_name: Optional[str] = None
    reporting_period_type: Optional[ReportingPeriodType] = None
    custom_start_date: Optional[date] = None
    custom_end_date: Optional[date] = None
    reporting_frequency: Optional[ReportingFrequency] = None
    reporting_currency: Optional[str] = None
    return_methodology: Optional[ReturnMethodology] = None
    cash_flow_timing_policy: Optional[CashFlowTimingPolicy] = None
    benchmark_id: Optional[str] = None
    benchmark_return_type: Optional[BenchmarkReturnType] = None
    benchmark_currency_policy: Optional[BenchmarkCurrencyPolicy] = None
    pnl_breakdown_config: Optional[Dict[str, Any]] = None
    data_completeness_policy: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class PerformanceReportConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    portfolio_id: str
    configuration_name: str
    reporting_period_type: ReportingPeriodType
    custom_start_date: Optional[date] = None
    custom_end_date: Optional[date] = None
    reporting_frequency: ReportingFrequency
    reporting_currency: str
    return_methodology: ReturnMethodology
    cash_flow_timing_policy: CashFlowTimingPolicy
    benchmark_id: Optional[str] = None
    benchmark_return_type: BenchmarkReturnType
    benchmark_currency_policy: BenchmarkCurrencyPolicy
    pnl_breakdown_config: Dict[str, Any]
    data_completeness_policy: Dict[str, Any]
    template_version: str
    configuration_version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PerformanceReportGenerateRequest(BaseModel):
    portfolio_id: str
    configuration_id: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    reporting_period_type: Optional[ReportingPeriodType] = None
    reporting_frequency: Optional[ReportingFrequency] = None
    reporting_currency: Optional[str] = None
    return_methodology: Optional[ReturnMethodology] = None
    benchmark_id: Optional[str] = None
    force_regenerate: bool = False
    regeneration_reason: Optional[str] = None


class ReturnObservationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    observation_start: date
    observation_end: date
    beginning_value: float
    ending_value: float
    external_contributions: float
    external_withdrawals: float
    periodic_return: Optional[float] = None
    cumulative_return: Optional[float] = None
    annualized_return: Optional[float] = None
    methodology: str
    observation_status: str
    source_snapshot_id: Optional[str] = None
    calculation_metadata: Dict[str, Any] = Field(default_factory=dict)


class PnLComponentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    component_type: str
    amount: float
    currency: str
    reporting_amount: float
    source_reference: Optional[str] = None
    classification_status: str
    reconciliation_status: str


class BenchmarkObservationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    benchmark_id: str
    observation_date: date
    benchmark_level: float
    periodic_return: Optional[float] = None
    cumulative_return: Optional[float] = None
    currency: str
    return_type: str
    source_reference: Optional[str] = None
    observation_status: str


class PerformanceCaveatSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    caveat_category: str
    severity: str
    affected_start_date: Optional[date] = None
    affected_end_date: Optional[date] = None
    affected_metric: str
    explanation: str
    source_references: List[str]
    affects_completeness: bool


class PerformanceArtifactSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    artifact_type: str
    storage_reference: str
    content_hash: str
    content_type: str
    file_size: int
    content_data: Optional[str] = None
    generated_at: datetime


class PerformanceSummarySchema(BaseModel):
    period_return: Optional[float] = None
    cumulative_return: Optional[float] = None
    annualized_return: Optional[float] = None
    beginning_nav: Optional[float] = None
    ending_nav: Optional[float] = None
    total_pnl: Optional[float] = None
    realized_pnl: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    net_external_flow: Optional[float] = None
    total_contributions: Optional[float] = None
    total_withdrawals: Optional[float] = None
    benchmark_return: Optional[float] = None
    active_return_difference: Optional[float] = None
    performance_data_status: PerformanceDataStatus


class PnLBreakdownSchema(BaseModel):
    total_pnl: Optional[float] = None
    realized_pnl: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    fees: Optional[float] = None
    dividends: Optional[float] = None
    interest: Optional[float] = None
    currency_fx: Optional[float] = None
    other_pnl: Optional[float] = None
    reconciliation_status: str
    components: List[PnLComponentSchema] = Field(default_factory=list)


class CashFlowSummarySchema(BaseModel):
    total_contributions: float = 0.0
    total_withdrawals: float = 0.0
    net_external_flow: float = 0.0
    total_flow_count: int = 0
    cash_flow_timing_policy: str


class BenchmarkSummarySchema(BaseModel):
    benchmark_id: Optional[str] = None
    benchmark_name: Optional[str] = None
    benchmark_return_type: str
    period_return: Optional[float] = None
    cumulative_return: Optional[float] = None
    active_return_difference: Optional[float] = None
    currency: Optional[str] = None
    aligned_observation_count: int = 0
    unmatched_dates_count: int = 0
    alignment_status: str


class CanonicalPerformanceReport(BaseModel):
    """Complete structured presentation of an M14.02 Performance Report."""
    report_id: str
    report_type: str = "PORTFOLIO_PERFORMANCE_REPORT"
    report_schema_version: str = "1.0"
    report_version: int
    portfolio: Dict[str, Any]
    reporting_period: Dict[str, Any]
    methodology: Dict[str, Any]
    performance_summary: PerformanceSummarySchema
    pnl_breakdown: PnLBreakdownSchema
    cash_flows: CashFlowSummarySchema
    benchmark: BenchmarkSummarySchema
    return_observations: List[ReturnObservationSchema] = Field(default_factory=list)
    benchmark_observations: List[BenchmarkObservationSchema] = Field(default_factory=list)
    caveats: List[PerformanceCaveatSchema] = Field(default_factory=list)
    source_manifest: Dict[str, Any] = Field(default_factory=dict)
    artifacts: List[PerformanceArtifactSchema] = Field(default_factory=list)
    generated_at: datetime
    created_by: str


class PerformanceReportRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    configuration_id: Optional[str] = None
    portfolio_id: str
    benchmark_id: Optional[str] = None
    reporting_start_date: date
    reporting_end_date: date
    generated_at: datetime
    generation_status: ReportGenerationStatus
    performance_data_status: PerformanceDataStatus
    report_version: int
    reporting_currency: str
    idempotency_key: str
    beginning_nav: Optional[float] = None
    ending_nav: Optional[float] = None
    period_return: Optional[float] = None
    cumulative_return: Optional[float] = None
    annualized_return: Optional[float] = None
    total_pnl: Optional[float] = None
    realized_pnl: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    net_external_flow: Optional[float] = None
    benchmark_return: Optional[float] = None
    active_return_difference: Optional[float] = None
    artifacts: List[PerformanceArtifactSchema] = Field(default_factory=list)


class PerformanceIntegrityVerificationResponse(BaseModel):
    artifact_id: str
    stored_sha256: str
    computed_sha256: str
    is_valid: bool
    verified_at: datetime
