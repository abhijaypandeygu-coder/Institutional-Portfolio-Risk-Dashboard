import React, { useState, useEffect } from 'react';
import {
  CanonicalStressReport,
  StressReportSummary,
} from '../../../types/stressReport';
import { StressReportHeader } from './components/StressReportHeader';
import { StressExecutiveSummaryCards } from './components/StressExecutiveSummaryCards';
import { ScenarioAssumptionsTable } from './components/ScenarioAssumptionsTable';
import { PositionAndSectorStressTable } from './components/PositionAndSectorStressTable';
import { SensitivityAndLimits } from './components/SensitivityAndLimits';
import { StressReportArchiveDrawer } from './components/StressReportArchiveDrawer';

export const StressTestingReportsPage: React.FC = () => {
  const [portfolioId, setPortfolioId] = useState('PORTFOLIO-INDIA-CORE');
  const [reportingDate, setReportingDate] = useState('2026-11-17');
  const [currency, setCurrency] = useState('USD');
  
  const [report, setReport] = useState<CanonicalStressReport | null>(null);
  const [reports, setReports] = useState<StressReportSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isArchiveOpen, setIsArchiveOpen] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [verificationResult, setVerificationResult] = useState<any>(null);

  const fetchReport = async (reportId?: string) => {
    setIsLoading(true);
    try {
      if (reportId) {
        const res = await fetch(`/api/v1/reports/stress/${reportId}`);
        if (res.ok) {
          const data = await res.json();
          setReport(data);
        }
      } else {
        const res = await fetch('/api/v1/reports/stress', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            portfolio_id: portfolioId,
            reporting_date: reportingDate,
            reporting_currency: currency,
            force_regenerate: false,
          }),
        });
        if (res.ok) {
          const data = await res.json();
          setReport(data);
        }
      }
    } catch (err) {
      console.error('Error fetching stress report:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchReportsList = async () => {
    try {
      const res = await fetch(
        `/api/v1/reports/stress?portfolio_id=${encodeURIComponent(portfolioId)}`
      );
      if (res.ok) {
        const data = await res.json();
        setReports(data);
      }
    } catch (err) {
      console.error('Error fetching stress report list:', err);
    }
  };

  const handleGenerate = async () => {
    setIsLoading(true);
    try {
      const res = await fetch('/api/v1/reports/stress', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          portfolio_id: portfolioId,
          reporting_date: reportingDate,
          reporting_currency: currency,
          force_regenerate: true,
          regeneration_reason: 'User manual regeneration trigger',
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setReport(data);
        await fetchReportsList();
      }
    } catch (err) {
      console.error('Error generating stress report:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyIntegrity = async () => {
    if (!report?.report_id) return;
    setIsVerifying(true);
    try {
      const res = await fetch(
        `/api/v1/reports/stress/${report.report_id}/verify-integrity`,
        { method: 'POST' }
      );
      if (res.ok) {
        const data = await res.json();
        setVerificationResult(data);
      }
    } catch (err) {
      console.error('Error verifying artifact integrity:', err);
    } finally {
      setIsVerifying(false);
    }
  };

  useEffect(() => {
    fetchReport();
    fetchReportsList();
  }, [portfolioId, reportingDate]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* 1. Header */}
      <StressReportHeader
        portfolioId={portfolioId}
        onPortfolioChange={setPortfolioId}
        reportingDate={reportingDate}
        onReportingDateChange={setReportingDate}
        currency={currency}
        onCurrencyChange={setCurrency}
        onGenerate={handleGenerate}
        onOpenArchive={() => setIsArchiveOpen(true)}
        isLoading={isLoading}
        versionNumber={report?.report_version}
      />

      {/* 2. Main Analytics Views */}
      <main className="flex-1 space-y-6 pb-12">
        {report && (
          <>
            <StressExecutiveSummaryCards
              summary={report.executive_summary}
              currency={report.reporting_currency}
            />

            <div className="px-6 space-y-6">
              {/* Scenario Descriptions Table */}
              <ScenarioAssumptionsTable scenarios={report.scenarios} />

              {/* Positions and Sectors */}
              <PositionAndSectorStressTable
                positions={report.position_results}
                sectors={report.sector_breakdown}
              />

              {/* Sensitivities & Limit Implications */}
              <SensitivityAndLimits
                sensitivities={report.sensitivities}
                limits={report.limit_results}
              />
            </div>
          </>
        )}
      </main>

      {/* 3. Historical Version & Integrity Drawer */}
      <StressReportArchiveDrawer
        isOpen={isArchiveOpen}
        onClose={() => setIsArchiveOpen(false)}
        reports={reports}
        onSelectReport={(reportId) => {
          fetchReport(reportId);
          setIsArchiveOpen(false);
        }}
        activeReportId={report?.report_id}
        artifacts={report?.artifacts}
        onVerifyIntegrity={handleVerifyIntegrity}
        isVerifying={isVerifying}
        verificationResult={verificationResult}
      />
    </div>
  );
};

export default StressTestingReportsPage;
