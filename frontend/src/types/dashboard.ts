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

// ===========================================================================
// M13.03 — Exposure Dashboard Contracts
// ===========================================================================

export type PositionSideFilter = 'ALL' | 'LONG' | 'SHORT';
export type HierarchyLevel = 'PORTFOLIO' | 'SECTOR' | 'INDUSTRY' | 'INSTRUMENT';

export interface SectorAllocationRow {
  sector_id: string;
  sector_name: string;
  classification_scheme: string;
  reporting_currency: string;
  net_market_value: number;
  long_market_value: number;
  short_market_value: number;
  gross_market_value: number;
  nav_weight_pct?: number | null;
  gross_weight_pct?: number | null;
  instrument_count: number;
  is_unclassified: boolean;
  data_quality_status: string;
}

export interface SectorAllocationSummary {
  portfolio_id: string;
  as_of: string;
  reporting_currency: string;
  total_sectors_count: number;
  total_long_exposure: number;
  total_short_exposure: number;
  total_net_exposure: number;
  total_gross_exposure: number;
  unclassified_exposure?: number | null;
  sectors: SectorAllocationRow[];
}

export interface RankedHoldingItem {
  rank: number;
  instrument_id: string;
  symbol: string;
  instrument_name: string;
  exchange_code: string;
  position_side: 'LONG' | 'SHORT';
  quantity: number;
  mark_price: number;
  price_currency: string;
  market_value: number;
  absolute_market_value: number;
  nav_weight_pct?: number | null;
  gross_weight_pct?: number | null;
  sector_name?: string | null;
  industry_name?: string | null;
  valuation_timestamp: string;
  valuation_status: string;
}

export interface InstrumentAllocationSummary {
  portfolio_id: string;
  as_of: string;
  reporting_currency: string;
  total_instruments_count: number;
  long_instruments_count: number;
  short_instruments_count: number;
  total_long_market_value: number;
  total_short_market_value: number;
  total_net_market_value: number;
  total_gross_market_value: number;
  top_long_holdings: RankedHoldingItem[];
  top_short_holdings: RankedHoldingItem[];
  all_ranked_holdings: RankedHoldingItem[];
}

export interface CashBalanceDetail {
  account_id: string;
  currency: string;
  settled_balance: number;
  available_balance: number;
  restricted_balance: number;
  base_equivalent: number;
  fx_rate_to_base: number;
}

export interface PortfolioAllocationSummary {
  portfolio_id: string;
  as_of: string;
  reporting_currency: string;
  total_nav: number;
  total_long_position_value: number;
  total_short_position_value: number;
  net_position_value: number;
  gross_position_exposure: number;
  total_cash_value: number;
  available_cash_value: number;
  restricted_cash_value: number;
  invested_nav_weight_pct: number;
  cash_nav_weight_pct: number;
  gross_exposure_to_nav_ratio: number;
  reconciliation_residual: number;
  reconciliation_status: string;
  cash_balances: CashBalanceDetail[];
}

export interface HierarchyBreadcrumb {
  level: HierarchyLevel;
  id: string;
  name: string;
}

export interface ExposureDrillDownResponse {
  portfolio_id: string;
  as_of: string;
  current_level: HierarchyLevel;
  breadcrumbs: HierarchyBreadcrumb[];
  reporting_currency: string;
  level_name: string;
  market_value: number;
  nav_weight_pct?: number | null;
  long_exposure: number;
  short_exposure: number;
  net_exposure: number;
  gross_exposure: number;
  sub_items: Record<string, unknown>[];
  holdings: RankedHoldingItem[];
}

export interface ConsolidatedExposureDashboardResponse {
  portfolio_id: string;
  portfolio_name: string;
  base_currency: string;
  as_of: string;
  generated_at: string;
  allocation_summary: PortfolioAllocationSummary;
  sector_summary: SectorAllocationSummary;
  instrument_summary: InstrumentAllocationSummary;
  overall_quality_status: string;
  valuation_timestamp: string;
  snapshot_id?: string | null;
  data_quality_notes: string[];
}

// ===========================================================================
// M13.04 — Risk Heatmaps Types
// ===========================================================================

export type HeatmapMetricCategory = 'EXPOSURE' | 'PERFORMANCE' | 'RISK' | 'LIQUIDITY' | 'SCENARIO';

export type HeatmapMetricDirection = 
  | 'HIGHER_IS_RISKIER'
  | 'LOWER_IS_RISKIER'
  | 'POSITIVE_IS_FAVORABLE'
  | 'NEGATIVE_IS_ADVERSE'
  | 'NEUTRAL_CENTERED'
  | 'MAGNITUDE_ONLY';

