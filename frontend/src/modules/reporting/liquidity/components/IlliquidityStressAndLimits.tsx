import React from 'react';
import {
  IlliquidityConcentration,
  StressComparison,
  LimitImplication,
} from '../../../../types/liquidityReport';

interface Props {
  concentrations: IlliquidityConcentration[];
  stressComparisons: StressComparison[];
  limits: LimitImplication[];
  currency: string;
}

export const IlliquidityStressAndLimits: React.FC<Props> = ({
  concentrations,
  stressComparisons,
  limits,
  currency,
}) => {
  const topPositions = concentrations.filter((c) => c.grouping_type === 'POSITION');
  const sectors = concentrations.filter((c) => c.grouping_type === 'SECTOR');

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
      {/* Illiquidity Concentrations */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 shadow-md">
        <h2 className="text-sm font-semibold text-slate-100 uppercase tracking-wide mb-3 flex items-center justify-between">
          <span>Top Illiquid Positions & Sectors</span>
          <span className="text-[10px] text-slate-400 font-normal">By Liquidation Cost</span>
        </h2>
        
        <div className="space-y-4">
          <div>
            <span className="text-xs font-semibold text-slate-400 block mb-2">Highest Cost Drivers</span>
            <div className="space-y-2">
              {topPositions.map((c) => (
                <div key={c.grouping_reference} className="bg-slate-950 p-2 rounded border border-slate-800 text-xs flex justify-between items-center">
                  <div>
                    <span className="font-semibold text-slate-200">{c.grouping_reference}</span>
                    <span className="text-[10px] text-slate-500 ml-1.5">MV: {currency} {(c.aggregate_position_value / 1e5).toFixed(1)}L</span>
                  </div>
                  <div className="text-right">
                    <span className="font-mono text-amber-400 font-medium">
                      {currency} {c.estimated_liquidation_cost.toFixed(2)}
                    </span>
                    <span className="text-[10px] text-slate-400 ml-1.5 font-mono">
                      ({c.cost_contribution_pct?.toFixed(1) || '0.0'}%)
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="pt-2 border-t border-slate-800">
            <span className="text-xs font-semibold text-slate-400 block mb-2">Sector Cost Concentration</span>
            <div className="space-y-1.5">
              {sectors.map((s) => (
                <div key={s.grouping_reference} className="flex items-center justify-between text-xs py-1 px-1.5 rounded hover:bg-slate-800/50">
                  <span className="text-slate-300">{s.grouping_reference}</span>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-slate-400">{currency} {s.estimated_liquidation_cost.toFixed(1)}</span>
                    <span className="font-mono text-amber-400 font-medium text-[11px] w-12 text-right">
                      {s.cost_contribution_pct?.toFixed(1) || '0.0'}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Liquidity Stress Comparison */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 shadow-md">
        <h2 className="text-sm font-semibold text-slate-100 uppercase tracking-wide mb-3 flex items-center justify-between">
          <span>Liquidity Stress Scenarios</span>
          <span className="text-[10px] text-purple-400 font-mono">M10 Replay / Vacuum</span>
        </h2>

        <div className="space-y-3">
          {stressComparisons.map((sc) => (
            <div key={sc.scenario_id} className="bg-slate-950 p-3 rounded border border-slate-800 text-xs">
              <div className="flex justify-between items-start mb-2">
                <span className="font-bold text-slate-200">{sc.scenario_name}</span>
                <span className="px-1.5 py-0.5 rounded text-[10px] bg-purple-950 text-purple-400 border border-purple-800 font-mono">
                  {sc.scenario_horizon}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-400 mb-2">
                <div>
                  Spread: <span className="text-slate-200 font-mono">{sc.stressed_spread_bps.toFixed(0)} bps</span>{' '}
                  <span className="text-rose-400 text-[10px]">(+{sc.spread_widening_pct.toFixed(0)}%)</span>
                </div>
                <div>
                  Depth: <span className="text-slate-200 font-mono">-{sc.depth_reduction_pct.toFixed(0)}%</span>
                </div>
                <div>
                  Horizon: <span className="text-blue-400 font-mono">{sc.stressed_liquidation_time_days.toFixed(1)} Days</span>
                </div>
                <div>
                  Score: <span className="text-slate-200 font-mono">{sc.stressed_liquidity_score.toFixed(0)} / 100</span>
                </div>
              </div>

              <div className="pt-2 border-t border-slate-800 flex justify-between items-center text-xs">
                <span className="text-slate-400">Stressed Liquidation Cost:</span>
                <span className="font-mono font-bold text-rose-400">
                  {currency} {sc.stressed_liquidation_cost.toFixed(2)}{' '}
                  <span className="text-[10px] text-slate-400 font-normal">
                    (+{currency} {sc.incremental_liquidation_cost.toFixed(2)})
                  </span>
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Liquidity Limits & Projected Exceedances */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 shadow-md">
        <h2 className="text-sm font-semibold text-slate-100 uppercase tracking-wide mb-3 flex items-center justify-between">
          <span>M11 Liquidity Limits Evaluation</span>
          <span className="text-[10px] text-slate-400 font-mono">Policy v1.0</span>
        </h2>

        <div className="space-y-3">
          {limits.map((l) => (
            <div key={l.limit_id} className="bg-slate-950 p-3 rounded border border-slate-800 text-xs">
              <div className="flex justify-between items-center mb-1.5">
                <span className="font-semibold text-slate-200">{l.limit_name}</span>
                <span
                  className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                    l.evaluation_status === 'WITHIN_LIMIT'
                      ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                      : l.evaluation_status === 'PROJECTED_STRESS_EXCEEDANCE'
                      ? 'bg-purple-950 text-purple-400 border border-purple-800'
                      : 'bg-rose-950 text-rose-400 border border-rose-800'
                  }`}
                >
                  {l.evaluation_status}
                </span>
              </div>

              <div className="flex justify-between items-center text-[11px] text-slate-400 mb-2">
                <span>Threshold: <span className="font-mono text-slate-200">{l.configured_threshold} {l.threshold_unit}</span></span>
                <span>Observed: <span className="font-mono text-slate-200">{l.current_metric?.toFixed(1) || '-'} {l.threshold_unit}</span></span>
              </div>

              {/* Utilization progress bar */}
              <div className="w-full bg-slate-800 h-1.5 rounded overflow-hidden mb-1">
                <div
                  className={`h-full ${
                    (l.utilization_pct || 0) > 100
                      ? 'bg-rose-500'
                      : (l.utilization_pct || 0) > 80
                      ? 'bg-amber-500'
                      : 'bg-emerald-500'
                  }`}
                  style={{ width: `${Math.min(100, l.utilization_pct || 0)}%` }}
                />
              </div>
              <div className="flex justify-between items-center text-[10px] text-slate-500">
                <span>Utilization: <span className="text-slate-300 font-mono">{(l.utilization_pct || 0).toFixed(1)}%</span></span>
                <span>Stressed: <span className="text-purple-400 font-mono">{l.stressed_metric?.toFixed(1) || '-'} {l.threshold_unit}</span></span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
