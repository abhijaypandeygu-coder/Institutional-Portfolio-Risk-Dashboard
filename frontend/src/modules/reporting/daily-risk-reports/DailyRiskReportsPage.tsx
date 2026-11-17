import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  CanonicalDailyRiskReport,
  DailyReportRunResponse,
  DailyReportIntegrityVerificationResponse,
} from "../../types/dailyReport";
import { DailyReportOverview } from "./components/DailyReportOverview";
import { DailyReportPortfolioSummary } from "./components/DailyReportPortfolioSummary";
import { DailyReportRiskSummary } from "./components/DailyReportRiskSummary";
import { DailyReportControlStatus } from "./components/DailyReportControlStatus";
import { DailyReportFreshnessManifest } from "./components/DailyReportFreshnessManifest";
import { DailyReportArchiveDrawer } from "./components/DailyReportArchiveDrawer";

const API_BASE = "http://localhost:8000/api/v1/reports/daily";

export const DailyRiskReportsPage: React.FC = () => {
  const [selectedPortfolio, setSelectedPortfolio] = useState<string>("PORT-01");
  const [selectedDate, setSelectedDate] = useState<string>(
    new Date().toISOString().split("T")[0]
  );
  const [report, setReport] = useState<CanonicalDailyRiskReport | null>(null);
  const [runs, setRuns] = useState<DailyReportRunResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [generating, setGenerating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch report runs / archives
  const fetchArchiveRuns = useCallback(async (portfolioId: string) => {
    try {
      const res = await axios.get<DailyReportRunResponse[]>(
        `${API_BASE}/runs/${portfolioId}?limit=15`
      );
      setRuns(res.data);
    } catch (err: any) {
      console.warn("Could not fetch archived runs:", err.message);
    }
  }, []);

  // Fetch report for portfolio & date
  const fetchReport = useCallback(async (portfolioId: string, reportDate: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get<CanonicalDailyRiskReport>(
        `${API_BASE}/${portfolioId}/${reportDate}`
      );
      setReport(res.data);
    } catch (err: any) {
      if (err.response?.status === 404) {
        setReport(null);
      } else {
        setError(err.response?.data?.detail || err.message);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch report by runId
  const fetchReportByRunId = async (runId: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get<CanonicalDailyRiskReport>(
        `${API_BASE}/run/${runId}`
      );
      setReport(res.data);
      if (res.data.portfolio?.portfolio_id) {
        setSelectedPortfolio(res.data.portfolio.portfolio_id);
      }
      if (res.data.metadata?.report_date) {
        setSelectedDate(res.data.metadata.report_date);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchArchiveRuns(selectedPortfolio);
    fetchReport(selectedPortfolio, selectedDate);
  }, [selectedPortfolio, selectedDate, fetchArchiveRuns, fetchReport]);

  // Generate Report
  const handleGenerateReport = async (forceRegenerate: boolean = false) => {
    setGenerating(true);
    setError(null);
    try {
      const res = await axios.post<CanonicalDailyRiskReport>(
        `${API_BASE}/generate`,
        {
          portfolio_id: selectedPortfolio,
          report_date: selectedDate,
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

  // Verify Artifact Integrity
  const handleVerifyIntegrity = async (
    artifactId: string
  ): Promise<DailyReportIntegrityVerificationResponse | null> => {
    try {
      const res = await axios.get<DailyReportIntegrityVerificationResponse>(
        `${API_BASE}/artifact/${artifactId}/verify`
      );
      return res.data;
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
      return null;
    }
  };

  // Download Artifact
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

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 space-y-6">
      {/* Header & Controls */}
      <DailyReportOverview
        report={report}
        selectedPortfolio={selectedPortfolio}
        selectedDate={selectedDate}
        onPortfolioChange={setSelectedPortfolio}
        onDateChange={setSelectedDate}
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
          Retrieving canonical EOD report records...
        </div>
      )}

      {!loading && !report && (
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-8 text-center">
          <p className="text-slate-400 text-sm font-mono">
            No Daily Risk Report has been generated for {selectedPortfolio} on {selectedDate}.
          </p>
          <button
            onClick={() => handleGenerateReport(false)}
            disabled={generating}
            className="mt-4 px-4 py-2 text-xs font-semibold rounded bg-cyan-600 hover:bg-cyan-500 text-white font-mono"
          >
            {generating ? "Generating..." : "Generate EOD Daily Report Now"}
          </button>
        </div>
      )}

      {report && (
        <>
          {/* Portfolio Accounting & Balances */}
          <DailyReportPortfolioSummary
            summary={report.portfolio_summary}
            reportingCurrency={report.portfolio?.reporting_currency || "USD"}
          />

          {/* Quantitative Risk Summary */}
          <DailyReportRiskSummary
            metrics={report.risk_metrics}
            reportingCurrency={report.portfolio?.reporting_currency || "USD"}
          />

          {/* Limit Status & Breach Audit Trail */}
          <DailyReportControlStatus limitStatus={report.risk_limit_status} />

          {/* Freshness Watermarks & Latency Manifest */}
          <DailyReportFreshnessManifest metadata={report.metadata} />
        </>
      )}

      {/* Historical Report Archive & Cryptographic Evidence */}
      {runs.length > 0 && (
        <DailyReportArchiveDrawer
          runs={runs}
          currentRunId={report?.run_id}
          onSelectRun={fetchReportByRunId}
          onVerifyIntegrity={handleVerifyIntegrity}
          onDownloadArtifact={handleDownloadArtifact}
        />
      )}
    </div>
  );
};

export default DailyRiskReportsPage;