export type HeatmapScaleType = 'SEQUENTIAL' | 'DIVERGING' | 'QUANTILE' | 'THRESHOLD';

export type HeatmapPaletteType = 'RED_GREEN' | 'BLUES' | 'REDS' | 'COOL_WARM' | 'VIRIDIS' | 'SPECTRAL';

export type HeatmapGrouping = 'NONE' | 'SECTOR' | 'INDUSTRY' | 'SIDE';

export type HeatmapPositionSide = 'ALL' | 'LONG' | 'SHORT';

export interface HeatmapMetricDefinition {
  metric_id: string;
  display_name: string;
  category: HeatmapMetricCategory;
  unit: string;
  semantic_direction: HeatmapMetricDirection;
  default_scale_type: HeatmapScaleType;
  default_palette: HeatmapPaletteType;
  source_module: string;
  description: string;
  is_additive: boolean;
  supports_sector_view: boolean;
  supports_security_view: boolean;
}

export interface HeatmapMetricRegistryResponse {
  metrics: HeatmapMetricDefinition[];
  total_metrics: number;
  as_of: string;
}

export interface ColorScaleConfig {
  scale_type: HeatmapScaleType;
  palette: HeatmapPaletteType;
  min_value?: number | null;
  max_value?: number | null;
  midpoint?: number | null;
  quantile_breaks?: number[] | null;
  threshold_steps?: Record<string, unknown>[] | null;
  clipped_outliers_count: number;
  is_inverted: boolean;
}

export interface HeatmapCell {
  entity_id: string;
  label: string;
  sub_label?: string | null;
  area_metric_id: string;
  area_value: number;
  area_weight_pct?: number | null;
  color_metric_id: string;
  color_metric_value?: number | null;
  formatted_value: string;
  normalized_score?: number | null;
  color_hex?: string | null;
  long_exposure: number;
  short_exposure: number;
  net_exposure: number;
  gross_exposure: number;
  instrument_count: number;
  data_quality_status: string;
  is_outlier_clipped: boolean;
  provenance_source: string;
  metadata?: Record<string, unknown>;
}

export interface SectorHeatmapResponse {
  portfolio_id: string;
  as_of_date: string;
  generated_at: string;
  reporting_currency: string;
  color_metric: HeatmapMetricDefinition;
  area_metric_id: string;
  color_scale: ColorScaleConfig;
  cells: HeatmapCell[];
  total_area_value: number;
  unclassified_cell?: HeatmapCell | null;
  data_quality_summary: Record<string, number>;
}

export interface SecurityGroupNode {
  group_id: string;
  group_name: string;
  group_area_value: number;
  group_area_pct: number;
  cells: HeatmapCell[];
}

export interface SecurityHeatmapResponse {
  portfolio_id: string;
  as_of_date: string;
  generated_at: string;
  reporting_currency: string;
  grouping: HeatmapGrouping;
  side_filter: HeatmapPositionSide;
  color_metric: HeatmapMetricDefinition;
  area_metric_id: string;
  color_scale: ColorScaleConfig;
  cells: HeatmapCell[];
  groups?: SecurityGroupNode[] | null;
  total_securities: number;
  total_area_value: number;
  data_quality_summary: Record<string, number>;
}

export interface DrilldownHoldingRow {
  instrument_id: string;
  symbol: string;
  instrument_name: string;
  sector_name?: string | null;
  industry_name?: string | null;
  side: string;
  quantity: number;
  market_price: number;
  market_value: number;
  weight_pct: number;
  color_metric_value?: number | null;
  formatted_color_metric: string;
  data_quality_status: string;
}

export interface HeatmapDrilldownResponse {
  portfolio_id: string;
  entity_id: string;
  entity_type: string;
  entity_name: string;
  as_of_date: string;
  generated_at: string;
  reporting_currency: string;
  color_metric: HeatmapMetricDefinition;
  area_metric_id: string;
  summary: Record<string, unknown>;
  holdings: DrilldownHoldingRow[];
  total_holdings: number;
  provenance_details: Record<string, unknown>;
}

// ===========================================================================
// M13.05 — Correlation Dashboard Types
// ===========================================================================

export type CorrelationUniverseType = 
  | 'PORTFOLIO_HOLDINGS' 
  | 'SECTOR_GROUP' 
  | 'CUSTOM_SECURITIES' 
  | 'RISK_FACTORS' 
  | 'MIXED';

