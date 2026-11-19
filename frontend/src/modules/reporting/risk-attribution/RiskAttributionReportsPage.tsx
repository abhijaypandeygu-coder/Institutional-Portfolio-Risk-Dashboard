import React, { useState, useEffect } from 'react';
import {
  RiskMeasureType,
  ValuationCutoffPolicy,
  CanonicalRiskAttributionReport,
  RiskAttributionRunSummary,
} from '../../../types/riskAttribution';
import { RiskAttributionHeader } from './components/RiskAttributionHeader';
import { RiskAttributionMetricsCards } from './components/RiskAttributionMetricsCards';
import { SecurityAttributionTable } from './components/SecurityAttributionTable';
import { SectorIndustryAttribution } from './components/SectorIndustryAttribution';
import { FactorAttributionPanel } from './components/FactorAttributionPanel';
import { ReconciliationAndCaveats } from './components/ReconciliationAndCaveats';
import { RiskAttributionArchiveDrawer } from './components/RiskAttributionArchiveDrawer';

export const RiskAttributionReportsPage: React.FC = () => {
  const [portfolioId, setPortfolioId] = useState('PORTFOLIO-INDIA-CORE');
  const [reportingDate, setReportingDate] = useState('2026-11-17');
  const [riskMeasure, setRiskMeasure] = useState<RiskMeasureType>('PORTFOLIO_VOLATILITY');
  const [cutoffPolicy, setCutoffPolicy] = useState<ValuationCutoffPolicy>('OFFICIAL_CLOSE');
  
  const [report, setReport] = useState<CanonicalRiskAttributionReport | null>(null);
  const [runs, setRuns] = useState<RiskAttributionRunSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isArchiveOpen, setIsArchiveOpen] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [verificationResult, setVerificationResult] = useState<any>(null);

  // Load latest report or runs
  const fetchReport = async (runId?: string) => {
    setIsLoading(true);
    try {
      if (runId) {
        const res = await fetch(`/api/v1/reports/risk-attribution/runs/${runId}`);
        if (res.ok) {
          const data = await res.json();
          setReport(data);
        }
      } else {
        // Trigger report generation or get existing
        const res = await fetch('/api/v1/reports/risk-attribution/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            portfolio_id: portfolioId,
            reporting_date: reportingDate,
            risk_measure: riskMeasure,
            valuation_cutoff_policy: cutoffPolicy,
            force_regenerate: false,
          }),
        });
        if (res.ok) {
          const data = await res.json();
          setReport(data);
        }
      }
    } catch (err) {
      console.error('Error fetching risk attribution report:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchRuns = async () => {
    try {
      const res = await fetch(
        `/api/v1/reports/risk-attribution/runs?portfolio_id=${encodeURIComponent(portfolioId)}`
      );
      if (res.ok) {
        const data = await res.json();
        setRuns(data);
      }
    } catch (err) {
      console.error('Error fetching run history:', err);
    }
  };

  const handleGenerate = async () => {
    setIsLoading(true);
    try {
      const res = await fetch('/api/v1/reports/risk-attribution/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          portfolio_id: portfolioId,
          reporting_date: reportingDate,
          risk_measure: riskMeasure,
          valuation_cutoff_policy: cutoffPolicy,
          force_regenerate: true,
          regeneration_reason: 'User manual regeneration trigger',
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setReport(data);
        await fetchRuns();
      }
    } catch (err) {
      console.error('Error generating risk attribution report:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyIntegrity = async () => {
    if (!report?.report_id) return;
    setIsVerifying(true);
    try {
      const res = await fetch(
        `/api/v1/reports/risk-attribution/runs/${report.report_id}/verify-integrity`,
        { method: 'POST' }
      );
      if (res.ok) {
        const data = await res.json();
        setVerificationResult(data);
      }
    } catch (err) {
      console.error('Error verifying integrity:', err);
    } finally {
      setIsVerifying(false);
    }
  };

  useEffect(() => {
    fetchReport();
    fetchRuns();
  }, [portfolioId, reportingDate]);

  return (
    <div className="min-h-screen bg-canvas text-ink flex flex-col">
      {/* 1. Header & Controls */}
      <RiskAttributionHeader
        portfolioId={portfolioId}
        onPortfolioChange={setPortfolioId}
        reportingDate={reportingDate}
        onReportingDateChange={setReportingDate}
        riskMeasure={riskMeasure}
        onRiskMeasureChange={setRiskMeasure}
        cutoffPolicy={cutoffPolicy}
        onCutoffPolicyChange={setCutoffPolicy}
        onGenerate={handleGenerate}
        onOpenArchive={() => setIsArchiveOpen(true)}
        isLoading={isLoading}
        versionNumber={report?.report_version}
      />

      {/* 2. Main Analytics Views */}
      <main className="flex-1 space-y-6 pb-12">
        {report && (
          <>
            <RiskAttributionMetricsCards
              authoritativeValue={report.authoritative_risk_value}
              riskMeasure={report.risk_measure}
              riskMeasureUnit={report.risk_measure_unit}
              riskComposition={report.risk_composition}
              reconciliationStatus={report.reconciliation_status}
            />

            <div className="px-6 space-y-6">
              {/* Security Table */}
              <SecurityAttributionTable securities={report.security_contributions} />

              {/* Group (Sector & Industry) */}
              <SectorIndustryAttribution
                sectors={report.sector_contributions}
                industries={report.industry_contributions}
              />

              {/* Systematic Factors */}
              <FactorAttributionPanel
                factors={report.factor_contributions}
                modelVersion={report.methodology_manifest?.factor_model_version}
              />

              {/* Audit Reconciliations & Caveats */}
              <ReconciliationAndCaveats
                reconciliations={report.reconciliations}
                caveats={report.caveats}
              />
            </div>
          </>
        )}
      </main>

      {/* 3. Historical Version & Integrity Drawer */}
      <RiskAttributionArchiveDrawer
        isOpen={isArchiveOpen}
        onClose={() => setIsArchiveOpen(false)}
        runs={runs}
        onSelectRun={(runId) => {
          fetchReport(runId);
          setIsArchiveOpen(false);
        }}
        activeRunId={report?.report_id}
        artifacts={report?.artifacts}
        onVerifyIntegrity={handleVerifyIntegrity}
        isVerifying={isVerifying}
        verificationResult={verificationResult}
      />
    </div>
  );
};

export default RiskAttributionReportsPage;
