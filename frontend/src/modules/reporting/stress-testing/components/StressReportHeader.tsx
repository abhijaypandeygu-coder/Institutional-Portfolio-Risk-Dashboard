import React from 'react';
import {
  Zap,
  Calendar,
  Layers,
  RefreshCw,
  FolderArchive,
  DollarSign,
  AlertOctagon,
} from 'lucide-react';

interface StressReportHeaderProps {
  portfolioId: string;
  onPortfolioChange: (id: string) => void;
  reportingDate: string;
  onReportingDateChange: (date: string) => void;
  currency: string;
  onCurrencyChange: (c: string) => void;
  onGenerate: () => void;
  onOpenArchive: () => void;
  isLoading: boolean;
  versionNumber?: number;
}

export const StressReportHeader: React.FC<StressReportHeaderProps> = ({
  portfolioId,
  onPortfolioChange,
  reportingDate,
  onReportingDateChange,
  currency,
  onCurrencyChange,
  onGenerate,
  onOpenArchive,
  isLoading,
  versionNumber,
}) => {
  return (
    <div className="bg-slate-900 border-b border-slate-800 p-6">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400">
            <Zap className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-slate-100 tracking-tight">
                Stress Testing Reports
              </h1>
              {versionNumber && (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-900/60 text-rose-300 border border-rose-700/50">
                  v{versionNumber}
                </span>
              )}
            </div>
            <p className="text-sm text-slate-400 mt-0.5">
              M14.04 Multi-Scenario Stress P&L, Sensitivity, and Limit Exceedance Analysis
            </p>
          </div>
        </div>

        {/* Global Action Buttons */}
        <div className="flex items-center gap-3">
          <button
            onClick={onOpenArchive}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium border border-slate-700 transition-colors"
          >
            <FolderArchive className="w-4 h-4 text-slate-400" />
            <span>Version Archive</span>
          </button>
          <button
            onClick={onGenerate}
            disabled={isLoading}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-sm font-medium transition-colors shadow-lg shadow-rose-600/20 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            <span>{isLoading ? 'Simulating...' : 'Generate Report'}</span>
          </button>
        </div>
      </div>

      {/* Control Bar */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6 pt-5 border-t border-slate-800/80">
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1.5 flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5" /> Portfolio
          </label>
          <select
            value={portfolioId}
            onChange={(e) => onPortfolioChange(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-rose-500"
          >
            <option value="PORTFOLIO-INDIA-CORE">PORTFOLIO-INDIA-CORE (NSE/BSE)</option>
            <option value="PORTFOLIO-US-EQUITY">PORTFOLIO-US-EQUITY (NYSE/NASDAQ)</option>
            <option value="PORTFOLIO-GLOBAL-TECH">PORTFOLIO-GLOBAL-TECH</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1.5 flex items-center gap-1.5">
            <Calendar className="w-3.5 h-3.5" /> Reporting Date
          </label>
          <input
            type="date"
            value={reportingDate}
            onChange={(e) => onReportingDateChange(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-rose-500"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1.5 flex items-center gap-1.5">
            <DollarSign className="w-3.5 h-3.5" /> Reporting Currency
          </label>
          <select
            value={currency}
            onChange={(e) => onCurrencyChange(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-rose-500"
          >
            <option value="USD">USD ($)</option>
            <option value="INR">INR (₹)</option>
          </select>
        </div>
      </div>
    </div>
  );
};
