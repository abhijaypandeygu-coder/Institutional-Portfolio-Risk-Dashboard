import React from "react";
import {
  CanonicalPerformanceReport,
  PerformanceDataStatus,
  ReportingPeriodType,
  ReturnMethodology,
} from "../../../../types/performanceReport";

interface PerformanceOverviewProps {
  report: CanonicalPerformanceReport | null;
  selectedPortfolio: string;
  periodType: ReportingPeriodType;
  startDate: string;
  endDate: string;
  returnMethod: ReturnMethodology;
  benchmarkId: string;
  onPortfolioChange: (val: string) => void;
  onPeriodTypeChange: (val: ReportingPeriodType) => void;
  onStartDateChange: (val: string) => void;
  onEndDateChange: (val: string) => void;
  onReturnMethodChange: (val: ReturnMethodology) => void;
  onBenchmarkChange: (val: string) => void;
  onGenerateReport: (forceRegen?: boolean) => void;
  isGenerating: boolean;
}

export const PerformanceReportOverview: React.FC<PerformanceOverviewProps> = ({
  report,
  selectedPortfolio,
  periodType,
  startDate,
  endDate,
  returnMethod,
  benchmarkId,
  onPortfolioChange,
  onPeriodTypeChange,
  onStartDateChange,
  onEndDateChange,
  onReturnMethodChange,
  onBenchmarkChange,
  onGenerateReport,
  isGenerating,
}) => {
  const getStatusBadge = (status?: PerformanceDataStatus) => {
    switch (status) {
      case "COMPLETE":
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-positive-soft text-positive border border-positive/20">STATUS: COMPLETE</span>;
      case "COMPLETE_WITH_APPROXIMATIONS":
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-warning-soft text-warning border border-warning/20">STATUS: APPROXIMATED</span>;
      case "PARTIAL":
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-orange-950 text-orange-400 border border-orange-800">STATUS: PARTIAL</span>;
      default:
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-negative-soft text-negative border border-negative/20">STATUS: UNAVAILABLE</span>;
    }
  };

  return (
    <div className="bg-surface border border-line rounded-lg p-5 shadow-lg">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-line pb-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-ink ">
              M14.02 — Portfolio Performance Reports
            </h1>
            {report && (
              <span className="px-2 py-0.5 text-xs font-sans rounded bg-subtle text-brand border border-line-strong">
                v{report.report_version}
              </span>
            )}
          </div>
          <p className="text-xs text-muted mt-1">
            Auditable Multi-Period Investment Returns, Cumulative Compounding, P&amp;L Attribution &amp; Benchmark Analysis
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {report && getStatusBadge(report.performance_summary?.performance_data_status)}

          <button
            onClick={() => onGenerateReport(false)}
            disabled={isGenerating}
            className="px-3.5 py-1.5 text-xs font-semibold rounded bg-brand hover:bg-brand-hover disabled:bg-subtle text-white transition-colors duration-150 shadow"
          >
            {isGenerating ? "Calculating Returns..." : "Generate Performance Report"}
          </button>

          {report && (
            <button
              onClick={() => onGenerateReport(true)}
              disabled={isGenerating}
              className="px-3 py-1.5 text-xs font-medium rounded bg-subtle hover:bg-hover text-secondary border border-line-strong transition-colors duration-150"
              title="Force non-destructive recalculation creating a new auditable version"
            >
              Recalculate (v{report.report_version + 1})
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3 pt-4">
        <div>
          <label className="block text-xs font-medium text-muted mb-1">Portfolio</label>
          <input
            type="text"
            value={selectedPortfolio}
            onChange={(e) => onPortfolioChange(e.target.value)}
            className="w-full bg-canvas border border-line-strong rounded px-2.5 py-1.5 text-xs text-secondary font-sans focus:outline-none focus:border-cyan-500"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-muted mb-1">Period Type</label>
          <select
            value={periodType}
            onChange={(e) => onPeriodTypeChange(e.target.value as ReportingPeriodType)}
            className="w-full bg-canvas border border-line-strong rounded px-2.5 py-1.5 text-xs text-secondary font-sans focus:outline-none focus:border-cyan-500"
          >
            <option value="DAILY">DAILY</option>
            <option value="WEEKLY">WEEKLY</option>
            <option value="MONTHLY">MONTHLY</option>
            <option value="QUARTERLY">QUARTERLY</option>
            <option value="YTD">YTD</option>
            <option value="ONE_YEAR">ONE_YEAR</option>
            <option value="CUSTOM">CUSTOM</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-muted mb-1">Start Date</label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => onStartDateChange(e.target.value)}
            className="w-full bg-canvas border border-line-strong rounded px-2.5 py-1.5 text-xs text-secondary font-sans focus:outline-none focus:border-cyan-500"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-muted mb-1">End Date</label>
          <input
            type="date"
            value={endDate}
            onChange={(e) => onEndDateChange(e.target.value)}
            className="w-full bg-canvas border border-line-strong rounded px-2.5 py-1.5 text-xs text-secondary font-sans focus:outline-none focus:border-cyan-500"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-muted mb-1">Methodology</label>
          <select
            value={returnMethod}
            onChange={(e) => onReturnMethodChange(e.target.value as ReturnMethodology)}
            className="w-full bg-canvas border border-line-strong rounded px-2.5 py-1.5 text-xs text-secondary font-sans focus:outline-none focus:border-cyan-500"
          >
            <option value="TWR">TWR (Exact Subperiod)</option>
            <option value="MODIFIED_DIETZ">Modified Dietz</option>
            <option value="MWR_XIRR">MWR / XIRR</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-muted mb-1">Benchmark</label>
          <input
            type="text"
            value={benchmarkId}
            onChange={(e) => onBenchmarkChange(e.target.value)}
            className="w-full bg-canvas border border-line-strong rounded px-2.5 py-1.5 text-xs text-secondary font-sans focus:outline-none focus:border-cyan-500"
            placeholder="SPX_TR, NIFTY_50_TR"
          />
        </div>
      </div>
    </div>
  );
};