export type CorrelationSamplingFrequency = 
  | 'ONE_MINUTE' 
  | 'FIVE_MINUTE' 
  | 'FIFTEEN_MINUTE' 
  | 'THIRTY_MINUTE' 
  | 'HOURLY' 
  | 'DAILY' 
  | 'WEEKLY';

export type CorrelationEstimatorType = 'PEARSON' | 'SPEARMAN' | 'KENDALL_TAU_B';

export type CorrelationReturnDefinition = 'LOGARITHMIC' | 'SIMPLE';

export type CorrelationClusteringMethod = 'HIERARCHICAL' | 'K_MEANS';

export type CorrelationHierarchicalLinkage = 'AVERAGE' | 'SINGLE' | 'COMPLETE' | 'WARD';

export type CorrelationMatrixSortOrder = 
  | 'ORIGINAL' 
  | 'ALPHABETICAL' 
  | 'SECTOR' 
  | 'CLUSTER' 
  | 'AVERAGE_CORRELATION';

export type OutlierDetectionReason = 
  | 'HIGH_POSITIVE_CORRELATION'
  | 'STRONG_NEGATIVE_CORRELATION'
  | 'LARGE_CORRELATION_CHANGE'
  | 'SIGN_REVERSAL'
  | 'REGIME_BREAK';

export interface UniverseInstrumentItem {
  instrument_id: string;
  symbol: string;
  instrument_name: string;
  exchange_code: string;
  market: string;
  asset_class: string;
  currency: string;
  sector_name?: string | null;
  industry_name?: string | null;
  is_eligible: boolean;
  data_quality_status: string;
  observation_count: number;
}

export interface UniverseResolveResponse {
  universe_type: CorrelationUniverseType;
  portfolio_id?: string | null;
  total_eligible: number;
  total_excluded: number;
  instruments: UniverseInstrumentItem[];
  warnings: string[];
}

export interface MatrixCellMetadata {
  instrument_a_id: string;
  instrument_b_id: string;
  instrument_a_symbol: string;
  instrument_b_symbol: string;
  correlation?: number | null;
  observation_count: number;
  data_quality_status: string;
  is_statistically_valid: boolean;
  color_hex?: string | null;
}

export interface CorrelationMatrixViewResponse {
  matrix_id: string;
  portfolio_id?: string | null;
  as_of_date: string;
  lookback_days: number;
  frequency: CorrelationSamplingFrequency;
  estimator: CorrelationEstimatorType;
  return_type: CorrelationReturnDefinition;
  dimension: number;
  asset_ids: string[];
  asset_symbols: string[];
  matrix: (number | null)[][];
  psd_status: string;
  min_eigenvalue: number;
  max_eigenvalue: number;
  condition_number?: number | null;
  average_correlation: number;
  median_correlation: number;
  completeness_ratio: number;
  sort_order: CorrelationMatrixSortOrder;
  reordered_symbols: string[];
  pair_metadata: MatrixCellMetadata[];
  warnings: string[];
}

export interface MatrixComparisonResponse {
  portfolio_id?: string | null;
  dimension: number;
  asset_ids: string[];
  asset_symbols: string[];
  current_matrix: (number | null)[][];
  comparison_matrix: (number | null)[][];
  difference_matrix: (number | null)[][];
  average_absolute_change: number;
  largest_positive_change: number;
  largest_negative_change: number;
  warnings: string[];
}

export interface ClusterSummaryNode {
  cluster_id: number;
  cluster_name: string;
  member_instrument_ids: string[];
  member_symbols: string[];
  dominant_sector?: string | null;
  average_within_correlation: number;
  min_within_correlation: number;
  max_within_correlation: number;
  member_count: number;
}

export interface DendrogramNode {
  node_id: number;
  left_child?: number | null;
  right_child?: number | null;
  distance: number;
  count: number;
  label?: string | null;
}

export interface CorrelationClusteringResponse {
  portfolio_id?: string | null;
  as_of_date: string;
  clustering_method: CorrelationClusteringMethod;
  linkage: CorrelationHierarchicalLinkage;
  distance_formula: string;
  total_instruments: number;
  number_of_clusters: number;
  clusters: ClusterSummaryNode[];
  reordered_symbols: string[];
  dendrogram_leaves: number[];
  dendrogram_nodes?: DendrogramNode[] | null;
  silhouette_score?: number | null;
  warnings: string[];
}

export interface CorrelationOutlierItem {
  instrument_a_id: string;
  instrument_b_id: string;
  instrument_a_symbol: string;
  instrument_b_symbol: string;
  instrument_a_sector?: string | null;
  instrument_b_sector?: string | null;
  current_correlation: number;
  reference_correlation?: number | null;
  delta_correlation?: number | null;
  detection_reason: OutlierDetectionReason;
  threshold_crossed?: number | null;
  observation_count: number;
  quality_status: string;
  z_score?: number | null;
}

