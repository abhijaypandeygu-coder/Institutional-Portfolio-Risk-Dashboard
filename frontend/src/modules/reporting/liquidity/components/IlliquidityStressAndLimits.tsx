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
      <div className="bg-surface border border-line rounded-lg p-5 shadow-md">
        <h2 className="text-sm font-semibold text-ink uppercase  mb-3 flex items-center justify-between">
          <span>Top Illiquid Positions & Sectors</span>
          <span className="text-[10px] text-muted font-normal">By Liquidation Cost</span>
        </h2>
        
        <div className="space-y-4">
          <div>
            <span className="text-xs font-semibold text-muted block mb-2">Highest Cost Drivers</span>
            <div className="space-y-2">
              {topPositions.map((c) => (
                <div key={c.grouping_reference} className="bg-canvas p-2 rounded border border-line text-xs flex justify-between items-center">
                  <div>
                    <span className="font-semibold text-secondary">{c.grouping_reference}</span>
                    <span className="text-[10px] text-muted ml-1.5">MV: {currency} {(c.aggregate_position_value / 1e5).toFixed(1)}L</span>
                  </div>
                  <div className="text-right">
                    <span className="font-sans text-warning font-medium">
                      {currency} {c.estimated_liquidation_cost.toFixed(2)}
                    </span>
                    <span className="text-[10px] text-muted ml-1.5 font-sans">
                      ({c.cost_contribution_pct?.toFixed(1) || '0.0'}%)
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="pt-2 border-t border-line">
            <span className="text-xs font-semibold text-muted block mb-2">Sector Cost Concentration</span>
            <div className="space-y-1.5">
              {sectors.map((s) => (
                <div key={s.grouping_reference} className="flex items-center justify-between text-xs py-1 px-1.5 rounded hover:bg-subtle/50">
                  <span className="text-secondary">{s.grouping_reference}</span>
                  <div className="flex items-center gap-2">
                    <span className="font-sans text-muted">{currency} {s.estimated_liquidation_cost.toFixed(1)}</span>
                    <span className="font-sans text-warning font-medium text-[11px] w-12 text-right">
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
      <div className="bg-surface border border-line rounded-lg p-5 shadow-md">
        <h2 className="text-sm font-semibold text-ink uppercase  mb-3 flex items-center justify-between">
          <span>Liquidity Stress Scenarios</span>
          <span className="text-[10px] text-info font-sans">M10 Replay / Vacuum</span>
        </h2>

        <div className="space-y-3">
          {stressComparisons.map((sc) => (
            <div key={sc.scenario_id} className="bg-canvas p-3 rounded border border-line text-xs">
              <div className="flex justify-between items-start mb-2">
                <span className="font-bold text-secondary">{sc.scenario_name}</span>
                <span className="px-1.5 py-0.5 rounded text-[10px] bg-info-soft text-info border border-info/20 font-sans">
                  {sc.scenario_horizon}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 text-[11px] text-muted mb-2">
                <div>
                  Spread: <span className="text-secondary font-sans">{sc.stressed_spread_bps.toFixed(0)} bps</span>{' '}
                  <span className="text-negative text-[10px]">(+{sc.spread_widening_pct.toFixed(0)}%)</span>
                </div>
                <div>
                  Depth: <span className="text-secondary font-sans">-{sc.depth_reduction_pct.toFixed(0)}%</span>
                </div>
                <div>
                  Horizon: <span className="text-brand font-sans">{sc.stressed_liquidation_time_days.toFixed(1)} Days</span>
                </div>
                <div>
                  Score: <span className="text-secondary font-sans">{sc.stressed_liquidity_score.toFixed(0)} / 100</span>
                </div>
              </div>

              <div className="pt-2 border-t border-line flex justify-between items-center text-xs">
                <span className="text-muted">Stressed Liquidation Cost:</span>
                <span className="font-sans font-bold text-negative">
                  {currency} {sc.stressed_liquidation_cost.toFixed(2)}{' '}
                  <span className="text-[10px] text-muted font-normal">
                    (+{currency} {sc.incremental_liquidation_cost.toFixed(2)})
                  </span>
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Liquidity Limits & Projected Exceedances */}
      <div className="bg-surface border border-line rounded-lg p-5 shadow-md">
        <h2 className="text-sm font-semibold text-ink uppercase  mb-3 flex items-center justify-between">
          <span>M11 Liquidity Limits Evaluation</span>
          <span className="text-[10px] text-muted font-sans">Policy v1.0</span>
        </h2>

        <div className="space-y-3">
          {limits.map((l) => (
            <div key={l.limit_id} className="bg-canvas p-3 rounded border border-line text-xs">
              <div className="flex justify-between items-center mb-1.5">
                <span className="font-semibold text-secondary">{l.limit_name}</span>
                <span
                  className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                    l.evaluation_status === 'WITHIN_LIMIT'
                      ? 'bg-positive-soft text-positive border border-positive/20'
                      : l.evaluation_status === 'PROJECTED_STRESS_EXCEEDANCE'
                      ? 'bg-info-soft text-info border border-info/20'
                      : 'bg-negative-soft text-negative border border-negative/20'
                  }`}
                >
                  {l.evaluation_status}
                </span>
              </div>

              <div className="flex justify-between items-center text-[11px] text-muted mb-2">
                <span>Threshold: <span className="font-sans text-secondary">{l.configured_threshold} {l.threshold_unit}</span></span>
                <span>Observed: <span className="font-sans text-secondary">{l.current_metric?.toFixed(1) || '-'} {l.threshold_unit}</span></span>
              </div>

              {/* Utilization progress bar */}
              <div className="w-full bg-subtle h-1.5 rounded overflow-hidden mb-1">
                <div
                  className={`h-full ${
                    (l.utilization_pct || 0) > 100
                      ? 'bg-rose-500'
                      : (l.utilization_pct || 0) > 80
                      ? 'bg-amber-500'
                      : 'bg-brand'
                  }`}
                  style={{ width: `${Math.min(100, l.utilization_pct || 0)}%` }}
                />
              </div>
              <div className="flex justify-between items-center text-[10px] text-muted">
                <span>Utilization: <span className="text-secondary font-sans">{(l.utilization_pct || 0).toFixed(1)}%</span></span>
                <span>Stressed: <span className="text-info font-sans">{l.stressed_metric?.toFixed(1) || '-'} {l.threshold_unit}</span></span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
