import React, { useState } from 'react';
import { VaRMetricCardData } from '../../../../types/dashboard';
import { formatCurrency, formatPercentage } from '../../../../utils/financialFormatting';

interface VaRCardProps {
  data: VaRMetricCardData;
  onMethodologyClick?: () => void;
}

export const VaRCard: React.FC<VaRCardProps> = ({ data, onMethodologyClick }) => {
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
            <span className="text-sm font-semibold text-slate-300">Value at Risk (VaR)</span>
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
              {formatCurrency(data.value, data.currency)}
            </div>
          ) : (
            <div className="text-xl font-medium text-slate-500">Unavailable</div>
          )}
          {data.percentage_of_nav !== null && data.percentage_of_nav !== undefined && (
            <div className="text-sm text-slate-400 mt-0.5">
              {formatPercentage(data.percentage_of_nav)} of Portfolio NAV
            </div>
          )}
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs text-slate-400 my-3 py-2 border-y border-slate-800/80">
          <div>
            <span className="text-slate-500 block">Confidence</span>
            <span className="font-medium text-slate-300">{data.confidence_display}</span>
          </div>
          <div>
            <span className="text-slate-500 block">Horizon</span>
            <span className="font-medium text-slate-300">{data.horizon_display}</span>
          </div>
          <div className="col-span-2 mt-1">
            <span className="text-slate-500 block">Methodology</span>
            <span className="font-medium text-slate-300 truncate block">{data.methodology}</span>
          </div>
        </div>
      </div>

      <div>
        <button
          onClick={() => {
            setShowDetails(!showDetails);
            if (onMethodologyClick) onMethodologyClick();
          }}
          className="text-xs text-blue-400 hover:text-blue-300 flex items-center justify-between w-full pt-1"
        >
          <span>{showDetails ? 'Hide Assumptions' : 'Inspect Methodology'}</span>
          <span>{showDetails ? '▲' : '▼'}</span>
        </button>

        {showDetails && data.methodology_details && (
          <div className="mt-3 p-3 bg-slate-950 rounded border border-slate-800 text-xs text-slate-300 space-y-1">
            <div><strong className="text-slate-400">Return Definition:</strong> {data.methodology_details.return_definition}</div>
            <div><strong className="text-slate-400">Estimation Window:</strong> {data.methodology_details.lookback_window} days</div>
            <div><strong className="text-slate-400">Observation Freq:</strong> {data.methodology_details.observation_frequency}</div>
            <div><strong className="text-slate-400">Model Version:</strong> {data.methodology_details.model_version}</div>
            <div className="text-slate-400 pt-1 italic">{data.methodology_details.assumptions_summary}</div>
          </div>
        )}
      </div>
    </div>
  );
};
