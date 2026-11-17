import React, { useState } from 'react';
import { StressAttributionResponse } from '../../../../types/dashboard';

interface StressAttributionPanelProps {
  attribution: StressAttributionResponse | null;
  loading: boolean;
}

export const StressAttributionPanel: React.FC<StressAttributionPanelProps> = ({
  attribution,
  loading,
}) => {
  const [viewDimension, setViewDimension] = useState<'POSITION' | 'SECTOR' | 'FACTOR'>('POSITION');

  if (loading) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 animate-pulse">
        <div className="h-6 bg-slate-800 rounded w-1/4 mb-4" />
        <div className="h-32 bg-slate-800 rounded mb-4" />
      </div>
    );
  }

  if (!attribution) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-8 text-center text-slate-400">
        No stress loss attribution data available for this scenario run. Select a run with M10.09 attribution results.
      </div>
    );
  }

  const {
    scenario_name,
    total_stressed_pnl,
    explained_pnl,
    residual_amount,
    is_reconciled,
    loss_hhi,
    effective_contributor_count,
    position_contributors,
    sector_contributors,
    factor_contributors,
    reconciliation_status,
  } = attribution;

  const currentContributors =
    viewDimension === 'POSITION'
      ? position_contributors
      : viewDimension === 'SECTOR'
      ? sector_contributors
      : factor_contributors;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-white">Stress Loss Attribution & Decomposition</h2>
            <span
              className={`px-2 py-0.5 text-xs font-semibold rounded ${
                is_reconciled
                  ? 'bg-emerald-900/60 text-emerald-300 border border-emerald-700/50'
                  : 'bg-amber-900/60 text-amber-300 border border-amber-700/50'
              }`}
            >
              {reconciliation_status}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Scenario: <span className="text-slate-200 font-medium">{scenario_name}</span> | Effective Contributors:{' '}
            <span className="font-mono text-slate-200 font-semibold">{effective_contributor_count.toFixed(1)}</span> · Loss HHI:{' '}
            <span className="font-mono text-slate-200 font-semibold">{loss_hhi.toFixed(2)}</span>
          </p>
        </div>

        {/* Dimension Switcher */}
        <div className="flex bg-slate-950 p-1 rounded-lg border border-slate-800 self-start md:self-auto">
          {(['POSITION', 'SECTOR', 'FACTOR'] as const).map((dim) => (
            <button
              key={dim}
              onClick={() => setViewDimension(dim)}
              className={`px-3 py-1 text-xs font-medium rounded transition ${
                viewDimension === dim
                  ? 'bg-blue-600 text-white font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {dim === 'POSITION'
                ? 'Positions'
                : dim === 'SECTOR'
                ? 'Sectors'
                : 'Economic Factors'}
            </button>
          ))}
        </div>
      </div>

      {/* Reconciliation Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-950/60 p-4 rounded-lg border border-slate-800">
          <div className="text-xs font-medium text-slate-400">Authoritative Scenario Loss</div>
          <div className="text-lg font-bold text-rose-400 font-mono mt-1">
            ${Math.abs(total_stressed_pnl).toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
          <div className="text-xs text-slate-500 mt-0.5">M10 total stressed P&L</div>
        </div>

        <div className="bg-slate-950/60 p-4 rounded-lg border border-slate-800">
          <div className="text-xs font-medium text-slate-400">Sum of Explained Drivers</div>
          <div className="text-lg font-bold text-slate-200 font-mono mt-1">
            ${Math.abs(explained_pnl).toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
          <div className="text-xs text-slate-500 mt-0.5">Direct factor / position decomposition</div>
        </div>

        <div
          className={`p-4 rounded-lg border ${
            Math.abs(residual_amount) > 1.0
              ? 'bg-amber-950/20 border-amber-800/60'
              : 'bg-emerald-950/20 border-emerald-900/50'
          }`}
        >
          <div className="text-xs font-medium text-slate-400">Residual / Cross-Terms</div>
          <div
            className={`text-lg font-bold font-mono mt-1 ${
              Math.abs(residual_amount) > 1.0 ? 'text-amber-400' : 'text-emerald-400'
            }`}
          >
            ${residual_amount.toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </div>
          <div className="text-xs text-slate-500 mt-0.5">
            {is_reconciled ? 'Clean exact arithmetic reconciliation' : 'Nonlinear cross-term variance'}
          </div>
        </div>

        <div className="bg-slate-950/60 p-4 rounded-lg border border-slate-800">
          <div className="text-xs font-medium text-slate-400">Top Dimension Contributors</div>
          <div className="text-lg font-bold text-white font-mono mt-1">
            {currentContributors.length} items
          </div>
          <div className="text-xs text-slate-500 mt-0.5">Ranked by absolute loss contribution</div>
        </div>
      </div>

      {/* Waterfall-Style Decomposition Table */}
      <div className="overflow-x-auto border border-slate-800 rounded-lg">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-slate-950/80 text-slate-400 uppercase font-semibold border-b border-slate-800">
            <tr>
              <th className="py-2.5 px-3">
                {viewDimension === 'POSITION'
                  ? 'Symbol'
                  : viewDimension === 'SECTOR'
                  ? 'Sector Name'
                  : 'Factor Driver'}
              </th>
              <th className="py-2.5 px-3 text-right">Pre Shock Exposure</th>
              <th className="py-2.5 px-3 text-right">Stressed P&L</th>
              <th className="py-2.5 px-3 text-right">Loss Contribution</th>
              <th className="py-2.5 px-3 text-right">% of Scenario Loss</th>
              <th className="py-2.5 px-3 w-40">Relative Impact Bar</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-mono">
            {currentContributors.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-4 text-center text-slate-500 font-sans">
                  No {viewDimension.toLowerCase()} attribution records available for this run.
                </td>
              </tr>
            ) : (
              currentContributors.map((item, idx) => {
                const isLoss = item.stressed_pnl < 0;
                const barWidth = Math.min(Math.abs(item.contribution_percentage), 100);

                return (
                  <tr
                    key={idx}
                    className="hover:bg-slate-800/40 transition-colors"
                  >
                    <td className="py-2.5 px-3 font-semibold text-white font-sans">
                      {item.dimension_name}
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-400">
                      ${item.baseline_exposure.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </td>
                    <td
                      className={`py-2.5 px-3 text-right font-bold ${
                        isLoss ? 'text-rose-400' : 'text-emerald-400'
                      }`}
                    >
                      {isLoss ? '-' : '+'}$
                      {Math.abs(item.stressed_pnl).toLocaleString(undefined, {
                        maximumFractionDigits: 0,
                      })}
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-200 font-semibold">
                      ${Math.abs(item.contribution_to_loss).toLocaleString(undefined, {
                        maximumFractionDigits: 0,
                      })}
                    </td>
                    <td className="py-2.5 px-3 text-right font-bold text-rose-400">
                      {item.contribution_percentage.toFixed(2)}%
                    </td>
                    <td className="py-2.5 px-3">
                      <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                        <div
                          style={{ width: `${barWidth}%` }}
                          className={`h-full rounded-full ${
                            isLoss ? 'bg-rose-500' : 'bg-emerald-500'
                          }`}
                        />
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
