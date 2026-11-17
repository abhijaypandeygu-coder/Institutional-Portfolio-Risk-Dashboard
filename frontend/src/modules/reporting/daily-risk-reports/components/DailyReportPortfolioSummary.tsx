import React from "react";
import { ReportPortfolioSummaryData } from "../../../types/dailyReport";

interface DailyReportPortfolioSummaryProps {
  summary?: ReportPortfolioSummaryData;
  reportingCurrency: string;
}

export const DailyReportPortfolioSummary: React.FC<DailyReportPortfolioSummaryProps> = ({
  summary,
  reportingCurrency,
}) => {
  if (!summary) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
        <h2 className="text-sm font-semibold text-slate-300 mb-2">Portfolio Financial State (M05 / M06)</h2>
        <p className="text-xs text-slate-500 italic">No authoritative valuation snapshot available for this date.</p>
      </div>
    );
  }

  const formatCurrency = (val?: number) => {
    if (val === undefined || val === null) return "UNAVAILABLE";
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: reportingCurrency || "USD",
      maximumFractionDigits: 2,
    }).format(val);
  };

  const formatPct = (val?: number) => {
    if (val === undefined || val === null) return "N/A";
    return `${(val * 100).toFixed(2)}%`;
  };

  const pnlColor = (summary.total_pnl ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400";

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 shadow-lg">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-200">
            Portfolio Financial State &amp; Balance Summary
          </h2>
          <p className="text-xs text-slate-500">
            Authoritative balance data consumed directly from M05.07 / M05.03 &amp; M06
          </p>
        </div>
        <div className="text-right">
          <span className="text-xs font-mono text-slate-400">
            Completeness:{" "}
            <span className={summary.valuation_completeness === "COMPLETE" ? "text-emerald-400" : "text-amber-400"}>
              {summary.valuation_completeness}
            </span>
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <div className="bg-slate-950/70 p-3 rounded border border-slate-800/80">
          <span className="text-xs text-slate-400 uppercase font-mono">Net Asset Value (NAV)</span>
          <div className="text-lg font-bold text-slate-100 font-mono mt-1">
            {formatCurrency(summary.nav)}
          </div>
        </div>

        <div className="bg-slate-950/70 p-3 rounded border border-slate-800/80">
          <span className="text-xs text-slate-400 uppercase font-mono">Total Market Value</span>
          <div className="text-lg font-bold text-slate-100 font-mono mt-1">
            {formatCurrency(summary.market_value)}
          </div>
        </div>

        <div className="bg-slate-950/70 p-3 rounded border border-slate-800/80">
          <span className="text-xs text-slate-400 uppercase font-mono">Total P&amp;L</span>
          <div className={`text-lg font-bold font-mono mt-1 ${pnlColor}`}>
            {formatCurrency(summary.total_pnl)}
          </div>
        </div>

        <div className="bg-slate-950/70 p-3 rounded border border-slate-800/80">
          <span className="text-xs text-slate-400 uppercase font-mono">Cash Balance</span>
          <div className="text-lg font-bold text-cyan-400 font-mono mt-1">
            {formatCurrency(summary.cash_balance)}
            <span className="text-xs font-normal text-slate-400 ml-1.5 font-sans">
              ({formatPct(summary.cash_allocation_pct)})
            </span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-2 border-t border-slate-800/60 text-xs">
        <div>
          <span className="text-slate-500 font-mono">Gross Exposure:</span>{" "}
          <span className="font-mono text-slate-300">{formatCurrency(summary.gross_exposure)}</span>
        </div>
        <div>
          <span className="text-slate-500 font-mono">Net Exposure:</span>{" "}
          <span className="font-mono text-slate-300">{formatCurrency(summary.net_exposure)}</span>
        </div>
        <div>
          <span className="text-slate-500 font-mono">Long / Short:</span>{" "}
          <span className="font-mono text-slate-300">
            {formatCurrency(summary.long_exposure)} / {formatCurrency(summary.short_exposure)}
          </span>
        </div>
        <div>
          <span className="text-slate-500 font-mono">Source Snapshot:</span>{" "}
          <span className="font-mono text-slate-400 truncate block">
            {summary.source_snapshot_id || "M05-RECORD"}
          </span>
        </div>
      </div>
    </div>
  );
};
