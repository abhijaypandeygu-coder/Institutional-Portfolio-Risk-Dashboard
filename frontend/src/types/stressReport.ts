/**
 * M14.04 Stress Testing Reports TypeScript Domain Contracts.
 */

export type StressScenarioType =
  | 'HISTORICAL'
  | 'HYPOTHETICAL'
  | 'MARKET_CRASH'
  | 'SECTOR_SHOCK'
  | 'CORRELATION_SHOCK'
  | 'LIQUIDITY_STRESS'
  | 'MONTE_CARLO'
  | 'COMBINED';

export type StressReportStatus = 'DRAFT' | 'PENDING' | 'COMPLETED' | 'FAILED';

export type StressReconciliationStatus =
  | 'RECONCILED'
  | 'RECONCILED_WITH_ROUNDING'
  | 'PARTIALLY_RECONCILED'
  | 'UNRECONCILED'
  | 'NOT_EVALUABLE';

export type LimitEvaluationStatus =
  | 'WITHIN_LIMIT'
  | 'APPROACHING_LIMIT'
  | 'PROJECTED_STRESS_EXCEEDANCE'
  | 'NOT_EVALUABLE'
  | 'UNSUPPORTED';

export type StressArtifactType = 'PDF' | 'HTML' | 'CSV' | 'JSON_MANIFEST';

export interface ScenarioDescription {
  id?: string;
  scenario_id: string;
  scenario_run_id: string;
  scenario_name: string;
  scenario_type: StressScenarioType;
  scenario_horizon: string;
  scenario_description: string;
  scenario_execution_timestamp: string;
  baseline_portfolio_nav: number;
  stressed_portfolio_value: number;
  stressed_pnl: number;
  stressed_loss: number;
  stress_impact_percentage: number;
  shock_magnitude_summary: string;
  shocks_breakdown: Array<{
    category: string;
    target: string;
    magnitude: number;
    unit: string;
  }>;
  affected_groups: string[];
  methodology: string;
  assumption_limitations: string[];
  comparison_rank: number;
}

export interface PositionStressResult {
  id?: string;
  scenario_id: string;
  instrument_id: string;
  symbol: string;
  instrument_name: string;
  sector: string;
  industry: string;
  position_side: 'LONG' | 'SHORT';
  position_quantity: number;
  baseline_price: number;
  stressed_price: number;
  baseline_market_value: number;
  stressed_market_value: number;
  stressed_pnl: number;
  stressed_loss: number;
  impact_percentage: number;
  applied_shock: string;
  source_reference: string;
}

export interface SectorStressBreakdown {
  sector_name: string;
  position_count: number;
  baseline_market_value: number;
  stressed_market_value: number;
  stressed_pnl: number;
  stressed_loss: number;
  impact_percentage: number;
}

export interface SensitivityItem {
  id?: string;
  sensitivity_dimension: string;
  assumption_name: string;
  assumption_value: string;
  assumption_unit: string;
  stressed_pnl: number;
  stressed_loss: number;
  impact_percentage: number;
  incremental_loss: number;
  source_sensitivity_reference: string;
}

export interface LimitImplication {
  id?: string;
  scenario_id: string;
  limit_id: string;
  limit_name: string;
  limit_scope: string;
  metric_name: string;
  limit_policy_version: string;
  configured_threshold: number;
  stressed_metric: number;
  utilization_percentage: number;
  evaluation_status: LimitEvaluationStatus;
  difference_from_threshold: number;
  is_projected_exceedance: bool;
  evaluation_timestamp: string;
}

export interface StressReconciliationRecord {
  scenario_id: string;
  authoritative_total_pnl: number;
  reported_total_pnl: number;
  position_level_pnl_sum: number;
  other_components_total: number;
  residual: number;
  tolerance: number;
  reconciliation_status: StressReconciliationStatus;
  exception_details: string;
}

export interface StressArtifact {
  id: string;
  artifact_type: StressArtifactType;
  storage_reference: string;
  file_hash: string;
  file_size_bytes: number;
  generated_at: string;
}

export interface ExecutiveSummary {
  portfolio_id: string;
  reporting_date: string;
  scenario_count: number;
  worst_scenario_name: string;
  worst_stressed_pnl: number;
  worst_stressed_loss: number;
  worst_stress_impact_percentage: number;
  baseline_portfolio_nav: number;
  projected_exceedances_count: number;
  overall_reconciliation_status: StressReconciliationStatus;
  data_quality_status: string;
}

export interface CanonicalStressReport {
  report_id: string;
  report_code: string;
  portfolio_id: string;
  report_name: string;
  report_status: StressReportStatus;
  report_version: number;
  reporting_currency: string;
  valuation_timestamp: string;
  reporting_date: string;
  executive_summary: ExecutiveSummary;
  scenarios: ScenarioDescription[];
  position_results: PositionStressResult[];
  sector_breakdown: SectorStressBreakdown[];
  sensitivities: SensitivityItem[];
  limit_results: LimitImplication[];
  reconciliations: StressReconciliationRecord[];
  caveats: Array<Record<string, any>>;
  provenance_manifest: Record<string, any>;
  artifacts: StressArtifact[];
}

export interface StressReportSummary {
  id: string;
  report_code: string;
  portfolio_id: string;
  report_name: string;
  report_status: StressReportStatus;
  report_version: number;
  reporting_currency: string;
  reporting_date: string;
  valuation_timestamp: string;
  worst_stressed_pnl: number;
  worst_stress_impact_percentage: number;
  projected_exceedances_count: number;
  reconciliation_status: StressReconciliationStatus;
  created_at: string;
  created_by: string;
}
