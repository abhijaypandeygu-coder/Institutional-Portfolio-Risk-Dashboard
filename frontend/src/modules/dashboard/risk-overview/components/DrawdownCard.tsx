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
            <span className="text-sm font-semibold text-secondary">Drawdown</span>
            <span className="text-xs px-2 py-0.5 rounded bg-subtle text-muted font-sans">
              {data.source_module}
            </span>
          </div>
          <span className={`text-xs px-2 py-0.5 rounded border font-medium ${getStatusColor(data.status)}`}>
            {data.status}
          </span>
        </div>

        <div className="mb-2">
          {data.current_drawdown_pct !== null && data.current_drawdown_pct !== undefined ? (
            <div className={`text-2xl font-bold  ${data.current_drawdown_pct < 0 ? 'text-negative' : 'text-ink'}`}>
              {formatPercentage(data.current_drawdown_pct)}
            </div>
          ) : (
            <div className="text-xl font-medium text-muted">Unavailable</div>
          )}
          <div className="text-sm text-muted mt-0.5">
            Current Drawdown below High-Water Mark
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs text-muted my-3 py-2 border-y border-line/80">
          <div>
            <span className="text-muted block">Maximum Drawdown</span>
            <span className="font-semibold text-negative">
              {data.maximum_drawdown_pct !== null && data.maximum_drawdown_pct !== undefined
                ? formatPercentage(data.maximum_drawdown_pct)
                : 'N/A'}
            </span>
          </div>
          <div>
            <span className="text-muted block">Measurement Window</span>
            <span className="font-medium text-secondary">{data.measurement_period}</span>
          </div>
          <div className="col-span-2 mt-1">
            <span className="text-muted block">Recovery Status</span>
            <span className="font-medium text-warning">{data.recovery_status || 'RECOVERING'}</span>
          </div>
        </div>
      </div>

      <div>
        <button
          onClick={() => setShowDetails(!showDetails)}
          className="text-xs text-brand hover:text-brand flex items-center justify-between w-full pt-1"
        >
          <span>{showDetails ? 'Hide Assumptions' : 'Inspect HWM & Window'}</span>
          <span>{showDetails ? '▲' : '▼'}</span>
        </button>

        {showDetails && data.methodology_details && (
          <div className="mt-3 p-3 bg-canvas rounded border border-line text-xs text-secondary space-y-1">
            <div><strong className="text-muted">HWM Policy:</strong> {data.methodology_details.high_water_mark_policy}</div>
            <div><strong className="text-muted">Valuation Frequency:</strong> {data.methodology_details.valuation_frequency}</div>
            <div><strong className="text-muted">Series Basis:</strong> {data.methodology_details.nav_basis}</div>
            <div><strong className="text-muted">Cash Flow Adjusted:</strong> {data.methodology_details.cash_flow_adjusted ? 'Yes' : 'No'}</div>
          </div>
        )}
      </div>
    </div>
  );
};
