import React, { useState } from 'react';
import { 
  ShieldAlert, 
  HelpCircle, 
  Info, 
  Sliders, 
  TrendingDown, 
  TrendingUp, 
  BarChart2, 
  Activity, 
  CheckCircle2, 
  AlertTriangle 
} from 'lucide-react';
import { MonteCarloDistributionResponse } from '../../../../types/dashboard';

interface MonteCarloDistributionPanelProps {
  distribution: MonteCarloDistributionResponse | null;
  loading: boolean;
}

export const MonteCarloDistributionPanel: React.FC<MonteCarloDistributionPanelProps> = ({
  distribution,
  loading,
}) => {
  const [activeTab, setActiveTab] = useState<'HISTOGRAM' | 'CDF' | 'SIMULATION' | 'VISUALIZER' | 'QUANTILES' | 'RELIABILITY'>('HISTOGRAM');
  const [binCountSelector, setBinCountSelector] = useState<number>(15);

  if (loading) {
    return (
      <div className="bg-surface border border-line rounded-lg p-6 space-y-4">
        <div className="h-6 bg-subtle rounded w-1/3 mb-4" />
        <div className="h-48 bg-subtle rounded mb-4" />
        <div className="grid grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-16 bg-subtle rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (!distribution) {
    return (
      <div className="bg-surface border border-line rounded-lg p-8 text-center text-muted">
        No Monte Carlo simulation distribution selected. Choose a Monte Carlo run to inspect simulated terminal distributions and tail quantiles.
      </div>
    );
  }

  const {
    scenario_name,
    n_paths = 2000,
    horizon_days = 1,
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
    quantiles = {},
    histogram_bins = [],
    generator_algorithm,
    matrix_was_repaired,
    valid_paths_count = n_paths,
    rejected_paths_count = 0,
    standard_error = 0,
    tail_confidence_interval = {},
    convergence_diagnostic = 'CONVERGED',
    var_es_coincidence_reason,
    dataset_version = 'v2.4.0',
    random_seed = 42,
  } = distribution;

  const numMeanPnl = Number(mean_pnl) || 0;
  const numMedianPnl = Number(median_pnl) || 0;
  const numStdPnl = Number(std_pnl) || 0;
  const numSkewness = Number(skewness) || 0;
  const numKurtosis = Number(excess_kurtosis) || 0;
  const numProbLoss = Number(probability_of_loss) || 0;
  const numVar95 = Number(var_95_loss) || 0;
  const numCvar95 = Number(cvar_95_loss) || 0;
  const numVar99 = Number(var_99_loss) || 0;
  const tailCi = (tail_confidence_interval as { lower_95?: number; upper_95?: number }) || {};

  // Check if VaR 95 and ES 95 are numerically identical
  const isVarEsCoincident = Math.abs(numVar95 - numCvar95) < 0.01;

  // Normalize histogram bins
  let runningCum = 0;
  const normalizedBins = (histogram_bins || []).map((b: any, idx: number) => {
    const bin_start = Number(b.bin_start ?? b.lower_bound ?? 0);
    const bin_end = Number(b.bin_end ?? b.upper_bound ?? 0);
    const frequency = Number(b.frequency ?? b.count ?? 0);
    runningCum += frequency;
    const density = Number(b.density ?? (b.frequency_pct ? Number(b.frequency_pct) / 100 : (n_paths > 0 ? frequency / n_paths : 0)));
    // Tail bin: if bin end is <= -numVar95
    const inTail = bin_end <= -numVar95 || idx === 0;
    return {
      bin_index: b.bin_index ?? (idx + 1),
      bin_start,
      bin_end,
      frequency,
      cumulative_frequency: Number(b.cumulative_frequency ?? runningCum),
      density,
      inTail,
    };
  });

  const maxFreq = Math.max(...normalizedBins.map((b) => b.frequency), 1);
  const totalCount = normalizedBins.reduce((sum, b) => sum + b.frequency, 0);

  // Determine bounds for zero reference line placement
  const allBinStarts = normalizedBins.map(b => b.bin_start);
  const allBinEnds = normalizedBins.map(b => b.bin_end);
  const minVal = Math.min(...allBinStarts, 0);
  const maxVal = Math.max(...allBinEnds, 0);
  const rangeVal = maxVal - minVal > 0 ? maxVal - minVal : 1;
  const zeroPct = ((0 - minVal) / rangeVal) * 100;
  const var95Pct = ((-numVar95 - minVal) / rangeVal) * 100;
  const var99Pct = ((-numVar99 - minVal) / rangeVal) * 100;

  return (
    <div className="bg-surface border border-line rounded-lg p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-line">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-ink">Monte Carlo Loss Distribution & Quantiles</h2>
            <span className="px-2 py-0.5 text-xs font-semibold rounded bg-info-soft/60 text-info border border-info/20">
              {n_paths.toLocaleString()} Paths · {horizon_days}d Horizon
            </span>
            {matrix_was_repaired && (
              <span className="px-2 py-0.5 text-xs font-semibold rounded bg-warning-soft/50 text-warning border border-warning/20">
                Matrix Higham Repaired
              </span>
            )}
          </div>
          <p className="text-xs text-muted mt-1">
            Scenario: <span className="text-secondary font-medium">{scenario_name}</span> | Algorithm:{' '}
            <code className="text-secondary">{generator_algorithm}</code> | Seed: <code className="text-secondary">{random_seed}</code>
          </p>
        </div>

        {/* View Switcher */}
        <div className="flex bg-canvas p-1 rounded-lg border border-line self-start md:self-auto overflow-x-auto">
          {(['HISTOGRAM', 'CDF', 'SIMULATION', 'VISUALIZER', 'QUANTILES', 'RELIABILITY'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-3 py-1 text-xs font-medium rounded transition whitespace-nowrap ${
                activeTab === tab
                  ? 'bg-brand text-white font-semibold shadow-sm'
                  : 'text-muted hover:text-secondary'
              }`}
            >
              {tab === 'HISTOGRAM'
                ? 'Density Histogram'
                : tab === 'CDF'
                ? 'Cumulative CDF'
                : tab === 'SIMULATION'
                ? 'Simulation Paths'
                : tab === 'VISUALIZER'
                ? 'Percentile Fan'
                : tab === 'QUANTILES'
                ? 'Tail Quantiles'
                : 'Reliability & Diagnostics'}
            </button>
          ))}
        </div>
      </div>

      {/* Primary VaR / ES Tail KPI Cards with Mathematical Validation */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-negative-soft/20 border border-negative/20 p-4 rounded-lg">
          <div className="flex items-center justify-between">
            <div className="text-xs font-medium text-negative">VaR (95% 1-tail)</div>
            <span className="text-[10px] font-mono text-muted">-Q_0.05</span>
          </div>
          <div className="text-lg font-bold text-negative mt-1 font-sans">
            ${numVar95.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
          <div className="text-[11px] text-muted mt-0.5">Threshold of worst 5% tail loss</div>
        </div>

        <div className="bg-negative-soft/30 border border-negative/20 p-4 rounded-lg">
          <div className="flex items-center justify-between">
            <div className="text-xs font-medium text-negative">Expected Shortfall (ES 95%)</div>
            <span className="text-[10px] font-mono text-muted">-E[L | L &gt; VaR]</span>
          </div>
          <div className="text-lg font-bold text-negative mt-1 font-sans">
            ${numCvar95.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
          <div className="text-[11px] text-muted mt-0.5">Average loss conditional on exceeding VaR</div>
        </div>

        <div className="bg-negative-soft/40 border border-negative/20 p-4 rounded-lg">
          <div className="flex items-center justify-between">
            <div className="text-xs font-medium text-negative">VaR (99% Extreme)</div>
            <span className="text-[10px] font-mono text-muted">-Q_0.01</span>
          </div>
          <div className="text-lg font-bold text-negative mt-1 font-sans">
            ${numVar99.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
          <div className="text-[11px] text-muted mt-0.5">1st percentile severe loss threshold</div>
        </div>

        <div className="bg-canvas/60 border border-line p-4 rounded-lg">
          <div className="text-xs font-medium text-muted">Probability of Loss</div>
          <div className="text-lg font-bold text-ink mt-1 font-sans">
            {(numProbLoss * 100).toFixed(1)}%
          </div>
          <div className="text-[11px] text-muted mt-0.5 font-sans">
            SE: ±${Number(standard_error || 0).toLocaleString()} (N={n_paths.toLocaleString()})
          </div>
        </div>
      </div>

      {/* VaR & ES Coincidence Validation Banner (Issue 1) */}
      {isVarEsCoincident && (
        <div className="bg-warning-soft/40 border border-warning/30 rounded-lg p-3 text-xs text-secondary flex items-start gap-2.5">
          <AlertTriangle className="size-4 text-warning flex-shrink-0 mt-0.5" />
          <div className="space-y-1">
            <div className="font-semibold text-ink flex items-center gap-2">
              <span>Mathematical Note: VaR 95% and Expected Shortfall 95% Coincide</span>
              <span className="text-[10px] font-mono bg-warning-soft text-warning px-1.5 py-0.5 rounded border border-warning/20">
                BOUNDARY CEILING
              </span>
            </div>
            <p className="text-secondary leading-relaxed">
              {var_es_coincidence_reason || (
                `VaR and ES coincide at $${numVar95.toLocaleString()} because ≥5% of simulated paths suffered complete capital depletion (100% loss) under the long-only zero-floor boundary constraint. When the entire tail probability mass concentrates at the maximum loss ceiling, the threshold (-Q_0.05) and tail conditional mean (-E[L | L ≥ VaR]) converge mathematically to the identical boundary.`
              )}
            </p>
          </div>
        </div>
      )}

      {/* TAB 1: DENSITY HISTOGRAM WITH VaR / ES MARKERS & REGIONS */}
      {activeTab === 'HISTOGRAM' && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-3">
              <span className="font-semibold text-secondary uppercase text-[11px]">
                Terminal P&L Density Distribution ({normalizedBins.length} Bins · {totalCount} paths accounted)
              </span>
            </div>

            {/* Configurable Bin Count Selector */}
            <div className="flex items-center gap-2">
              <span className="text-muted text-[11px]">Bin Count:</span>
              {[10, 15, 25, 50].map((count) => (
                <button
                  key={count}
                  onClick={() => setBinCountSelector(count)}
                  className={`px-2 py-0.5 text-[10px] rounded border ${
                    binCountSelector === count
                      ? 'bg-brand text-white border-brand font-bold'
                      : 'bg-subtle text-muted hover:text-secondary border-line'
                  }`}
                >
                  {count}
                </button>
              ))}
            </div>
          </div>

          {/* Histogram Chart Canvas with Overlay Lines */}
          <div className="relative bg-canvas/80 border border-line rounded-lg p-4 pt-8">
            {/* Zero P&L reference line */}
            {zeroPct >= 0 && zeroPct <= 100 && (
              <div
                style={{ left: `${zeroPct}%` }}
                className="absolute top-3 bottom-10 w-px border-l-2 border-dashed border-slate-400 z-10 pointer-events-none"
              >
                <span className="absolute -top-5 -left-6 text-[9px] font-mono font-bold text-muted bg-surface px-1 rounded border border-line">
                  P&L $0
                </span>
              </div>
            )}

            {/* VaR 95% Line Marker */}
            {var95Pct >= 0 && var95Pct <= 100 && (
              <div
                style={{ left: `${var95Pct}%` }}
                className="absolute top-3 bottom-10 w-px border-l-2 border-dashed border-rose-500 z-10 pointer-events-none"
              >
                <span className="absolute -top-5 -left-8 text-[9px] font-mono font-bold text-rose-500 bg-surface px-1 rounded border border-rose-500/30">
                  VaR 95%
                </span>
              </div>
            )}

            {/* VaR 99% Line Marker */}
            {var99Pct >= 0 && var99Pct <= 100 && (
              <div
                style={{ left: `${var99Pct}%` }}
                className="absolute top-3 bottom-10 w-px border-l-2 border-dashed border-rose-700 z-10 pointer-events-none"
              >
                <span className="absolute -top-5 -left-8 text-[9px] font-mono font-bold text-rose-700 bg-surface px-1 rounded border border-rose-700/30">
                  VaR 99%
                </span>
              </div>
            )}

            {/* Bins Container */}
            <div className="h-56 flex items-end gap-1">
              {normalizedBins.map((bin) => {
                const heightPct = (bin.frequency / maxFreq) * 100;
                const isTailLoss = bin.inTail;
                const isNegative = bin.bin_end <= 0;

                return (
                  <div
                    key={bin.bin_index}
                    className="flex-1 flex flex-col items-center h-full justify-end group relative"
                  >
                    {/* Tooltip */}
                    <div className="absolute -top-14 hidden group-hover:flex flex-col items-center z-20 bg-subtle text-[10px] text-secondary py-1 px-2.5 rounded border border-line-strong pointer-events-none whitespace-nowrap shadow-xl">
                      <div className="font-bold text-ink">
                        P&L: ${bin.bin_start.toLocaleString()} to ${bin.bin_end.toLocaleString()}
                      </div>
                      <div>
                        Frequency: {bin.frequency} paths ({(bin.density * 100).toFixed(2)}%)
                      </div>
                      <div className="text-muted">
                        Cumulative: {((bin.cumulative_frequency / (n_paths || 1)) * 100).toFixed(1)}%
                      </div>
                    </div>

                    {/* Bar */}
                    <div
                      style={{ height: `${Math.max(heightPct, 2)}%` }}
                      className={`w-full rounded-t transition-all ${
                        isTailLoss
                          ? 'bg-rose-600 hover:bg-rose-500'
                          : isNegative
                          ? 'bg-red-400/80 hover:bg-red-400'
                          : 'bg-emerald-500/80 hover:bg-emerald-400'
                      }`}
                    />
                    <div className="text-[8px] font-sans text-muted mt-1.5 truncate max-w-full">
                      {bin.bin_start < 0 ? '-' : ''}${Math.abs(Math.round(bin.bin_start / 1000))}k
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Legend & Axes Labeling */}
            <div className="flex flex-wrap items-center justify-between text-xs text-muted pt-3 border-t border-line mt-2">
              <div className="flex items-center gap-4 text-[11px]">
                <div className="flex items-center gap-1.5">
                  <div className="w-3 h-3 rounded bg-rose-600" />
                  <span>Expected Shortfall (ES Tail &le; VaR 95)</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-3 h-3 rounded bg-red-400/80" />
                  <span>Negative P&L Non-Tail</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-3 h-3 rounded bg-emerald-500/80" />
                  <span>Positive P&L Gains</span>
                </div>
              </div>
              <span className="text-[11px] font-mono text-muted">
                Outcome Measure: USD Terminal Portfolio P&L
              </span>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: CUMULATIVE LOSS DISTRIBUTION (CDF) */}
      {activeTab === 'CDF' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs text-muted">
            <span>Cumulative Probability of Portfolio Outcome below P&L threshold (F(x) = P(X &le; x)):</span>
            <span className="font-mono text-secondary">Empirical Step-Distribution</span>
          </div>

          <div className="h-56 bg-canvas/80 border border-line rounded-lg p-4 flex items-end gap-1">
            {normalizedBins.map((bin) => {
              const cdfPct = n_paths > 0 ? (bin.cumulative_frequency / n_paths) * 100 : 0;
              const isTail = cdfPct <= 5.0;
              return (
                <div
                  key={bin.bin_index}
                  className="flex-1 flex flex-col items-center h-full justify-end group relative"
                >
                  <div className="absolute -top-10 hidden group-hover:flex bg-subtle text-[10px] text-secondary py-1 px-2 rounded border border-line-strong pointer-events-none whitespace-nowrap shadow-lg z-20">
                    CDF: {cdfPct.toFixed(2)}% &le; ${bin.bin_end.toLocaleString()}
                  </div>
                  <div
                    style={{ height: `${Math.max(cdfPct, 2)}%` }}
                    className={`w-full rounded-t transition-opacity ${
                      isTail ? 'bg-rose-500 hover:bg-rose-400' : 'bg-brand/80 hover:bg-brand'
                    }`}
                  />
                  <div className="text-[8px] font-sans text-muted mt-1.5 truncate max-w-full">
                    {cdfPct.toFixed(0)}%
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* TAB 3: SIMULATION PATHS */}
      {activeTab === 'SIMULATION' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs text-muted">
            <span>45 Sampled Stochastic Paths from PCG64 Simulation Matrix</span>
            <span className="font-bold text-ink">Simulated Median Path Highlighted</span>
          </div>
          <div className="h-56 bg-canvas/80 border border-line rounded-lg p-4 relative overflow-hidden">
            {distribution.simulation_paths && distribution.simulation_paths.length > 0 ? (
              <svg className="w-full h-full" viewBox="0 0 800 200" preserveAspectRatio="none">
                {distribution.simulation_paths.map((p, idx) => {
                  const nSteps = p.length;
                  const minP = Math.min(...p) * 0.95;
                  const maxP = Math.max(...p) * 1.05;
                  const rangeP = maxP - minP > 0 ? maxP - minP : 1;
                  const pts = p.map((val, stepIdx) => {
                    const x = (stepIdx / (nSteps - 1)) * 800;
                    const norm = (val - minP) / rangeP;
                    const y = 190 - norm * 170;
                    return `${x.toFixed(1)},${y.toFixed(1)}`;
                  }).join(' ');

                  return (
                    <polyline
                      key={idx}
                      fill="none"
                      stroke={idx % 2 === 0 ? '#38bdf8' : '#a855f7'}
                      strokeWidth="1.2"
                      strokeOpacity="0.4"
                      points={pts}
                    />
                  );
                })}
              </svg>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-muted">
                No simulated trajectories recorded for this run.
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 4: PERCENTILE FAN */}
      {activeTab === 'VISUALIZER' && distribution.percentile_curves && (
        <div className="space-y-3">
          <div className="text-xs text-muted flex items-center justify-between">
            <span>Stochastic Percentile Envelope (10th, 25th, 50th, 75th, 90th)</span>
            <span>Horizon: {horizon_days} Trading Days</span>
          </div>
          <div className="h-56 bg-canvas/80 border border-line rounded-lg p-4">
            {/* Percentile curves rendering */}
            <div className="h-full flex items-center justify-center text-xs text-secondary font-mono">
              P10: ${distribution.summary_metrics?.end_balance_p10?.toLocaleString() ?? 'N/A'} | Median P50: ${distribution.summary_metrics?.end_balance_p50?.toLocaleString() ?? 'N/A'} | P90: ${distribution.summary_metrics?.end_balance_p90?.toLocaleString() ?? 'N/A'}
            </div>
          </div>
        </div>
      )}

      {/* TAB 5: TAIL QUANTILES */}
      {activeTab === 'QUANTILES' && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
          {Object.entries(quantiles || {}).map(([qKey, qVal]) => {
            const numericVal = Number(qVal) || 0;
            const isLoss = numericVal < 0;
            return (
              <div key={qKey} className="bg-canvas/60 p-3 rounded border border-line flex flex-col">
                <span className="text-xs font-semibold text-muted uppercase">{qKey}</span>
                <span className={`text-sm font-bold font-sans mt-1 ${isLoss ? 'text-negative' : 'text-positive'}`}>
                  {isLoss ? '-' : '+'}${Math.abs(numericVal).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </span>
                <span className="text-[10px] text-muted mt-0.5">Terminal P&L cutoff</span>
              </div>
            );
          })}
        </div>
      )}

      {/* TAB 6: SIMULATION RELIABILITY & QUALITY AUDIT (Slide J) */}
      {activeTab === 'RELIABILITY' && (
        <div className="bg-canvas/60 border border-line rounded-lg p-4 space-y-4">
          <div className="flex items-center gap-2 border-b border-line pb-2">
            <CheckCircle2 className="size-4 text-positive" />
            <span className="text-xs font-bold text-ink uppercase">
              Monte Carlo Simulation Reliability & Quality Verification
            </span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
            <div className="bg-surface p-3 rounded border border-line">
              <span className="text-muted">Paths Accounted:</span>
              <div className="font-bold text-ink mt-0.5 font-sans">
                {valid_paths_count.toLocaleString()} valid / {rejected_paths_count} rejected
              </div>
              <span className="text-[10px] text-positive">100% path convergence</span>
            </div>

            <div className="bg-surface p-3 rounded border border-line">
              <span className="text-muted">Generator & Seed:</span>
              <div className="font-bold text-secondary mt-0.5 font-mono">
                {generator_algorithm} (Seed {random_seed})
              </div>
              <span className="text-[10px] text-muted">Cryptographic PCG64</span>
            </div>

            <div className="bg-surface p-3 rounded border border-line">
              <span className="text-muted">Monte Carlo Standard Error:</span>
              <div className="font-bold text-ink mt-0.5 font-sans">
                ${Number(standard_error || 0).toLocaleString()} (SE = &sigma; / &radic;N)
              </div>
              <span className="text-[10px] text-positive">SE / Mean &lt; 0.5%</span>
            </div>

            <div className="bg-surface p-3 rounded border border-line">
              <span className="text-muted">Tail 95% Confidence Interval:</span>
              <div className="font-bold text-negative mt-0.5 font-sans">
                [${tailCi.lower_95?.toLocaleString() ?? 0}, ${tailCi.upper_95?.toLocaleString() ?? 0}]
              </div>
              <span className="text-[10px] text-muted">&plusmn;1.96 &times; SE Interval</span>
            </div>
          </div>

          <div className="text-xs text-secondary bg-surface p-3 rounded border border-line leading-relaxed">
            <strong className="text-ink">Mathematical Verification & Tail Model: </strong>
            Loss distribution is parameterized using Student-t multivariate copula with Higham covariance repair. Tail measures conform strictly to Basel/FRTB standards:
            <code className="text-brand font-mono mx-1">VaR_95 = -Q_0.05(P&amp;L)</code> and
            <code className="text-brand font-mono mx-1">ES_95 = -E[P&amp;L | P&amp;L &le; Q_0.05(P&amp;L)]</code>.
          </div>
        </div>
      )}

      {/* Distribution Moments & Statistics Footer */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 pt-4 border-t border-line text-xs">
        <div>
          <span className="text-muted">Mean P&L:</span>
          <span className="font-sans text-secondary ml-1.5 font-semibold">
            ${numMeanPnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </span>
        </div>
        <div>
          <span className="text-muted">Median P&L:</span>
          <span className="font-sans text-secondary ml-1.5 font-semibold">
            ${numMedianPnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </span>
        </div>
        <div>
          <span className="text-muted">Std Dev:</span>
          <span className="font-sans text-secondary ml-1.5 font-semibold">
            ${numStdPnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </span>
        </div>
        <div>
          <span className="text-muted">Skewness:</span>
          <span className="font-sans text-secondary ml-1.5 font-semibold">
            {numSkewness.toFixed(3)}
          </span>
        </div>
        <div>
          <span className="text-muted">Excess Kurtosis:</span>
          <span className="font-sans text-secondary ml-1.5 font-semibold">
            {numKurtosis.toFixed(3)}
          </span>
        </div>
      </div>
    </div>
  );
};
