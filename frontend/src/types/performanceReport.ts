/**
 * TypeScript Type Definitions for M14.02 — Portfolio Performance Reports.
 * Institutional Portfolio Risk Dashboard.
 */

export type ReportingPeriodType = "DAILY" | "WEEKLY" | "MONTHLY" | "QUARTERLY" | "YTD" | "ONE_YEAR" | "CUSTOM";

export type ReportingFrequency = "DAILY" | "WEEKLY" | "MONTHLY" | "QUARTERLY";

export type ReturnMethodology = "TWR" | "MODIFIED_DIETZ" | "MWR_XIRR";

export type CashFlowTimingPolicy = "VALUATION_AT_FLOW_BOUNDARY" | "START_OF_DAY" | "END_OF_DAY" | "MID_DAY_APPROXIMATION";

export type BenchmarkReturnType = "TOTAL_RETURN" | "PRICE_RETURN";

export type BenchmarkCurrencyPolicy = "NATIVE" | "PORTFOLIO_REPORTING_CURRENCY" | "EXPLICIT_CONVERSION";

export type PerformanceDataStatus = "COMPLETE" | "COMPLETE_WITH_APPROXIMATIONS" | "PARTIAL" | "INCOMPLETE" | "UNAVAILABLE";

export type ReportGenerationStatus = "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";

export interface PerformanceSummarySchema {
  period_return?: number;
  cumulative_return?: number;
  annualized_return?: number;
  beginning_nav?: number;
  ending_nav?: number;
  total_pnl?: number;
  realized_pnl?: number;
  unrealized_pnl?: number;
  net_external_flow?: number;
  total_contributions?: number;
  total_withdrawals?: number;
  benchmark_return?: number;
  active_return_difference?: number;
  performance_data_status: PerformanceDataStatus;
}

export interface PnLComponentSchema {
  id: string;
  component_type: string;
  amount: number;
  currency: string;
  reporting_amount: number;
  source_reference?: string;
  classification_status: string;
  reconciliation_status: string;
}

export interface PnLBreakdownSchema {
  total_pnl?: number;
  realized_pnl?: number;
  unrealized_pnl?: number;
  fees?: number;
  dividends?: number;
  interest?: number;
  currency_fx?: number;
  other_pnl?: number;
  reconciliation_status: string;
  components: PnLComponentSchema[];
}

export interface CashFlowSummarySchema {
  total_contributions: number;
  total_withdrawals: number;
  net_external_flow: number;
  total_flow_count: number;
  cash_flow_timing_policy: string;
}

export interface BenchmarkSummarySchema {
  benchmark_id?: string;
  benchmark_name?: string;
  benchmark_return_type: string;
  period_return?: number;
  cumulative_return?: number;
  active_return_difference?: number;
  currency?: string;
  aligned_observation_count: number;
  unmatched_dates_count: number;
  alignment_status: string;
}

export interface ReturnObservationSchema {
  id: string;
  observation_start: string;
  observation_end: string;
  beginning_value: number;
  ending_value: number;
  external_contributions: number;
  external_withdrawals: number;
  periodic_return?: number;
  cumulative_return?: number;
  annualized_return?: number;
  methodology: string;
  observation_status: string;
  source_snapshot_id?: string;
  calculation_metadata: Record<string, any>;
}

export interface BenchmarkObservationSchema {
  id: string;
  benchmark_id: string;
  observation_date: string;
  benchmark_level: number;
  periodic_return?: number;
  cumulative_return?: number;
  currency: string;
  return_type: string;
  source_reference?: string;
  observation_status: string;
}

export interface PerformanceCaveatSchema {
  id: string;
  caveat_category: string;
  severity: "INFO" | "WARNING" | "CRITICAL";
  affected_start_date?: string;
  affected_end_date?: string;
  affected_metric: string;
  explanation: string;
  source_references: string[];
  affects_completeness: boolean;
}

export interface PerformanceArtifactSchema {
  id: string;
  artifact_type: "PDF" | "HTML" | "CSV" | "JSON";
  storage_reference: string;
  content_hash: string;
  content_type: string;
  file_size: number;
  content_data?: string;
  generated_at: string;
}

export interface CanonicalPerformanceReport {
  report_id: string;
  report_type: string;
  report_schema_version: string;
  report_version: number;
  portfolio: {
    portfolio_id: string;
    reporting_currency: string;
  };
  reporting_period: {
    start_date: string;
    end_date: string;
    reporting_currency: string;
  };
  methodology: {
    return_methodology: string;
    benchmark_methodology: string;
    cash_flow_timing: string;
    day_count_convention: string;
  };
  performance_summary: PerformanceSummarySchema;
  pnl_breakdown: PnLBreakdownSchema;
  cash_flows: CashFlowSummarySchema;
  benchmark: BenchmarkSummarySchema;
  return_observations: ReturnObservationSchema[];
  benchmark_observations: BenchmarkObservationSchema[];
  caveats: PerformanceCaveatSchema[];
  source_manifest: Record<string, any>;
  artifacts: PerformanceArtifactSchema[];
  generated_at: string;
  created_by: string;
}

export interface PerformanceReportRunResponse {
  id: string;
  configuration_id?: string;
  portfolio_id: string;
  benchmark_id?: string;
  reporting_start_date: string;
  reporting_end_date: string;
  generated_at: string;
  generation_status: ReportGenerationStatus;
  performance_data_status: PerformanceDataStatus;
  report_version: number;
  reporting_currency: string;
  idempotency_key: string;
  beginning_nav?: number;
  ending_nav?: number;
  period_return?: number;
  cumulative_return?: number;
  annualized_return?: number;
  total_pnl?: number;
  realized_pnl?: number;
  unrealized_pnl?: number;
  net_external_flow?: number;
  benchmark_return?: number;
  active_return_difference?: number;
  artifacts: PerformanceArtifactSchema[];
}

export interface PerformanceIntegrityVerificationResponse {
  artifact_id: string;
  stored_sha256: string;
  computed_sha256: string;
  is_valid: boolean;
  verified_at: string;
}
