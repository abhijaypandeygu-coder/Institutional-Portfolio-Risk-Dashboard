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
