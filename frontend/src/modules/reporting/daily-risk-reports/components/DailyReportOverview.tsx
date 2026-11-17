import React from "react";
import {
  CanonicalDailyRiskReport,
  OverallControlStatus,
  OverallFreshnessStatus,
} from "../../../types/dailyReport";

interface DailyReportOverviewProps {
  report: CanonicalDailyRiskReport | null;
  selectedPortfolio: string;
  selectedDate: string;
  onPortfolioChange: (id: string) => void;
  onDateChange: (date: string) => void;
  onGenerateReport: (forceRegenerate?: boolean) => void;
  isGenerating: boolean;
}

export const DailyReportOverview: React.FC<DailyReportOverviewProps> = ({
  report,
  selectedPortfolio,
  selectedDate,
  onPortfolioChange,
  onDateChange,
  onGenerateReport,
  isGenerating,
}) => {
  const getControlStatusBadge = (status?: OverallControlStatus) => {
    switch (status) {
      case "CLEAR":
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-emerald-950 text-emerald-400 border border-emerald-800">CONTROL: CLEAR</span>;
      case "WARNINGS":
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-amber-950 text-amber-400 border border-amber-800">CONTROL: WARNINGS</span>;
      case "CRITICAL":
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-rose-950 text-rose-400 border border-rose-800">CONTROL: CRITICAL</span>;
      case "EMERGENCY":
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-purple-950 text-purple-300 border border-purple-700 animate-pulse">CONTROL: EMERGENCY</span>;
      default:
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-slate-800 text-slate-400 border border-slate-700">CONTROL: UNKNOWN</span>;
    }
  };

  const getFreshnessBadge = (status?: OverallFreshnessStatus) => {
    switch (status) {
      case "FRESH":
        return <span className="px-2.5 py-1 text-xs font-medium rounded bg-emerald-950/60 text-emerald-400 border border-emerald-900/80">DATA: FRESH</span>;
      case "STALE":
        return <span className="px-2.5 py-1 text-xs font-medium rounded bg-amber-950/60 text-amber-400 border border-amber-900/80">DATA: STALE</span>;
      case "PARTIAL":
        return <span className="px-2.5 py-1 text-xs font-medium rounded bg-orange-950/60 text-orange-400 border border-orange-900/80">DATA: PARTIAL</span>;
      default:
        return <span className="px-2.5 py-1 text-xs font-medium rounded bg-rose-950/60 text-rose-400 border border-rose-900/80">DATA: UNAVAILABLE</span>;
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 shadow-lg">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-slate-100 tracking-tight">
              M14.01 — Daily Risk Report
            </h1>
            {report && (
              <span className="px-2 py-0.5 text-xs font-mono rounded bg-slate-800 text-cyan-400 border border-slate-700">
                v{report.version_number}
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Authoritative End-of-Day Institutional Risk, Valuation &amp; Limit Control Record
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {report && (
            <>
              {getControlStatusBadge(report.risk_limit_status?.overall_control_status)}
              {getFreshnessBadge(report.metadata?.overall_freshness)}
            </>
          )}

          <button
            onClick={() => onGenerateReport(false)}
            disabled={isGenerating}
            className="px-3.5 py-1.5 text-xs font-semibold rounded bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-800 text-white transition-colors duration-150 shadow"
          >
            {isGenerating ? "Assembling Report..." : "Generate EOD Report"}
          </button>

          {report && (
            <button
              onClick={() => onGenerateReport(true)}
              disabled={isGenerating}
              className="px-3 py-1.5 text-xs font-medium rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors duration-150"
              title="Force full non-destructive report regeneration incrementing version lineage"
            >
              Regenerate (v{report.version_number + 1})
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 pt-4">
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">Portfolio</label>
          <input
            type="text"
            value={selectedPortfolio}
            onChange={(e) => onPortfolioChange(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-cyan-500 font-mono"
            placeholder="PORTFOLIO-01"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">Report As-Of Date</label>
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => onDateChange(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-cyan-500 font-mono"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">Calendar &amp; Cutoff</label>
          <div className="text-xs text-slate-300 bg-slate-950/60 border border-slate-800 rounded px-3 py-2 font-mono">
            {report?.portfolio?.reporting_calendar || "NSE_INDIA"} | {report?.portfolio?.base_currency || "USD"}
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">Valuation As-Of</label>
          <div className="text-xs text-slate-300 bg-slate-950/60 border border-slate-800 rounded px-3 py-2 font-mono truncate">
            {report?.metadata?.valuation_timestamp
              ? new Date(report.metadata.valuation_timestamp).toLocaleString()
              : "Pending Cutoff"}
          </div>
        </div>
      </div>
    </div>
  );
};
