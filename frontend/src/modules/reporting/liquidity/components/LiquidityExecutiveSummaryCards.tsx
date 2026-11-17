import React from 'react';
import {
  LiquidityExecutiveSummary,
  LiquidityProfileSummary,
} from '../../../../types/liquidityReport';

interface Props {
  summary: LiquidityExecutiveSummary;
  profile: LiquidityProfileSummary;
  reportCode: string;
}

export const LiquidityExecutiveSummaryCards: React.FC<Props> = ({ summary, profile, reportCode }) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
      {/* Liquidation Cost */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 shadow-sm">
        <div className="flex justify-between items-start">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Total Liquidation Cost
          </span>
          <span className="text-xs px-2 py-0.5 rounded bg-amber-950 text-amber-400 border border-amber-800 font-mono">
            {summary.estimated_portfolio_liquidation_cost_bps.toFixed(1)} bps
          </span>
        </div>
        <div className="text-xl font-bold text-amber-400 mt-2 font-mono">
          {summary.reporting_currency} {summary.estimated_portfolio_liquidation_cost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </div>
        <div className="text-xs text-slate-400 mt-1 flex items-center justify-between">
          <span>NAV: {summary.reporting_currency} {(summary.total_portfolio_nav / 1e7).toFixed(2)} Cr</span>
          <span className="text-slate-500 text-[10px]">Scope: {summary.estimation_scope}</span>
        </div>
      </div>

      {/* Liquidation Horizon */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 shadow-sm">
        <div className="flex justify-between items-start">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Liquidation Horizon
          </span>
          <span className="text-xs px-2 py-0.5 rounded bg-blue-950 text-blue-400 border border-blue-800 font-mono">
            Slowest Position
          </span>
        </div>
        <div className="text-xl font-bold text-blue-400 mt-2 font-mono">
          {summary.estimated_portfolio_liquidation_days.toFixed(2)} <span className="text-sm font-normal text-slate-400">Trading Days</span>
        </div>
        <div className="text-xs text-slate-400 mt-1">
          Positions Analyzed: <span className="text-slate-200 font-medium">{summary.position_count}</span> (100% covered)
        </div>
      </div>

      {/* Liquidity Score & Spread */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 shadow-sm">
        <div className="flex justify-between items-start">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Liquidity Score / Spread
          </span>
          <span className="text-xs px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 font-mono">
            {profile.portfolio_liquidity_tier}
          </span>
        </div>
        <div className="text-xl font-bold text-emerald-400 mt-2 font-mono">
          {profile.portfolio_liquidity_score.toFixed(1)} <span className="text-xs text-slate-400 font-normal">/ 100</span>
        </div>
        <div className="text-xs text-slate-400 mt-1">
          Weighted Spread: <span className="text-slate-200 font-mono">{profile.portfolio_weighted_spread_bps.toFixed(1)} bps</span>
        </div>
      </div>

      {/* Stress & Limit Risk Status */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 shadow-sm">
        <div className="flex justify-between items-start">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Stress & Limits Status
          </span>
          <span
            className={`text-xs px-2 py-0.5 rounded border font-mono ${
              summary.reconciliation_status === 'RECONCILED'
                ? 'bg-emerald-950 text-emerald-400 border-emerald-800'
                : 'bg-amber-950 text-amber-400 border-amber-800'
            }`}
          >
            {summary.reconciliation_status}
          </span>
        </div>
        <div className="text-xl font-bold text-purple-400 mt-2 font-mono">
          {summary.projected_limit_exceedances_count} <span className="text-xs text-slate-400 font-normal">Projected Exceedances</span>
        </div>
        <div className="text-xs text-slate-400 mt-1">
          Live Breaches: <span className="text-slate-200 font-medium">{summary.actual_breaches_count}</span> | Code: <span className="text-slate-400 font-mono">{reportCode}</span>
        </div>
      </div>
    </div>
  );
};
