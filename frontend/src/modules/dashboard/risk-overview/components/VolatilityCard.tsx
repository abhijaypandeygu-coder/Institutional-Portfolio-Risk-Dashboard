import React, { useState } from 'react';
import { VolatilityMetricCardData } from '../../../types/dashboard';
import { formatPercentage } from '../../../utils/financialFormatting';

interface VolatilityCardProps {
  data: VolatilityMetricCardData;
}

export const VolatilityCard: React.FC<VolatilityCardProps> = ({ data }) => {
  const [showDetails, setShowDetails] = useState(false);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'VALID':
        return 'text-emerald-400 bg-emerald-950/40 border-emerald-800';
      case 'STALE':
        return 'text-amber-400 bg-amber-950/40 border-amber-800';
      case 'ERROR':
      case 'INVALID':
        return 'text-rose-400 bg-rose-950/40 border-rose-800';
      default:
        return 'text-slate-400 bg-slate-800 border-slate-700';
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 flex flex-col justify-between hover:border-slate-700 transition">
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <span className="text-sm font-semibold text-slate-300">Portfolio Volatility</span>
            <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">
              {data.source_module}
            </span>
          </div>
          <span className={`text-xs px-2 py-0.5 rounded border font-medium ${getStatusColor(data.status)}`}>
            {data.status}
          </span>
        </div>

        <div className="mb-2">
          {data.value !== null && data.value !== undefined ? (
            <div className="text-2xl font-bold tracking-tight text-white">
              {formatPercentage(data.value)}
            </div>
          ) : (
            <div className="text-xl font-medium text-slate-500">Unavailable</div>
          )}
          <div className="text-sm text-slate-400 mt-0.5">
            {data.volatility_type} • {data.is_annualized ? 'Annualized Basis' : 'Periodic Basis'}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs text-slate-400 my-3 py-2 border-y border-slate-800/80">
          <div>
            <span className="text-slate-500 block">Lookback Window</span>
            <span className="font-medium text-slate-300">{data.lookback_window} trading days</span>
          </div>
          <div>
            <span className="text-slate-500 block">Frequency</span>
            <span className="font-medium text-slate-300">{data.return_frequency}</span>
          </div>
          <div className="col-span-2 mt-1">
            <span className="text-slate-500 block">Estimator</span>
            <span className="font-medium text-slate-300">{data.estimator}</span>
          </div>
        </div>
      </div>

      <div>
        <button
          onClick={() => setShowDetails(!showDetails)}
          className="text-xs text-blue-400 hover:text-blue-300 flex items-center justify-between w-full pt-1"
        >
          <span>{showDetails ? 'Hide Assumptions' : 'Inspect Estimator Details'}</span>
          <span>{showDetails ? '▲' : '▼'}</span>
        </button>

        {showDetails && data.methodology_details && (
          <div className="mt-3 p-3 bg-slate-950 rounded border border-slate-800 text-xs text-slate-300 space-y-1">
            <div><strong className="text-slate-400">Estimator:</strong> {data.methodology_details.calculation_method}</div>
            <div><strong className="text-slate-400">Periods/Year:</strong> {data.methodology_details.periods_per_year}</div>
            <div><strong className="text-slate-400">Annualization Factor:</strong> √{data.methodology_details.periods_per_year} ({data.methodology_details.annualization_factor.toFixed(4)})</div>
            <div><strong className="text-slate-400">Sample Count:</strong> {data.methodology_details.sample_count} observations</div>
          </div>
        )}
      </div>
    </div>
  );
};
