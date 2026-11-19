import React from 'react';
import { ReportArchiveType, ArchiveStatus } from '../../../../types/reportArchive';

interface Props {
  portfolioId: string;
  setPortfolioId: (val: string) => void;
  reportType: string;
  setReportType: (val: string) => void;
  statusFilter: string;
  setStatusFilter: (val: string) => void;
  runIdFilter: string;
  setRunIdFilter: (val: string) => void;
  onSearch: () => void;
  onReset: () => void;
  onRunDryRun: () => void;
}

export const ArchiveFilterBar: React.FC<Props> = ({
  portfolioId,
  setPortfolioId,
  reportType,
  setReportType,
  statusFilter,
  setStatusFilter,
  runIdFilter,
  setRunIdFilter,
  onSearch,
  onReset,
  onRunDryRun,
}) => {
  return (
    <div className="bg-surface border border-line rounded-lg p-4 mb-6 shadow-sm">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
        <div>
          <label className="block text-xs font-semibold text-muted mb-1">Portfolio</label>
          <input
            type="text"
            placeholder="e.g. PORT-001"
            value={portfolioId}
            onChange={(e) => setPortfolioId(e.target.value)}
            className="w-full bg-subtle border border-line-strong text-secondary text-sm rounded px-3 py-1.5 focus:outline-none focus:border-cyan-500"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-muted mb-1">Report Type</label>
          <select
            value={reportType}
            onChange={(e) => setReportType(e.target.value)}
            className="w-full bg-subtle border border-line-strong text-secondary text-sm rounded px-3 py-1.5 focus:outline-none focus:border-cyan-500"
          >
            <option value="">All Types</option>
            <option value="DAILY_RISK">Daily Risk</option>
            <option value="PORTFOLIO_PERFORMANCE">Portfolio Performance</option>
            <option value="RISK_ATTRIBUTION">Risk Attribution</option>
            <option value="STRESS_TESTING">Stress Testing</option>
            <option value="LIQUIDITY">Liquidity</option>
            <option value="OTHER">Other</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold text-muted mb-1">Archive Status</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="w-full bg-subtle border border-line-strong text-secondary text-sm rounded px-3 py-1.5 focus:outline-none focus:border-cyan-500"
          >
            <option value="">All Statuses</option>
            <option value="AVAILABLE">Available</option>
            <option value="SUPERSEDED">Superseded</option>
            <option value="RESTATED">Restated</option>
            <option value="WITHDRAWN">Withdrawn</option>
            <option value="QUARANTINED">Quarantined</option>
            <option value="EXPIRED">Expired</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold text-muted mb-1">Report Run ID</label>
          <input
            type="text"
            placeholder="e.g. RUN-1042"
            value={runIdFilter}
            onChange={(e) => setRunIdFilter(e.target.value)}
            className="w-full bg-subtle border border-line-strong text-secondary text-sm rounded px-3 py-1.5 focus:outline-none focus:border-cyan-500"
          />
        </div>
      </div>

      <div className="flex justify-between items-center pt-2 border-t border-line">
        <div className="flex gap-2">
          <button
            onClick={onSearch}
            className="bg-brand hover:bg-brand-hover text-white text-xs font-medium px-4 py-1.5 rounded transition"
          >
            Search Archives
          </button>
          <button
            onClick={onReset}
            className="bg-subtle hover:bg-hover text-secondary text-xs font-medium px-3 py-1.5 rounded transition"
          >
            Reset
          </button>
        </div>

        <div>
          <button
            onClick={onRunDryRun}
            className="bg-brand/30 hover:bg-brand-hover/50 text-brand border border-indigo-500/40 text-xs font-medium px-3 py-1.5 rounded transition"
          >
            Retention Policy Dry-Run
          </button>
        </div>
      </div>
    </div>
  );
};
