import React from "react";
import {
  CanonicalPerformanceReport,
  PerformanceDataStatus,
  ReportingPeriodType,
  ReturnMethodology,
} from "../../../types/performanceReport";

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
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-emerald-950 text-emerald-400 border border-emerald-800">STATUS: COMPLETE</span>;
      case "COMPLETE_WITH_APPROXIMATIONS":
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-amber-950 text-amber-400 border border-amber-800">STATUS: APPROXIMATED</span>;
      case "PARTIAL":
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-orange-950 text-orange-400 border border-orange-800">STATUS: PARTIAL</span>;
      default:
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-rose-950 text-rose-400 border border-rose-800">STATUS: UNAVAILABLE</span>;
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 shadow-lg">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-slate-100 tracking-tight">
              M14.02 — Portfolio Performance Reports
            </h1>
            {report && (
              <span className="px-2 py-0.5 text-xs font-mono rounded bg-slate-800 text-cyan-400 border border-slate-700">
                v{report.report_version}
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Auditable Multi-Period Investment Returns, Cumulative Compounding, P&amp;L Attribution &amp; Benchmark Analysis
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {report && getStatusBadge(report.performance_summary?.performance_data_status)}

          <button
            onClick={() => onGenerateReport(false)}
            disabled={isGenerating}
            className="px-3.5 py-1.5 text-xs font-semibold rounded bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-800 text-white transition-colors duration-150 shadow"
          >
            {isGenerating ? "Calculating Returns..." : "Generate Performance Report"}
          </button>

          {report && (
            <button
              onClick={() => onGenerateReport(true)}
              disabled={isGenerating}
              className="px-3 py-1.5 text-xs font-medium rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors duration-150"
              title="Force non-destructive recalculation creating a new auditable version"
            >
              Recalculate (v{report.report_version + 1})
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3 pt-4">
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">Portfolio</label>
          <input
            type="text"
            value={selectedPortfolio}
            onChange={(e) => onPortfolioChange(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">Period Type</label>
          <select
            value={periodType}
            onChange={(e) => onPeriodTypeChange(e.target.value as ReportingPeriodType)}
            className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
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
          <label className="block text-xs font-medium text-slate-400 mb-1">Start Date</label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => onStartDateChange(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">End Date</label>
          <input
            type="date"
            value={endDate}
            onChange={(e) => onEndDateChange(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">Methodology</label>
          <select
            value={returnMethod}
            onChange={(e) => onReturnMethodChange(e.target.value as ReturnMethodology)}
            className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
          >
            <option value="TWR">TWR (Exact Subperiod)</option>
            <option value="MODIFIED_DIETZ">Modified Dietz</option>
            <option value="MWR_XIRR">MWR / XIRR</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">Benchmark</label>
          <input
            type="text"
            value={benchmarkId}
            onChange={(e) => onBenchmarkChange(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
            placeholder="SPX_TR, NIFTY_50_TR"
          />
        </div>
      </div>
    </div>
  );
};
