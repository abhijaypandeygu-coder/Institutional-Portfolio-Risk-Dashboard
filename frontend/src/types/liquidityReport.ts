"""TypeScript types and contracts for M14.05 Liquidity Reports."""

export type LiquidityReportStatus = 'DRAFT' | 'GENERATING' | 'GENERATED' | 'FAILED' | 'ARCHIVED';

export type LiquidityQualityStatus =
  | 'VALID'
  | 'STALE'
  | 'PARTIAL'
  | 'MISSING'
  | 'INVALID'
  | 'NOT_SUPPORTED'
  | 'NOT_APPLICABLE'
  | 'FAILED';

export type LiquidityReconciliationStatus =
  | 'RECONCILED'
  | 'RECONCILED_WITH_ROUNDING'
  | 'PARTIALLY_RECONCILED'
  | 'UNRECONCILED'
  | 'NOT_EVALUABLE';

export type LiquidityLimitEvaluationStatus =
  | 'WITHIN_LIMIT'
  | 'APPROACHING_LIMIT'
  | 'PROJECTED_STRESS_EXCEEDANCE'
  | 'ACTUAL_LIMIT_BREACH'
  | 'NOT_EVALUABLE'
  | 'UNSUPPORTED'
  | 'STALE_INPUTS';

export type LiquidityArtifactType = 'PDF' | 'HTML' | 'CSV' | 'JSON_MANIFEST';

export interface LiquidationAssumptionsInput {
  participation_rate: number;
  target_fraction: number;
  execution_horizon: string;
  side: string;
  include_fees: boolean;
  estimation_scope: 'INDEPENDENT' | 'SHARED_CAPACITY';
}

export interface ScenarioSelectionItem {
  scenario_id: string;
  scenario_run_id?: string;
}

export interface LiquidityReportCreateRequest {
  portfolio_id: string;
  report_name: string;
  as_of_timestamp?: string;
  reporting_currency: string;
  liquidation_assumptions: LiquidationAssumptionsInput;
  scenario_runs: ScenarioSelectionItem[];
  include_position_analysis: boolean;
  include_concentration: boolean;
  include_stress_comparison: boolean;
  include_limit_implications: boolean;
  export_formats: string[];
  created_by?: string;
}

export interface LiquidityProfileSummary {
  portfolio_weighted_spread_bps: number;
  total_bid_depth_notional: number;
  total_ask_depth_notional: number;
  average_daily_volume_shares: number;
  average_daily_turnover: number;
  portfolio_liquidity_score: number;
  portfolio_liquidity_tier: string;
  coverage_ratio: number;
  stale_unavailable_count: number;
  spread_distribution: Record<string, number>;
  score_distribution: Record<string, number>;
}

export interface PositionLiquidity {
  instrument_id: string;
  symbol: string;
  exchange: string;
  sector?: string;
  industry?: string;
  position_quantity: number;
  position_market_value: number;
  currency: string;
  spread?: number;
  relative_spread?: number;
  spread_bps?: number;
  bid_depth?: number;
  ask_depth?: number;
  traded_volume?: number;
  average_daily_volume?: number;
  turnover?: number;
  liquidity_score?: number;
  liquidity_classification: string;
  liquidity_quality_status: LiquidityQualityStatus;
}

export interface LiquidationEstimate {
  instrument_id: string;
  symbol: string;
  liquidation_direction: 'SELL' | 'BUY';
  target_quantity: number;
  target_fraction: number;
  participation_rate: number;
  estimated_executable_volume?: number;
  estimated_duration_days?: number;
  estimated_duration_sessions?: number;
  estimated_completion_timestamp?: string;
  estimated_spread_cost: number;
  estimated_market_impact: number;
  estimated_slippage: number;
  estimated_fees: number;
  estimated_total_cost: number;
  estimated_cost_bps: number;
  cost_currency: string;
  estimation_scope: string;
  quality_status: LiquidityQualityStatus;
}

export interface IlliquidityConcentration {
  grouping_type: string;
  grouping_reference: string;
  position_count: number;
  aggregate_position_value: number;
  estimated_liquidation_cost: number;
  cost_contribution_pct?: number;
  liquidity_coverage: number;
}

