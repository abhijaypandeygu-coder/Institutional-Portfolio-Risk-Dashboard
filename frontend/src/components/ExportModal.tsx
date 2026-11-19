import { ModalSurface } from './ModalSurface';
import React, { useState } from 'react';
import { 
  X, 
  Download, 
  FileSpreadsheet, 
  FileText, 
  Check, 
  Loader2, 
  ShieldAlert, 
  Calendar,
  Layers,
  ArrowRight
} from 'lucide-react';

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedPortfolio: string;
  portfolioList: Array<{ portfolio_id: string; portfolio_name: string }>;
  dateRangeLabel: string;
}

interface DatasetOption {
  id: string;
  name: string;
  category: string;
  description: string;
  module: string;
}

const DATASETS: DatasetOption[] = [
  {
    id: 'daily_risk_positions',
    name: 'Position Risk & Factor Valuations',
    category: 'Risk Reporting',
    description: 'Position-level risk valuations, sensitivities, and factor betas from daily reports.',
    module: 'M14',
  },
  {
    id: 'portfolio_performance_series',
    name: 'Historical Performance & PnL Series',
    category: 'Performance',
    description: 'Daily TWR/MWR return series, NAV trajectory, benchmark returns, and cash flows.',
    module: 'M14',
  },
  {
    id: 'liquidity_positions_and_costs',
    name: 'Liquidity & Order-Book Exit Costs',
    category: 'Microstructure',
    description: 'Bid-ask spreads, depth walk slippages, and liquidation time estimates.',
    module: 'M14',
  },
  {
    id: 'stress_testing_results',
    name: 'Stress Testing & Monte Carlo Scenarios',
    category: 'Scenario Analysis',
    description: 'Historical shock impacts, factor spillovers, and empirical tail distributions.',
    module: 'M14',
  },
  {
    id: 'risk_limits_and_breaches',
    name: 'Risk Limits & Threshold Breaches',
    category: 'Governance',
    description: 'Active hard and soft limit utilization, warning thresholds, and evaluations.',
    module: 'M14',
  },
];

