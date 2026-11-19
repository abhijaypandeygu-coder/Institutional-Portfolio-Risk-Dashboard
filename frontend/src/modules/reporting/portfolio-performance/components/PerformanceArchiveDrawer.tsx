import React, { useState } from "react";
import {
  PerformanceReportRunResponse,
  PerformanceArtifactSchema,
  PerformanceIntegrityVerificationResponse,
} from "../../../../types/performanceReport";

interface PerformanceArchiveDrawerProps {
  runs: PerformanceReportRunResponse[];
  currentRunId?: string;
  onSelectRun: (runId: string) => void;
  onVerifyIntegrity: (artifactId: string) => Promise<PerformanceIntegrityVerificationResponse | null>;
  onDownloadArtifact: (artifactId: string, fileName: string) => void;
}

export const PerformanceArchiveDrawer: React.FC<PerformanceArchiveDrawerProps> = ({
  runs,
  currentRunId,
  onSelectRun,
  onVerifyIntegrity,
  onDownloadArtifact,
}) => {
  const [verificationResult, setVerificationResult] = useState<PerformanceIntegrityVerificationResponse | null>(null);
  const [verifyingId, setVerifyingId] = useState<string | null>(null);

  const handleVerify = async (artifactId: string) => {
    setVerifyingId(artifactId);
    try {
      const res = await onVerifyIntegrity(artifactId);
      setVerificationResult(res);
    } finally {
      setVerifyingId(null);
    }
  };

  return (
    <div className="bg-surface border border-line rounded-lg p-5 shadow-lg">
      <div className="border-b border-line pb-3 mb-4">
        <h2 className="text-sm font-semibold text-secondary">
          Performance Report Archive &amp; Audit Trail
        </h2>
        <p className="text-xs text-muted">
          Historical report run lineage, non-destructive recalculations, and verifiable cryptographic SHA-256 digests
        </p>
      </div>

      {verificationResult && (
        <div className={`p-3 mb-4 rounded border text-xs font-sans ${
          verificationResult.is_valid
            ? "bg-positive-soft/60 border-positive/20 text-positive"
            : "bg-negative-soft/60 border-negative/20 text-negative"
        }`}>
          <div className="flex items-center justify-between mb-1">
            <span className="font-bold">
              {verificationResult.is_valid ? "✓ SHA-256 INTEGRITY CERTIFIED (AUTHENTIC)" : "✗ INTEGRITY MISMATCH DETECTED"}
            </span>
            <button
              onClick={() => setVerificationResult(null)}
              className="text-muted hover:text-secondary"
            >
              ✕
            </button>
          </div>
          <div className="text-[11px] break-all">Stored: {verificationResult.stored_sha256}</div>
          <div className="text-[11px] break-all">Computed: {verificationResult.computed_sha256}</div>
        </div>
      )}

      <div className="space-y-4">
        {runs.map((r) => {
          const isSelected = r.id === currentRunId;
          const cumPct = r.cumulative_return ? `${(r.cumulative_return * 100).toFixed(2)}%` : "N/A";
          const pnlFmt = r.total_pnl ? `$${r.total_pnl.toLocaleString()}` : "N/A";

          return (
            <div
              key={r.id}
              className={`p-4 rounded border transition-colors ${
                isSelected
                  ? "bg-subtle/80 border-cyan-500/60 shadow-md"
                  : "bg-canvas/60 border-line hover:border-line-strong"
              }`}
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-line/80 pb-2 mb-3">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => onSelectRun(r.id)}
                    className="font-sans text-xs font-bold text-brand hover:underline"
                  >
                    {r.id}
                  </button>
                  <span className="px-1.5 py-0.5 text-[10px] font-sans rounded bg-subtle text-secondary border border-line-strong">
                    v{r.report_version}
                  </span>
                  <span className="text-xs text-muted font-sans">
                    {r.reporting_start_date} → {r.reporting_end_date}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-xs font-sans">
                  <span className="text-muted">Cum Ret:</span>
                  <span className="text-positive font-semibold">{cumPct}</span>
                  <span className="text-muted">| P&amp;L:</span>
                  <span className="text-secondary font-semibold">{pnlFmt}</span>
                </div>
              </div>

              {/* Artifacts */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                {r.artifacts.map((art: PerformanceArtifactSchema) => (
                  <div
                    key={art.id}
                    className="bg-surface/90 p-2.5 rounded border border-line text-xs flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-sans font-semibold text-secondary">{art.artifact_type}</span>
                        <span className="text-[10px] font-sans text-muted">
                          {(art.file_size / 1024).toFixed(1)} KB
                        </span>
                      </div>
                      <p className="text-[11px] font-sans text-muted truncate" title={art.storage_reference}>
                        {art.storage_reference.split("/").pop()}
                      </p>
                      <p className="text-[9px] font-sans text-secondary truncate mt-1">
                        SHA256: {art.content_hash}
                      </p>
                    </div>

                    <div className="flex items-center gap-2 mt-3 pt-2 border-t border-line/80">
                      <button
                        onClick={() => onDownloadArtifact(art.id, art.storage_reference.split("/").pop() || "report")}
                        className="flex-1 px-2 py-1 text-[11px] font-semibold bg-cyan-700/80 hover:bg-brand-hover text-white rounded transition-colors"
                      >
                        Download
                      </button>
                      <button
                        onClick={() => handleVerify(art.id)}
                        disabled={verifyingId === art.id}
                        className="px-2 py-1 text-[11px] font-sans bg-subtle hover:bg-hover text-secondary rounded border border-line-strong transition-colors"
                      >
                        {verifyingId === art.id ? "Verifying..." : "Verify"}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
