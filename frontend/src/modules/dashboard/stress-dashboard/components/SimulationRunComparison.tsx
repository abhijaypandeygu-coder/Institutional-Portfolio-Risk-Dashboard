import React from 'react';
import { MonteCarloDistributionResponse } from '../../../../types/dashboard';

export interface CompletedSimulation {
  result: MonteCarloDistributionResponse;
  config: Record<string, any>;
  completedAt: string;
}

export function SimulationRunComparison({ runs, onClose }: { runs: CompletedSimulation[]; onClose: () => void }) {
  if (runs.length !== 2) return null;
  const number = (value: unknown, suffix = '') => {
    if (value === null || value === undefined || value === '') return 'Unavailable';
    const n = Number(value);
    return Number.isFinite(n) ? `${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}${suffix}` : 'Unavailable';
  };
  const metrics: Array<[string, (run: CompletedSimulation) => string]> = [
    ['Simulation mode', r => r.config.portfolio_mode === 'INSTITUTIONAL' ? 'Institutional portfolio risk' : 'Wealth projection'],
    ['Horizon (trading days)', r => number(r.result.horizon_days)],
    ['Simulated paths', r => number(r.result.n_paths)],
    ['Initial balance', r => number(r.result.summary_metrics?.initial_balance)],
    ['Median ending balance', r => number(r.result.summary_metrics?.end_balance_p50)],
    ['Mean P&L', r => number(r.result.mean_pnl)],
    ['Median P&L', r => number(r.result.median_pnl)],
    ['95% VaR loss', r => number(r.result.var_95_loss)],
    ['95% expected shortfall', r => number(r.result.cvar_95_loss)],
    ['Probability of loss', r => number(r.result.probability_of_loss == null ? null : Number(r.result.probability_of_loss) * 100, '%')],
    ['Probability of survival', r => number(r.result.summary_metrics?.probability_of_success, '%')],
    ['Quality status', r => r.result.quality_status || 'Unavailable'],
  ];
  return (
    <section aria-labelledby="simulation-comparison-heading" className="rounded-xl border border-line bg-surface p-6 space-y-4">
      <div className="flex items-center justify-between gap-4">
        <h2 id="simulation-comparison-heading" tabIndex={-1} className="text-lg font-semibold text-ink">Simulation comparison</h2>
        <button type="button" onClick={onClose} className="rounded-lg border border-line px-3 py-2 text-sm text-secondary">Close comparison</button>
      </div>
      <p className="text-sm text-muted">Last two successful runs for this portfolio in this session. Amounts use each run’s reported currency; horizons and starting balances may differ. Values are model outputs.</p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead><tr className="border-b border-line">
            <th scope="col" className="p-3">Metric</th>
            {runs.map((r, i) => <th key={i} scope="col" className="p-3">
              {i === 0 ? 'Previous run' : 'Latest run'}
              <span className="block text-xs font-normal text-muted">{new Date(r.completedAt).toLocaleString()}</span>
              <span className="block text-xs font-normal text-muted">Currency: {(r.result as MonteCarloDistributionResponse & { currency?: string }).currency || 'Unavailable'}</span>
              <span className="block text-xs font-normal text-muted">{r.result.simulation_id}</span>
            </th>)}
          </tr></thead>
          <tbody>{metrics.map(([label, value]) => <tr key={label} className="border-b border-line">
            <th scope="row" className="p-3 font-medium text-secondary">{label}</th>
            {runs.map((r, i) => <td key={i} className="p-3 tabular-nums text-ink">{value(r)}</td>)}
          </tr>)}</tbody>
        </table>
      </div>
    </section>
  );
}
