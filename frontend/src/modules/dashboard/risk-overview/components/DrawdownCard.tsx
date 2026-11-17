import React, { useState } from 'react';
import { DrawdownMetricCardData } from '../../../../types/dashboard';
import { formatPercentage, formatCurrency } from '../../../../utils/financialFormatting';

interface DrawdownCardProps {
  data: DrawdownMetricCardData;
}

export const DrawdownCard: React.FC<DrawdownCardProps> = ({ data }) => {
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
            <span className="text-sm font-semibold text-slate-300">Drawdown</span>
            <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">
              {data.source_module}
            </span>
          </div>
          <span className={`text-xs px-2 py-0.5 rounded border font-medium ${getStatusColor(data.status)}`}>
            {data.status}
          </span>
        </div>

        <div className="mb-2">
          {data.current_drawdown_pct !== null && data.current_drawdown_pct !== undefined ? (
            <div className={`text-2xl font-bold tracking-tight ${data.current_drawdown_pct < 0 ? 'text-rose-400' : 'text-white'}`}>
              {formatPercentage(data.current_drawdown_pct)}
            </div>
          ) : (
            <div className="text-xl font-medium text-slate-500">Unavailable</div>
          )}
          <div className="text-sm text-slate-400 mt-0.5">
            Current Drawdown below High-Water Mark
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs text-slate-400 my-3 py-2 border-y border-slate-800/80">
          <div>
            <span className="text-slate-500 block">Maximum Drawdown</span>
            <span className="font-semibold text-rose-300">
              {data.maximum_drawdown_pct !== null && data.maximum_drawdown_pct !== undefined
                ? formatPercentage(data.maximum_drawdown_pct)
                : 'N/A'}
            </span>
          </div>
          <div>
            <span className="text-slate-500 block">Measurement Window</span>
            <span className="font-medium text-slate-300">{data.measurement_period}</span>
          </div>
          <div className="col-span-2 mt-1">
            <span className="text-slate-500 block">Recovery Status</span>
            <span className="font-medium text-amber-300">{data.recovery_status || 'RECOVERING'}</span>
          </div>
        </div>
      </div>

      <div>
        <button
          onClick={() => setShowDetails(!showDetails)}
          className="text-xs text-blue-400 hover:text-blue-300 flex items-center justify-between w-full pt-1"
        >
          <span>{showDetails ? 'Hide Assumptions' : 'Inspect HWM & Window'}</span>
          <span>{showDetails ? '▲' : '▼'}</span>
        </button>

        {showDetails && data.methodology_details && (
          <div className="mt-3 p-3 bg-slate-950 rounded border border-slate-800 text-xs text-slate-300 space-y-1">
            <div><strong className="text-slate-400">HWM Policy:</strong> {data.methodology_details.high_water_mark_policy}</div>
            <div><strong className="text-slate-400">Valuation Frequency:</strong> {data.methodology_details.valuation_frequency}</div>
            <div><strong className="text-slate-400">Series Basis:</strong> {data.methodology_details.nav_basis}</div>
            <div><strong className="text-slate-400">Cash Flow Adjusted:</strong> {data.methodology_details.cash_flow_adjusted ? 'Yes' : 'No'}</div>
          </div>
        )}
      </div>
    </div>
  );
};
