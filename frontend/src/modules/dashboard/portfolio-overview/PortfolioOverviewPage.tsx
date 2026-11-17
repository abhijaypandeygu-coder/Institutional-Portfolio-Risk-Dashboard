import React, { useState, useEffect } from 'react';
import { PortfolioOverviewResponse } from '../../../types/dashboard';
import { MetricCard } from '../shared/MetricCard';
import { DataFreshnessPanel } from './DataFreshnessPanel';
import { ExposureOverviewSection } from './ExposureOverviewSection';
import { PortfolioSummaryTable } from './PortfolioSummaryTable';
import { formatUtcTimestamp } from '../../../utils/financialFormatting';

interface PortfolioOverviewPageProps {
  portfolioId: string;
  apiBaseUrl?: string;
  onNavigateDetail?: (moduleCode: string) => void;
}

export const PortfolioOverviewPage: React.FC<PortfolioOverviewPageProps> = ({
  portfolioId,
  apiBaseUrl = '/api/v1',
  onNavigateDetail,
}) => {
  const [data, setData] = useState<PortfolioOverviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchOverview = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${apiBaseUrl}/dashboard/portfolios/${portfolioId}/overview`);
      if (!resp.ok) {
        throw new Error(`Failed to load overview: HTTP ${resp.status}`);
      }
      const json = await resp.json();
      setData(json);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Unknown network error');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchOverview();
  }, [portfolioId]);

  if (isLoading && !data) {
    return (
      <div className="p-8 text-center text-slate-500">
        <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900 mb-2"></div>
        <p className="text-sm">Loading authoritative portfolio overview...</p>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="p-6 bg-rose-50 border border-rose-200 rounded-lg text-rose-800 m-6">
        <h3 className="font-semibold text-sm">Failed to Load Portfolio Overview</h3>
        <p className="text-xs mt-1">{error}</p>
        <button
          onClick={fetchOverview}
          className="mt-3 px-3 py-1 bg-rose-600 text-white rounded text-xs hover:bg-rose-700"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* 1. Header with Portfolio Context */}
      <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-xl font-bold text-slate-900">
              {data.portfolio.portfolio_name}
            </h1>
            <span className="text-xs px-2 py-0.5 rounded bg-blue-100 text-blue-800 font-medium">
              {data.portfolio.portfolio_type}
            </span>
            <span className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-600 font-medium">
              Base: {data.portfolio.base_currency}
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            ID: <span className="font-mono">{data.portfolio.portfolio_id}</span> | Strategy:{' '}
            {data.portfolio.strategy} | Benchmark: {data.portfolio.benchmark}
          </p>
        </div>

        <div className="text-right text-xs text-slate-500">
          <div>Valuation As of: {formatUtcTimestamp(data.total_nav.as_of)}</div>
          <div className="text-[11px] text-slate-400">Generated: {formatUtcTimestamp(data.generated_at)}</div>
        </div>
      </div>

      {/* 2. Data Quality & Freshness Summary */}
      <DataFreshnessPanel
        freshness={data.freshness}
        onRefresh={fetchOverview}
        isLoading={isLoading}
      />

      {/* 3. Core Overview KPI Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <MetricCard
          metric={data.total_nav}
          onClick={() => onNavigateDetail?.('valuation')}
        />
        <MetricCard
          metric={data.intraday_pnl}
          secondaryComparison={data.intraday_pnl_pct ? data.intraday_pnl_pct.value_display : undefined}
          onClick={() => onNavigateDetail?.('performance')}
        />
        <MetricCard
          metric={data.unrealized_pnl}
          onClick={() => onNavigateDetail?.('valuation')}
        />
        <MetricCard
          metric={data.realized_pnl}
          onClick={() => onNavigateDetail?.('performance')}
        />
        <MetricCard
          metric={data.total_pnl}
          onClick={() => onNavigateDetail?.('performance')}
        />
        <MetricCard
          metric={data.exposure.gross_exposure}
          secondaryComparison={
            data.exposure.gross_exposure_pct_nav
              ? `${data.exposure.gross_exposure_pct_nav.value_display} NAV`
              : undefined
          }
          onClick={() => onNavigateDetail?.('exposures')}
        />
      </div>

      {/* 4. Combined Exposure Summary Section */}
      <ExposureOverviewSection
        exposure={data.exposure}
        onNavigateDetail={onNavigateDetail}
      />

      {/* 5. Tabular Summary */}
      <PortfolioSummaryTable rows={data.summary_table_rows} />
    </div>
  );
};
