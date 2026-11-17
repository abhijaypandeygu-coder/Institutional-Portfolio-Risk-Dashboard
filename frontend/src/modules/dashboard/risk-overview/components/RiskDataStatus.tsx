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
          <span className="px-2 py-0.5 rounded text-xs bg-emerald-950/60 border border-emerald-800 text-emerald-300 font-medium">
            All Authoritative Calculations Valid
          </span>
        );
      case 'STALE':
        return (
          <span className="px-2 py-0.5 rounded text-xs bg-amber-950/60 border border-amber-800 text-amber-300 font-medium">
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
          <span className="px-2 py-0.5 rounded text-xs bg-rose-950/60 border border-rose-800 text-rose-300 font-medium">
            Risk Calculation Engine Unavailable
          </span>
        );
    }
  };

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
      <div className="flex items-center space-x-3">
        <span className="text-xs text-slate-400">Risk Engine Status:</span>
        {getStatusBadge()}
      </div>

      <div className="flex items-center space-x-4 text-xs text-slate-400">
        <div>
          <span className="text-slate-500">Valuation As-Of: </span>
          <span className="font-mono text-slate-300">{new Date(asOf).toLocaleString()}</span>
        </div>
        {failed_metrics.length > 0 && (
          <div className="text-rose-400">
            <span>Unavailable: </span>
            <span className="font-semibold">{failed_metrics.join(', ')}</span>
          </div>
        )}
        {stale_metrics.length > 0 && (
          <div className="text-amber-400">
            <span>Stale: </span>
            <span className="font-semibold">{stale_metrics.join(', ')}</span>
          </div>
        )}
      </div>
    </div>
  );
};
