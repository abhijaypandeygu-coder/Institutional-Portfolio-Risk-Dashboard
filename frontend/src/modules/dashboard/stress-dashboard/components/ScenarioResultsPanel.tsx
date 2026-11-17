import React from 'react';
import { ScenarioDetailResultResponse } from '../../../../types/dashboard';

interface ScenarioResultsPanelProps {
  data: ScenarioDetailResultResponse | null;
  loading: boolean;
  onRefresh?: () => void;
}

export const ScenarioResultsPanel: React.FC<ScenarioResultsPanelProps> = ({
  data,
  loading,
  onRefresh,
}) => {
  if (loading) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 animate-pulse">
        <div className="h-6 bg-slate-800 rounded w-1/4 mb-4" />
        <div className="grid grid-cols-4 gap-4 mb-6">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-20 bg-slate-800 rounded" />
          ))}
        </div>
        <div className="h-48 bg-slate-800 rounded" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-8 text-center text-slate-400">
        No scenario calculation selected. Select a scenario from the library above to inspect results.
      </div>
    );
  }

  const { summary, definition, positions } = data;
  const isLoss = summary.stressed_pnl < 0;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-6">
      {/* Header & Meta */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-white">{summary.scenario_name}</h2>
            <span className="px-2 py-0.5 text-xs font-semibold rounded bg-blue-900/60 text-blue-300 border border-blue-700/50">
              {summary.category}
            </span>
            <span
              className={`px-2 py-0.5 text-xs font-semibold rounded ${
                summary.calculation_status === 'COMPLETED'
                  ? 'bg-emerald-900/50 text-emerald-300 border border-emerald-700/50'
                  : 'bg-amber-900/50 text-amber-300 border border-amber-700/50'
              }`}
            >
              {summary.calculation_status}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Calculation ID: <code className="text-slate-300">{summary.calculation_id}</code> | Timestamp:{' '}
            {new Date(summary.calculation_timestamp).toLocaleString()}
          </p>
        </div>

        {onRefresh && (
          <button
            onClick={onRefresh}
            className="px-3 py-1.5 text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded transition"
          >
            Refresh Run
          </button>
        )}
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-950/60 p-4 rounded-lg border border-slate-800">
          <div className="text-xs font-medium text-slate-400">Baseline Portfolio Value</div>
          <div className="text-lg font-bold text-white mt-1">
            ${summary.baseline_nav.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </div>
          <div className="text-xs text-slate-500 mt-0.5">Pre-shock portfolio valuation</div>
        </div>

        <div className="bg-slate-950/60 p-4 rounded-lg border border-slate-800">
          <div className="text-xs font-medium text-slate-400">Stressed Portfolio Value</div>
          <div className="text-lg font-bold text-white mt-1">
            ${summary.stressed_nav.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </div>
          <div className="text-xs text-slate-500 mt-0.5">Post-shock terminal valuation</div>
        </div>

        <div
          className={`p-4 rounded-lg border ${
            isLoss ? 'bg-rose-950/20 border-rose-900/50' : 'bg-emerald-950/20 border-emerald-900/50'
          }`}
        >
          <div className="text-xs font-medium text-slate-400">Stressed P&L</div>
          <div
            className={`text-lg font-bold mt-1 ${
              isLoss ? 'text-rose-400' : 'text-emerald-400'
            }`}
          >
            {isLoss ? '-' : '+'}$
            {Math.abs(summary.stressed_pnl).toLocaleString(undefined, {
              minimumFractionDigits: 2,
            })}
          </div>
          <div className="text-xs text-slate-400 mt-0.5">
            Return: {summary.return_percentage >= 0 ? '+' : ''}
            {summary.return_percentage.toFixed(2)}%
          </div>
        </div>

        <div className="bg-slate-950/60 p-4 rounded-lg border border-slate-800">
          <div className="text-xs font-medium text-slate-400">Shock Coverage & Scope</div>
          <div className="text-lg font-bold text-slate-200 mt-1">
            {summary.coverage_percentage.toFixed(1)}%
          </div>
          <div className="text-xs text-slate-500 mt-0.5">
            {summary.eligible_holdings} eligible positions analyzed
          </div>
        </div>
      </div>

      {/* Narrative & Assumptions Accordion */}
      {definition.description && (
        <div className="bg-slate-950/40 p-3.5 rounded border border-slate-800 text-xs text-slate-300">
          <span className="font-semibold text-slate-200">Scenario Description: </span>
          {definition.description}
        </div>
      )}

      {/* Position Results Breakdown Table */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
            Holdings Impact Breakdown
          </h3>
          <span className="text-xs text-slate-500">
            Sorted by largest negative stressed P&L
          </span>
        </div>

        <div className="overflow-x-auto border border-slate-800 rounded-lg">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-950/80 text-slate-400 uppercase font-semibold border-b border-slate-800">
              <tr>
                <th className="py-2.5 px-3">Symbol / Listing</th>
                <th className="py-2.5 px-3">Side</th>
                <th className="py-2.5 px-3 text-right">Quantity</th>
                <th className="py-2.5 px-3 text-right">Pre Price</th>
                <th className="py-2.5 px-3 text-right">Stressed Price</th>
                <th className="py-2.5 px-3 text-right">Pre MV</th>
                <th className="py-2.5 px-3 text-right">Post MV</th>
                <th className="py-2.5 px-3 text-right">Stressed P&L</th>
                <th className="py-2.5 px-3 text-right">% Change</th>
                <th className="py-2.5 px-3 text-right">Loss Contrib</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {positions.length === 0 ? (
                <tr>
                  <td colSpan={10} className="py-4 text-center text-slate-500">
                    No position shock detail recorded for this run.
                  </td>
                </tr>
              ) : (
                positions.map((pos) => {
                  const pnlLoss = pos.stressed_pnl < 0;
                  return (
                    <tr
                      key={pos.instrument_id}
                      className="hover:bg-slate-800/40 transition-colors"
                    >
                      <td className="py-2 px-3 font-semibold text-white">
                        {pos.symbol}
                      </td>
                      <td className="py-2 px-3">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            pos.position_side === 'LONG'
                              ? 'bg-blue-950 text-blue-300 border border-blue-800/60'
                              : 'bg-purple-950 text-purple-300 border border-purple-800/60'
                          }`}
                        >
                          {pos.position_side}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-right text-slate-300">
                        {pos.quantity.toLocaleString()}
                      </td>
                      <td className="py-2 px-3 text-right text-slate-400">
                        ${pos.baseline_price.toFixed(2)}
                      </td>
                      <td className="py-2 px-3 text-right text-slate-300">
                        ${pos.stressed_price.toFixed(2)}
                      </td>
                      <td className="py-2 px-3 text-right text-slate-400">
                        ${pos.baseline_market_value.toLocaleString(undefined, {
                          maximumFractionDigits: 0,
                        })}
                      </td>
                      <td className="py-2 px-3 text-right text-slate-300">
                        ${pos.stressed_market_value.toLocaleString(undefined, {
                          maximumFractionDigits: 0,
                        })}
                      </td>
                      <td
                        className={`py-2 px-3 text-right font-bold ${
                          pnlLoss ? 'text-rose-400' : 'text-emerald-400'
                        }`}
                      >
                        {pnlLoss ? '-' : '+'}$
                        {Math.abs(pos.stressed_pnl).toLocaleString(undefined, {
                          maximumFractionDigits: 0,
                        })}
                      </td>
                      <td
                        className={`py-2 px-3 text-right ${
                          pos.percentage_change < 0 ? 'text-rose-400' : 'text-emerald-400'
                        }`}
                      >
                        {pos.percentage_change >= 0 ? '+' : ''}
                        {pos.percentage_change.toFixed(2)}%
                      </td>
                      <td className="py-2 px-3 text-right text-slate-400 font-semibold">
                        {pos.contribution_to_loss_pct > 0
                          ? `${pos.contribution_to_loss_pct.toFixed(1)}%`
                          : '-'}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
