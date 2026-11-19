import React from "react";
import {
  CanonicalDailyRiskReport,
  OverallControlStatus,
  OverallFreshnessStatus,
} from "../../../../types/dailyReport";

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
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-positive-soft text-positive border border-positive/20">CONTROL: CLEAR</span>;
      case "WARNINGS":
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-warning-soft text-warning border border-warning/20">CONTROL: WARNINGS</span>;
      case "CRITICAL":
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-negative-soft text-negative border border-negative/20">CONTROL: CRITICAL</span>;
      case "EMERGENCY":
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-info-soft text-info border border-info/20 ">CONTROL: EMERGENCY</span>;
      default:
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-subtle text-muted border border-line-strong">CONTROL: UNKNOWN</span>;
    }
  };

  const getFreshnessBadge = (status?: OverallFreshnessStatus) => {
    switch (status) {
      case "FRESH":
        return <span className="px-2.5 py-1 text-xs font-medium rounded bg-positive-soft/60 text-positive border border-positive/20">DATA: FRESH</span>;
      case "STALE":
        return <span className="px-2.5 py-1 text-xs font-medium rounded bg-warning-soft/60 text-warning border border-warning/20">DATA: STALE</span>;
      case "PARTIAL":
        return <span className="px-2.5 py-1 text-xs font-medium rounded bg-orange-950/60 text-orange-400 border border-orange-900/80">DATA: PARTIAL</span>;
      default:
        return <span className="px-2.5 py-1 text-xs font-medium rounded bg-negative-soft/60 text-negative border border-negative/20">DATA: UNAVAILABLE</span>;
    }
  };

  return (
    <div className="bg-surface border border-line rounded-lg p-5 shadow-lg">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-line pb-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-ink ">
              M14.01 — Daily Risk Report
            </h1>
            {report && (
              <span className="px-2 py-0.5 text-xs font-sans rounded bg-subtle text-brand border border-line-strong">
                v{report.version_number}
              </span>
            )}
          </div>
          <p className="text-xs text-muted mt-1">
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
            className="px-3.5 py-1.5 text-xs font-semibold rounded bg-brand hover:bg-brand-hover disabled:bg-subtle text-white transition-colors duration-150 shadow"
          >
            {isGenerating ? "Assembling Report..." : "Generate EOD Report"}
          </button>

          {report && (
            <button
              onClick={() => onGenerateReport(true)}
              disabled={isGenerating}
              className="px-3 py-1.5 text-xs font-medium rounded bg-subtle hover:bg-hover text-secondary border border-line-strong transition-colors duration-150"
              title="Force full non-destructive report regeneration incrementing version lineage"
            >
              Regenerate (v{report.version_number + 1})
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 pt-4">
        <div>
          <label className="block text-xs font-medium text-muted mb-1">Portfolio</label>
          <input
            type="text"
            value={selectedPortfolio}
            onChange={(e) => onPortfolioChange(e.target.value)}
            className="w-full bg-canvas border border-line-strong rounded px-3 py-1.5 text-sm text-secondary focus:outline-none focus:border-cyan-500 font-sans"
            placeholder="PORTFOLIO-01"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-muted mb-1">Report As-Of Date</label>
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => onDateChange(e.target.value)}
            className="w-full bg-canvas border border-line-strong rounded px-3 py-1.5 text-sm text-secondary focus:outline-none focus:border-cyan-500 font-sans"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-muted mb-1">Calendar &amp; Cutoff</label>
          <div className="text-xs text-secondary bg-canvas/60 border border-line rounded px-3 py-2 font-sans">
            {report?.portfolio?.reporting_calendar || "NSE_INDIA"} | {report?.portfolio?.base_currency || "USD"}
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-muted mb-1">Valuation As-Of</label>
          <div className="text-xs text-secondary bg-canvas/60 border border-line rounded px-3 py-2 font-sans truncate">
            {report?.metadata?.valuation_timestamp
              ? new Date(report.metadata.valuation_timestamp).toLocaleString()
              : "Pending Cutoff"}
          </div>
        </div>
      </div>
    </div>
  );
};
