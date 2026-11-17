import React, { useState, useEffect } from 'react';
import {
  CanonicalLiquidityReport,
  LiquidityReportSummaryResponse,
  LiquidationAssumptionsInput,
  LiquidityArtifactType,
} from '../../../types/liquidityReport';
import { LiquidityReportHeader } from './components/LiquidityReportHeader';
import { LiquidityExecutiveSummaryCards } from './components/LiquidityExecutiveSummaryCards';
import { PositionLiquidityAndCostTable } from './components/PositionLiquidityAndCostTable';
import { IlliquidityStressAndLimits } from './components/IlliquidityStressAndLimits';
import { LiquidityReportArchiveDrawer } from './components/LiquidityReportArchiveDrawer';

export const LiquidityReportsPage: React.FC = () => {
  const [portfolioId, setPortfolioId] = useState('portfolio_001');
  const [asOfDate, setAsOfDate] = useState('2026-11-17');
  const [currency, setCurrency] = useState('INR');
  const [assumptions, setAssumptions] = useState<LiquidationAssumptionsInput>({
    participation_rate: 0.10,
    target_fraction: 1.0,
    execution_horizon: 'CONFIGURED_BY_UPSTREAM_MODEL',
    side: 'AUTO',
    include_fees: true,
    estimation_scope: 'INDEPENDENT',
  });

  const [report, setReport] = useState<CanonicalLiquidityReport | null>(null);
  const [history, setHistory] = useState<LiquidityReportSummaryResponse[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isArchiveOpen, setIsArchiveOpen] = useState(false);
  const [verifiedStatus, setVerifiedStatus] = useState<Record<string, boolean>>({});

  const fetchReports = async () => {
    try {
      const res = await fetch(`/api/v1/reports/liquidity?portfolio_id=${portfolioId}`);
      if (res.ok) {
        const data: LiquidityReportSummaryResponse[] = await res.json();
        setHistory(data);
        if (data.length > 0 && !report) {
          loadReport(data[0].report_id);
        }
      }
    } catch (e) {
      console.error('Failed to fetch liquidity report history', e);
    }
  };

  const loadReport = async (reportId: string) => {
    try {
      const res = await fetch(`/api/v1/reports/liquidity/${reportId}`);
      if (res.ok) {
        const data: CanonicalLiquidityReport = await res.json();
        setReport(data);
      }
    } catch (e) {
      console.error('Failed to load canonical report', e);
    }
  };

  const handleGenerate = async () => {
    setIsGenerating(true);
    try {
      const res = await fetch('/api/v1/reports/liquidity', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          portfolio_id: portfolioId,
          report_name: `Portfolio Liquidity & Exit Review (${portfolioId})`,
          as_of_timestamp: `${asOfDate}T10:00:00Z`,
          reporting_currency: currency,
          liquidation_assumptions: assumptions,
          export_formats: ['PDF', 'CSV', 'HTML'],
          include_position_analysis: true,
          include_concentration: true,
          include_stress_comparison: true,
          include_limit_implications: true,
        }),
      });
      if (res.ok) {
        const newReport: CanonicalLiquidityReport = await res.json();
        setReport(newReport);
        await fetchReports();
      }
    } catch (e) {
      console.error('Failed to generate liquidity report', e);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleVerifyHash = async (artifactType: LiquidityArtifactType) => {
    if (!report) return;
    try {
      const res = await fetch(`/api/v1/reports/liquidity/${report.report_id}/verify/${artifactType}`);
      if (res.ok) {
        setVerifiedStatus((prev) => ({ ...prev, [artifactType]: true }));
      }
    } catch (e) {
      console.error('Integrity verification failed', e);
    }
  };

  useEffect(() => {
    fetchReports();
  }, [portfolioId]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6">
      <LiquidityReportHeader
        portfolioId={portfolioId}
        onPortfolioChange={setPortfolioId}
        asOfDate={asOfDate}
        onAsOfDateChange={setAsOfDate}
        currency={currency}
        onCurrencyChange={setCurrency}
        assumptions={assumptions}
        onAssumptionsChange={setAssumptions}
        isGenerating={isGenerating}
        onGenerate={handleGenerate}
        onOpenArchive={() => setIsArchiveOpen(!isArchiveOpen)}
        isArchiveOpen={isArchiveOpen}
      />

      {report ? (
        <>
          <LiquidityExecutiveSummaryCards
            summary={report.executive_summary}
            profile={report.profile}
            reportCode={report.report_code}
          />

          <PositionLiquidityAndCostTable
            positions={report.positions}
            liquidations={report.liquidations}
            currency={report.reporting_currency}
          />

          <IlliquidityStressAndLimits
            concentrations={report.concentrations}
            stressComparisons={report.stress_comparisons}
            limits={report.limits}
            currency={report.reporting_currency}
          />
        </>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-12 text-center text-slate-400">
          <p className="text-sm">No report loaded for portfolio {portfolioId}. Click "Generate Liquidity Report" to initiate analysis.</p>
        </div>
      )}

      {report && (
        <LiquidityReportArchiveDrawer
          isOpen={isArchiveOpen}
          onClose={() => setIsArchiveOpen(false)}
          reports={history}
          currentReportId={report.report_id}
          onSelectReport={loadReport}
          artifacts={report.artifacts}
          onVerifyHash={handleVerifyHash}
          verifiedStatus={verifiedStatus}
        />
      )}
    </div>
  );
};