export interface StressComparison {
  scenario_id: string;
  scenario_run_id?: string;
  scenario_name: string;
  scenario_version: string;
  scenario_horizon: string;
  baseline_spread_bps: number;
  stressed_spread_bps: number;
  spread_widening_pct: number;
  baseline_depth: number;
  stressed_depth: number;
  depth_reduction_pct: number;
  baseline_volume: number;
  stressed_volume: number;
  volume_contraction_pct: number;
  baseline_liquidity_score: number;
  stressed_liquidity_score: number;
  baseline_liquidation_time_days: number;
  stressed_liquidation_time_days: number;
  baseline_liquidation_cost: number;
  stressed_liquidation_cost: number;
  incremental_liquidation_cost: number;
  comparison_status: string;
}

export interface LimitImplication {
  limit_id: string;
  limit_code: string;
  limit_name: string;
  policy_version: string;
  target_type: string;
  target_reference: string;
  metric_name: string;
  configured_threshold: number;
  threshold_unit: string;
  current_metric?: number;
  stressed_metric?: number;
  utilization_pct?: number;
  evaluation_status: LiquidityLimitEvaluationStatus;
  evaluation_reference?: string;
  evaluation_timestamp: string;
}

export interface LiquidityReconciliation {
  metric_name: string;
  source_value: number;
  report_value: number;
  difference: number;
  tolerance: number;
  coverage_status: string;
  reconciliation_status: LiquidityReconciliationStatus;
  exception_details?: string;
}

export interface LiquidityArtifact {
  artifact_type: LiquidityArtifactType;
  storage_reference: string;
  file_hash: string;
  file_size_bytes: number;
  generated_at: string;
  artifact_status: string;
}

export interface LiquidityExecutiveSummary {
  portfolio_id: string;
  portfolio_name: string;
  as_of_timestamp: string;
  reporting_currency: string;
  position_count: number;
  liquidity_coverage_ratio: number;
  portfolio_liquidity_score: number;
  portfolio_weighted_spread_bps: number;
  total_portfolio_nav: number;
  estimated_portfolio_liquidation_cost: number;
  estimated_portfolio_liquidation_cost_bps: number;
  estimated_portfolio_liquidation_days: number;
  estimation_scope: string;
  worst_liquidity_stress_scenario?: string;
  worst_stressed_liquidation_cost: number;
  projected_limit_exceedances_count: number;
  actual_breaches_count: number;
  reconciliation_status: LiquidityReconciliationStatus;
}

export interface CanonicalLiquidityReport {
  report_id: string;
  report_code: string;
  portfolio_id: string;
  report_name: string;
  report_status: LiquidityReportStatus;
  report_version: number;
  reporting_currency: string;
  as_of_timestamp: string;
  coverage_status: string;
  reconciliation_status: LiquidityReconciliationStatus;
  template_version: string;
  generator_version: string;
  created_at: string;
  completed_at?: string;

  executive_summary: LiquidityExecutiveSummary;
  profile: LiquidityProfileSummary;
  positions: PositionLiquidity[];
  liquidations: LiquidationEstimate[];
  concentrations: IlliquidityConcentration[];
  stress_comparisons: StressComparison[];
  limits: LimitImplication[];
  reconciliations: LiquidityReconciliation[];
  artifacts: LiquidityArtifact[];
}

export interface LiquidityReportSummaryResponse {
  report_id: string;
  report_code: string;
  portfolio_id: string;
  report_name: string;
  report_status: LiquidityReportStatus;
  report_version: number;
  reporting_currency: string;
  as_of_timestamp: string;
  position_count: number;
  liquidity_coverage: number;
  reconciliation_status: LiquidityReconciliationStatus;
  generated_at: string;
  artifacts: Array<{ type: string; hash: string }>;
}

export interface LiquidityReportIntegrityResponse {
  report_id: string;
  report_code: string;
  report_version: number;
  artifact_type: string;
  file_hash: string;
  is_valid: boolean;
  verified_at: string;
  details: string;
}
