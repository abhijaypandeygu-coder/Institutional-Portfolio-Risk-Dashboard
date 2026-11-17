import React, { useState } from 'react';
import { MonteCarloDistributionResponse } from '../../../types/dashboard';

interface MonteCarloDistributionPanelProps {
  distribution: MonteCarloDistributionResponse | null;
  loading: boolean;
}

export const MonteCarloDistributionPanel: React.FC<MonteCarloDistributionPanelProps> = ({
  distribution,
  loading,
}) => {
  const [activeTab, setActiveTab] = useState<'HISTOGRAM' | 'CDF' | 'QUANTILES'>('HISTOGRAM');

  if (loading) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 animate-pulse">
        <div className="h-6 bg-slate-800 rounded w-1/3 mb-4" />
        <div className="h-48 bg-slate-800 rounded mb-4" />
        <div className="grid grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-16 bg-slate-800 rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (!distribution) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-8 text-center text-slate-400">
        No Monte Carlo simulation distribution selected. Choose a Monte Carlo run to inspect simulated terminal distributions and tail quantiles.
      </div>
    );
  }

  const {
    scenario_name,
    n_paths,
    horizon_days,
    mean_pnl,
    median_pnl,
    std_pnl,
    skewness,
    excess_kurtosis,
    probability_of_loss,
    var_95_loss,
    cvar_95_loss,
    var_99_loss,
    cvar_99_loss,
    quantiles,
    histogram_bins,
    generator_algorithm,
    matrix_was_repaired,
  } = distribution;

  const maxFreq = Math.max(...histogram_bins.map((b) => b.frequency), 1);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-white">Monte Carlo Loss Distribution</h2>
            <span className="px-2 py-0.5 text-xs font-semibold rounded bg-purple-900/60 text-purple-300 border border-purple-700/50">
              {n_paths.toLocaleString()} Paths · {horizon_days}d Horizon
            </span>
            {matrix_was_repaired && (
              <span className="px-2 py-0.5 text-xs font-semibold rounded bg-amber-900/50 text-amber-300 border border-amber-700/50">
                Matrix Higham Repaired
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Scenario: <span className="text-slate-200 font-medium">{scenario_name}</span> | Algorithm:{' '}
            <code className="text-slate-300">{generator_algorithm}</code>
          </p>
        </div>

        {/* View Switcher */}
        <div className="flex bg-slate-950 p-1 rounded-lg border border-slate-800 self-start md:self-auto">
          {(['HISTOGRAM', 'CDF', 'QUANTILES'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-3 py-1 text-xs font-medium rounded transition ${
                activeTab === tab
                  ? 'bg-blue-600 text-white font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {tab === 'HISTOGRAM'
                ? 'Density Histogram'
                : tab === 'CDF'
                ? 'Cumulative CDF'
                : 'Tail Quantiles'}
            </button>
          ))}
        </div>
      </div>

      {/* Primary VaR / ES Tail KPI Banners */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-rose-950/20 border border-rose-900/50 p-4 rounded-lg">
          <div className="text-xs font-medium text-rose-300">VaR (95% 1-tail)</div>
          <div className="text-lg font-bold text-rose-400 mt-1 font-mono">
            ${var_95_loss.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">5th percentile loss amount</div>
        </div>

        <div className="bg-rose-950/30 border border-rose-800/60 p-4 rounded-lg">
          <div className="text-xs font-medium text-rose-300">Expected Shortfall (CVaR 95%)</div>
          <div className="text-lg font-bold text-rose-300 mt-1 font-mono">
            ${cvar_95_loss.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">Average loss beyond 95% VaR</div>
        </div>

        <div className="bg-rose-950/40 border border-rose-700/70 p-4 rounded-lg">
          <div className="text-xs font-medium text-rose-200">VaR (99% Extreme Tail)</div>
          <div className="text-lg font-bold text-rose-200 mt-1 font-mono">
            ${var_99_loss.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">1st percentile loss amount</div>
        </div>

        <div className="bg-slate-950/60 border border-slate-800 p-4 rounded-lg">
          <div className="text-xs font-medium text-slate-400">Probability of Loss</div>
          <div className="text-lg font-bold text-white mt-1 font-mono">
            {(probability_of_loss * 100).toFixed(1)}%
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">
            Paths ending in negative P&L
          </div>
        </div>
      </div>

      {/* Main Visual Display */}
      {activeTab === 'HISTOGRAM' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Stressed Loss Tail (Left)</span>
            <span>Terminal P&L Density Distribution (15 Bins)</span>
            <span>Upside Gains (Right)</span>
          </div>

          <div className="h-48 bg-slate-950/60 border border-slate-800 rounded-lg p-3 flex items-end gap-1.5">
            {histogram_bins.map((bin) => {
              const heightPct = (bin.frequency / maxFreq) * 100;
              const isTail = bin.is_tail_bin;
              const isNeg = bin.bin_end <= 0;

              return (
                <div
                  key={bin.bin_index}
                  className="flex-1 flex flex-col items-center h-full justify-end group relative"
                >
                  {/* Tooltip */}
                  <div className="absolute -top-12 hidden group-hover:flex flex-col items-center z-10 bg-slate-800 text-[10px] text-slate-200 py-1 px-2 rounded border border-slate-700 pointer-events-none whitespace-nowrap shadow-lg">
                    <div>
                      Range: ${bin.bin_start.toFixed(0)} to ${bin.bin_end.toFixed(0)}
                    </div>
                    <div>
                      Count: {bin.frequency} paths ({(bin.density * 100).toFixed(1)}%)
                    </div>
                  </div>

                  {/* Bar */}
                  <div
                    style={{ height: `${Math.max(heightPct, 3)}%` }}
                    className={`w-full rounded-t transition-all duration-200 ${
                      isTail
                        ? 'bg-rose-500 hover:bg-rose-400'
                        : isNeg
                        ? 'bg-amber-600/70 hover:bg-amber-500'
                        : 'bg-emerald-600/70 hover:bg-emerald-500'
                    }`}
                  />
                  <div className="text-[9px] font-mono text-slate-500 mt-1 truncate max-w-full">
                    {bin.bin_start < 0 ? '-' : ''}${Math.abs(Math.round(bin.bin_start / 1000))}k
                  </div>
                </div>
              );
            })}
          </div>

          <div className="flex items-center gap-4 text-xs text-slate-400 pt-1">
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded bg-rose-500" />
              <span>Downside 5% Tail Quantile (VaR 95)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded bg-amber-600/70" />
              <span>Negative P&L Non-Tail</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded bg-emerald-600/70" />
              <span>Positive P&L Gains</span>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'CDF' && (
        <div className="space-y-3">
          <div className="text-xs text-slate-400">
            Cumulative Probability of Portfolio Outcome below P&L threshold:
          </div>
          <div className="h-48 bg-slate-950/60 border border-slate-800 rounded-lg p-3 flex items-end gap-1.5">
            {histogram_bins.map((bin) => {
              const cdfPct = (bin.cumulative_frequency / n_paths) * 100;
              return (
                <div
                  key={bin.bin_index}
                  className="flex-1 flex flex-col items-center h-full justify-end group relative"
                >
                  <div className="absolute -top-10 hidden group-hover:flex bg-slate-800 text-[10px] text-slate-200 py-1 px-2 rounded border border-slate-700 pointer-events-none whitespace-nowrap shadow-lg">
                    CDF: {cdfPct.toFixed(1)}% ≤ ${bin.bin_end.toFixed(0)}
                  </div>
                  <div
                    style={{ height: `${Math.max(cdfPct, 2)}%` }}
                    className="w-full bg-blue-500/80 hover:bg-blue-400 rounded-t transition-all"
                  />
                  <div className="text-[9px] font-mono text-slate-500 mt-1 truncate max-w-full">
                    {cdfPct.toFixed(0)}%
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {activeTab === 'QUANTILES' && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
          {Object.entries(quantiles).map(([qKey, qVal]) => {
            const isLoss = qVal < 0;
            return (
              <div
                key={qKey}
                className="bg-slate-950/60 p-3 rounded border border-slate-800 flex flex-col"
              >
                <span className="text-xs font-semibold text-slate-400 uppercase">{qKey}</span>
                <span
                  className={`text-sm font-bold font-mono mt-1 ${
                    isLoss ? 'text-rose-400' : 'text-emerald-400'
                  }`}
                >
                  {isLoss ? '-' : '+'}${Math.abs(qVal).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </span>
                <span className="text-[10px] text-slate-500 mt-0.5">Terminal P&L cutoff</span>
              </div>
            );
          })}
        </div>
      )}

      {/* Distribution Moments & Statistics Footer */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 pt-4 border-t border-slate-800 text-xs">
        <div>
          <span className="text-slate-500">Mean P&L:</span>
          <span className="font-mono text-slate-200 ml-1.5 font-semibold">
            ${mean_pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </span>
        </div>
        <div>
          <span className="text-slate-500">Median P&L:</span>
          <span className="font-mono text-slate-200 ml-1.5 font-semibold">
            ${median_pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </span>
        </div>
        <div>
          <span className="text-slate-500">Std Dev:</span>
          <span className="font-mono text-slate-200 ml-1.5 font-semibold">
            ${std_pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </span>
        </div>
        <div>
          <span className="text-slate-500">Skewness:</span>
          <span className="font-mono text-slate-200 ml-1.5 font-semibold">
            {skewness.toFixed(3)}
          </span>
        </div>
        <div>
          <span className="text-slate-500">Excess Kurtosis:</span>
          <span className="font-mono text-slate-200 ml-1.5 font-semibold">
            {excess_kurtosis.toFixed(3)}
          </span>
        </div>
      </div>
    </div>
  );
};
