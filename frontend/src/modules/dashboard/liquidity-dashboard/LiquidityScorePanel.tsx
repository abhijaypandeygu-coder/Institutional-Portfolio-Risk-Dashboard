import React from 'react';
import { money } from '../../../utils/liquidityAnalytics';
import { InstrumentLiquidityScore } from '../../../types/dashboard';

interface LiquidityScorePanelProps {
  score: InstrumentLiquidityScore | null;
  currency?: string | null;
}

export const LiquidityScorePanel: React.FC<LiquidityScorePanelProps> = ({ score, currency }) => {
  if (!score) {
    return (
      <div className="bg-surface border border-line rounded-lg p-5 text-muted text-sm">
        No liquidity score available.
      </div>
    );
  }

  const getBucketBadge = (bucket: string) => {
    switch (bucket) {
      case 'TIER_1_HIGH':
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-positive-soft text-positive border border-positive/20">TIER 1 (HIGH LIQUIDITY)</span>;
      case 'TIER_2_MODERATE':
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-brand-soft text-brand border border-brand/20">TIER 2 (MODERATE)</span>;
      case 'TIER_3_LOW':
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-warning-soft text-warning border border-warning/20">TIER 3 (LOW LIQUIDITY)</span>;
      case 'TIER_4_ILLIQUID':
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-negative-soft text-negative border border-negative/20">TIER 4 (ILLIQUID)</span>;
      default:
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-subtle text-secondary">{bucket}</span>;
    }
  };

  const getComponentColor = (status: string) => {
    switch (status) {
      case 'HEALTHY':
        return 'bg-brand';
      case 'ADEQUATE':
        return 'bg-brand';
      case 'WARNING':
        return 'bg-amber-500';
      case 'CRITICAL':
        return 'bg-rose-500';
      default:
        return 'bg-muted';
    }
  };

  return (
    <div className="bg-surface border border-line rounded-lg p-5 shadow-lg flex flex-col gap-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-ink text-base">Composite Liquidity Score</span>
          {getBucketBadge(score.liquidity_bucket)}
        </div>

        <div className="flex items-center gap-2 text-xs text-muted font-sans">
          Coverage: {(Number(score.data_quality_coverage ?? 0) * 100).toFixed(0)}%
        </div>
      </div>

      {/* Main Composite Score Display */}
      <div className="flex items-center justify-between bg-canvas p-4 rounded border border-line/80">
        <div className="flex flex-col">
          <span className="text-xs text-muted uppercase  font-semibold">Institutional Score</span>
          <span className="text-3xl font-extrabold text-brand font-sans">
            {Number(score.composite_score).toFixed(1)} <span className="text-sm font-normal text-muted">/ 100</span>
          </span>
        </div>

        <div className="flex flex-col text-right">
          <span className="text-xs text-muted">Average daily volume · {score.volume_observations ?? 0} observed sessions</span>
          <span className="text-base font-bold text-secondary font-sans">
            {score.adv_shares_20d != null ? `${Number(score.adv_shares_20d).toLocaleString(undefined, {maximumFractionDigits: 0})} shares/day` : 'Unavailable'}
          </span>
          <span className="text-[11px] text-muted font-sans">
            Average daily turnover: {money(score.adtv_native_20d, score.currency || currency || 'USD', true)} / day
          </span>
        </div>
      </div>

      <p className="text-xs text-muted">{score.volume_source || 'Volume source unavailable'}{score.volume_as_of ? ` · through ${score.volume_as_of}` : ''}. {score.fx_conversion || 'No verified FX conversion available.'}</p>
      {/* Decomposed Components */}
      <div className="flex flex-col gap-2.5">
        <span className="text-xs font-semibold text-secondary">Score Components Breakdown</span>
        {score.components.map((comp) => (
          <div key={comp.name} className="flex flex-col gap-1 text-xs">
            <div className="flex items-center justify-between">
              <span className="capitalize text-secondary font-medium">{comp.name.replace('_', ' ')}</span>
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-muted font-sans">Weight: {(Number(comp.weight) * 100).toFixed(0)}%</span>
                <span className="font-sans font-bold text-secondary">{Number(comp.score).toFixed(1)}</span>
              </div>
            </div>

            <div className="w-full bg-canvas h-2 rounded-full overflow-hidden border border-line">
              <div
                className={`h-full ${getComponentColor(comp.status)} transition-opacity duration-300`}
                style={{ width: `${Math.min(100, Math.max(0, Number(comp.score)))}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
