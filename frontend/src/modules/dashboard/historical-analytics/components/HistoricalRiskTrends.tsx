import React from 'react';
import { HistoricalRiskTrendResponse } from '../../../../types/dashboard';

interface HistoricalRiskTrendsProps {
  data?: HistoricalRiskTrendResponse | null;
  selectedMetric: string;
  onMetricChange: (metric: string) => void;
  onSelectTimestamp?: (timestamp: string) => void;
}

export const HistoricalRiskTrends: React.FC<HistoricalRiskTrendsProps> = ({
  data,
  selectedMetric,
  onMetricChange,
  onSelectTimestamp,
}) => {
  return (
    <div className="bg-surface border border-line rounded-lg p-5 shadow-sm text-ink">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4 border-b border-line pb-3">
        <div>
          <h3 className="text-base font-semibold text-ink flex items-center gap-2">
            Quantitative Risk Evolution
            <span className="text-xs font-normal px-2 py-0.5 rounded bg-subtle text-secondary">
              Source: M07 Risk Engine
            </span>
          </h3>
          <p className="text-xs text-muted mt-0.5">
            Model parameters and confidence horizons preserved from authoritative runs
          </p>
        </div>

        {/* Metric Selector */}
        <div className="flex bg-subtle border border-line-strong rounded overflow-hidden">
          {[
            { label: 'VaR (99%)', value: 'VAR' },
            { label: 'Expected Shortfall', value: 'ES' },
            { label: 'Volatility', value: 'VOLATILITY' },
            { label: 'Drawdown', value: 'DRAWDOWN' },
          ].map((m) => (
            <button
              key={m.value}
              type="button"
              onClick={() => onMetricChange(m.value)}
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                selectedMetric === m.value
                  ? 'bg-rose-600 text-white'
                  : 'text-muted hover:text-secondary hover:bg-hover'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {!data || !data.observations || data.observations.length === 0 ? (
        <div className="py-12 text-center text-muted text-sm">
          No authoritative risk observations recorded for {selectedMetric} in this window.
        </div>
      ) : (
        <div>
          {/* Summary Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <div className="bg-canvas/50 p-2.5 rounded border border-line/80">
              <span className="text-xs text-muted">Latest</span>
              <div className="text-sm font-semibold text-negative">
                {data.summary_statistics.latest_value.toLocaleString(undefined, { minimumFractionDigits: 2 })}{' '}
                {data.unit === 'PERCENTAGE' ? '%' : data.currency}
              </div>
            </div>
            <div className="bg-canvas/50 p-2.5 rounded border border-line/80">
              <span className="text-xs text-muted">Peak Risk</span>
              <div className="text-sm font-semibold text-negative">
                {data.summary_statistics.max_value.toLocaleString(undefined, { minimumFractionDigits: 2 })}{' '}
                {data.unit === 'PERCENTAGE' ? '%' : data.currency}
              </div>
            </div>
            <div className="bg-canvas/50 p-2.5 rounded border border-line/80">
              <span className="text-xs text-muted">Average</span>
              <div className="text-sm font-semibold text-secondary">
                {data.summary_statistics.mean_value.toLocaleString(undefined, { minimumFractionDigits: 2 })}{' '}
                {data.unit === 'PERCENTAGE' ? '%' : data.currency}
              </div>
            </div>
            <div className="bg-canvas/50 p-2.5 rounded border border-line/80">
              <span className="text-xs text-muted">Trough Risk</span>
              <div className="text-sm font-semibold text-muted">
                {data.summary_statistics.min_value.toLocaleString(undefined, { minimumFractionDigits: 2 })}{' '}
                {data.unit === 'PERCENTAGE' ? '%' : data.currency}
              </div>
            </div>
          </div>

          {/* SVG Trendline */}
          <div className="relative h-48 w-full pt-2 pb-2">
            <svg className="w-full h-full overflow-visible" viewBox="0 0 1000 160" preserveAspectRatio="none">
              <line x1="0" y1="20" x2="1000" y2="20" stroke="#d2d2d7" strokeDasharray="3 3" />
              <line x1="0" y1="80" x2="1000" y2="80" stroke="#d2d2d7" strokeDasharray="3 3" />
              <line x1="0" y1="140" x2="1000" y2="140" stroke="#d2d2d7" strokeDasharray="3 3" />

              <polyline
                fill="none"
                stroke="#f43f5e"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                points={data.observations
                  .map((obs, idx) => {
                    const x = (idx / (data.observations.length - 1 || 1)) * 1000;
                    const min = data.summary_statistics.min_value;
                    const max = data.summary_statistics.max_value;
                    const range = max - min > 0 ? max - min : 1;
                    const normalized = ((obs.value ?? 0) - min) / range;
                    const y = 140 - normalized * 120;
                    return `${x},${y}`;
                  })
                  .join(' ')}
              />

              {data.observations.map((obs, idx) => {
                const x = (idx / (data.observations.length - 1 || 1)) * 1000;
                const min = data.summary_statistics.min_value;
                const max = data.summary_statistics.max_value;
                const range = max - min > 0 ? max - min : 1;
                const normalized = ((obs.value ?? 0) - min) / range;
                const y = 140 - normalized * 120;
                return (
                  <circle
                    key={obs.observation_id}
                    cx={x}
                    cy={y}
                    r="3.5"
                    className="fill-rose-500 hover:fill-amber-300 cursor-pointer transition-colors"
                    onClick={() => onSelectTimestamp?.(obs.effective_at)}
                  />
                );
              })}
            </svg>
          </div>
        </div>
      )}
    </div>
  );
};
