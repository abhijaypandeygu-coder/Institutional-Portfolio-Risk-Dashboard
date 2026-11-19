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
            <span className="text-sm font-semibold text-secondary">Value at Risk (VaR)</span>
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
              {formatCurrency(data.value, data.currency)}
            </div>
          ) : (
            <div className="text-xl font-medium text-muted">Unavailable</div>
          )}
          {data.percentage_of_nav !== null && data.percentage_of_nav !== undefined && (
            <div className="text-sm text-muted mt-0.5">
              {formatPercentage(data.percentage_of_nav)} of Portfolio NAV
            </div>
          )}
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs text-muted my-3 py-2 border-y border-line/80">
          <div>
            <span className="text-muted block">Confidence</span>
            <span className="font-medium text-secondary">{data.confidence_display}</span>
          </div>
          <div>
            <span className="text-muted block">Horizon</span>
            <span className="font-medium text-secondary">{data.horizon_display}</span>
          </div>
          <div className="col-span-2 mt-1">
            <span className="text-muted block">Methodology</span>
            <span className="font-medium text-secondary truncate block">{data.methodology}</span>
          </div>
        </div>
      </div>

      <div>
        <button
          onClick={() => {
            setShowDetails(!showDetails);
            if (onMethodologyClick) onMethodologyClick();
          }}
          className="text-xs text-brand hover:text-brand flex items-center justify-between w-full pt-1"
        >
          <span>{showDetails ? 'Hide Assumptions' : 'Inspect Methodology'}</span>
          <span>{showDetails ? '▲' : '▼'}</span>
        </button>

        {showDetails && data.methodology_details && (
          <div className="mt-3 p-3 bg-canvas rounded border border-line text-xs text-secondary space-y-1">
            <div><strong className="text-muted">Return Definition:</strong> {data.methodology_details.return_definition}</div>
            <div><strong className="text-muted">Estimation Window:</strong> {data.methodology_details.lookback_window} days</div>
            <div><strong className="text-muted">Observation Freq:</strong> {data.methodology_details.observation_frequency}</div>
            <div><strong className="text-muted">Model Version:</strong> {data.methodology_details.model_version}</div>
            <div className="text-muted pt-1 italic">{data.methodology_details.assumptions_summary}</div>
          </div>
        )}
      </div>
    </div>
  );
};
