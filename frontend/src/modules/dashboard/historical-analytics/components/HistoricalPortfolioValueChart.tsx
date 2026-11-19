import React from 'react';
import { HistoricalPortfolioValueResponse } from '../../../../types/dashboard';

interface HistoricalPortfolioValueChartProps {
  data?: HistoricalPortfolioValueResponse | null;
  onSelectTimestamp?: (timestamp: string) => void;
}

export const HistoricalPortfolioValueChart: React.FC<HistoricalPortfolioValueChartProps> = ({
  data,
  onSelectTimestamp,
}) => {
  if (!data || !data.observations || data.observations.length === 0) {
    return (
      <div className="bg-surface border border-line rounded-lg p-6 text-center text-muted">
        No authoritative historical portfolio snapshot records found for the selected horizon.
      </div>
    );
  }

  const { observations, summary_kpis, base_currency } = data;
  const values = observations.map((o) => o.value ?? 0);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const range = maxVal - minVal > 0 ? maxVal - minVal : 1;

  return (
    <div className="bg-surface border border-line rounded-lg p-5 shadow-sm text-ink">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4 border-b border-line pb-3">
        <div>
          <h3 className="text-base font-semibold text-ink flex items-center gap-2">
            Historical Portfolio Valuation (NAV)
            <span className="text-xs font-normal px-2 py-0.5 rounded bg-subtle text-secondary">
              Source: M05.07 / M05.03
            </span>
          </h3>
          <p className="text-xs text-muted mt-0.5">
            Preserved historical valuations without interpolation or forward-filling
          </p>
        </div>

        {/* KPI Strip */}
        <div className="flex items-center gap-6 text-right">
          <div>
            <div className="text-xs text-muted">Starting NAV</div>
            <div className="text-sm font-semibold text-secondary">
              {summary_kpis.starting_nav.toLocaleString(undefined, { minimumFractionDigits: 2 })} {base_currency}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted">Ending NAV</div>
            <div className="text-sm font-semibold text-secondary">
              {summary_kpis.ending_nav.toLocaleString(undefined, { minimumFractionDigits: 2 })} {base_currency}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted">Total Return</div>
            <div
              className={`text-sm font-semibold ${
                summary_kpis.total_return_pct >= 0 ? 'text-positive' : 'text-negative'
              }`}
            >
              {summary_kpis.total_return_pct >= 0 ? '+' : ''}
              {summary_kpis.total_return_pct.toFixed(2)}%
            </div>
          </div>
        </div>
      </div>

      {/* SVG Sparkline / Interactive Line Plot */}
      <div className="relative h-64 w-full pt-4 pb-2">
        <svg className="w-full h-full overflow-visible" viewBox="0 0 1000 200" preserveAspectRatio="none">
          {/* Grid lines */}
          <line x1="0" y1="20" x2="1000" y2="20" stroke="#d2d2d7" strokeDasharray="3 3" />
          <line x1="0" y1="100" x2="1000" y2="100" stroke="#d2d2d7" strokeDasharray="3 3" />
          <line x1="0" y1="180" x2="1000" y2="180" stroke="#d2d2d7" strokeDasharray="3 3" />

          {/* Value Area / Polyline */}
          <polyline
            fill="none"
            stroke="#6366f1"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            points={observations
              .map((obs, idx) => {
                const x = (idx / (observations.length - 1 || 1)) * 1000;
                const normalized = ((obs.value ?? 0) - minVal) / range;
                const y = 180 - normalized * 160;
                return `${x},${y}`;
              })
              .join(' ')}
          />

          {/* Clickable Observation Data Points */}
          {observations.map((obs, idx) => {
            const x = (idx / (observations.length - 1 || 1)) * 1000;
            const normalized = ((obs.value ?? 0) - minVal) / range;
            const y = 180 - normalized * 160;
            return (
              <g
                key={obs.observation_id}
                className="cursor-pointer group"
                onClick={() => onSelectTimestamp?.(obs.effective_at)}
              >
                <circle
                  cx={x}
                  cy={y}
                  r="4"
                  className="fill-indigo-500 hover:fill-emerald-400 transition-colors"
                />
              </g>
            );
          })}
        </svg>
      </div>

      {/* Timeline Labels */}
      <div className="flex justify-between text-xs text-muted mt-2 px-1">
        <span>{new Date(observations[0].effective_at).toLocaleDateString()}</span>
        <span>Click any observation node to inspect Point-in-Time State</span>
        <span>{new Date(observations[observations.length - 1].effective_at).toLocaleDateString()}</span>
      </div>
    </div>
  );
};
