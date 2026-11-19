import React, { useState, useEffect } from 'react';
import { PortfolioOverviewResponse } from '../../../types/dashboard';
import { MetricCard } from '../shared/MetricCard';
import { DataFreshnessPanel } from './DataFreshnessPanel';
import { ExposureOverviewSection } from './ExposureOverviewSection';
import { PortfolioSummaryTable } from './PortfolioSummaryTable';
import { formatUtcTimestamp } from '../../../utils/financialFormatting';

interface PortfolioOverviewPageProps {
  portfolioId?: string;
  apiBaseUrl?: string;
  onNavigateDetail?: (moduleCode: string) => void;
}

export const PortfolioOverviewPage: React.FC<PortfolioOverviewPageProps> = ({
  portfolioId: initialPortfolioId,
  apiBaseUrl = '/api/v1',
  onNavigateDetail,
}) => {
  const [activePortfolioId, setActivePortfolioId] = useState<string>('');
  const [availablePortfolios, setAvailablePortfolios] = useState<Array<{ portfolio_id: string; portfolio_name: string }>>([]);
  const [data, setData] = useState<PortfolioOverviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialPortfolioId && initialPortfolioId !== activePortfolioId) {
      setActivePortfolioId(initialPortfolioId);
      fetchOverview(initialPortfolioId);
    }
  }, [initialPortfolioId]);

  // 1. Fetch available portfolios on mount to resolve valid portfolio IDs dynamically
  useEffect(() => {
    let isMounted = true;
    const fetchPortfolios = async () => {
      try {
        const res = await fetch(`${apiBaseUrl}/portfolios?limit=20`);
        if (res.ok) {
          const list = await res.json();
          if (Array.isArray(list) && list.length > 0 && isMounted) {
            setAvailablePortfolios(list);
            const exists = initialPortfolioId && list.some((p: any) => p.portfolio_id === initialPortfolioId);
            const selectedId = exists ? (initialPortfolioId as string) : list[0].portfolio_id;
            setActivePortfolioId(selectedId);
            fetchOverview(selectedId);
          }
        }
      } catch (err) {
        console.error('Failed to load portfolio dropdown list', err);
      }
    };
    fetchPortfolios();
    return () => { isMounted = false; };
  }, [apiBaseUrl]);

  const fetchOverview = async (targetId: string) => {
    if (!targetId) return;
    setIsLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${apiBaseUrl}/dashboard/portfolios/${targetId}/overview`);
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

  const handlePortfolioChange = (newId: string) => {
    setActivePortfolioId(newId);
    fetchOverview(newId);
  };

  if (isLoading && !data) {
    return (
      <div className="p-8 text-center text-muted">
        <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-line mb-2"></div>
        <p className="text-sm">Loading authoritative portfolio overview...</p>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="p-6 bg-rose-50 border border-rose-200 rounded-lg text-negative m-6">
        <h3 className="font-semibold text-sm">Failed to Load Portfolio Overview</h3>
        <p className="text-xs mt-1">{error}</p>
        <div className="mt-3 flex gap-2">
          <button
            onClick={() => fetchOverview(activePortfolioId)}
            className="px-3 py-1 bg-rose-600 text-white rounded text-xs hover:bg-rose-700"
          >
            Retry
          </button>
          {availablePortfolios.length > 0 && (
            <select
              value={activePortfolioId}
              onChange={(e) => handlePortfolioChange(e.target.value)}
              className="text-xs border border-line-strong rounded px-2 py-1 bg-white text-ink"
            >
              {availablePortfolios.map((p) => (
                <option key={p.portfolio_id} value={p.portfolio_id}>
                  {p.portfolio_name} ({p.portfolio_id})
                </option>
              ))}
            </select>
          )}
        </div>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* 1. Header with Portfolio Context */}
      <div className="bg-white border border-line rounded-lg p-5 shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-xl font-bold text-ink">
              {data.portfolio.portfolio_name}
            </h1>
            <span className="text-xs px-2 py-0.5 rounded bg-blue-100 text-brand font-medium">
              {data.portfolio.portfolio_type}
            </span>
            <span className="text-xs px-2 py-0.5 rounded bg-subtle text-secondary font-medium">
              Base: {data.portfolio.base_currency}
            </span>
          </div>
          <p className="text-xs text-muted mt-1">
            ID: <span className="font-sans">{data.portfolio.portfolio_id}</span> | Strategy:{' '}
            {data.portfolio.strategy} | Benchmark: {data.portfolio.benchmark}
          </p>
        </div>

        <div className="text-right text-xs text-muted flex flex-col items-end gap-1">
          {availablePortfolios.length > 0 && (
            <select
              value={activePortfolioId}
              onChange={(e) => handlePortfolioChange(e.target.value)}
              className="text-xs border border-line-strong rounded px-2 py-1 bg-white text-ink"
            >
              {availablePortfolios.map((p) => (
                <option key={p.portfolio_id} value={p.portfolio_id}>
                  {p.portfolio_name} ({p.portfolio_id})
                </option>
              ))}
            </select>
          )}
          <div>Valuation As of: {formatUtcTimestamp(data.total_nav.as_of)}</div>
          <div className="text-[11px] text-muted">Generated: {formatUtcTimestamp(data.generated_at)}</div>
        </div>
      </div>

      {/* 2. Data Quality & Freshness Summary */}
      <DataFreshnessPanel
        freshness={data.freshness}
        onRefresh={() => fetchOverview(activePortfolioId)}
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
