import React from 'react';
import {
  TrendingDown,
  AlertOctagon,
  Scale,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react';
import { ExecutiveSummary } from '../../../../types/stressReport';

interface StressExecutiveSummaryCardsProps {
  summary: ExecutiveSummary;
  currency: string;
}

export const StressExecutiveSummaryCards: React.FC<StressExecutiveSummaryCardsProps> = ({
  summary,
  currency,
}) => {
  const isLoss = summary.worst_stressed_pnl < 0;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 p-6 bg-slate-950">
      {/* 1. Worst Stressed Loss */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 relative overflow-hidden">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider">
            Worst Stressed Loss
          </span>
          <TrendingDown className="w-4 h-4 text-rose-400" />
        </div>
        <div className="text-2xl font-bold text-rose-400 font-mono">
          -${Math.abs(summary.worst_stressed_pnl).toLocaleString('en-US', { minimumFractionDigits: 2 })}
        </div>
        <div className="text-xs text-slate-400 mt-2 flex items-center justify-between">
          <span>{summary.worst_scenario_name}</span>
          <span className="text-rose-400 font-mono text-[11px]">
            {summary.worst_stress_impact_percentage.toFixed(2)}% NAV
          </span>
        </div>
      </div>

      {/* 2. Baseline NAV */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 relative overflow-hidden">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider">
            Baseline Portfolio NAV
          </span>
          <ShieldCheck className="w-4 h-4 text-indigo-400" />
        </div>
        <div className="text-2xl font-bold text-slate-100 font-mono">
          ${summary.baseline_portfolio_nav.toLocaleString('en-US', { minimumFractionDigits: 2 })}
        </div>
        <div className="text-xs text-slate-400 mt-2 flex items-center justify-between">
          <span>Official Valuation</span>
          <span className="text-indigo-400 font-mono text-[11px]">{currency}</span>
        </div>
      </div>

      {/* 3. Projected Limit Exceedances */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 relative overflow-hidden">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider">
            Projected Limit Exceedances
          </span>
          <AlertOctagon className="w-4 h-4 text-amber-400" />
        </div>
        <div className="text-2xl font-bold text-slate-100 font-mono flex items-center gap-2">
          <span>{summary.projected_exceedances_count}</span>
          {summary.projected_exceedances_count > 0 && (
            <span className="text-xs px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 font-sans">
              Hypothetical
            </span>
          )}
        </div>
        <div className="text-xs text-slate-400 mt-2 flex items-center justify-between">
          <span>Derived from M11 Limits</span>
          <span className="text-amber-400 font-mono text-[11px]">Non-Breach</span>
        </div>
      </div>

      {/* 4. Reconciliation Status */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 relative overflow-hidden">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider">
            P&L Reconciliation
          </span>
          <Scale className="w-4 h-4 text-emerald-400" />
        </div>
        <div className="mt-1 flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
            <CheckCircle2 className="w-3.5 h-3.5" />
            {summary.overall_reconciliation_status}
          </span>
        </div>
        <div className="text-xs text-slate-400 mt-2.5 flex items-center justify-between">
          <span>Position Sum = Total</span>
          <span className="text-slate-500 font-mono text-[11px]">M10 / M14</span>
        </div>
      </div>
    </div>
  );
};