export interface CorrelationOutliersResponse {
  portfolio_id?: string | null;
  as_of_date: string;
  high_positive_pairs: CorrelationOutlierItem[];
  strong_negative_pairs: CorrelationOutlierItem[];
  large_change_pairs: CorrelationOutlierItem[];
  sign_reversal_pairs: CorrelationOutlierItem[];
  total_outliers_flagged: number;
}

export interface ReturnObservationPair {
  observation_date: string;
  return_a: number;
  return_b: number;
}

export interface CorrelationPairDetailResponse {
  instrument_a_id: string;
  instrument_b_id: string;
  instrument_a_symbol: string;
  instrument_b_symbol: string;
  instrument_a_name: string;
  instrument_b_name: string;
  instrument_a_sector?: string | null;
  instrument_b_sector?: string | null;
  correlation: number;
  estimator: CorrelationEstimatorType;
  lookback_days: number;
  frequency: CorrelationSamplingFrequency;
  sample_size: number;
  p_value?: number | null;
  t_statistic?: number | null;
  std_error?: number | null;
  ci_lower_95?: number | null;
  ci_upper_95?: number | null;
  covariance?: number | null;
  volatility_a?: number | null;
  volatility_b?: number | null;
  scatter_points: ReturnObservationPair[];
  least_squares_slope?: number | null;
  least_squares_intercept?: number | null;
  rolling_points: Record<string, unknown>[];
  data_quality_status: string;
  provenance_module: string;
}

