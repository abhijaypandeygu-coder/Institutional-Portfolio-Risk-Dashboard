import React from "react";
import { ReportPortfolioSummaryData } from "../../../../types/dailyReport";

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
      <div className="bg-surface border border-line rounded-lg p-5">
        <h2 className="text-sm font-semibold text-secondary mb-2">Portfolio Financial State (M05 / M06)</h2>
        <p className="text-xs text-muted italic">No authoritative valuation snapshot available for this date.</p>
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

  const pnlColor = (summary.total_pnl ?? 0) >= 0 ? "text-positive" : "text-negative";

  return (
    <div className="bg-surface border border-line rounded-lg p-5 shadow-lg">
      <div className="flex items-center justify-between border-b border-line pb-3 mb-4">
        <div>
          <h2 className="text-sm font-semibold text-secondary">
            Portfolio Financial State &amp; Balance Summary
          </h2>
          <p className="text-xs text-muted">
            Authoritative balance data consumed directly from M05.07 / M05.03 &amp; M06
          </p>
        </div>
        <div className="text-right">
          <span className="text-xs font-sans text-muted">
            Completeness:{" "}
            <span className={summary.valuation_completeness === "COMPLETE" ? "text-positive" : "text-warning"}>
              {summary.valuation_completeness}
            </span>
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <div className="bg-canvas/70 p-3 rounded border border-line/80">
          <span className="text-xs text-muted uppercase font-sans">Net Asset Value (NAV)</span>
          <div className="text-lg font-bold text-ink font-sans mt-1">
            {formatCurrency(summary.nav)}
          </div>
        </div>

        <div className="bg-canvas/70 p-3 rounded border border-line/80">
          <span className="text-xs text-muted uppercase font-sans">Total Market Value</span>
          <div className="text-lg font-bold text-ink font-sans mt-1">
            {formatCurrency(summary.market_value)}
          </div>
        </div>

        <div className="bg-canvas/70 p-3 rounded border border-line/80">
          <span className="text-xs text-muted uppercase font-sans">Total P&amp;L</span>
          <div className={`text-lg font-bold font-sans mt-1 ${pnlColor}`}>
            {formatCurrency(summary.total_pnl)}
          </div>
        </div>

        <div className="bg-canvas/70 p-3 rounded border border-line/80">
          <span className="text-xs text-muted uppercase font-sans">Cash Balance</span>
          <div className="text-lg font-bold text-brand font-sans mt-1">
            {formatCurrency(summary.cash_balance)}
            <span className="text-xs font-normal text-muted ml-1.5 font-sans">
              ({formatPct(summary.cash_allocation_pct)})
            </span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-2 border-t border-line/60 text-xs">
        <div>
          <span className="text-muted font-sans">Gross Exposure:</span>{" "}
          <span className="font-sans text-secondary">{formatCurrency(summary.gross_exposure)}</span>
        </div>
        <div>
          <span className="text-muted font-sans">Net Exposure:</span>{" "}
          <span className="font-sans text-secondary">{formatCurrency(summary.net_exposure)}</span>
        </div>
        <div>
          <span className="text-muted font-sans">Long / Short:</span>{" "}
          <span className="font-sans text-secondary">
            {formatCurrency(summary.long_exposure)} / {formatCurrency(summary.short_exposure)}
          </span>
        </div>
        <div>
          <span className="text-muted font-sans">Source Snapshot:</span>{" "}
          <span className="font-sans text-muted truncate block">
            {summary.source_snapshot_id || "M05-RECORD"}
          </span>
        </div>
      </div>
    </div>
  );
};
