import React from 'react';
import { DataQualitySummary } from '../../../../types/dashboard';

interface RiskDataStatusProps {
  summary: DataQualitySummary;
  asOf: string;
}

export const RiskDataStatus: React.FC<RiskDataStatusProps> = ({ summary, asOf }) => {
  const { overall_status, stale_metrics, failed_metrics, quality_notes } = summary;

  const getStatusBadge = () => {
    switch (overall_status) {
      case 'VALID':
        return (
          <span className="px-2 py-0.5 rounded text-xs bg-positive-soft/60 border border-positive/20 text-positive font-medium">
            All Authoritative Calculations Valid
          </span>
        );
      case 'STALE':
        return (
          <span className="px-2 py-0.5 rounded text-xs bg-warning-soft/60 border border-warning/20 text-warning font-medium">
            Stale Risk Calculations Detected
          </span>
        );
      case 'INCOMPLETE':
        return (
          <span className="px-2 py-0.5 rounded text-xs bg-orange-950/60 border border-orange-800 text-orange-300 font-medium">
            Partial Risk Metrics Available
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded text-xs bg-negative-soft/60 border border-negative/20 text-negative font-medium">
            Risk Calculation Engine Unavailable
          </span>
        );
    }
  };

  return (
    <div className="bg-surface/80 border border-line rounded-lg p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
      <div className="flex items-center space-x-3">
        <span className="text-xs text-muted">Risk Engine Status:</span>
        {getStatusBadge()}
      </div>

      <div className="flex items-center space-x-4 text-xs text-muted">
        <div>
          <span className="text-muted">Valuation As-Of: </span>
          <span className="font-sans text-secondary">{new Date(asOf).toLocaleString()}</span>
        </div>
        {failed_metrics.length > 0 && (
          <div className="text-negative">
            <span>Unavailable: </span>
            <span className="font-semibold">{failed_metrics.join(', ')}</span>
          </div>
        )}
        {stale_metrics.length > 0 && (
          <div className="text-warning">
            <span>Stale: </span>
            <span className="font-semibold">{stale_metrics.join(', ')}</span>
          </div>
        )}
      </div>
    </div>
  );
};
