import React from 'react';
import { HeatmapDrilldownResponse } from '../../../../types/dashboard';

interface HeatmapDetailDrawerProps {
  drilldown: HeatmapDrilldownResponse | null;
  isLoading: boolean;
  onClose: () => void;
}

export const HeatmapDetailDrawer: React.FC<HeatmapDetailDrawerProps> = ({
  drilldown,
  isLoading,
  onClose,
}) => {
  if (!drilldown && !isLoading) {
    return null;
  }

  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-xl bg-surface border-l border-line shadow-2xl z-50 overflow-y-auto flex flex-col">
      {/* Header */}
      <div className="p-5 border-b border-line flex items-center justify-between bg-canvas/80 sticky top-0 ">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase  px-2 py-0.5 rounded bg-brand-soft text-brand border border-brand/20">
              {drilldown?.entity_type} DRILL-THROUGH
            </span>
            <span className="text-xs text-muted">Provenance: {drilldown?.color_metric.source_module}</span>
          </div>
          <h3 className="text-lg font-bold text-ink mt-1">
            {drilldown?.entity_name || 'Loading Details...'}
          </h3>
        </div>
        <button
          onClick={onClose}
          className="text-muted hover:text-secondary p-2 rounded-lg hover:bg-subtle transition-colors"
          title="Close drawer"
        >
          ✕
        </button>
      </div>

      {/* Body */}
      <div className="p-5 flex-1 space-y-6">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center h-48 space-y-3">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
            <p className="text-xs text-muted">Resolving underlying holdings and model parameters...</p>
          </div>
        ) : drilldown ? (
          <>
            {/* Top Summary Stats */}
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-subtle/60 p-3 rounded-lg border border-line">
                <div className="text-[11px] text-muted">Total Metric Value</div>
                <div className="text-sm font-bold text-ink mt-0.5">
                  {drilldown.summary.formatted_total_color_metric as string}
                </div>
              </div>
              <div className="bg-subtle/60 p-3 rounded-lg border border-line">
                <div className="text-[11px] text-muted">Gross Market Value</div>
                <div className="text-sm font-bold text-ink mt-0.5">
                  {drilldown.reporting_currency} {(Number(drilldown.summary.total_gross_market_value || 0)).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </div>
              </div>
              <div className="bg-subtle/60 p-3 rounded-lg border border-line">
                <div className="text-[11px] text-muted">Holdings Count</div>
                <div className="text-sm font-bold text-ink mt-0.5">
                  {drilldown.total_holdings} Positions
                </div>
              </div>
            </div>

            {/* Constituents Table */}
            <div>
              <h4 className="text-xs font-semibold uppercase  text-muted mb-2">
                Underlying Constituent Holdings ({drilldown.holdings.length})
              </h4>
              <div className="border border-line rounded-lg overflow-hidden bg-canvas/40">
                <table className="min-w-full divide-y divide-slate-800 text-xs">
                  <thead className="bg-surface/60 text-muted">
                    <tr>
                      <th className="py-2.5 px-3 text-left font-semibold">Symbol / Name</th>
                      <th className="py-2.5 px-3 text-center font-semibold">Side</th>
                      <th className="py-2.5 px-3 text-right font-semibold">Weight</th>
                      <th className="py-2.5 px-3 text-right font-semibold">Market Value</th>
                      <th className="py-2.5 px-3 text-right font-semibold">{drilldown.color_metric.display_name}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 text-secondary">
                    {drilldown.holdings.map((h) => (
                      <tr key={h.instrument_id} className="hover:bg-subtle/40">
                        <td className="py-2 px-3">
                          <div className="font-semibold text-ink">{h.symbol}</div>
                          <div className="text-[10px] text-muted truncate max-w-[140px]">{h.instrument_name}</div>
                        </td>
                        <td className="py-2 px-3 text-center">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-semibold ${
                            h.side === 'SHORT' ? 'bg-warning-soft text-warning border border-warning/20' : 'bg-brand-soft text-brand border border-brand/20'
                          }`}>
                            {h.side}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-right font-medium">
                          {h.weight_pct.toFixed(2)}%
                        </td>
                        <td className="py-2 px-3 text-right font-medium">
                          {drilldown.reporting_currency} {Number(h.market_value).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                        </td>
                        <td className="py-2 px-3 text-right font-bold text-ink">
                          {h.formatted_color_metric}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Provenance Metadata */}
            <div className="p-3 bg-canvas border border-line rounded-lg text-xs space-y-1 text-muted">
              <div className="font-semibold text-secondary mb-1">Authoritative Backend Provenance</div>
              <div>Source Valuation: {drilldown.provenance_details.source_valuation_module as string}</div>
              <div>Classification: {drilldown.provenance_details.source_classification_module as string}</div>
              <div>Exposure Engine: {drilldown.provenance_details.source_exposure_module as string}</div>
              <div className="text-[11px] text-muted mt-2">
                All metrics are computed authoritatively by backend microservices.
              </div>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
};
