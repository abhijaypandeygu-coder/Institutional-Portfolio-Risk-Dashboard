/**
 * M14.03 Risk Attribution Reports TypeScript Contracts.
 */

export type RiskMeasureType =
  | 'PORTFOLIO_VOLATILITY'
  | 'PORTFOLIO_VARIANCE'
  | 'PARAMETRIC_VAR'
  | 'HISTORICAL_VAR'
  | 'EXPECTED_SHORTFALL'
  | 'SYSTEMATIC_FACTOR_RISK'
  | 'IDIOSYNCRATIC_RISK';

export type ValuationCutoffPolicy =
  | 'OFFICIAL_CLOSE'
  | 'INTRADAY_SNAPSHOT'
  | 'LATEST_AVAILABLE';

export type AttributionGranularity =
  | 'SECURITY'
  | 'SECTOR'
  | 'INDUSTRY'
  | 'FACTOR'
  | 'ALL';

export type AttributionGroupType = 'SECTOR' | 'INDUSTRY';

export type AttributionContributionStatus =
  | 'ACTIVE'
  | 'UNCLASSIFIED'
  | 'APPROXIMATED'
  | 'UNAVAILABLE';

export type ReconciliationStatusType =
  | 'EXACT_RECONCILIATION'
  | 'ROUNDING_DIFFERENCE'
  | 'RESIDUAL_PRESENT'
  | 'NON_ADDITIVE'
  | 'INCOMPLETE';

export type CaveatCategory =
  | 'DATA_GAP'
  | 'CLASSIFICATION_MISSING'
  | 'NON_ADDITIVE_METHODOLOGY'
  | 'COVARIANCE_APPROXIMATION'
  | 'FACTOR_MODEL_MISMATCH'
  | 'ROUNDING_RESIDUAL';

export type CaveatSeverity = 'INFO' | 'WARNING' | 'CRITICAL';

export type ReportArtifactType = 'PDF' | 'HTML' | 'CSV';

export interface SecurityContribution {
  id?: string;
  instrument_id: string;
  listing_id?: string;
  symbol: string;
  display_name?: string;
  sector: string;
  industry: string;
  position_quantity: number;
  market_value: number;
  position_weight: number;
  position_side: 'LONG' | 'SHORT';
  standalone_volatility?: number;
  marginal_risk_contribution: number;
  component_risk_contribution: number;
  contribution_percentage: number;
  contribution_rank: number;
  source_reference: string;
  contribution_status: AttributionContributionStatus;
}

export interface GroupContribution {
  id?: string;
  group_type: AttributionGroupType;
  group_id: string;
  group_name: string;
  parent_group_id?: string;
  security_count: number;
  total_market_value: number;
  total_weight: number;
  component_risk_contribution: number;
  contribution_percentage: number;
  group_rank: number;
  classification_version: string;
  contribution_status: AttributionContributionStatus;
}

export interface FactorContribution {
  id?: string;
  factor_id: string;
  factor_name: string;
  factor_category: string;
  factor_exposure: number;
  marginal_risk_contribution: number;
  component_risk_contribution: number;
  contribution_percentage: number;
  factor_rank: number;
  factor_model_version: string;
  source_reference: string;
  contribution_status: AttributionContributionStatus;
}

export interface ReconciliationRecord {
  attribution_level: AttributionGranularity;
  risk_measure: RiskMeasureType;
  authoritative_value: number;
  contribution_sum: number;
  residual: number;
  absolute_difference: number;
  relative_difference: number;
  absolute_tolerance: number;
  relative_tolerance: number;
  reconciliation_status: ReconciliationStatusType;
  explanation: string;
}

export interface AttributionCaveat {
  caveat_category: CaveatCategory;
  severity: CaveatSeverity;
  affected_entity: string;
  affected_metric: string;
  explanation: string;
  source_reference: string;
  affects_completeness: boolean;
}

export interface AttributionArtifact {
  id: string;
  artifact_type: ReportArtifactType;
  storage_reference: string;
  content_hash: string;
  content_type: string;
  file_size_bytes: number;
  generated_at: string;
}

export interface RiskComposition {
  total_risk?: number;
  systematic_risk?: number;
  idiosyncratic_risk?: number;
  residual_risk?: number;
  systematic_percentage?: number;
  idiosyncratic_percentage?: number;
  status: string;
}

export interface CanonicalRiskAttributionReport {
  report_id: string;
  report_type: string;
  report_schema_version: string;
  portfolio_id: string;
  reporting_date: string;
  valuation_timestamp: string;
  generated_at: string;
  reporting_currency: string;
  risk_measure: RiskMeasureType;
  risk_measure_unit: string;
  authoritative_risk_value?: number;
  risk_methodology: string;
  risk_composition: RiskComposition;
  reconciliation_status: ReconciliationStatusType;
  security_contributions: SecurityContribution[];
  sector_contributions: GroupContribution[];
  industry_contributions: GroupContribution[];
  factor_contributions: FactorContribution[];
  reconciliations: ReconciliationRecord[];
  top_positive_securities: SecurityContribution[];
  top_negative_securities: SecurityContribution[];
  top_contributing_sectors: GroupContribution[];
  top_contributing_factors: FactorContribution[];
  coverage_manifest: Record<string, any>;
  source_manifest: Record<string, any>;
  methodology_manifest: Record<string, any>;
  caveats: AttributionCaveat[];
  report_version: number;
  artifacts: AttributionArtifact[];
}

export interface RiskAttributionRunSummary {
  id: string;
  configuration_id?: string;
  portfolio_id: string;
  reporting_date: string;
  valuation_timestamp: string;
  risk_measure: RiskMeasureType;
  authoritative_risk_value?: number;
  generation_status: 'PENDING' | 'COMPLETED' | 'FAILED';
  reconciliation_status: ReconciliationStatusType;
  model_version: string;
  factor_model_version?: string;
  classification_version: string;
  report_version: number;
  generated_at: string;
  created_by: string;
}

export interface RiskAttributionConfig {
  id: string;
  portfolio_id: string;
  configuration_name: string;
  risk_measure: RiskMeasureType;
  valuation_cutoff_policy: ValuationCutoffPolicy;
  reporting_currency: string;
  attribution_levels: string[];
  factor_model_id?: string;
  reconciliation_absolute_tolerance: number;
  reconciliation_relative_tolerance: number;
  ranking_limit: number;
  template_version: string;
  configuration_version: number;
  is_active: boolean;
}
