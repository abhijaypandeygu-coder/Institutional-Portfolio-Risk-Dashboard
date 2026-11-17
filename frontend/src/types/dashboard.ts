/**
 * TypeScript contracts for M13 — Dashboard & Visualization Layer.
 * Mirrors the Pydantic schemas from backend standard response models.
 */

export type QualityStatus = 
  | 'FRESH'
  | 'STALE'
  | 'DELAYED'
  | 'PARTIAL'
  | 'MISSING'
  | 'INVALID'
  | 'NOT_AVAILABLE'
  | 'ERROR';

export type MetricUnit = 'CURRENCY' | 'PERCENTAGE' | 'RATIO' | 'COUNT';

export interface StandardMetricValue {
  metric_code: string;
  metric_name: string;
  value: number | null;
  value_display: string;
  currency?: string | null;
  unit: MetricUnit;
  as_of: string;
  retrieved_at: string;
  quality_status: QualityStatus;
  source_module: string;
  calculation_basis: string;
  is_negative: boolean;
  metadata?: Record<string, unknown>;
}

export interface PortfolioMetadataContext {
  portfolio_id: string;
  portfolio_name: string;
  portfolio_type: string;
  base_currency: string;
  status: string;
  benchmark?: string | null;
  strategy?: string | null;
  owner?: string | null;
  inception_date?: string | null;
}

export interface DataFreshnessSummary {
  overall_status: QualityStatus;
  last_portfolio_snapshot_at?: string | null;
  last_valuation_at?: string | null;
  last_pnl_calculation_at?: string | null;
  last_exposure_calculation_at?: string | null;
  last_market_data_update_at?: string | null;
  market_data_source: string;
  latency_seconds?: number | null;
  is_stale: boolean;
  stale_reason?: string | null;
}

export interface ExposureSummaryDetail {
  gross_exposure: StandardMetricValue;
  net_exposure: StandardMetricValue;
  long_exposure: StandardMetricValue;
  short_exposure: StandardMetricValue;
  gross_exposure_pct_nav?: StandardMetricValue | null;
  net_exposure_pct_nav?: StandardMetricValue | null;
  directional_status: string;
  directional_description: string;
}

export interface NavTrendPoint {
  timestamp: string;
  nav: number;
  currency: string;
}

export interface PnlTrendPoint {
  timestamp: string;
  realized_pnl: number;
  unrealized_pnl: number;
  total_pnl: number;
  currency: string;
}

export interface PortfolioOverviewResponse {
  portfolio: PortfolioMetadataContext;
  freshness: DataFreshnessSummary;
  total_nav: StandardMetricValue;
  intraday_pnl: StandardMetricValue;
  intraday_pnl_pct?: StandardMetricValue | null;
  unrealized_pnl: StandardMetricValue;
  realized_pnl: StandardMetricValue;
  total_pnl: StandardMetricValue;
  exposure: ExposureSummaryDetail;
  nav_trend: NavTrendPoint[];
  pnl_trend: PnlTrendPoint[];
  summary_table_rows: StandardMetricValue[];
  generated_at: string;
}

// ===========================================================================
// M13.02 — Risk Overview Contracts
// ===========================================================================

export type MetricState =
  | 'VALID'
  | 'STALE'
  | 'INCOMPLETE'
  | 'INVALID'
  | 'NOT_SUPPORTED'
  | 'NOT_APPLICABLE'
  | 'PENDING'
  | 'ERROR';

export type VolatilityType = 'REALIZED' | 'FORECAST';

export interface VaRMethodologyDetails {
  method: string;
  return_definition: string;
  confidence_level: number;
  horizon_days: number;
  horizon_label: string;
  lookback_window: number;
  observation_frequency: string;
  valuation_base_type: string;
  distribution_assumption?: string | null;
  model_version: string;
  calculation_timestamp: string;
  assumptions_summary: string;
}

export interface ESMethodologyDetails {
  method: string;
  confidence_level: number;
  horizon_days: number;
  horizon_label: string;
  tail_definition: string;
  tail_weighting_method: string;
  observation_frequency: string;
  estimation_window: number;
  model_version: string;
  calculation_timestamp: string;
}

export interface VolatilityMethodologyDetails {
  volatility_type: VolatilityType;
  calculation_method: string;
  return_frequency: string;
  lookback_window: number;
  annualization_factor: number;
  periods_per_year: number;
  sample_count: number;
  model_version: string;
  calculation_timestamp: string;
}

export interface DrawdownMethodologyDetails {
  measurement_period: string;
  valuation_frequency: string;
  high_water_mark_policy: string;
  nav_basis: string;
  cash_flow_adjusted: boolean;
  calculation_timestamp: string;
}

