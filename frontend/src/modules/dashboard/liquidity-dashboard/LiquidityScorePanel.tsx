import React from 'react';
import { InstrumentLiquidityScore } from '../../../types/dashboard';

interface LiquidityScorePanelProps {
  score: InstrumentLiquidityScore | null;
}

export const LiquidityScorePanel: React.FC<LiquidityScorePanelProps> = ({ score }) => {
  if (!score) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 text-slate-400 text-sm">
        No liquidity score available.
      </div>
    );
  }

  const getBucketBadge = (bucket: string) => {
    switch (bucket) {
      case 'TIER_1_HIGH':
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-emerald-950 text-emerald-400 border border-emerald-800">TIER 1 (HIGH LIQUIDITY)</span>;
      case 'TIER_2_MODERATE':
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-blue-950 text-blue-400 border border-blue-800">TIER 2 (MODERATE)</span>;
      case 'TIER_3_LOW':
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-amber-950 text-amber-400 border border-amber-800">TIER 3 (LOW LIQUIDITY)</span>;
      case 'TIER_4_ILLIQUID':
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-rose-950 text-rose-400 border border-rose-800">TIER 4 (ILLIQUID)</span>;
      default:
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-slate-800 text-slate-300">{bucket}</span>;
    }
  };

  const getComponentColor = (status: string) => {
    switch (status) {
      case 'HEALTHY':
        return 'bg-emerald-500';
      case 'ADEQUATE':
        return 'bg-blue-500';
      case 'WARNING':
        return 'bg-amber-500';
      case 'CRITICAL':
        return 'bg-rose-500';
      default:
        return 'bg-slate-500';
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 shadow-lg flex flex-col gap-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-slate-100 text-base">Composite Liquidity Score</span>
          {getBucketBadge(score.liquidity_bucket)}
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-400 font-mono">
          Coverage: {(score.data_quality_coverage ? Number(score.data_quality_coverage) * 100 : 100).toFixed(0)}%
        </div>
      </div>

      {/* Main Composite Score Display */}
      <div className="flex items-center justify-between bg-slate-950 p-4 rounded border border-slate-800/80">
        <div className="flex flex-col">
          <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Institutional Score</span>
          <span className="text-3xl font-extrabold text-cyan-400 font-mono">
            {Number(score.composite_score).toFixed(1)} <span className="text-sm font-normal text-slate-500">/ 100</span>
          </span>
        </div>

        <div className="flex flex-col text-right">
          <span className="text-xs text-slate-400">20d Traded Volume / ADV</span>
          <span className="text-base font-bold text-slate-200 font-mono">
            {score.adv_shares_20d ? `${(Number(score.adv_shares_20d) / 1000).toFixed(1)}k shares` : '—'}
          </span>
          <span className="text-[11px] text-slate-500 font-mono">
            ADTV: {score.adtv_usd_20d ? `$${(Number(score.adtv_usd_20d) / 1000000).toFixed(2)}M` : '—'}
          </span>
        </div>
      </div>

      {/* Decomposed Components */}
      <div className="flex flex-col gap-2.5">
        <span className="text-xs font-semibold text-slate-300">Score Components Breakdown</span>
        {score.components.map((comp) => (
          <div key={comp.name} className="flex flex-col gap-1 text-xs">
            <div className="flex items-center justify-between">
              <span className="capitalize text-slate-300 font-medium">{comp.name.replace('_', ' ')}</span>
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-slate-500 font-mono">Weight: {(Number(comp.weight) * 100).toFixed(0)}%</span>
                <span className="font-mono font-bold text-slate-200">{Number(comp.score).toFixed(1)}</span>
              </div>
            </div>

            <div className="w-full bg-slate-950 h-2 rounded-full overflow-hidden border border-slate-800">
              <div
                className={`h-full ${getComponentColor(comp.status)} transition-all duration-300`}
                style={{ width: `${Math.min(100, Math.max(0, Number(comp.score)))}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
