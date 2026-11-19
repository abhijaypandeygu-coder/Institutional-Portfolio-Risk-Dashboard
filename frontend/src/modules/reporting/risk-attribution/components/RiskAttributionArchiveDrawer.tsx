import React, { useState } from 'react';
import {
  X,
  Download,
  CheckCircle2,
  AlertTriangle,
  FileText,
  FileSpreadsheet,
  Globe,
  Clock,
  ShieldCheck,
} from 'lucide-react';
import {
  RiskAttributionRunSummary,
  AttributionArtifact,
} from '../../../../types/riskAttribution';

interface RiskAttributionArchiveDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  runs: RiskAttributionRunSummary[];
  onSelectRun: (runId: string) => void;
  activeRunId?: string;
  artifacts?: AttributionArtifact[];
  onVerifyIntegrity: () => void;
  isVerifying: boolean;
  verificationResult?: {
    is_valid: boolean;
    artifacts: any[];
  } | null;
}

export const RiskAttributionArchiveDrawer: React.FC<RiskAttributionArchiveDrawerProps> = ({
  isOpen,
  onClose,
  runs,
  onSelectRun,
  activeRunId,
  artifacts = [],
  onVerifyIntegrity,
  isVerifying,
  verificationResult,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-canvas/80  flex justify-end">
      <div className="w-full max-w-xl bg-surface border-l border-line h-full flex flex-col shadow-2xl">
        {/* Header */}
        <div className="p-5 border-b border-line flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-ink">
              Risk Attribution Archive & Integrity
            </h2>
            <p className="text-xs text-muted mt-0.5">
              Historical version lineage, signed downloads, and cryptographic verification
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-muted hover:text-secondary hover:bg-subtle transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          {/* Artifacts Download Section */}
          <div>
            <h3 className="text-xs font-semibold text-secondary uppercase  mb-3">
              Signed Report Artifacts
            </h3>
            <div className="grid grid-cols-3 gap-3">
              {['PDF', 'HTML', 'CSV'].map((format) => {
                const art = artifacts.find((a) => a.artifact_type === format);
                return (
                  <a
                    key={format}
                    href={
                      activeRunId
                        ? `/api/v1/reports/risk-attribution/runs/${activeRunId}/artifacts/${format}`
                        : '#'
                    }
                    download
                    className={`flex flex-col items-center justify-center p-3.5 rounded-xl border transition-opacity text-center ${
                      art
                        ? 'bg-canvas border-line hover:border-indigo-500 hover:bg-subtle/60 text-secondary'
                        : 'bg-canvas/40 border-line/40 text-secondary pointer-events-none'
                    }`}
                  >
                    {format === 'PDF' && <FileText className="w-5 h-5 mb-1.5 text-negative" />}
                    {format === 'HTML' && <Globe className="w-5 h-5 mb-1.5 text-brand" />}
                    {format === 'CSV' && (
                      <FileSpreadsheet className="w-5 h-5 mb-1.5 text-positive" />
                    )}
                    <span className="text-xs font-medium">{format} Export</span>
                    {art && (
                      <span className="text-[10px] text-muted font-sans mt-1">
                        {(art.file_size_bytes / 1024).toFixed(1)} KB
                      </span>
                    )}
                  </a>
                );
              })}
            </div>
          </div>

          {/* Cryptographic SHA-256 Verification */}
          <div className="bg-canvas border border-line rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-positive" />
                <span className="text-xs font-bold text-secondary">
                  Cryptographic Integrity (SHA-256)
                </span>
              </div>
              <button
                onClick={onVerifyIntegrity}
                disabled={isVerifying || !activeRunId}
                className="px-3 py-1 rounded bg-brand hover:bg-brand-hover text-white text-xs font-medium transition-colors disabled:opacity-50"
              >
                {isVerifying ? 'Verifying...' : 'Verify Hashes'}
              </button>
            </div>

            {verificationResult && (
              <div
                className={`mt-2 p-3 rounded-lg border text-xs flex items-start gap-2.5 ${
                  verificationResult.is_valid
                    ? 'bg-brand/10 border-emerald-500/20 text-positive'
                    : 'bg-rose-500/10 border-rose-500/20 text-negative'
                }`}
              >
                {verificationResult.is_valid ? (
                  <CheckCircle2 className="w-4 h-4 text-positive mt-0.5" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-negative mt-0.5" />
                )}
                <div>
                  <div className="font-semibold">
                    {verificationResult.is_valid
                      ? 'All Artifact Checksums Validated'
                      : 'Integrity Check Failed'}
                  </div>
                  <div className="text-[11px] text-muted mt-1">
                    SHA-256 signatures match database cryptographic ledger.
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Version Lineage History */}
          <div>
            <h3 className="text-xs font-semibold text-secondary uppercase  mb-3">
              Historical Run Versions
            </h3>
            <div className="space-y-2">
              {runs.map((r) => {
                const isActive = r.id === activeRunId;
                return (
                  <div
                    key={r.id}
                    onClick={() => onSelectRun(r.id)}
                    className={`p-3.5 rounded-lg border cursor-pointer transition-opacity ${
                      isActive
                        ? 'bg-brand/10 border-indigo-500 text-ink'
                        : 'bg-canvas border-line hover:border-line-strong text-secondary'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold font-sans">
                          v{r.report_version}
                        </span>
                        <span className="text-xs text-secondary font-sans">
                          {r.reporting_date}
                        </span>
                      </div>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-subtle text-muted font-sans">
                        {r.reconciliation_status}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-muted font-sans">
                      <span>{r.risk_measure}</span>
                      <span>
                        {r.authoritative_risk_value !== undefined
                          ? `${(r.authoritative_risk_value * 100).toFixed(2)}%`
                          : 'N/A'}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
