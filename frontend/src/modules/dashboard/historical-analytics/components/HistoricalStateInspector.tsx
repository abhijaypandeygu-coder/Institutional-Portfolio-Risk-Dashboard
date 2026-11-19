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
        return 'text-positive bg-positive-soft/60 border-positive/20';
      case 'RESTATED':
        return 'text-warning bg-warning-soft/60 border-warning/20';
      default:
        return 'text-negative bg-negative-soft/60 border-negative/20';
    }
  };

  return (
    <div className="bg-surface border border-line rounded-lg p-5 shadow-lg text-ink mb-6">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line pb-3 mb-4">
        <div>
          <h3 className="text-base font-semibold text-ink flex items-center gap-2">
            Point-in-Time State Reconstruction
            <span
              className={`text-xs px-2 py-0.5 rounded border font-semibold ${getStatusColor(
                manifest.consistency_status
              )}`}
            >
              {manifest.consistency_status}
            </span>
          </h3>
          <p className="text-xs text-muted mt-0.5">
            Effective As Of: <span className="text-secondary font-sans">{new Date(state.effective_at).toLocaleString()}</span> | 
            Knowledge As Of: <span className="text-secondary font-sans">{new Date(state.known_at).toLocaleString()}</span>
          </p>
        </div>

        {onClose && (
          <button
            onClick={onClose}
            className="text-xs px-2 py-1 bg-subtle hover:bg-hover text-secondary rounded transition-colors"
          >
            Close Inspector
          </button>
        )}
      </div>

      {/* Snapshot Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        <div className="bg-canvas/70 p-3 rounded border border-line">
          <span className="text-xs text-muted">Total Reconstructed NAV</span>
          <div className="text-base font-bold text-ink font-sans mt-1">
            {state.total_nav_base.toLocaleString(undefined, { minimumFractionDigits: 2 })} {state.base_currency}
          </div>
        </div>
        <div className="bg-canvas/70 p-3 rounded border border-line">
          <span className="text-xs text-muted">Market Value</span>
          <div className="text-base font-bold text-ink font-sans mt-1">
            {state.total_market_value_base.toLocaleString(undefined, { minimumFractionDigits: 2 })} {state.base_currency}
          </div>
        </div>
        <div className="bg-canvas/70 p-3 rounded border border-line">
          <span className="text-xs text-muted">Cash Balance</span>
          <div className="text-base font-bold text-ink font-sans mt-1">
            {state.total_cash_value_base.toLocaleString(undefined, { minimumFractionDigits: 2 })} {state.base_currency}
          </div>
        </div>
        <div className="bg-canvas/70 p-3 rounded border border-line">
          <span className="text-xs text-muted">Unrealized P&L</span>
          <div
            className={`text-base font-bold font-sans mt-1 ${
              state.total_unrealized_pnl_base >= 0 ? 'text-positive' : 'text-negative'
            }`}
          >
            {state.total_unrealized_pnl_base.toLocaleString(undefined, { minimumFractionDigits: 2 })} {state.base_currency}
          </div>
        </div>
      </div>

      {/* Holdings & Provenance Tabs */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Holdings Table */}
        <div className="bg-canvas/50 rounded border border-line p-4">
          <h4 className="text-xs uppercase font-semibold text-muted mb-3 ">
            Position Holdings ({state.positions.length})
          </h4>
          {state.positions.length === 0 ? (
            <div className="text-xs text-muted py-6 text-center">No positions recorded in snapshot.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-line text-muted">
                    <th className="py-2">Instrument</th>
                    <th className="py-2 text-right">Quantity</th>
                    <th className="py-2 text-right">Market Price</th>
                    <th className="py-2 text-right">Market Value</th>
                    <th className="py-2 text-right">Weight</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-sans">
                  {state.positions.map((pos) => (
                    <tr key={pos.instrument_id}>
                      <td className="py-2 font-semibold text-secondary">{pos.instrument_id}</td>
                      <td className="py-2 text-right text-secondary">{pos.quantity.toLocaleString()}</td>
                      <td className="py-2 text-right text-secondary">{pos.market_price.toFixed(2)}</td>
                      <td className="py-2 text-right text-ink">{pos.market_value_base.toLocaleString()}</td>
                      <td className="py-2 text-right text-muted">{(pos.weight_pct * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Provenance Manifest Card */}
        <div className="bg-canvas/50 rounded border border-line p-4">
          <h4 className="text-xs uppercase font-semibold text-muted mb-3 ">
            Provenance Manifest ({manifest.manifest_id})
          </h4>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-line/80">
              <span className="text-muted">Position Snapshot:</span>
              <span className="font-sans text-secondary">{manifest.position_snapshot_id ?? 'None'}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-line/80">
              <span className="text-muted">Source Modules:</span>
              <span className="font-sans text-secondary">{manifest.source_modules.join(', ')}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-line/80">
              <span className="text-muted">Risk Calculation IDs:</span>
              <span className="font-sans text-secondary">
                {manifest.risk_calculation_ids.length > 0
                  ? manifest.risk_calculation_ids.join(', ')
                  : 'None'}
              </span>
            </div>
            {manifest.consistency_notes && (
              <div className="mt-3 p-2 rounded bg-warning-soft/30 border border-warning/20 text-[11px] text-warning">
                <strong>Audit Note:</strong> {manifest.consistency_notes}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
