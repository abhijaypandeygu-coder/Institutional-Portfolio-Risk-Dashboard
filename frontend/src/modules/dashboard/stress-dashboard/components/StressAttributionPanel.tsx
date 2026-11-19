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
      <div className="bg-surface border border-line rounded-lg p-6 ">
        <div className="h-6 bg-subtle rounded w-1/4 mb-4" />
        <div className="h-32 bg-subtle rounded mb-4" />
      </div>
    );
  }

  if (!attribution) {
    return (
      <div className="bg-surface border border-line rounded-lg p-8 text-center text-muted">
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

  const totalLoss = Number(total_stressed_pnl) || 0;
  const explainedLoss = Number(explained_pnl) || 0;
  const residual = Number(residual_amount) || 0;
  const hhi = Number(loss_hhi) || 0;
  const effCount = Number(effective_contributor_count) || 0;

  const currentContributors =
    viewDimension === 'POSITION'
      ? position_contributors
      : viewDimension === 'SECTOR'
      ? sector_contributors
      : factor_contributors;

  return (
    <div className="bg-surface border border-line rounded-lg p-6 space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-line">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-ink">Stress Loss Attribution & Decomposition</h2>
            <span
              className={`px-2 py-0.5 text-xs font-semibold rounded ${
                is_reconciled
                  ? 'bg-positive-soft/60 text-positive border border-positive/20'
                  : 'bg-warning-soft/60 text-warning border border-warning/20'
              }`}
            >
              {reconciliation_status}
            </span>
          </div>
          <p className="text-xs text-muted mt-1">
            Scenario: <span className="text-secondary font-medium">{scenario_name}</span> | Effective Contributors:{' '}
            <span className="font-sans text-secondary font-semibold">{effCount.toFixed(1)}</span> · Loss HHI:{' '}
            <span className="font-sans text-secondary font-semibold">{hhi.toFixed(2)}</span>
          </p>
        </div>

        {/* Dimension Switcher */}
        <div className="flex bg-canvas p-1 rounded-lg border border-line self-start md:self-auto">
          {(['POSITION', 'SECTOR', 'FACTOR'] as const).map((dim) => (
            <button
              key={dim}
              onClick={() => setViewDimension(dim)}
              className={`px-3 py-1 text-xs font-medium rounded transition ${
                viewDimension === dim
                  ? 'bg-brand text-white font-semibold'
                  : 'text-muted hover:text-secondary'
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
        <div className="bg-canvas/60 p-4 rounded-lg border border-line">
          <div className="text-xs font-medium text-muted">Authoritative Scenario Loss</div>
          <div className="text-lg font-bold text-negative font-sans mt-1">
            ${Math.abs(totalLoss).toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
          <div className="text-xs text-muted mt-0.5">M10 total stressed P&L</div>
        </div>

        <div className="bg-canvas/60 p-4 rounded-lg border border-line">
          <div className="text-xs font-medium text-muted">Sum of Explained Drivers</div>
          <div className="text-lg font-bold text-secondary font-sans mt-1">
            ${Math.abs(explainedLoss).toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
          <div className="text-xs text-muted mt-0.5">Direct factor / position decomposition</div>
        </div>

        <div
          className={`p-4 rounded-lg border ${
            Math.abs(residual) > 1.0
              ? 'bg-warning-soft/20 border-warning/20'
              : 'bg-positive-soft/20 border-positive/20'
          }`}
        >
          <div className="text-xs font-medium text-muted">Residual / Cross-Terms</div>
          <div
            className={`text-lg font-bold font-sans mt-1 ${
              Math.abs(residual) > 1.0 ? 'text-warning' : 'text-positive'
            }`}
          >
            ${residual.toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </div>
          <div className="text-xs text-muted mt-0.5">
            {is_reconciled ? 'Clean exact arithmetic reconciliation' : 'Nonlinear cross-term variance'}
          </div>
        </div>

        <div className="bg-canvas/60 p-4 rounded-lg border border-line">
          <div className="text-xs font-medium text-muted">Top Dimension Contributors</div>
          <div className="text-lg font-bold text-ink font-sans mt-1">
            {currentContributors.length} items
          </div>
          <div className="text-xs text-muted mt-0.5">Ranked by absolute loss contribution</div>
        </div>
      </div>

      {/* Waterfall-Style Decomposition Table */}
      <div className="overflow-x-auto border border-line rounded-lg">
        <table className="w-full text-left text-xs text-secondary">
          <thead className="bg-canvas/80 text-muted uppercase font-semibold border-b border-line">
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
          <tbody className="divide-y divide-slate-800/60 font-sans">
            {currentContributors.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-4 text-center text-muted font-sans">
                  No {viewDimension.toLowerCase()} attribution records available for this run.
                </td>
              </tr>
            ) : (
              currentContributors.map((item, idx) => {
                const stressedPnl = Number(item.stressed_pnl) || 0;
                const isLoss = stressedPnl < 0;
                const contribPct = Number(item.contribution_percentage) || 0;
                const barWidth = Math.min(Math.abs(contribPct), 100);
                const exposure = Number(item.baseline_exposure) || 0;
                const lossAmt = Number(item.contribution_to_loss) || 0;

                return (
                  <tr
                    key={idx}
                    className="hover:bg-subtle/40 transition-colors"
                  >
                    <td className="py-2.5 px-3 font-semibold text-ink font-sans">
                      {item.dimension_name}
                    </td>
                    <td className="py-2.5 px-3 text-right text-muted">
                      ${exposure.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </td>
                    <td
                      className={`py-2.5 px-3 text-right font-bold ${
                        isLoss ? 'text-negative' : 'text-positive'
                      }`}
                    >
                      {isLoss ? '-' : '+'}$
                      {Math.abs(stressedPnl).toLocaleString(undefined, {
                        maximumFractionDigits: 0,
                      })}
                    </td>
                    <td className="py-2.5 px-3 text-right text-secondary font-semibold">
                      ${Math.abs(lossAmt).toLocaleString(undefined, {
                        maximumFractionDigits: 0,
                      })}
                    </td>
                    <td className="py-2.5 px-3 text-right font-bold text-negative">
                      {contribPct.toFixed(2)}%
                    </td>
                    <td className="py-2.5 px-3">
                      <div className="w-full bg-subtle rounded-full h-2 overflow-hidden">
                        <div
                          style={{ width: `${barWidth}%` }}
                          className={`h-full rounded-full ${
                            isLoss ? 'bg-rose-500' : 'bg-brand'
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