export interface CorrelationDashboardPreferenceResponse {
  id: string;
  user_id: string;
  dashboard_name: string;
  default_portfolio_id?: string | null;
  default_universe_type: CorrelationUniverseType;
  default_lookback_days: number;
  sampling_frequency: CorrelationSamplingFrequency;
  correlation_method: CorrelationEstimatorType;
  return_definition: CorrelationReturnDefinition;
  min_observations: number;
  display_configuration: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CorrelationSavedUniverseResponse {
  id: string;
  user_id: string;
  universe_name: string;
  description?: string | null;
  universe_type: CorrelationUniverseType;
  portfolio_id?: string | null;
  member_instrument_ids: string[];
  member_count: number;
  created_at: string;
  updated_at: string;
}

export interface CorrelationInvestigationResponse {
  id: string;
  user_id: string;
  portfolio_id?: string | null;
  instrument_a_id: string;
  instrument_b_id: string;
  correlation_value: number;
  previous_correlation?: number | null;
  correlation_method: CorrelationEstimatorType;
  lookback_days: number;
  sampling_frequency: CorrelationSamplingFrequency;
  observation_count: number;
  detection_reason: OutlierDetectionReason;
  source_result_reference?: string | null;
  user_notes: string;
  status: string;
  created_at: string;
  updated_at: string;
}

// ===========================================================================
// M13.06 — Liquidity Dashboard Contracts
// ===========================================================================

export interface CurrentQuoteItem {
  instrument_id: string;
  symbol: string;
  best_bid?: number | null;
  best_ask?: number | null;
  mid_price?: number | null;
  spread_abs?: number | null;
  spread_rel?: number | null;
  spread_bps?: number | null;
  spread_in_ticks?: number | null;
  tick_size?: number | null;
  quote_condition: 'NORMAL' | 'WIDE' | 'LOCKED' | 'CROSSED' | 'ONE_SIDED' | 'STALE' | 'UNAVAILABLE';
  bid_timestamp?: string | null;
  ask_timestamp?: string | null;
  observation_timestamp?: string | null;
  venue?: string | null;
}

export interface HistoricalSpreadPoint {
  timestamp: string;
  spread_bps?: number | null;
  spread_abs?: number | null;
  relative_spread?: number | null;
  is_anomaly: boolean;
}

export interface InstrumentSpreadDetail {
  instrument_id: string;
  symbol: string;
  current_quote: CurrentQuoteItem;
  avg_spread_bps_30d?: number | null;
  min_spread_bps_30d?: number | null;
  max_spread_bps_30d?: number | null;
  spread_percentile?: number | null;
  historical_series: HistoricalSpreadPoint[];
}

export interface DepthLevelItem {
  level_index: number;
  price: number;
  quantity: number;
  notional: number;
  distance_bps: number;
  order_count?: number | null;
}

export interface OrderBookDepthLadder {
  instrument_id: string;
  symbol: string;
  snapshot_timestamp: string;
  bids: DepthLevelItem[];
  asks: DepthLevelItem[];
  total_bid_quantity: number;
  total_ask_quantity: number;
  total_bid_notional: number;
  total_ask_notional: number;
  cumulative_bid_notional: number[];
  cumulative_ask_notional: number[];
  depth_imbalance?: number | null;
  imbalance_status: 'BID_HEAVY' | 'ASK_HEAVY' | 'NEUTRAL' | 'BALANCED';
  is_stale: boolean;
}

export interface ScoreComponentBreakdown {
  name: string;
  score: number;
  weight: number;
  weighted_score: number;
  raw_metric_value?: number | null;
  raw_metric_unit?: string | null;
  status: 'HEALTHY' | 'ADEQUATE' | 'WARNING' | 'CRITICAL';
}

export interface InstrumentLiquidityScore {
  instrument_id: string;
  symbol: string;
  composite_score: number;
  liquidity_bucket: 'TIER_1_HIGH' | 'TIER_2_MODERATE' | 'TIER_3_LOW' | 'TIER_4_ILLIQUID';
  rank?: number | null;
  components: ScoreComponentBreakdown[];
  adv_shares_20d?: number | null;
  adtv_usd_20d?: number | null;
  turnover_ratio?: number | null;
  data_quality_coverage?: number | null;
  calculated_at: string;
}

export interface TargetLiquidationScenario {
  target_percentage: number;
  shares_to_liquidate: number;
  notional_value: number;
  liquidation_direction: 'SELL' | 'BUY';
  order_type_assumed: string;
  participation_rate: number;
  spread_cost_bps: number;
  market_impact_cost_bps: number;
  slippage_cost_bps: number;
  total_cost_bps: number;
  total_cost_usd: number;
  estimated_duration_minutes: number;
  estimated_trading_days: number;
  capacity_exhaustion_pct: number;
  risk_haircut_bps?: number | null;
}

export interface InstrumentLiquidationProfile {
  instrument_id: string;
  symbol: string;
  current_position_shares: number;
  current_position_notional: number;
  position_direction: 'LONG' | 'SHORT' | 'FLAT';
  liquidation_direction: 'SELL' | 'BUY' | 'NONE';
  base_participation_rate: number;
  scenarios: TargetLiquidationScenario[];
}

export interface HoldingLiquiditySummary {
  instrument_id: string;
  symbol: string;
  sector?: string | null;
  position_shares: number;
  position_notional: number;
  weight_pct: number;
  position_direction: 'LONG' | 'SHORT' | 'FLAT';
  spread_bps?: number | null;
  quote_condition: string;
  composite_score?: number | null;
  liquidity_bucket: string;
  depth_imbalance?: number | null;
  full_liquidation_cost_bps?: number | null;
  full_liquidation_cost_usd?: number | null;
  full_liquidation_days?: number | null;
}

export interface PortfolioLiquidityDashboardResponse {
  portfolio_id: string;
  as_of_date: string;
  total_nav: number;
  holdings_count: number;
  weighted_composite_score: number;
  weighted_spread_bps: number;
  total_full_liquidation_cost_usd: number;
  portfolio_liquidation_cost_bps: number;
  max_days_to_liquidate: number;
  low_liquidity_capital_pct: number;
  locked_or_crossed_instruments_count: number;
  severe_imbalance_count: number;
  holdings: HoldingLiquiditySummary[];
}

export interface LiquidityPreferenceResponse {
  id: string;
  user_id: string;
  dashboard_name: string;
  default_portfolio_id?: string | null;
  spread_unit: 'BPS' | 'RELATIVE' | 'ABSOLUTE';
  depth_levels_count: number;
  default_lookback_days: number;
  default_participation_rate: number;
  default_liquidation_scenario: string;
  default_target_percentage: number;
  display_configuration?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface LiquiditySavedViewResponse {
  id: string;
  user_id: string;
  view_name: string;
  description?: string | null;
  portfolio_id?: string | null;
  filters: Record<string, unknown>;
  selected_instrument_ids: string[];
  is_public: boolean;
  created_at: string;
  updated_at: string;
}

export interface LiquidityInvestigationResponse {
  id: string;
  user_id: string;
  portfolio_id?: string | null;
  instrument_id: string;
  investigation_type: string;
  severity: string;
  status: string;
  title: string;
  notes: string;
  metrics_snapshot?: Record<string, unknown> | null;
  resolved_at?: string | null;
  resolved_by?: string | null;
  created_at: string;
  updated_at: string;
}
