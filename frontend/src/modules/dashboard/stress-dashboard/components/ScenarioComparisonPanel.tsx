import React from 'react';
import { ScenarioComparisonResponse } from '../../../types/dashboard';

interface ScenarioComparisonPanelProps {
  comparison: ScenarioComparisonResponse | null;
  loading: boolean;
  onSelectScenario?: (calculationId: string) => void;
}

export const ScenarioComparisonPanel: React.FC<ScenarioComparisonPanelProps> = ({
  comparison,
  loading,
  onSelectScenario,
}) => {
  if (loading) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 animate-pulse">
        <div className="h-6 bg-slate-800 rounded w-1/3 mb-4" />
        <div className="h-40 bg-slate-800 rounded mb-4" />
      </div>
    );
  }

  if (!comparison || comparison.scenarios.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-8 text-center text-slate-400">
        No comparison scenarios loaded. Select multiple scenario runs to perform institutional side-by-side loss severity analysis.
      </div>
    );
  }

  const { scenarios, worst_scenario_name, best_scenario_name, max_loss_pnl, max_loss_percentage } =
    comparison;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h2 className="text-xl font-bold text-white">Cross-Scenario Impact Comparison</h2>
          <p className="text-xs text-slate-400 mt-1">
            Comparing <span className="text-slate-200 font-semibold">{scenarios.length}</span> stress scenarios ranked by loss severity
          </p>
        </div>

        {/* Highlights Pill */}
        {worst_scenario_name && (
          <div className="flex items-center gap-2 bg-rose-950/40 border border-rose-900/60 px-3 py-1.5 rounded-lg text-xs">
            <span className="text-rose-400 font-semibold">Worst Case Shock:</span>
            <span className="text-rose-200 font-medium">{worst_scenario_name}</span>
            {max_loss_pnl !== null && max_loss_pnl !== undefined && (
              <span className="text-rose-400 font-mono font-bold">
                (${Math.abs(max_loss_pnl).toLocaleString(undefined, { maximumFractionDigits: 0 })})
              </span>
            )}
          </div>
        )}
      </div>

      {/* Comparison Table */}
      <div className="overflow-x-auto border border-slate-800 rounded-lg">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-slate-950/80 text-slate-400 uppercase font-semibold border-b border-slate-800">
            <tr>
              <th className="py-2.5 px-3">Rank</th>
              <th className="py-2.5 px-3">Scenario Name</th>
              <th className="py-2.5 px-3">Type</th>
              <th className="py-2.5 px-3 text-right">Pre Shock NAV</th>
              <th className="py-2.5 px-3 text-right">Stressed NAV</th>
              <th className="py-2.5 px-3 text-right">Stressed P&L</th>
              <th className="py-2.5 px-3 text-right">Return %</th>
              <th className="py-2.5 px-3">Baseline Compatibility</th>
              <th className="py-2.5 px-3 text-center">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-mono">
            {scenarios.map((scen) => {
              const isLoss = scen.stressed_pnl < 0;
              return (
                <tr
                  key={scen.calculation_id}
                  className="hover:bg-slate-800/40 transition-colors"
                >
                  <td className="py-2.5 px-3 font-bold text-slate-400">
                    #{scen.loss_rank}
                  </td>
                  <td className="py-2.5 px-3 font-semibold text-white font-sans">
                    {scen.scenario_name}
                  </td>
                  <td className="py-2.5 px-3">
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-950 text-blue-300 border border-blue-800/60 font-sans">
                      {scen.category}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-right text-slate-400">
                    ${scen.baseline_nav.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </td>
                  <td className="py-2.5 px-3 text-right text-slate-300">
                    ${scen.stressed_nav.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </td>
                  <td
                    className={`py-2.5 px-3 text-right font-bold ${
                      isLoss ? 'text-rose-400' : 'text-emerald-400'
                    }`}
                  >
                    {isLoss ? '-' : '+'}$
                    {Math.abs(scen.stressed_pnl).toLocaleString(undefined, {
                      maximumFractionDigits: 0,
                    })}
                  </td>
                  <td
                    className={`py-2.5 px-3 text-right ${
                      scen.return_percentage < 0 ? 'text-rose-400' : 'text-emerald-400'
                    }`}
                  >
                    {scen.return_percentage >= 0 ? '+' : ''}
                    {scen.return_percentage.toFixed(2)}%
                  </td>
                  <td className="py-2.5 px-3 font-sans">
                    {scen.is_compatible ? (
                      <span className="text-[11px] text-emerald-400 flex items-center gap-1 font-semibold">
                        ✓ Aligned
                      </span>
                    ) : (
                      <span className="text-[11px] text-amber-400 flex items-center gap-1 font-semibold" title={scen.compatibility_warning || 'Snapshot variance'}>
                        ⚠ Snapshot Mismatch
                      </span>
                    )}
                  </td>
                  <td className="py-2.5 px-3 text-center font-sans">
                    {onSelectScenario && (
                      <button
                        onClick={() => onSelectScenario(scen.calculation_id)}
                        className="px-2 py-1 text-[11px] font-medium text-blue-400 hover:text-blue-300 hover:bg-blue-950/60 rounded border border-blue-900/40 transition"
                      >
                        Inspect
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
