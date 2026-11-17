import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  CanonicalPerformanceReport,
  PerformanceReportRunResponse,
  PerformanceIntegrityVerificationResponse,
  ReportingPeriodType,
  ReturnMethodology,
} from "../../types/performanceReport";
import { PerformanceReportOverview } from "./components/PerformanceReportOverview";
import { PerformanceMetricsCards } from "./components/PerformanceMetricsCards";
import { ReturnSeriesTable } from "./components/ReturnSeriesTable";
import { PnLAndCaveats } from "./components/PnLAndCaveats";
import { PerformanceArchiveDrawer } from "./components/PerformanceArchiveDrawer";

const API_BASE = "http://localhost:8000/api/v1/reports/performance";

export const PortfolioPerformanceReportsPage: React.FC = () => {
  const [selectedPortfolio, setSelectedPortfolio] = useState<string>("PORT-01");
  const [periodType, setPeriodType] = useState<ReportingPeriodType>("MONTHLY");
  const [startDate, setStartDate] = useState<string>("2026-11-01");
  const [endDate, setEndDate] = useState<string>("2026-11-17");
  const [returnMethod, setReturnMethod] = useState<ReturnMethodology>("TWR");
  const [benchmarkId, setBenchmarkId] = useState<string>("SPX_TR");

  const [report, setReport] = useState<CanonicalPerformanceReport | null>(null);
  const [runs, setRuns] = useState<PerformanceReportRunResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [generating, setGenerating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchArchiveRuns = useCallback(async (portfolioId: string) => {
    try {
      const res = await axios.get<PerformanceReportRunResponse[]>(
        `${API_BASE}/archive/${portfolioId}?limit=20`
      );
      setRuns(res.data);
    } catch (err: any) {
      console.warn("Could not fetch archived performance reports:", err.message);
    }
  }, []);

  const fetchReportByRunId = async (runId: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get<CanonicalPerformanceReport>(
        `${API_BASE}/runs/${runId}`
      );
      setReport(res.data);
      if (res.data.portfolio?.portfolio_id) {
        setSelectedPortfolio(res.data.portfolio.portfolio_id);
      }
      if (res.data.reporting_period?.start_date) {
        setStartDate(res.data.reporting_period.start_date);
      }
      if (res.data.reporting_period?.end_date) {
        setEndDate(res.data.reporting_period.end_date);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateReport = async (forceRegenerate: boolean = false) => {
    setGenerating(true);
    setError(null);
    try {
      const res = await axios.post<CanonicalPerformanceReport>(
        `${API_BASE}/generate`,
        {
          portfolio_id: selectedPortfolio,
          start_date: startDate,
          end_date: endDate,
          reporting_period_type: periodType,
          return_methodology: returnMethod,
          benchmark_id: benchmarkId,
          force_regenerate: forceRegenerate,
        }
      );
      setReport(res.data);
      await fetchArchiveRuns(selectedPortfolio);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setGenerating(false);
    }
  };

  const handleVerifyIntegrity = async (
    artifactId: string
  ): Promise<PerformanceIntegrityVerificationResponse | null> => {
    try {
      const res = await axios.get<PerformanceIntegrityVerificationResponse>(
        `${API_BASE}/artifact/${artifactId}/verify`
      );
      return res.data;
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
      return null;
    }
  };

  const handleDownloadArtifact = async (artifactId: string, fileName: string) => {
    try {
      const res = await axios.get(`${API_BASE}/artifact/${artifactId}/download`, {
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", fileName);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
    }
  };

  useEffect(() => {
    fetchArchiveRuns(selectedPortfolio);
  }, [selectedPortfolio, fetchArchiveRuns]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 space-y-6">
      {/* Header Controls & Filter Parameters */}
      <PerformanceReportOverview
        report={report}
        selectedPortfolio={selectedPortfolio}
        periodType={periodType}
        startDate={startDate}
        endDate={endDate}
        returnMethod={returnMethod}
        benchmarkId={benchmarkId}
        onPortfolioChange={setSelectedPortfolio}
        onPeriodTypeChange={setPeriodType}
        onStartDateChange={setStartDate}
        onEndDateChange={setEndDate}
        onReturnMethodChange={setReturnMethod}
        onBenchmarkChange={setBenchmarkId}
        onGenerateReport={handleGenerateReport}
        isGenerating={generating}
      />

      {error && (
        <div className="bg-rose-950/60 border border-rose-800 text-rose-300 px-4 py-3 rounded text-xs font-mono flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-rose-400 hover:text-rose-200">
            ✕
          </button>
        </div>
      )}

      {loading && (
        <div className="text-center py-8 text-xs font-mono text-cyan-400 animate-pulse">
          Loading performance analytics record...
        </div>
      )}

      {!loading && !report && (
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-8 text-center">
          <p className="text-slate-400 text-sm font-mono">
            No Performance Report currently loaded for {selectedPortfolio}.
          </p>
          <button
            onClick={() => handleGenerateReport(false)}
            disabled={generating}
            className="mt-4 px-4 py-2 text-xs font-semibold rounded bg-cyan-600 hover:bg-cyan-500 text-white font-mono"
          >
            {generating ? "Generating..." : "Generate Performance Report Now"}
          </button>
        </div>
      )}

      {report && (
        <>
          {/* Executive Return & Balance Metrics */}
          <PerformanceMetricsCards
            summary={report.performance_summary}
            pnl={report.pnl_breakdown}
            flows={report.cash_flows}
            currency={report.portfolio?.reporting_currency || "USD"}
          />

          {/* Subperiod Return Series & Benchmark Aligned Observations */}
          <ReturnSeriesTable
            returns={report.return_observations}
            benchmarks={report.benchmark_observations}
            currency={report.portfolio?.reporting_currency || "USD"}
          />

          {/* P&L Breakdown Attribution & Caveats */}
          <PnLAndCaveats
            pnl={report.pnl_breakdown}
            caveats={report.caveats}
            currency={report.portfolio?.reporting_currency || "USD"}
          />
        </>
      )}

      {/* Report Archive & Cryptographic Verification */}
      {runs.length > 0 && (
        <PerformanceArchiveDrawer
          runs={runs}
          currentRunId={report?.report_id}
          onSelectRun={fetchReportByRunId}
          onVerifyIntegrity={handleVerifyIntegrity}
          onDownloadArtifact={handleDownloadArtifact}
        />
      )}
    </div>
  );
};

export default PortfolioPerformanceReportsPage;
