"""
M14.04 Stress Testing Reports Schemas.
Pydantic 2.x data contracts for stress testing reports, scenario descriptions,
stressed P&L, sensitivity analyses, limit implications, and cryptographic verification.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from backend.app.modules.reporting_attribution_audit.stress_testing.models.stress_report_models import (
    StressScenarioType,
    StressReportStatus,
    StressReconciliationStatus,
    LimitEvaluationStatus,
    StressArtifactType,
)


class ScenarioSelectionItem(BaseModel):
    scenario_id: str
    scenario_run_id: Optional[str] = None


class StressReportCreateRequest(BaseModel):
    portfolio_id: str
    report_name: Optional[str] = "Comprehensive Stress Testing Review"
    reporting_date: Optional[date] = None
    scenario_runs: Optional[List[ScenarioSelectionItem]] = None
    reporting_currency: str = "USD"
    include_position_breakdown: bool = True
    include_sector_breakdown: bool = True
    include_factor_breakdown: bool = True
    include_sensitivity: bool = True
    include_limit_implications: bool = True
    include_reconciliation: bool = True
    force_regenerate: bool = False
    regeneration_reason: Optional[str] = "Manual regeneration trigger"
    requested_by: str = "SYSTEM"


class ScenarioDescriptionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    scenario_id: str
    scenario_run_id: str
    scenario_name: str
    scenario_type: StressScenarioType
    scenario_horizon: str
    scenario_description: str
    scenario_execution_timestamp: datetime
    baseline_portfolio_nav: Decimal
    stressed_portfolio_value: Decimal
    stressed_pnl: Decimal
    stressed_loss: Decimal
    stress_impact_percentage: Decimal
    shock_magnitude_summary: str
    shocks_breakdown: List[Dict[str, Any]]
    affected_groups: List[str]
    methodology: str
    assumption_limitations: List[str]
    comparison_rank: int


class PositionStressResultSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    scenario_id: str
    instrument_id: str
    symbol: str
    instrument_name: str
    sector: str
    industry: str
    position_side: str
    position_quantity: Decimal
    baseline_price: Decimal
    stressed_price: Decimal
    baseline_market_value: Decimal
    stressed_market_value: Decimal
    stressed_pnl: Decimal
    stressed_loss: Decimal
    impact_percentage: Decimal
    applied_shock: str
    source_reference: str


class SectorStressBreakdownSchema(BaseModel):
    sector_name: str
    position_count: int
    baseline_market_value: Decimal
    stressed_market_value: Decimal
    stressed_pnl: Decimal
    stressed_loss: Decimal
    impact_percentage: Decimal


class SensitivityItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    sensitivity_dimension: str
    assumption_name: str
    assumption_value: str
    assumption_unit: str
    stressed_pnl: Decimal
    stressed_loss: Decimal
    impact_percentage: Decimal
    incremental_loss: Decimal
    source_sensitivity_reference: str


class LimitImplicationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    scenario_id: str
    limit_id: str
    limit_name: str
    limit_scope: str
    metric_name: str
    limit_policy_version: str
    configured_threshold: Decimal
    stressed_metric: Decimal
    utilization_percentage: Decimal
    evaluation_status: LimitEvaluationStatus
    difference_from_threshold: Decimal
    is_projected_exceedance: bool
    evaluation_timestamp: datetime


class StressReconciliationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scenario_id: str
    authoritative_total_pnl: Decimal
    reported_total_pnl: Decimal
    position_level_pnl_sum: Decimal
    other_components_total: Decimal
    residual: Decimal
    tolerance: Decimal
    reconciliation_status: StressReconciliationStatus
    exception_details: str


class StressArtifactSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    artifact_type: StressArtifactType
    storage_reference: str
    file_hash: str
    file_size_bytes: int
    generated_at: datetime


class ExecutiveSummarySchema(BaseModel):
    portfolio_id: str
    reporting_date: date
    scenario_count: int
    worst_scenario_name: str
    worst_stressed_pnl: Decimal
    worst_stressed_loss: Decimal
    worst_stress_impact_percentage: Decimal
    baseline_portfolio_nav: Decimal
    projected_exceedances_count: int
    overall_reconciliation_status: StressReconciliationStatus
    data_quality_status: str = "VALID"


class CanonicalStressReport(BaseModel):
    report_id: str
    report_code: str
    portfolio_id: str
    report_name: str
    report_status: StressReportStatus
    report_version: int
    reporting_currency: str
    valuation_timestamp: datetime
    reporting_date: date
    executive_summary: ExecutiveSummarySchema
    scenarios: List[ScenarioDescriptionSchema]
    position_results: List[PositionStressResultSchema]
    sector_breakdown: List[SectorStressBreakdownSchema]
    sensitivities: List[SensitivityItemSchema]
    limit_results: List[LimitImplicationSchema]
    reconciliations: List[StressReconciliationSchema]
    caveats: List[Dict[str, Any]]
    provenance_manifest: Dict[str, Any]
    artifacts: List[StressArtifactSchema] = Field(default_factory=list)


class StressReportSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    report_code: str
    portfolio_id: str
    report_name: str
    report_status: StressReportStatus
    report_version: int
    reporting_currency: str
    reporting_date: date
    valuation_timestamp: datetime
    worst_stressed_pnl: Decimal
    worst_stress_impact_percentage: Decimal
    projected_exceedances_count: int
    reconciliation_status: StressReconciliationStatus
    created_at: datetime
    created_by: str


class StressReportIntegrityResponse(BaseModel):
    report_id: str
    is_valid: bool
    verified_at: datetime
    artifacts: List[Dict[str, Any]]
