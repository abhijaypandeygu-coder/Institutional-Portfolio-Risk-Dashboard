import React from 'react';
import {
  LiquidationAssumptionsInput,
} from '../../../../types/liquidityReport';

interface Props {
  portfolioId: string;
  onPortfolioChange: (id: string) => void;
  asOfDate: string;
  onAsOfDateChange: (date: string) => void;
  currency: string;
  onCurrencyChange: (curr: string) => void;
  assumptions: LiquidationAssumptionsInput;
  onAssumptionsChange: (assumptions: LiquidationAssumptionsInput) => void;
  isGenerating: boolean;
  onGenerate: () => void;
  onOpenArchive: () => void;
  isArchiveOpen: boolean;
}

export const LiquidityReportHeader: React.FC<Props> = ({
  portfolioId,
  onPortfolioChange,
  asOfDate,
  onAsOfDateChange,
  currency,
  onCurrencyChange,
  assumptions,
  onAssumptionsChange,
  isGenerating,
  onGenerate,
  onOpenArchive,
  isArchiveOpen,
}) => {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 mb-6 shadow-md">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <span className="px-2.5 py-0.5 rounded text-xs font-semibold bg-emerald-950 text-emerald-400 border border-emerald-800">
              M14.05
            </span>
            <h1 className="text-xl font-bold text-slate-100 tracking-tight">
              Liquidity Reports Engine
            </h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Authoritative portfolio liquidity profiles, liquidation time & cost, illiquidity concentration, and stress comparison.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={onOpenArchive}
            className={`px-3 py-1.5 text-xs font-medium rounded border transition-colors ${
              isArchiveOpen
                ? 'bg-slate-800 text-indigo-300 border-indigo-700'
                : 'bg-slate-950 text-slate-300 border-slate-700 hover:bg-slate-800'
            }`}
          >
            📋 Version Lineage & Archive
          </button>

          <button
            onClick={onGenerate}
            disabled={isGenerating}
            className="px-4 py-1.5 text-xs font-semibold rounded bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50 flex items-center gap-2 shadow"
          >
            {isGenerating ? (
              <>
                <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                <span>Generating Report...</span>
              </>
            ) : (
              <span>⚡ Generate Liquidity Report</span>
            )}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mt-5 pt-4 border-t border-slate-800 text-xs">
        <div>
          <label className="block text-slate-400 font-medium mb-1">Portfolio</label>
          <select
            value={portfolioId}
            onChange={(e) => onPortfolioChange(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-emerald-500"
          >
            <option value="portfolio_001">Alpha Flagship (portfolio_001)</option>
            <option value="portfolio_002">US-India Quant (portfolio_002)</option>
            <option value="portfolio_003">HFT Arbitrage (portfolio_003)</option>
          </select>
        </div>

        <div>
          <label className="block text-slate-400 font-medium mb-1">As of Snapshot</label>
          <input
            type="date"
            value={asOfDate}
            onChange={(e) => onAsOfDateChange(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-emerald-500"
          />
        </div>

        <div>
          <label className="block text-slate-400 font-medium mb-1">Base Currency</label>
          <select
            value={currency}
            onChange={(e) => onCurrencyChange(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-emerald-500"
          >
            <option value="INR">INR (₹)</option>
            <option value="USD">USD ($)</option>
          </select>
        </div>

        <div>
          <label className="block text-slate-400 font-medium mb-1">Participation Rate</label>
          <select
            value={assumptions.participation_rate}
            onChange={(e) =>
              onAssumptionsChange({
                ...assumptions,
                participation_rate: parseFloat(e.target.value),
              })
            }
            className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-emerald-500"
          >
            <option value={0.05}>5% of ADV (Conservative)</option>
            <option value={0.10}>10% of ADV (Standard)</option>
            <option value={0.15}>15% of ADV (Aggressive)</option>
            <option value={0.20}>20% of ADV (Distress)</option>
          </select>
        </div>

        <div>
          <label className="block text-slate-400 font-medium mb-1">Target Reduction</label>
          <select
            value={assumptions.target_fraction}
            onChange={(e) =>
              onAssumptionsChange({
                ...assumptions,
                target_fraction: parseFloat(e.target.value),
              })
            }
            className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-emerald-500"
          >
            <option value={1.0}>100% Full Liquidation</option>
            <option value={0.5}>50% Position Reduction</option>
            <option value={0.25}>25% De-risking</option>
          </select>
        </div>
      </div>
    </div>
  );
};
