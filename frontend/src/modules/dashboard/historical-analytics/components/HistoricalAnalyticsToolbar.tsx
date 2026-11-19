import React from 'react';
import {
  HistoricalMode,
} from '../../../../types/dashboard';

interface HistoricalAnalyticsToolbarProps {
  portfolioId: string;
  onPortfolioChange: (id: string) => void;
  lookbackDays: number;
  onLookbackChange: (days: number) => void;
  frequency: string;
  onFrequencyChange: (freq: string) => void;
  historicalMode: HistoricalMode;
  onHistoricalModeChange: (mode: HistoricalMode) => void;
  showEvents: boolean;
  onToggleEvents: (show: boolean) => void;
  onRefresh: () => void;
  isLoading?: boolean;
}

export const HistoricalAnalyticsToolbar: React.FC<HistoricalAnalyticsToolbarProps> = ({
  portfolioId,
  onPortfolioChange,
  lookbackDays,
  onLookbackChange,
  frequency,
  onFrequencyChange,
  historicalMode,
  onHistoricalModeChange,
  showEvents,
  onToggleEvents,
  onRefresh,
  isLoading = false,
}) => {
  return (
    <div className="bg-surface border border-line rounded-lg p-4 flex flex-wrap items-center justify-between gap-4 mb-6 text-ink shadow-sm">
      <div className="flex flex-wrap items-center gap-4">
        {/* Portfolio Selection */}
        <div>
          <label className="block text-xs uppercase  text-muted font-semibold mb-1">
            Portfolio
          </label>
          <select
            value={portfolioId}
            onChange={(e) => onPortfolioChange(e.target.value)}
            className="bg-subtle border border-line-strong text-ink text-sm rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            <option value="PORT-HIST-01">PORT-HIST-01 (Flagship US)</option>
            <option value="PORT-INDIA-01">PORT-INDIA-01 (India Core)</option>
            <option value="PORT-BALANCED">PORT-BALANCED (Global Balanced)</option>
          </select>
        </div>

        {/* Lookback Horizon */}
        <div>
          <label className="block text-xs uppercase  text-muted font-semibold mb-1">
            Horizon
          </label>
          <div className="flex bg-subtle border border-line-strong rounded overflow-hidden">
            {[
              { label: '30D', value: 30 },
              { label: '90D', value: 90 },
              { label: '180D', value: 180 },
              { label: '1Y', value: 365 },
              { label: 'ALL', value: 730 },
            ].map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => onLookbackChange(option.value)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  lookbackDays === option.value
                    ? 'bg-brand text-white'
                    : 'text-muted hover:text-secondary hover:bg-hover'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {/* Sampling Frequency */}
        <div>
          <label className="block text-xs uppercase  text-muted font-semibold mb-1">
            Frequency
          </label>
          <select
            value={frequency}
            onChange={(e) => onFrequencyChange(e.target.value)}
            className="bg-subtle border border-line-strong text-ink text-sm rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            <option value="DAILY">Daily Close (Authoritative)</option>
            <option value="WEEKLY">Weekly Aggregation</option>
          </select>
        </div>

        {/* Historical Mode (Bitemporal) */}
        <div>
          <label className="block text-xs uppercase  text-muted font-semibold mb-1">
            Bitemporal Mode
          </label>
          <select
            value={historicalMode}
            onChange={(e) => onHistoricalModeChange(e.target.value as HistoricalMode)}
            className={`border text-sm rounded px-3 py-1.5 focus:outline-none font-medium ${
              historicalMode === 'AS_KNOWN_AT_TIME'
                ? 'bg-positive-soft/60 border-positive/20 text-positive'
                : 'bg-warning-soft/60 border-warning/20 text-warning'
            }`}
          >
            <option value="AS_KNOWN_AT_TIME">As Known At Time (Point-in-Time Audit)</option>
            <option value="LATEST_RESTATED">Latest Restated (Current View)</option>
          </select>
        </div>
      </div>

      {/* Action Controls */}
      <div className="flex items-center gap-3">
        {/* Toggle Event Overlays */}
        <label className="inline-flex items-center gap-2 cursor-pointer text-xs font-medium text-secondary">
          <input
            type="checkbox"
            checked={showEvents}
            onChange={(e) => onToggleEvents(e.target.checked)}
            className="w-4 h-4 text-brand rounded bg-subtle border-line-strong focus:ring-indigo-500"
          />
          Material Events
        </label>

        {/* Refresh Button */}
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="flex items-center gap-2 px-3 py-1.5 bg-brand hover:bg-brand-hover disabled:bg-hover text-white text-xs font-semibold rounded shadow transition-colors"
        >
          {isLoading ? (
            <span className="animate-spin inline-block w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full" />
          ) : (
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          )}
          Refresh
        </button>
      </div>
    </div>
  );
};
