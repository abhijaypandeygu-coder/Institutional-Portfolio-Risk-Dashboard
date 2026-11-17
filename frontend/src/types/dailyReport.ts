/**
 * M14.01 — Daily Risk Reports TypeScript Definitions.
 * Institutional Portfolio Risk Dashboard.
 */

export type ReportGenerationStatus = "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";

export type OverallControlStatus = "CLEAR" | "WARNINGS" | "CRITICAL" | "EMERGENCY";

export type OverallFreshnessStatus = "FRESH" | "STALE" | "PARTIAL" | "UNAVAILABLE";

export type BreachSeverity = "WARNING" | "CRITICAL" | "EMERGENCY";

export type BreachLifecycleStatus = "OPEN" | "ACKNOWLEDGED" | "RESOLVED" | "EXEMPTED";

export interface ReportPortfolioContext {
  portfolio_id: string;
  portfolio_name?: string;
  base_currency: string;
  reporting_currency: string;
  reporting_calendar: string;
}

export interface ReportPortfolioSummaryData {
  nav?: number;
  market_value?: number;
  cash_balance?: number;
  realized_pnl?: number;
  unrealized_pnl?: number;
  total_pnl?: number;
  gross_exposure?: number;
  net_exposure?: number;
  long_exposure?: number;
  short_exposure?: number;
  invested_capital?: number;
  cash_allocation_pct?: number;
  currency: string;
  valuation_timestamp?: string;
  valuation_completeness: string;
  source_snapshot_id?: string;
  valuation_version?: number;
}

export interface ReportVaRMetric {
  value?: number;
  confidence_level?: number;
  horizon_days?: number;
  methodology?: string;
  currency?: string;
  status: string;
  notes?: string;
}

export interface ReportESMetric {
  value?: number;
  confidence_level?: number;
  horizon_days?: number;
  methodology?: string;
  currency?: string;
  status: string;
  notes?: string;
}

export interface ReportVolatilityMetric {
  value?: number;
  return_frequency?: string;
  annualization_factor?: number;
  lookback_window?: number;
  designation?: string;
  status: string;
  notes?: string;
}

export interface ReportDrawdownMetric {
  current_drawdown?: number;
  maximum_drawdown?: number;
  peak_date?: string;
  trough_date?: string;
  duration_days?: number;
  recovery_status?: string;
  status: string;
  notes?: string;
}

export interface ReportRiskMetricsData {
  var?: ReportVaRMetric;
  expected_shortfall?: ReportESMetric;
  volatility?: ReportVolatilityMetric;
  drawdown?: ReportDrawdownMetric;
  calculation_date?: string;
  model_versions: Record<string, string>;
  methodology_references: Record<string, string>;
}

export interface ReportLimitBreachDetail {
  limit_id: string;
  limit_name?: string;
  metric_name: string;
  target_entity: string;
  observed_value: number;
  warning_threshold?: number;
  critical_threshold?: number;
  unit: string;
  utilization_pct: number;
  severity: BreachSeverity;
  status: BreachLifecycleStatus;
  detected_at?: string;
  escalation_level?: string;
}

export interface ReportLimitStatusData {
  overall_control_status: OverallControlStatus;
  total_limits_evaluated: number;
  total_breaches: number;
  critical_breaches_count: number;
  warning_breaches_count: number;
  breaches: ReportLimitBreachDetail[];
}

export interface SourceFreshnessItem {
  source_module: string;
  last_watermark?: string;
  latency_minutes?: number;
  status: OverallFreshnessStatus;
  quality_status?: string;
}

export interface ReportAsOfMetadata {
  report_date: string;
  valuation_timestamp?: string;
  generated_at: string;
  timezone: string;
  reporting_calendar: string;
  overall_freshness: OverallFreshnessStatus;
  data_stale_flag: boolean;
  stale_reasons: string[];
  source_watermarks: Record<string, SourceFreshnessItem>;
}

export interface DailyReportArtifactResponse {
  artifact_id: string;
  artifact_type: "PDF" | "HTML" | "CSV" | "JSON";
  file_name: string;
  file_size_bytes: number;
  content_sha256: string;
  content_data?: string;
  created_at: string;
}

export interface CanonicalDailyRiskReport {
  report_id: string;
  run_id: string;
  version_number: number;
  portfolio: ReportPortfolioContext;
  portfolio_summary: ReportPortfolioSummaryData;
  risk_metrics: ReportRiskMetricsData;
  risk_limit_status: ReportLimitStatusData;
  metadata: ReportAsOfMetadata;
  artifacts?: DailyReportArtifactResponse[];
}

export interface DailyReportConfigurationResponse {
  config_id: string;
  portfolio_id: string;
  reporting_calendar: string;
  valuation_cutoff_time: string;
  timezone: string;
  reporting_currency: string;
  var_confidence_levels: number[];
  var_holding_period_days: number;
  include_var: boolean;
  include_es: boolean;
  include_volatility: boolean;
  include_drawdown: boolean;
  include_limit_status: boolean;
  max_allowed_data_staleness_hours: number;
  require_complete_valuation: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DailyReportRunResponse {
  run_id: string;
  portfolio_id: string;
  report_date: string;
  version_number: number;
  run_status: ReportGenerationStatus;
  overall_control_status: OverallControlStatus;
  overall_freshness_status: OverallFreshnessStatus;
  nav?: number;
  total_pnl?: number;
  var_99_amount?: number;
  es_99_amount?: number;
  annualized_vol?: number;
  max_drawdown_pct?: number;
  total_breaches_count: number;
  critical_breaches_count: number;
  valuation_timestamp?: string;
  generated_at: string;
  generated_by: string;
  idempotency_key: string;
  artifacts: DailyReportArtifactResponse[];
}

export interface DailyReportIntegrityVerificationResponse {
  artifact_id: string;
  stored_sha256: string;
  computed_sha256: string;
  is_valid: boolean;
  verified_at: string;
}
