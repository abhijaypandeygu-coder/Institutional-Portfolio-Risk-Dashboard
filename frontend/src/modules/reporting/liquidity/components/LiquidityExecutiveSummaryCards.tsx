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
      <div className="bg-surface border border-line rounded-lg p-4 shadow-sm">
        <div className="flex justify-between items-start">
          <span className="text-xs font-semibold text-muted uppercase ">
            Total Liquidation Cost
          </span>
          <span className="text-xs px-2 py-0.5 rounded bg-warning-soft text-warning border border-warning/20 font-sans">
            {summary.estimated_portfolio_liquidation_cost_bps.toFixed(1)} bps
          </span>
        </div>
        <div className="text-xl font-bold text-warning mt-2 font-sans">
          {summary.reporting_currency} {summary.estimated_portfolio_liquidation_cost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </div>
        <div className="text-xs text-muted mt-1 flex items-center justify-between">
          <span>NAV: {summary.reporting_currency} {(summary.total_portfolio_nav / 1e7).toFixed(2)} Cr</span>
          <span className="text-muted text-[10px]">Scope: {summary.estimation_scope}</span>
        </div>
      </div>

      {/* Liquidation Horizon */}
      <div className="bg-surface border border-line rounded-lg p-4 shadow-sm">
        <div className="flex justify-between items-start">
          <span className="text-xs font-semibold text-muted uppercase ">
            Liquidation Horizon
          </span>
          <span className="text-xs px-2 py-0.5 rounded bg-brand-soft text-brand border border-brand/20 font-sans">
            Slowest Position
          </span>
        </div>
        <div className="text-xl font-bold text-brand mt-2 font-sans">
          {summary.estimated_portfolio_liquidation_days.toFixed(2)} <span className="text-sm font-normal text-muted">Trading Days</span>
        </div>
        <div className="text-xs text-muted mt-1">
          Positions Analyzed: <span className="text-secondary font-medium">{summary.position_count}</span> (100% covered)
        </div>
      </div>

      {/* Liquidity Score & Spread */}
      <div className="bg-surface border border-line rounded-lg p-4 shadow-sm">
        <div className="flex justify-between items-start">
          <span className="text-xs font-semibold text-muted uppercase ">
            Liquidity Score / Spread
          </span>
          <span className="text-xs px-2 py-0.5 rounded bg-positive-soft text-positive border border-positive/20 font-sans">
            {profile.portfolio_liquidity_tier}
          </span>
        </div>
        <div className="text-xl font-bold text-positive mt-2 font-sans">
          {profile.portfolio_liquidity_score.toFixed(1)} <span className="text-xs text-muted font-normal">/ 100</span>
        </div>
        <div className="text-xs text-muted mt-1">
          Weighted Spread: <span className="text-secondary font-sans">{profile.portfolio_weighted_spread_bps.toFixed(1)} bps</span>
        </div>
      </div>

      {/* Stress & Limit Risk Status */}
      <div className="bg-surface border border-line rounded-lg p-4 shadow-sm">
        <div className="flex justify-between items-start">
          <span className="text-xs font-semibold text-muted uppercase ">
            Stress & Limits Status
          </span>
          <span
            className={`text-xs px-2 py-0.5 rounded border font-sans ${
              summary.reconciliation_status === 'RECONCILED'
                ? 'bg-positive-soft text-positive border-positive/20'
                : 'bg-warning-soft text-warning border-warning/20'
            }`}
          >
            {summary.reconciliation_status}
          </span>
        </div>
        <div className="text-xl font-bold text-info mt-2 font-sans">
          {summary.projected_limit_exceedances_count} <span className="text-xs text-muted font-normal">Projected Exceedances</span>
        </div>
        <div className="text-xs text-muted mt-1">
          Live Breaches: <span className="text-secondary font-medium">{summary.actual_breaches_count}</span> | Code: <span className="text-muted font-sans">{reportCode}</span>
        </div>
      </div>
    </div>
  );
};
