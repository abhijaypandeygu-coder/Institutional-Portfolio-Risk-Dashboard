"""Pydantic schemas and contracts for M14.05 Liquidity Reports."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from backend.app.modules.reporting_attribution_audit.liquidity.models.liquidity_report_models import (
    LiquidityReportStatus,
    LiquidityQualityStatus,
    LiquidityReconciliationStatus,
    LiquidityLimitEvaluationStatus,
    LiquidityArtifactType,
)


class LiquidationAssumptionsInput(BaseModel):
    participation_rate: float = Field(0.10, ge=0.01, le=1.0, description="Max volume participation rate (e.g. 10%)")
    target_fraction: float = Field(1.0, ge=0.01, le=1.0, description="Target reduction fraction (1.0 = 100%)")
    execution_horizon: str = Field("CONFIGURED_BY_UPSTREAM_MODEL", description="Execution horizon assumptions")
    side: str = Field("AUTO", description="AUTO, SELL (for long liquidation), BUY (for short covering)")
    include_fees: bool = Field(True, description="Whether to include brokerage and exchange fees")
    estimation_scope: str = Field("INDEPENDENT", description="INDEPENDENT or SHARED_CAPACITY")


class ScenarioSelectionItem(BaseModel):
    scenario_id: str
    scenario_run_id: Optional[str] = None


class LiquidityReportCreateRequest(BaseModel):
    portfolio_id: str = Field(..., description="Target portfolio identifier")
    report_name: str = Field("Monthly Portfolio Liquidity Review", description="Human-readable report title")
    as_of_timestamp: Optional[datetime] = Field(None, description="Valuation snapshot timestamp (UTC)")
    reporting_currency: str = Field("INR", description="Portfolio base currency for reporting")
    liquidation_assumptions: LiquidationAssumptionsInput = Field(default_factory=LiquidationAssumptionsInput)
    scenario_runs: List[ScenarioSelectionItem] = Field(default_factory=list)
    include_position_analysis: bool = Field(True)
    include_concentration: bool = Field(True)
    include_stress_comparison: bool = Field(True)
    include_limit_implications: bool = Field(True)
    export_formats: List[str] = Field(default=["PDF", "CSV", "HTML"])
    created_by: str = Field("SYSTEM")


class LiquidityProfileSummarySchema(BaseModel):
    portfolio_weighted_spread_bps: float
    total_bid_depth_notional: float
    total_ask_depth_notional: float
    average_daily_volume_shares: float
    average_daily_turnover: float
    portfolio_liquidity_score: float
    portfolio_liquidity_tier: str
    coverage_ratio: float
    stale_unavailable_count: int
    spread_distribution: Dict[str, int]
    score_distribution: Dict[str, int]


class PositionLiquiditySchema(BaseModel):
    instrument_id: str
    symbol: str
    exchange: str
    sector: Optional[str] = "Unclassified"
    industry: Optional[str] = "Unclassified"
    position_quantity: float
    position_market_value: float
    currency: str
    spread: Optional[float] = None
    relative_spread: Optional[float] = None
    spread_bps: Optional[float] = None
    bid_depth: Optional[float] = None
    ask_depth: Optional[float] = None
    traded_volume: Optional[float] = None
    average_daily_volume: Optional[float] = None
    turnover: Optional[float] = None
    liquidity_score: Optional[float] = None
    liquidity_classification: str = "MODERATE"
    liquidity_quality_status: LiquidityQualityStatus = LiquidityQualityStatus.VALID


class LiquidationEstimateSchema(BaseModel):
    instrument_id: str
    symbol: str
    liquidation_direction: str  # SELL or BUY
    target_quantity: float
    target_fraction: float
    participation_rate: float
    estimated_executable_volume: Optional[float] = None
    estimated_duration_days: Optional[float] = None
    estimated_duration_sessions: Optional[float] = None
    estimated_completion_timestamp: Optional[datetime] = None
    estimated_spread_cost: float = 0.0
    estimated_market_impact: float = 0.0
    estimated_slippage: float = 0.0
    estimated_fees: float = 0.0
    estimated_total_cost: float = 0.0
    estimated_cost_bps: float = 0.0
    cost_currency: str = "INR"
    estimation_scope: str = "INDEPENDENT"
    quality_status: LiquidityQualityStatus = LiquidityQualityStatus.VALID


class IlliquidityConcentrationSchema(BaseModel):
    grouping_type: str  # POSITION, SECTOR, LIQUIDITY_TIER
    grouping_reference: str
    position_count: int
    aggregate_position_value: float
    estimated_liquidation_cost: float
    cost_contribution_pct: Optional[float] = None
    liquidity_coverage: float = 1.0


class StressComparisonSchema(BaseModel):
    scenario_id: str
    scenario_run_id: Optional[str] = None
    scenario_name: str
    scenario_version: str = "v1"
    scenario_horizon: str = "10D"
    baseline_spread_bps: float
    stressed_spread_bps: float
    spread_widening_pct: float
    baseline_depth: float
    stressed_depth: float
    depth_reduction_pct: float
    baseline_volume: float
    stressed_volume: float
    volume_contraction_pct: float
    baseline_liquidity_score: float
    stressed_liquidity_score: float
    baseline_liquidation_time_days: float
    stressed_liquidation_time_days: float
    baseline_liquidation_cost: float
    stressed_liquidation_cost: float
    incremental_liquidation_cost: float
    comparison_status: str = "COMPLETED"


class LimitImplicationSchema(BaseModel):
    limit_id: str
    limit_code: str
    limit_name: str
    policy_version: str = "v1"
    target_type: str = "PORTFOLIO"
    target_reference: str
    metric_name: str
    configured_threshold: float
    threshold_unit: str = "BPS"
    current_metric: Optional[float] = None
    stressed_metric: Optional[float] = None
    utilization_pct: Optional[float] = None
    evaluation_status: LiquidityLimitEvaluationStatus = LiquidityLimitEvaluationStatus.WITHIN_LIMIT
    evaluation_reference: Optional[str] = None
    evaluation_timestamp: datetime


class LiquidityReconciliationSchema(BaseModel):
    metric_name: str
    source_value: float
    report_value: float
    difference: float
    tolerance: float = 0.01
    coverage_status: str = "FULL"
    reconciliation_status: LiquidityReconciliationStatus = LiquidityReconciliationStatus.RECONCILED
    exception_details: Optional[str] = None


class LiquidityArtifactSchema(BaseModel):
    artifact_type: LiquidityArtifactType
    storage_reference: str
    file_hash: str
    file_size_bytes: int
    generated_at: datetime
    artifact_status: str = "AVAILABLE"


class LiquidityExecutiveSummarySchema(BaseModel):
    portfolio_id: str
    portfolio_name: str
    as_of_timestamp: datetime
    reporting_currency: str
    position_count: int
    liquidity_coverage_ratio: float
    portfolio_liquidity_score: float
    portfolio_weighted_spread_bps: float
    total_portfolio_nav: float
    estimated_portfolio_liquidation_cost: float
    estimated_portfolio_liquidation_cost_bps: float
    estimated_portfolio_liquidation_days: float
    estimation_scope: str  # INDEPENDENT or SHARED_CAPACITY
    worst_liquidity_stress_scenario: Optional[str] = None
    worst_stressed_liquidation_cost: float = 0.0
    projected_limit_exceedances_count: int = 0
    actual_breaches_count: int = 0
    reconciliation_status: LiquidityReconciliationStatus = LiquidityReconciliationStatus.RECONCILED


class CanonicalLiquidityReport(BaseModel):
    report_id: str
    report_code: str
    portfolio_id: str
    report_name: str
    report_status: LiquidityReportStatus
    report_version: int
    reporting_currency: str
    as_of_timestamp: datetime
    coverage_status: str
    reconciliation_status: LiquidityReconciliationStatus
    template_version: str
    generator_version: str
    created_at: datetime
    completed_at: Optional[datetime] = None

    executive_summary: LiquidityExecutiveSummarySchema
    profile: LiquidityProfileSummarySchema
    positions: List[PositionLiquiditySchema]
    liquidations: List[LiquidationEstimateSchema]
    concentrations: List[IlliquidityConcentrationSchema]
    stress_comparisons: List[StressComparisonSchema]
    limits: List[LimitImplicationSchema]
    reconciliations: List[LiquidityReconciliationSchema]
    artifacts: List[LiquidityArtifactSchema]


class LiquidityReportSummaryResponse(BaseModel):
    report_id: str
    report_code: str
    portfolio_id: str
    report_name: str
    report_status: LiquidityReportStatus
    report_version: int
    reporting_currency: str
    as_of_timestamp: datetime
    position_count: int
    liquidity_coverage: float
    reconciliation_status: LiquidityReconciliationStatus
    generated_at: datetime
    artifacts: List[Dict[str, str]]


class LiquidityReportIntegrityResponse(BaseModel):
    report_id: str
    report_code: str
    report_version: int
    artifact_type: str
    file_hash: str
    is_valid: bool
    verified_at: datetime
    details: str
