import React from 'react';
import { Check, AlertTriangle } from 'lucide-react';
import { ScenarioComparisonResponse } from '../../../../types/dashboard';

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
      <div className="bg-surface border border-line rounded-lg p-6 ">
        <div className="h-6 bg-subtle rounded w-1/3 mb-4" />
        <div className="h-40 bg-subtle rounded mb-4" />
      </div>
    );
  }

  if (!comparison || comparison.scenarios.length === 0) {
    return (
      <div className="bg-surface border border-line rounded-lg p-8 text-center text-muted">
        No comparison scenarios loaded. Select multiple scenario runs to perform institutional side-by-side loss severity analysis.
      </div>
    );
  }

  const { scenarios, worst_scenario_name, best_scenario_name, max_loss_pnl, max_loss_percentage } =
    comparison;

  return (
    <div className="bg-surface border border-line rounded-lg p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-line">
        <div>
          <h2 className="text-xl font-bold text-ink">Cross-Scenario Impact Comparison</h2>
          <p className="text-xs text-muted mt-1">
            Comparing <span className="text-secondary font-semibold">{scenarios.length}</span> stress scenarios ranked by loss severity
          </p>
        </div>

        {/* Highlights Pill */}
        {worst_scenario_name && (
          <div className="flex items-center gap-2 bg-negative-soft/40 border border-negative/20 px-3 py-1.5 rounded-lg text-xs">
            <span className="text-negative font-semibold">Worst Case Shock:</span>
            <span className="text-negative font-medium">{worst_scenario_name}</span>
            {max_loss_pnl !== null && max_loss_pnl !== undefined && (
              <span className="text-negative font-sans font-bold">
                (${Math.abs(Number(max_loss_pnl) || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })})
              </span>
            )}
          </div>
        )}
      </div>

      {/* Comparison Table */}
      <div className="overflow-x-auto border border-line rounded-lg">
        <table className="w-full text-left text-xs text-secondary">
          <thead className="bg-canvas/80 text-muted uppercase font-semibold border-b border-line">
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
          <tbody className="divide-y divide-slate-800/60 font-sans">
            {scenarios.map((scen) => {
              const pnl = Number(scen.stressed_pnl) || 0;
              const isLoss = pnl < 0;
              const baselineNav = Number(scen.baseline_nav) || 0;
              const stressedNav = Number(scen.stressed_nav) || 0;
              const retPct = Number(scen.return_percentage) || 0;

              return (
                <tr
                  key={scen.calculation_id}
                  className="hover:bg-subtle/40 transition-colors"
                >
                  <td className="py-2.5 px-3 font-bold text-muted">
                    #{scen.loss_rank}
                  </td>
                  <td className="py-2.5 px-3 font-semibold text-ink font-sans">
                    {scen.scenario_name}
                  </td>
                  <td className="py-2.5 px-3">
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-brand-soft text-brand border border-brand/20 font-sans">
                      {scen.category}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-right text-muted">
                    ${baselineNav.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </td>
                  <td className="py-2.5 px-3 text-right text-secondary">
                    ${stressedNav.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </td>
                  <td
                    className={`py-2.5 px-3 text-right font-bold ${
                      isLoss ? 'text-negative' : 'text-positive'
                    }`}
                  >
                    {isLoss ? '-' : '+'}$
                    {Math.abs(pnl).toLocaleString(undefined, {
                      maximumFractionDigits: 0,
                    })}
                  </td>
                  <td
                    className={`py-2.5 px-3 text-right ${
                      retPct < 0 ? 'text-negative' : 'text-positive'
                    }`}
                  >
                    {retPct >= 0 ? '+' : ''}
                    {retPct.toFixed(2)}%
                  </td>
                  <td className="py-2.5 px-3 font-sans">
                    {scen.is_compatible ? (
                      <span className="text-[11px] text-positive flex items-center gap-1 font-semibold">
                        <Check className="size-3 stroke-[2.5]" />
                        <span>Aligned</span>
                      </span>
                    ) : (
                      <span className="text-[11px] text-warning flex items-center gap-1 font-semibold" title={scen.compatibility_warning || 'Snapshot variance'}>
                        <AlertTriangle className="size-3 stroke-[2.5]" />
                        <span>Snapshot Mismatch</span>
                      </span>
                    )}
                  </td>
                  <td className="py-2.5 px-3 text-center font-sans">
                    {onSelectScenario && (
                      <button
                        onClick={() => onSelectScenario(scen.calculation_id)}
                        className="px-2 py-1 text-[11px] font-medium text-brand hover:text-brand hover:bg-brand-hover-soft/60 rounded border border-brand/20 transition"
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
