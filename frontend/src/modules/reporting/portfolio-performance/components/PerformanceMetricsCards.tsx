import React from "react";
import {
  PerformanceSummarySchema,
  PnLBreakdownSchema,
  CashFlowSummarySchema,
} from "../../../types/performanceReport";

interface PerformanceMetricsCardsProps {
  summary?: PerformanceSummarySchema;
  pnl?: PnLBreakdownSchema;
  flows?: CashFlowSummarySchema;
  currency: string;
}

export const PerformanceMetricsCards: React.FC<PerformanceMetricsCardsProps> = ({
  summary,
  pnl,
  flows,
  currency,
}) => {
  if (!summary) return null;

  const fmtCurrency = (val?: number) => {
    if (val === undefined || val === null) return "N/A";
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency || "USD",
      maximumFractionDigits: 0,
    }).format(val);
  };

  const fmtPct = (val?: number) => {
    if (val === undefined || val === null) return "N/A";
    return `${(val * 100).toFixed(2)}%`;
  };

  const pnlColor = (summary.total_pnl ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400";
  const retColor = (summary.cumulative_return ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400";
  const alphaColor = (summary.active_return_difference ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400";

  return (
    <div className="space-y-4">
      {/* Primary KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg shadow-lg">
          <span className="text-xs text-slate-400 uppercase font-mono">Cumulative Return</span>
          <div className={`text-2xl font-bold font-mono mt-1 ${retColor}`}>
            {fmtPct(summary.cumulative_return)}
          </div>
          <div className="text-[11px] text-slate-500 font-mono mt-2">
            Annualized: <span className="text-slate-300">{fmtPct(summary.annualized_return)}</span>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg shadow-lg">
          <span className="text-xs text-slate-400 uppercase font-mono">Total Portfolio P&amp;L</span>
          <div className={`text-2xl font-bold font-mono mt-1 ${pnlColor}`}>
            {fmtCurrency(summary.total_pnl)}
          </div>
          <div className="text-[11px] text-slate-500 font-mono mt-2 flex justify-between">
            <span>R: {fmtCurrency(summary.realized_pnl)}</span>
            <span>U: {fmtCurrency(summary.unrealized_pnl)}</span>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg shadow-lg">
          <span className="text-xs text-slate-400 uppercase font-mono">Benchmark Alpha (Active Diff)</span>
          <div className={`text-2xl font-bold font-mono mt-1 ${alphaColor}`}>
            {summary.active_return_difference !== undefined && summary.active_return_difference !== null
              ? `${(summary.active_return_difference * 100).toFixed(2)}%`
              : "N/A"}
          </div>
          <div className="text-[11px] text-slate-500 font-mono mt-2">
            Bmk Ret: <span className="text-slate-300">{fmtPct(summary.benchmark_return)}</span>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg shadow-lg">
          <span className="text-xs text-slate-400 uppercase font-mono">Net External Flows</span>
          <div className="text-2xl font-bold text-cyan-400 font-mono mt-1">
            {fmtCurrency(flows?.net_external_flow)}
          </div>
          <div className="text-[11px] text-slate-500 font-mono mt-2">
            Neutralized from TWR
          </div>
        </div>
      </div>

      {/* Capital & Balance Rollups */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 shadow-lg grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono">
        <div>
          <span className="text-slate-500 block">Beginning NAV</span>
          <span className="text-slate-100 font-bold mt-0.5 block">{fmtCurrency(summary.beginning_nav)}</span>
        </div>
        <div>
          <span className="text-slate-500 block">Ending NAV</span>
          <span className="text-slate-100 font-bold mt-0.5 block">{fmtCurrency(summary.ending_nav)}</span>
        </div>
        <div>
          <span className="text-slate-500 block">External Contributions</span>
          <span className="text-emerald-400 font-bold mt-0.5 block">{fmtCurrency(summary.total_contributions)}</span>
        </div>
        <div>
          <span className="text-slate-500 block">External Withdrawals</span>
          <span className="text-rose-400 font-bold mt-0.5 block">{fmtCurrency(summary.total_withdrawals)}</span>
        </div>
      </div>
    </div>
  );
};