export const ExportModal: React.FC<ExportModalProps> = ({
  isOpen,
  onClose,
  selectedPortfolio,
  portfolioList,
  dateRangeLabel,
}) => {
  const [selectedDataset, setSelectedDataset] = useState<string>('daily_risk_positions');
  const [targetPortfolio, setTargetPortfolio] = useState<string>(selectedPortfolio || 'PORT_STR_a74557');
  const [format, setFormat] = useState<'CSV' | 'XLSX' | 'PDF'>('CSV');
  const [includeMetadata, setIncludeMetadata] = useState<boolean>(true);
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successInfo, setSuccessInfo] = useState<{ code: string; count: number } | null>(null);

  if (!isOpen) return null;

  const currentDataset = DATASETS.find((d) => d.id === selectedDataset) || DATASETS[0];

  const handleTriggerExport = async () => {
    setIsExporting(true);
    setErrorMsg(null);
    setSuccessInfo(null);

    try {
      const payload = {
        source: {
          module: currentDataset.module,
          dataset_id: currentDataset.id,
        },
        formats: [format],
        scope: {
          portfolio_id: targetPortfolio,
        },
        options: {
          timezone: 'UTC',
          include_methodology: includeMetadata,
          include_metadata: includeMetadata,
          include_data_quality: true,
        },
      };

      const res = await fetch('/api/v1/exports', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData?.error?.message || `Export failed with status ${res.status}`);
      }

      const jobData = await res.json();
      const exportId = jobData.id;
      const artifact = jobData.artifacts?.[0];

      if (artifact?.artifact_id) {
        // Direct download trigger
        const downloadUrl = `/api/v1/exports/${exportId}/download/${artifact.artifact_id}`;
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = artifact.file_name || `export-${currentDataset.id}.${format.toLowerCase()}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);

        setSuccessInfo({
          code: jobData.export_code,
          count: jobData.total_records ?? 0,
        });
      } else {
        setSuccessInfo({
          code: jobData.export_code,
          count: jobData.total_records ?? 0,
        });
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Export execution error');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <ModalSurface open={isOpen} onClose={onClose} label="Export portfolio data">
      <div 
        className="w-full max-w-xl bg-surface border border-line rounded-xl shadow-none flex flex-col overflow-hidden text-ink"

      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-line/80 bg-surface/60">
          <div className="flex items-center gap-2.5">
            <div className="size-8 rounded-lg bg-brand/10 border border-emerald-500/20 flex items-center justify-center text-positive">
              <Download className="size-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-ink">Export portfolio</h2>
              <p className="text-xs text-muted">Choose a dataset and file format.</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close export portfolio data"
            className="size-8 rounded-lg flex items-center justify-center text-muted hover:text-secondary hover:bg-subtle transition-colors"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Form Body */}
        <div className="p-6 space-y-5 overflow-y-auto max-h-[60dvh]">
          {/* Target Portfolio & Scope */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            <div>
              <label htmlFor="exportmodal-field-1" className="block text-xs font-semibold text-secondary mb-1.5">
                Target Portfolio
              </label>
              <select id="exportmodal-field-1"
                value={targetPortfolio}
                onChange={(e) => setTargetPortfolio(e.target.value)}
                className="w-full bg-canvas border border-line rounded-xl px-3 py-2 text-xs font-medium text-secondary focus:outline-none focus:border-line-strong transition-colors"
              >
                {portfolioList.map((p) => (
                  <option key={p.portfolio_id} value={p.portfolio_id}>
                    {p.portfolio_name} ({p.portfolio_id})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-secondary mb-1.5">
                Evaluation Window
              </label>
              <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-canvas border border-line text-xs text-secondary">
                <Calendar className="size-3.5 text-muted shrink-0" />
                <span className="truncate">{dateRangeLabel}</span>
              </div>
            </div>
          </div>

          {/* Dataset Selection */}
          <div>
            <label className="block text-xs font-semibold text-secondary mb-2">
              Select Dataset
            </label>
            <div className="space-y-2">
              {DATASETS.map((ds) => {
                const isSelected = selectedDataset === ds.id;
                return (
                  <button type="button" aria-pressed={isSelected}
                    key={ds.id}
                    onClick={() => setSelectedDataset(ds.id)}
                    className={`w-full p-3 rounded-xl border text-left cursor-pointer transition-opacity ${
                      isSelected
                        ? 'bg-subtle/80 border-line-strong text-ink ring-1 ring-slate-600/50'
                        : 'bg-canvas/60 border-line/80 text-secondary hover:border-line-strong hover:bg-subtle/40'
                    }`}
                  >
                    <span className="flex items-center justify-between">
                      <span className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-ink">{ds.name}</span>
                        <span className="text-[10px] font-sans uppercase px-1.5 py-0.5 rounded bg-subtle text-muted border border-line-strong/50">
                          {ds.module}
                        </span>
                      </span>
                      <span className="text-[10px] text-muted uppercase font-medium">{ds.category}</span>
                    </span>
                    <span className="block text-[11px] text-muted mt-1 line-clamp-1">{ds.description}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Format Choice */}
          <div>
            <label className="block text-xs font-semibold text-secondary mb-2">
              Export Format
            </label>
            <div className="grid grid-cols-3 gap-2.5">
              {(['CSV', 'XLSX', 'PDF'] as const).map((fmt) => {
                const isSelected = format === fmt;
                return (
                  <button
                    key={fmt}
                    aria-pressed={isSelected}
                    type="button"
                    onClick={() => setFormat(fmt)}
                    className={`flex items-center justify-center gap-2 py-2 px-3 rounded-xl border text-xs font-medium transition-opacity ${
                      isSelected
                        ? 'bg-brand/10 border-emerald-500/40 text-positive ring-1 ring-emerald-500/30'
                        : 'bg-canvas border-line text-muted hover:border-line-strong hover:text-secondary'
                    }`}
                  >
                    {fmt === 'CSV' && <FileSpreadsheet className="size-3.5" />}
                    {fmt === 'XLSX' && <FileSpreadsheet className="size-3.5" />}
                    {fmt === 'PDF' && <FileText className="size-3.5" />}
                    <span>{fmt}</span>
                    {isSelected && <Check className="size-3 stroke-[2.5]" />}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Options */}
          <div className="flex items-center justify-between p-3 rounded-xl bg-canvas/60 border border-line/80">
            <div>
              <div className="text-xs font-medium text-secondary">Include Audit Manifest & Metadata Header</div>
              <div className="text-[11px] text-muted">Appends SHA-256 hash, timestamps, and governance notes</div>
            </div>
            <input
              type="checkbox"
              aria-label="Include audit manifest and metadata header"
              checked={includeMetadata}
              onChange={(e) => setIncludeMetadata(e.target.checked)}
              className="size-4 accent-emerald-500 rounded bg-subtle border-line-strong cursor-pointer"
            />
          </div>

          {/* Error Message */}
          {errorMsg && (
            <div className="flex items-center gap-2 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-negative text-xs">
              <ShieldAlert className="size-4 shrink-0" />
              <span role="alert">{errorMsg}</span>
            </div>
          )}

          {/* Success Info */}
          {successInfo && (
            <div className="flex items-center gap-2.5 p-3 rounded-xl bg-brand/10 border border-emerald-500/20 text-positive text-xs">
              <Check className="size-4 shrink-0 text-positive" />
              <div>
                <span className="font-semibold">Export Job Completed ({successInfo.code})</span>
                <span className="text-muted ml-1.5">• {successInfo.count} rows generated & downloaded</span>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-line/80 bg-surface/60 flex items-center justify-between">
          <span className="text-[11px] text-muted font-sans">Ready to export</span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isExporting}
              className="px-3.5 py-1.5 rounded-xl border border-line text-xs font-medium text-muted hover:text-secondary hover:border-line-strong transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleTriggerExport}
              disabled={isExporting}
              className="flex items-center gap-2 px-4 py-1.5 rounded-xl bg-brand hover:bg-brand-hover text-white text-xs font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isExporting ? (
                <>
                  <Loader2 className="size-3.5 " />
                  <span>Processing...</span>
                </>
              ) : (
                <>
                  <Download className="size-3.5" />
                  <span>Download Export</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </ModalSurface>
  );
};
