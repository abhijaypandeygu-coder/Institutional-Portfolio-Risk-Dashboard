"""
M14.03 Risk Attribution Reports Schemas.
Pydantic 2.x data contracts for risk attribution configurations, generation runs,
canonical reports, and reconciliation.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from backend.app.modules.reporting_attribution_audit.risk_attribution.models.risk_attribution_models import (
    RiskMeasureType,
    ValuationCutoffPolicy,
    AttributionGranularity,
    AttributionGroupType,
    AttributionContributionStatus,
    ReconciliationStatusType,
    CaveatCategory,
    CaveatSeverity,
    ReportArtifactType,
    ReportGenerationStatus,
)


class RiskAttributionConfigCreate(BaseModel):
    portfolio_id: str
    configuration_name: str
    risk_measure: RiskMeasureType = RiskMeasureType.PORTFOLIO_VOLATILITY
    valuation_cutoff_policy: ValuationCutoffPolicy = ValuationCutoffPolicy.OFFICIAL_CLOSE
    reporting_currency: str = "USD"
    attribution_levels: List[str] = Field(default_factory=lambda: ["SECURITY", "SECTOR", "INDUSTRY", "FACTOR"])
    factor_model_id: Optional[str] = None
    reconciliation_absolute_tolerance: Decimal = Decimal("0.0001")
    reconciliation_relative_tolerance: Decimal = Decimal("0.001")
    ranking_limit: int = 10
    created_by: str = "SYSTEM"


class RiskAttributionConfigUpdate(BaseModel):
    configuration_name: Optional[str] = None
    risk_measure: Optional[RiskMeasureType] = None
    valuation_cutoff_policy: Optional[ValuationCutoffPolicy] = None
    reporting_currency: Optional[str] = None
    attribution_levels: Optional[List[str]] = None
    factor_model_id: Optional[str] = None
    reconciliation_absolute_tolerance: Optional[Decimal] = None
    reconciliation_relative_tolerance: Optional[Decimal] = None
    ranking_limit: Optional[int] = None
    is_active: Optional[bool] = None


class RiskAttributionConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    portfolio_id: str
    configuration_name: str
    risk_measure: RiskMeasureType
    valuation_cutoff_policy: ValuationCutoffPolicy
    reporting_currency: str
    attribution_levels: List[str]
    factor_model_id: Optional[str]
    reconciliation_absolute_tolerance: Decimal
    reconciliation_relative_tolerance: Decimal
    ranking_limit: int
    template_version: str
    configuration_version: int
    is_active: bool
    created_by: str
    created_at: datetime
    updated_at: datetime


class RiskAttributionGenerateRequest(BaseModel):
    portfolio_id: str
    reporting_date: date
    risk_measure: Optional[RiskMeasureType] = None
    valuation_cutoff_policy: Optional[ValuationCutoffPolicy] = None
    factor_model_id: Optional[str] = None
    ranking_limit: Optional[int] = 10
    force_regenerate: bool = False
    regeneration_reason: Optional[str] = "Manual regeneration trigger"
    requested_by: str = "SYSTEM"


class SecurityContributionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    instrument_id: str
    listing_id: Optional[str] = None
    symbol: str
    display_name: Optional[str] = None
    sector: str
    industry: str
    position_quantity: Decimal
    market_value: Decimal
    position_weight: Decimal
    position_side: str
    standalone_volatility: Optional[Decimal] = None
    marginal_risk_contribution: Decimal
    component_risk_contribution: Decimal
    contribution_percentage: Decimal
    contribution_rank: int
    source_reference: str = "M07.09"
    contribution_status: AttributionContributionStatus = AttributionContributionStatus.ACTIVE


class GroupContributionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    group_type: AttributionGroupType
    group_id: str
    group_name: str
    parent_group_id: Optional[str] = None
    security_count: int
    total_market_value: Decimal
    total_weight: Decimal
    component_risk_contribution: Decimal
    contribution_percentage: Decimal
    group_rank: int
    classification_version: str = "v1.0"
    contribution_status: AttributionContributionStatus = AttributionContributionStatus.ACTIVE


class FactorContributionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    factor_id: str
    factor_name: str
    factor_category: str = "STYLE"
    factor_exposure: Decimal
    marginal_risk_contribution: Decimal
    component_risk_contribution: Decimal
    contribution_percentage: Decimal
    factor_rank: int
    factor_model_version: str = "v1.0"
    source_reference: str = "M08.05"
    contribution_status: AttributionContributionStatus = AttributionContributionStatus.ACTIVE


class ReconciliationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    attribution_level: AttributionGranularity
    risk_measure: RiskMeasureType
    authoritative_value: Decimal
    contribution_sum: Decimal
    residual: Decimal
    absolute_difference: Decimal
    relative_difference: Decimal
    absolute_tolerance: Decimal
    relative_tolerance: Decimal
    reconciliation_status: ReconciliationStatusType
    explanation: str


class AttributionCaveatSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    caveat_category: CaveatCategory
    severity: CaveatSeverity
    affected_entity: str
    affected_metric: str
    explanation: str
    source_reference: str
    affects_completeness: bool


class AttributionArtifactSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    artifact_type: ReportArtifactType
    storage_reference: str
    content_hash: str
    content_type: str
    file_size_bytes: int
    generated_at: datetime


class RiskCompositionSchema(BaseModel):
    total_risk: Optional[Decimal] = None
    systematic_risk: Optional[Decimal] = None
    idiosyncratic_risk: Optional[Decimal] = None
    residual_risk: Optional[Decimal] = None
    systematic_percentage: Optional[Decimal] = None
    idiosyncratic_percentage: Optional[Decimal] = None
    status: str = "COMPLETE"


class CanonicalRiskAttributionReport(BaseModel):
    report_id: str
    report_type: str = "RISK_ATTRIBUTION_REPORT"
    report_schema_version: str = "1.0"
    portfolio_id: str
    reporting_date: date
    valuation_timestamp: datetime
    generated_at: datetime
    reporting_currency: str
    risk_measure: RiskMeasureType
    risk_measure_unit: str
    authoritative_risk_value: Optional[Decimal]
    risk_methodology: str
    risk_composition: RiskCompositionSchema
    reconciliation_status: ReconciliationStatusType
    security_contributions: List[SecurityContributionSchema]
    sector_contributions: List[GroupContributionSchema]
    industry_contributions: List[GroupContributionSchema]
    factor_contributions: List[FactorContributionSchema]
    reconciliations: List[ReconciliationSchema]
    top_positive_securities: List[SecurityContributionSchema]
    top_negative_securities: List[SecurityContributionSchema]
    top_contributing_sectors: List[GroupContributionSchema]
    top_contributing_factors: List[FactorContributionSchema]
    coverage_manifest: Dict[str, Any]
    source_manifest: Dict[str, Any]
    methodology_manifest: Dict[str, Any]
    caveats: List[AttributionCaveatSchema]
    report_version: int
    artifacts: List[AttributionArtifactSchema] = Field(default_factory=list)


class RiskAttributionRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    configuration_id: Optional[str]
    portfolio_id: str
    reporting_date: date
    valuation_timestamp: datetime
    risk_measure: RiskMeasureType
    authoritative_risk_value: Optional[Decimal]
    generation_status: ReportGenerationStatus
    reconciliation_status: ReconciliationStatusType
    model_version: str
    factor_model_version: Optional[str]
    classification_version: str
    report_version: int
    generated_at: datetime
    created_by: str


class RiskAttributionIntegrityResponse(BaseModel):
    run_id: str
    is_valid: bool
    verified_at: datetime
    artifacts: List[Dict[str, Any]]
