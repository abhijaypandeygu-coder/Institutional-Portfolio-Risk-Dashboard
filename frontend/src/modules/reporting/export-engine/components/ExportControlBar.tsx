import React from 'react';
import { DatasetRegistryItem, ExportFormat } from '../../../../types/exportEngine';

interface Props {
  datasets: DatasetRegistryItem[];
  selectedDatasetCode: string;
  onSelectDataset: (code: string) => void;
  selectedFormats: ExportFormat[];
  onToggleFormat: (fmt: ExportFormat) => void;
  portfolioId: string;
  onPortfolioChange: (pid: string) => void;
  reportingCurrency: string;
  onCurrencyChange: (curr: string) => void;
  isExecuting: boolean;
  onExecuteExport: () => void;
}

export const ExportControlBar: React.FC<Props> = ({
  datasets,
  selectedDatasetCode,
  onSelectDataset,
  selectedFormats,
  onToggleFormat,
  portfolioId,
  onPortfolioChange,
  reportingCurrency,
  onCurrencyChange,
  isExecuting,
  onExecuteExport,
}) => {
  const currentDataset = datasets.find((d) => d.dataset_code === selectedDatasetCode);

  return (
    <div className="bg-surface border border-line rounded-xl p-5 mb-6 text-ink shadow-xl">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line pb-4 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded text-xs font-semibold bg-brand/20 text-positive border border-emerald-500/30">
              M14.06 CENTRALIZED PLATFORM
            </span>
            <span className="text-xs text-muted">Institutional Multi-Format Export Infrastructure</span>
          </div>
          <h2 className="text-xl font-bold  text-ink mt-1">Export Center</h2>
        </div>

        <button
          onClick={onExecuteExport}
          disabled={isExecuting || selectedFormats.length === 0}
          className={`px-5 py-2.5 rounded-lg text-sm font-semibold  transition-opacity shadow-md flex items-center gap-2 ${
            isExecuting || selectedFormats.length === 0
              ? 'bg-subtle text-muted cursor-not-allowed'
              : 'bg-brand hover:bg-brand-hover text-white shadow-emerald-950/40 hover:shadow-emerald-900/50'
          }`}
        >
          {isExecuting ? (
            <>
              <svg className="animate-spin h-4 w-4 text-ink" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              <span>Generating Artifacts...</span>
            </>
          ) : (
            <>
              <span>Execute Export</span>
              <span className="text-xs px-1.5 py-0.5 bg-emerald-700/60 rounded">
                {selectedFormats.join(' + ')}
              </span>
            </>
          )}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Dataset Selection */}
        <div>
          <label className="block text-xs font-medium text-muted mb-1.5 uppercase ">
            Registered Dataset
          </label>
          <select
            value={selectedDatasetCode}
            onChange={(e) => onSelectDataset(e.target.value)}
            className="w-full bg-canvas border border-line-strong rounded-lg px-3 py-2 text-sm text-secondary focus:outline-none focus:border-emerald-500"
          >
            {datasets.map((d) => (
              <option key={d.dataset_code} value={d.dataset_code}>
                [{d.source_module}] {d.dataset_name}
              </option>
            ))}
          </select>
        </div>

        {/* Target Portfolio */}
        <div>
          <label className="block text-xs font-medium text-muted mb-1.5 uppercase ">
            Portfolio Scope
          </label>
          <select
            value={portfolioId}
            onChange={(e) => onPortfolioChange(e.target.value)}
            className="w-full bg-canvas border border-line-strong rounded-lg px-3 py-2 text-sm text-secondary focus:outline-none focus:border-emerald-500"
          >
            <option value="port_liq_001">PORT_LIQ_001 (Institutional Growth)</option>
            <option value="port_alpha_india">PORT_ALPHA_INDIA (NSE/BSE Core)</option>
            <option value="port_us_tech">PORT_US_TECH (NASDAQ 100 Long/Short)</option>
            <option value="*">All Authorized Portfolios</option>
          </select>
        </div>

        {/* Reporting Currency */}
        <div>
          <label className="block text-xs font-medium text-muted mb-1.5 uppercase ">
            Currency Presentation
          </label>
          <select
            value={reportingCurrency}
            onChange={(e) => onCurrencyChange(e.target.value)}
            className="w-full bg-canvas border border-line-strong rounded-lg px-3 py-2 text-sm text-secondary focus:outline-none focus:border-emerald-500"
          >
            <option value="INR">INR (₹ Indian Rupee)</option>
            <option value="USD">USD ($ United States Dollar)</option>
          </select>
        </div>

        {/* Format Selector Pills */}
        <div>
          <label className="block text-xs font-medium text-muted mb-1.5 uppercase ">
            Output Formats
          </label>
          <div className="flex gap-2">
            {(['CSV', 'XLSX', 'PDF'] as ExportFormat[]).map((fmt) => {
              const isSupported = currentDataset?.supported_formats.includes(fmt) ?? true;
              const isSelected = selectedFormats.includes(fmt);
              return (
                <button
                  key={fmt}
                  type="button"
                  disabled={!isSupported}
                  onClick={() => onToggleFormat(fmt)}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-bold border transition-opacity ${
                    !isSupported
                      ? 'bg-canvas/40 text-secondary border-line cursor-not-allowed'
                      : isSelected
                      ? 'bg-brand/20 text-positive border-emerald-500/50 shadow-inner'
                      : 'bg-canvas text-muted border-line hover:border-line-strong'
                  }`}
                >
                  {fmt}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
