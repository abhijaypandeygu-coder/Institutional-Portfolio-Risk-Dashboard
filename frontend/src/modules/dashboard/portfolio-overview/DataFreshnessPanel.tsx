import React from 'react';
import { DataFreshnessSummary } from '../../../types/dashboard';
import { DataQualityBadge } from '../shared/DataQualityBadge';
import { formatUtcTimestamp } from '../../../utils/financialFormatting';

interface DataFreshnessPanelProps {
  freshness: DataFreshnessSummary;
  onRefresh?: () => void;
  isLoading?: boolean;
}

export const DataFreshnessPanel: React.FC<DataFreshnessPanelProps> = ({
  freshness,
  onRefresh,
  isLoading = false,
}) => {
  return (
    <div className="bg-canvas border border-line rounded-lg p-4 shadow-sm mb-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <span className="text-xs font-semibold text-secondary uppercase ">
            Data Quality & Freshness:
          </span>
          <DataQualityBadge status={freshness.overall_status} />
          {freshness.is_stale && (
            <span className="text-xs text-warning bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
              {freshness.stale_reason || 'Data exceeds staleness threshold'}
            </span>
          )}
        </div>

        <div className="flex items-center space-x-6 text-xs text-secondary">
          <div>
            <span className="text-muted mr-1">Last Valuation:</span>
            <span className="font-medium">
              {formatUtcTimestamp(freshness.last_valuation_at)}
            </span>
          </div>
          <div>
            <span className="text-muted mr-1">Last Exposure Calc:</span>
            <span className="font-medium">
              {formatUtcTimestamp(freshness.last_exposure_calculation_at)}
            </span>
          </div>
          <div>
            <span className="text-muted mr-1">Feed Source:</span>
            <span className="font-medium">{freshness.market_data_source}</span>
          </div>

          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={isLoading}
              className="inline-flex items-center px-3 py-1 bg-white border border-line-strong rounded text-xs font-medium text-secondary hover:bg-canvas disabled:opacity-50 transition"
            >
              {isLoading ? 'Refreshing...' : 'Refresh'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
