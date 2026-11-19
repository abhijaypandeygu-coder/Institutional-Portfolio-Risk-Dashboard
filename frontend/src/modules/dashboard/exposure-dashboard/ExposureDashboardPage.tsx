import React, { useState, useEffect } from 'react';
import {
  ConsolidatedExposureDashboardResponse,
  ExposureDrillDownResponse,
  PositionSideFilter,
} from '../../../types/dashboard';
import { SectorAllocationTable } from './components/SectorAllocationTable';
import { InstrumentAllocationTable } from './components/InstrumentAllocationTable';
import { PortfolioAllocationCard } from './components/PortfolioAllocationCard';

interface ExposureDashboardPageProps {
  portfolioId: string;
}

export const ExposureDashboardPage: React.FC<ExposureDashboardPageProps> = ({ portfolioId }) => {
  const [data, setData] = useState<ConsolidatedExposureDashboardResponse | null>(null);
  const [drillData, setDrillData] = useState<ExposureDrillDownResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [sideFilter, setSideFilter] = useState<PositionSideFilter>('ALL');

  const fetchDashboard = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/v1/dashboard/portfolios/${portfolioId}/exposure-dashboard?position_side=${sideFilter}`
      );
      if (!res.ok) {
        throw new Error(`Failed to fetch exposure dashboard: ${res.statusText}`);
      }
      const json: ConsolidatedExposureDashboardResponse = await res.json();
      setData(json);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDrillDownSector = async (sectorId: string) => {
    try {
      const res = await fetch(
        `/api/v1/dashboard/portfolios/${portfolioId}/exposure-dashboard/drilldown?level=SECTOR&sector_id=${sectorId}`
      );
      if (res.ok) {
        const json: ExposureDrillDownResponse = await res.json();
        setDrillData(json);
      }
    } catch (err) {
      console.error('Failed to drill down to sector:', err);
    }
  };

  const handleResetBreadcrumbs = () => {
    setDrillData(null);
  };

  useEffect(() => {
    fetchDashboard();
  }, [portfolioId, sideFilter]);

  if (isLoading && !data) {
    return (
      <div className="flex items-center justify-center p-12 text-muted">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mr-3"></div>
        <span>Retrieving authoritative exposure aggregations...</span>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="p-6 bg-negative-soft/40 border border-negative/20 rounded-lg text-negative">
        <h2 className="text-base font-semibold mb-1">Exposure Dashboard Unavailable</h2>
        <p className="text-sm">{error}</p>
        <button
          onClick={fetchDashboard}
          className="mt-4 px-3 py-1.5 bg-negative-soft hover:bg-rose-700 text-white rounded text-xs font-medium"
        >
          Retry Connection
        </button>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-6">
      {/* Header & Global Filters */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b border-line">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-xl font-bold  text-ink">M13.03 — Exposure Dashboard</h1>
            <span className="text-xs px-2 py-0.5 rounded bg-brand-soft border border-brand/20 text-brand font-sans">
              {data.portfolio_id}
            </span>
          </div>
          <p className="text-xs text-muted mt-1">
            Capital and risk allocation across sectors, ranked instruments, and cash balances.
          </p>
        </div>

        {/* Side Filter */}
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-1 bg-surface border border-line p-1 rounded">
            {(['ALL', 'LONG', 'SHORT'] as PositionSideFilter[]).map((side) => (
              <button
                key={side}
                onClick={() => setSideFilter(side)}
                className={`px-3 py-1 rounded text-xs font-medium transition ${
                  sideFilter === side
                    ? 'bg-brand text-white'
                    : 'text-muted hover:text-secondary'
                }`}
              >
                {side}
              </button>
            ))}
          </div>
          <button
            onClick={fetchDashboard}
            className="px-3 py-1.5 bg-subtle hover:bg-hover text-secondary rounded text-xs font-medium border border-line-strong"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Drill-down Breadcrumb Banner if active */}
      {drillData && (
        <div className="p-3 bg-brand-soft/40 border border-brand/20 rounded-lg flex items-center justify-between text-xs text-brand">
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-secondary">Hierarchy:</span>
            {drillData.breadcrumbs.map((b, i) => (
              <React.Fragment key={b.id}>
                {i > 0 && <span>&gt;</span>}
                <span className={i === drillData.breadcrumbs.length - 1 ? 'font-bold text-ink' : 'underline cursor-pointer'}>
                  {b.name}
                </span>
              </React.Fragment>
            ))}
          </div>
          <button
            onClick={handleResetBreadcrumbs}
            className="text-xs underline text-brand hover:text-brand"
          >
            Back to Full Portfolio View
          </button>
        </div>
      )}

      {/* Section 1: Portfolio Capital Allocation & Cash Composition */}
      <PortfolioAllocationCard summary={data.allocation_summary} />

      {/* Section 2: Sector Allocation Table */}
      <SectorAllocationTable
        summary={data.sector_summary}
        onSelectSector={handleDrillDownSector}
      />

      {/* Section 3: Ranked Instrument Holdings Table */}
      <InstrumentAllocationTable
        holdings={drillData ? drillData.holdings : data.instrument_summary.all_ranked_holdings}
        reportingCurrency={data.base_currency}
      />
    </div>
  );
};