export interface VaRMetricCardData {
  metric_id: string;
  value: number | null;
  value_display?: string | null;
  currency: string;
  percentage_of_nav?: number | null;
  percentage_display?: string | null;
  confidence_level: number;
  confidence_display: string;
  horizon_days: number;
  horizon_display: string;
  methodology: string;
  status: MetricState;
  calculation_timestamp?: string | null;
  data_quality_status: string;
  source_module: string;
  methodology_details?: VaRMethodologyDetails | null;
}

export interface ExpectedShortfallMetricCardData {
  metric_id: string;
  value: number | null;
  value_display?: string | null;
  currency: string;
  percentage_of_nav?: number | null;
  percentage_display?: string | null;
  confidence_level: number;
  confidence_display: string;
  horizon_days: number;
  horizon_display: string;
  methodology: string;
  status: MetricState;
  calculation_timestamp?: string | null;
  data_quality_status: string;
  source_module: string;
  methodology_details?: ESMethodologyDetails | null;
}

export interface VolatilityMetricCardData {
  metric_id: string;
  value: number | null;
  value_display?: string | null;
  volatility_type: VolatilityType;
  is_annualized: boolean;
  lookback_window: number;
  return_frequency: string;
  estimator: string;
  status: MetricState;
  calculation_timestamp?: string | null;
  data_quality_status: string;
  source_module: string;
  methodology_details?: VolatilityMethodologyDetails | null;
}

export interface DrawdownMetricCardData {
  metric_id: string;
  current_drawdown_pct?: number | null;
  current_drawdown_display?: string | null;
  current_drawdown_amount?: number | null;
  current_drawdown_amount_display?: string | null;
  maximum_drawdown_pct?: number | null;
  maximum_drawdown_display?: string | null;
  maximum_drawdown_amount?: number | null;
  high_water_mark?: number | null;
  peak_date?: string | null;
  trough_date?: string | null;
  recovery_status?: string | null;
  measurement_period: string;
  status: MetricState;
  calculation_timestamp?: string | null;
  data_quality_status: string;
  source_module: string;
  methodology_details?: DrawdownMethodologyDetails | null;
}

export interface VaRESComparisonItem {
  portfolio_id: string;
  reporting_currency: string;
  confidence_level: number;
  horizon_days: number;
  var_monetary_amount?: number | null;
  var_percentage_of_nav?: number | null;
  es_monetary_amount?: number | null;
  es_percentage_of_nav?: number | null;
  tail_excess_amount?: number | null;
  tail_excess_pct?: number | null;
  es_to_var_ratio?: number | null;
  is_compatible: boolean;
  compatibility_note?: string | null;
}

export interface DataQualitySummary {
  overall_status: MetricState;
  last_valuation_timestamp?: string | null;
  last_risk_run_timestamp?: string | null;
  stale_metrics: string[];
  failed_metrics: string[];
  quality_notes: string[];
}

export interface RiskOverviewResponse {
  portfolio_id: string;
  portfolio_name: string;
  base_currency: string;
  as_of: string;
  generated_at: string;
  valuation_nav?: number | null;
  var: VaRMetricCardData;
  expected_shortfall: ExpectedShortfallMetricCardData;
  volatility: VolatilityMetricCardData;
  drawdown: DrawdownMetricCardData;
  var_es_comparison?: VaRESComparisonItem | null;
  quality_summary: DataQualitySummary;
  available_confidence_levels: number[];
  available_horizons_days: number[];
  available_var_methodologies: string[];
  available_volatility_lookbacks: number[];
  available_drawdown_periods: string[];
}

export interface HistoricalTrendPoint {
  observation_date: string;
  value: number;
  percentage?: number | null;
  currency?: string | null;
  methodology?: string | null;
  confidence_level?: number | null;
  horizon_days?: number | null;
  status: MetricState;
}

export interface UnderwaterChartPoint {
  observation_date: string;
  portfolio_nav: number;
  high_water_mark: number;
  drawdown_pct: number;
  drawdown_amount: number;
  is_peak: boolean;
  is_trough: boolean;
  is_recovered: boolean;
  episode_id?: string | null;
}

export interface DrawdownEpisodeSummary {
  episode_id: string;
  peak_date: string;
  trough_date?: string | null;
  recovery_date?: string | null;
  peak_value: number;
  trough_value?: number | null;
  max_decline_pct: number;
  underwater_duration_days?: number | null;
  recovery_duration_days?: number | null;
  status: string;
}

export interface RiskHistoryResponse {
  portfolio_id: string;
  metric: string;
  reporting_currency: string;
  points: HistoricalTrendPoint[];
  underwater_points?: UnderwaterChartPoint[] | null;
  episodes?: DrawdownEpisodeSummary[] | null;
}
