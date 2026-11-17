import React from 'react';
import {
  PointInTimeStateResponse,
  ProvenanceManifestResponse,
} from '../../../../types/dashboard';

interface HistoricalStateInspectorProps {
  state?: PointInTimeStateResponse | null;
  onClose?: () => void;
}

export const HistoricalStateInspector: React.FC<HistoricalStateInspectorProps> = ({
  state,
  onClose,
}) => {
  if (!state) return null;

  const { manifest } = state;

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'CONSISTENT':
        return 'text-emerald-400 bg-emerald-950/60 border-emerald-800';
      case 'RESTATED':
        return 'text-amber-400 bg-amber-950/60 border-amber-800';
      default:
        return 'text-rose-400 bg-rose-950/60 border-rose-800';
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 shadow-lg text-slate-100 mb-6">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-3 mb-4">
        <div>
          <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            Point-in-Time State Reconstruction
            <span
              className={`text-xs px-2 py-0.5 rounded border font-semibold ${getStatusColor(
                manifest.consistency_status
              )}`}
            >
              {manifest.consistency_status}
            </span>
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Effective As Of: <span className="text-slate-200 font-mono">{new Date(state.effective_at).toLocaleString()}</span> | 
            Knowledge As Of: <span className="text-slate-200 font-mono">{new Date(state.known_at).toLocaleString()}</span>
          </p>
        </div>

        {onClose && (
          <button
            onClick={onClose}
            className="text-xs px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded transition-colors"
          >
            Close Inspector
          </button>
        )}
      </div>

      {/* Snapshot Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        <div className="bg-slate-950/70 p-3 rounded border border-slate-800">
          <span className="text-xs text-slate-400">Total Reconstructed NAV</span>
          <div className="text-base font-bold text-slate-100 font-mono mt-1">
            {state.total_nav_base.toLocaleString(undefined, { minimumFractionDigits: 2 })} {state.base_currency}
          </div>
        </div>
        <div className="bg-slate-950/70 p-3 rounded border border-slate-800">
          <span className="text-xs text-slate-400">Market Value</span>
          <div className="text-base font-bold text-slate-100 font-mono mt-1">
            {state.total_market_value_base.toLocaleString(undefined, { minimumFractionDigits: 2 })} {state.base_currency}
          </div>
        </div>
        <div className="bg-slate-950/70 p-3 rounded border border-slate-800">
          <span className="text-xs text-slate-400">Cash Balance</span>
          <div className="text-base font-bold text-slate-100 font-mono mt-1">
            {state.total_cash_value_base.toLocaleString(undefined, { minimumFractionDigits: 2 })} {state.base_currency}
          </div>
        </div>
        <div className="bg-slate-950/70 p-3 rounded border border-slate-800">
          <span className="text-xs text-slate-400">Unrealized P&L</span>
          <div
            className={`text-base font-bold font-mono mt-1 ${
              state.total_unrealized_pnl_base >= 0 ? 'text-emerald-400' : 'text-rose-400'
            }`}
          >
            {state.total_unrealized_pnl_base.toLocaleString(undefined, { minimumFractionDigits: 2 })} {state.base_currency}
          </div>
        </div>
      </div>

      {/* Holdings & Provenance Tabs */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Holdings Table */}
        <div className="bg-slate-950/50 rounded border border-slate-800 p-4">
          <h4 className="text-xs uppercase font-semibold text-slate-400 mb-3 tracking-wider">
            Position Holdings ({state.positions.length})
          </h4>
          {state.positions.length === 0 ? (
            <div className="text-xs text-slate-500 py-6 text-center">No positions recorded in snapshot.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400">
                    <th className="py-2">Instrument</th>
                    <th className="py-2 text-right">Quantity</th>
                    <th className="py-2 text-right">Market Price</th>
                    <th className="py-2 text-right">Market Value</th>
                    <th className="py-2 text-right">Weight</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {state.positions.map((pos) => (
                    <tr key={pos.instrument_id}>
                      <td className="py-2 font-semibold text-slate-200">{pos.instrument_id}</td>
                      <td className="py-2 text-right text-slate-300">{pos.quantity.toLocaleString()}</td>
                      <td className="py-2 text-right text-slate-300">{pos.market_price.toFixed(2)}</td>
                      <td className="py-2 text-right text-slate-100">{pos.market_value_base.toLocaleString()}</td>
                      <td className="py-2 text-right text-slate-400">{(pos.weight_pct * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Provenance Manifest Card */}
        <div className="bg-slate-950/50 rounded border border-slate-800 p-4">
          <h4 className="text-xs uppercase font-semibold text-slate-400 mb-3 tracking-wider">
            Provenance Manifest ({manifest.manifest_id})
          </h4>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-800/80">
              <span className="text-slate-400">Position Snapshot:</span>
              <span className="font-mono text-slate-200">{manifest.position_snapshot_id ?? 'None'}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800/80">
              <span className="text-slate-400">Source Modules:</span>
              <span className="font-mono text-slate-200">{manifest.source_modules.join(', ')}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800/80">
              <span className="text-slate-400">Risk Calculation IDs:</span>
              <span className="font-mono text-slate-200">
                {manifest.risk_calculation_ids.length > 0
                  ? manifest.risk_calculation_ids.join(', ')
                  : 'None'}
              </span>
            </div>
            {manifest.consistency_notes && (
              <div className="mt-3 p-2 rounded bg-amber-950/30 border border-amber-900/50 text-[11px] text-amber-200">
                <strong>Audit Note:</strong> {manifest.consistency_notes}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
