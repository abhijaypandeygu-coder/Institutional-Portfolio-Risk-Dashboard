import React, { useState } from 'react';
import { VolatilityMetricCardData } from '../../../../types/dashboard';
import { formatPercentage } from '../../../../utils/financialFormatting';

interface VolatilityCardProps {
  data: VolatilityMetricCardData;
}

export const VolatilityCard: React.FC<VolatilityCardProps> = ({ data }) => {
  const [showDetails, setShowDetails] = useState(false);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'VALID':
        return 'text-positive bg-positive-soft/40 border-positive/20';
      case 'STALE':
        return 'text-warning bg-warning-soft/40 border-warning/20';
      case 'ERROR':
      case 'INVALID':
        return 'text-negative bg-negative-soft/40 border-negative/20';
      default:
        return 'text-muted bg-subtle border-line-strong';
    }
  };

  return (
    <div className="bg-surface border border-line rounded-lg p-5 flex flex-col justify-between hover:border-line-strong transition">
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <span className="text-sm font-semibold text-secondary">Portfolio Volatility</span>
            <span className="text-xs px-2 py-0.5 rounded bg-subtle text-muted font-sans">
              {data.source_module}
            </span>
          </div>
          <span className={`text-xs px-2 py-0.5 rounded border font-medium ${getStatusColor(data.status)}`}>
            {data.status}
          </span>
        </div>

        <div className="mb-2">
          {data.value !== null && data.value !== undefined ? (
            <div className="text-2xl font-bold  text-ink">
              {formatPercentage(data.value)}
            </div>
          ) : (
            <div className="text-xl font-medium text-muted">Unavailable</div>
          )}
          <div className="text-sm text-muted mt-0.5">
            {data.volatility_type} • {data.is_annualized ? 'Annualized Basis' : 'Periodic Basis'}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs text-muted my-3 py-2 border-y border-line/80">
          <div>
            <span className="text-muted block">Lookback Window</span>
            <span className="font-medium text-secondary">{data.lookback_window} trading days</span>
          </div>
          <div>
            <span className="text-muted block">Frequency</span>
            <span className="font-medium text-secondary">{data.return_frequency}</span>
          </div>
          <div className="col-span-2 mt-1">
            <span className="text-muted block">Estimator</span>
            <span className="font-medium text-secondary">{data.estimator}</span>
          </div>
        </div>
      </div>

      <div>
        <button
          onClick={() => setShowDetails(!showDetails)}
          className="text-xs text-brand hover:text-brand flex items-center justify-between w-full pt-1"
        >
          <span>{showDetails ? 'Hide Assumptions' : 'Inspect Estimator Details'}</span>
          <span>{showDetails ? '▲' : '▼'}</span>
        </button>

        {showDetails && data.methodology_details && (
          <div className="mt-3 p-3 bg-canvas rounded border border-line text-xs text-secondary space-y-1">
            <div><strong className="text-muted">Estimator:</strong> {data.methodology_details.calculation_method}</div>
            <div><strong className="text-muted">Periods/Year:</strong> {data.methodology_details.periods_per_year}</div>
            <div><strong className="text-muted">Annualization Factor:</strong> √{data.methodology_details.periods_per_year} ({data.methodology_details.annualization_factor.toFixed(4)})</div>
            <div><strong className="text-muted">Sample Count:</strong> {data.methodology_details.sample_count} observations</div>
          </div>
        )}
      </div>
    </div>
  );
};
