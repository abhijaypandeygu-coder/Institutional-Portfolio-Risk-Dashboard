import React from 'react';
import { HeatmapDrilldownResponse } from '../../../types/dashboard';

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
    <div className="fixed inset-y-0 right-0 w-full max-w-xl bg-slate-900 border-l border-slate-800 shadow-2xl z-50 overflow-y-auto flex flex-col">
      {/* Header */}
      <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-950/80 sticky top-0 backdrop-blur-md">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-blue-950 text-blue-400 border border-blue-800">
              {drilldown?.entity_type} DRILL-THROUGH
            </span>
            <span className="text-xs text-slate-400">Provenance: {drilldown?.color_metric.source_module}</span>
          </div>
          <h3 className="text-lg font-bold text-slate-100 mt-1">
            {drilldown?.entity_name || 'Loading Details...'}
          </h3>
        </div>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-slate-200 p-2 rounded-lg hover:bg-slate-800 transition-colors"
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
            <p className="text-xs text-slate-400">Resolving underlying holdings and model parameters...</p>
          </div>
        ) : drilldown ? (
          <>
            {/* Top Summary Stats */}
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-slate-800/60 p-3 rounded-lg border border-slate-800">
                <div className="text-[11px] text-slate-400">Total Metric Value</div>
                <div className="text-sm font-bold text-slate-100 mt-0.5">
                  {drilldown.summary.formatted_total_color_metric as string}
                </div>
              </div>
              <div className="bg-slate-800/60 p-3 rounded-lg border border-slate-800">
                <div className="text-[11px] text-slate-400">Gross Market Value</div>
                <div className="text-sm font-bold text-slate-100 mt-0.5">
                  {drilldown.reporting_currency} {(Number(drilldown.summary.total_gross_market_value || 0)).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </div>
              </div>
              <div className="bg-slate-800/60 p-3 rounded-lg border border-slate-800">
                <div className="text-[11px] text-slate-400">Holdings Count</div>
                <div className="text-sm font-bold text-slate-100 mt-0.5">
                  {drilldown.total_holdings} Positions
                </div>
              </div>
            </div>

            {/* Constituents Table */}
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                Underlying Constituent Holdings ({drilldown.holdings.length})
              </h4>
              <div className="border border-slate-800 rounded-lg overflow-hidden bg-slate-950/40">
                <table className="min-w-full divide-y divide-slate-800 text-xs">
                  <thead className="bg-slate-900/60 text-slate-400">
                    <tr>
                      <th className="py-2.5 px-3 text-left font-semibold">Symbol / Name</th>
                      <th className="py-2.5 px-3 text-center font-semibold">Side</th>
                      <th className="py-2.5 px-3 text-right font-semibold">Weight</th>
                      <th className="py-2.5 px-3 text-right font-semibold">Market Value</th>
                      <th className="py-2.5 px-3 text-right font-semibold">{drilldown.color_metric.display_name}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 text-slate-300">
                    {drilldown.holdings.map((h) => (
                      <tr key={h.instrument_id} className="hover:bg-slate-800/40">
                        <td className="py-2 px-3">
                          <div className="font-semibold text-slate-100">{h.symbol}</div>
                          <div className="text-[10px] text-slate-400 truncate max-w-[140px]">{h.instrument_name}</div>
                        </td>
                        <td className="py-2 px-3 text-center">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-semibold ${
                            h.side === 'SHORT' ? 'bg-amber-950 text-amber-300 border border-amber-800' : 'bg-blue-950 text-blue-300 border border-blue-800'
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
                        <td className="py-2 px-3 text-right font-bold text-slate-100">
                          {h.formatted_color_metric}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Provenance Metadata */}
            <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg text-xs space-y-1 text-slate-400">
              <div className="font-semibold text-slate-300 mb-1">Authoritative Backend Provenance</div>
              <div>Source Valuation: {drilldown.provenance_details.source_valuation_module as string}</div>
              <div>Classification: {drilldown.provenance_details.source_classification_module as string}</div>
              <div>Exposure Engine: {drilldown.provenance_details.source_exposure_module as string}</div>
              <div className="text-[11px] text-slate-400 mt-2">
                All metrics are computed authoritatively by backend microservices.
              </div>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
};
