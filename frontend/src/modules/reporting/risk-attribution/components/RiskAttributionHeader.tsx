import React from 'react';
import {
  ShieldAlert,
  Calendar,
  Layers,
  Sparkles,
  RefreshCw,
  FolderArchive,
  BarChart3,
  Sliders,
} from 'lucide-react';
import { RiskMeasureType, ValuationCutoffPolicy } from '../../../../types/riskAttribution';

interface RiskAttributionHeaderProps {
  portfolioId: string;
  onPortfolioChange: (id: string) => void;
  reportingDate: string;
  onReportingDateChange: (date: string) => void;
  riskMeasure: RiskMeasureType;
  onRiskMeasureChange: (rm: RiskMeasureType) => void;
  cutoffPolicy: ValuationCutoffPolicy;
  onCutoffPolicyChange: (cp: ValuationCutoffPolicy) => void;
  onGenerate: () => void;
  onOpenArchive: () => void;
  isLoading: boolean;
  versionNumber?: number;
}

export const RiskAttributionHeader: React.FC<RiskAttributionHeaderProps> = ({
  portfolioId,
  onPortfolioChange,
  reportingDate,
  onReportingDateChange,
  riskMeasure,
  onRiskMeasureChange,
  cutoffPolicy,
  onCutoffPolicyChange,
  onGenerate,
  onOpenArchive,
  isLoading,
  versionNumber,
}) => {
  return (
    <div className="bg-surface border-b border-line p-6">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-brand/10 border border-indigo-500/20 rounded-xl text-brand">
              <ShieldAlert className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold text-ink ">
                  Risk Attribution Reports
                </h1>
                {versionNumber && (
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-brand-soft/60 text-brand border border-brand/20">
                    v{versionNumber}
                  </span>
                )}
              </div>
              <p className="text-sm text-muted mt-0.5">
                M14.03 Institutional Multi-Level Risk Decomposition (Securities, Sectors, Factors)
              </p>
            </div>
          </div>
        </div>

        {/* Global Action Buttons */}
        <div className="flex items-center gap-3">
          <button
            onClick={onOpenArchive}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-subtle hover:bg-hover text-secondary text-sm font-medium border border-line-strong transition-colors"
          >
            <FolderArchive className="w-4 h-4 text-muted" />
            <span>Version Archive</span>
          </button>
          <button
            onClick={onGenerate}
            disabled={isLoading}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-brand hover:bg-brand-hover text-white text-sm font-medium transition-colors shadow-lg shadow-indigo-600/20 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            <span>{isLoading ? 'Decomposing...' : 'Generate Report'}</span>
          </button>
        </div>
      </div>

      {/* Control Bar */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-6 pt-5 border-t border-line/80">
        <div>
          <label className="block text-xs font-medium text-muted mb-1.5 flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5" /> Portfolio
          </label>
          <select
            value={portfolioId}
            onChange={(e) => onPortfolioChange(e.target.value)}
            className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-secondary focus:outline-none focus:border-indigo-500"
          >
            <option value="PORTFOLIO-INDIA-CORE">PORTFOLIO-INDIA-CORE (NSE/BSE)</option>
            <option value="PORTFOLIO-US-EQUITY">PORTFOLIO-US-EQUITY (NYSE/NASDAQ)</option>
            <option value="PORTFOLIO-GLOBAL-TECH">PORTFOLIO-GLOBAL-TECH</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-muted mb-1.5 flex items-center gap-1.5">
            <Calendar className="w-3.5 h-3.5" /> Reporting Date
          </label>
          <input
            type="date"
            value={reportingDate}
            onChange={(e) => onReportingDateChange(e.target.value)}
            className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-secondary focus:outline-none focus:border-indigo-500"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-muted mb-1.5 flex items-center gap-1.5">
            <BarChart3 className="w-3.5 h-3.5" /> Risk Measure
          </label>
          <select
            value={riskMeasure}
            onChange={(e) => onRiskMeasureChange(e.target.value as RiskMeasureType)}
            className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-secondary focus:outline-none focus:border-indigo-500"
          >
            <option value="PORTFOLIO_VOLATILITY">Portfolio Volatility (sigma_p)</option>
            <option value="PORTFOLIO_VARIANCE">Portfolio Variance (sigma_p^2)</option>
            <option value="PARAMETRIC_VAR">Parametric VaR (95%)</option>
            <option value="SYSTEMATIC_FACTOR_RISK">Systematic Factor Risk</option>
            <option value="IDIOSYNCRATIC_RISK">Idiosyncratic Residual Risk</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-muted mb-1.5 flex items-center gap-1.5">
            <Sliders className="w-3.5 h-3.5" /> Cutoff Policy
          </label>
          <select
            value={cutoffPolicy}
            onChange={(e) => onCutoffPolicyChange(e.target.value as ValuationCutoffPolicy)}
            className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-secondary focus:outline-none focus:border-indigo-500"
          >
            <option value="OFFICIAL_CLOSE">Official Close</option>
            <option value="INTRADAY_SNAPSHOT">Intraday Snapshot</option>
            <option value="LATEST_AVAILABLE">Latest Available</option>
          </select>
        </div>
      </div>
    </div>
  );
};
