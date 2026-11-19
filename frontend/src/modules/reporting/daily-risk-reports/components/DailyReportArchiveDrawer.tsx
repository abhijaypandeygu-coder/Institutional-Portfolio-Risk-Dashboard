import React, { useState } from "react";
import {
  DailyReportRunResponse,
  DailyReportArtifactResponse,
  DailyReportIntegrityVerificationResponse,
} from "../../../../types/dailyReport";

interface DailyReportArchiveDrawerProps {
  runs: DailyReportRunResponse[];
  currentRunId?: string;
  onSelectRun: (runId: string) => void;
  onVerifyIntegrity: (artifactId: string) => Promise<DailyReportIntegrityVerificationResponse | null>;
  onDownloadArtifact: (artifactId: string, fileName: string) => void;
}

export const DailyReportArchiveDrawer: React.FC<DailyReportArchiveDrawerProps> = ({
  runs,
  currentRunId,
  onSelectRun,
  onVerifyIntegrity,
  onDownloadArtifact,
}) => {
  const [verificationResult, setVerificationResult] = useState<DailyReportIntegrityVerificationResponse | null>(null);
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
          Immutable Daily Report Archive &amp; Cryptographic Evidence
        </h2>
        <p className="text-xs text-muted">
          Audit-grade version lineage, verifiable artifact hashes, and multi-format exports (PDF, HTML, CSV)
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
              {verificationResult.is_valid ? "✓ SHA-256 INTEGRITY VERIFIED (AUTHENTIC)" : "✗ INTEGRITY MISMATCH DETECTED"}
            </span>
            <button
              onClick={() => setVerificationResult(null)}
              className="text-muted hover:text-secondary"
            >
              ✕
            </button>
          </div>
          <div className="text-[11px] break-all">
            Stored: {verificationResult.stored_sha256}
          </div>
          <div className="text-[11px] break-all">
            Computed: {verificationResult.computed_sha256}
          </div>
        </div>
      )}

      <div className="space-y-4">
        {runs.map((r) => {
          const isSelected = r.run_id === currentRunId;
          return (
            <div
              key={r.run_id}
              className={`p-4 rounded border transition-colors ${
                isSelected
                  ? "bg-subtle/80 border-cyan-500/60 shadow-md"
                  : "bg-canvas/60 border-line hover:border-line-strong"
              }`}
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-line/80 pb-2 mb-3">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => onSelectRun(r.run_id)}
                    className="font-sans text-xs font-bold text-brand hover:underline"
                  >
                    {r.run_id}
                  </button>
                  <span className="px-1.5 py-0.5 text-[10px] font-sans rounded bg-subtle text-secondary border border-line-strong">
                    v{r.version_number}
                  </span>
                  <span className="text-xs text-muted font-sans">
                    {r.report_date}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-xs font-sans">
                  <span className="text-muted">NAV:</span>
                  <span className="text-secondary font-semibold">
                    {r.nav ? `$${r.nav.toLocaleString()}` : "N/A"}
                  </span>
                  <span className="text-muted">| Control:</span>
                  <span className={r.critical_breaches_count > 0 ? "text-negative font-bold" : "text-positive"}>
                    {r.overall_control_status}
                  </span>
                </div>
              </div>

              {/* Artifacts for this run */}
              <div className="space-y-2">
                <span className="text-[11px] font-sans uppercase text-muted block">
                  Rendered Artifacts &amp; Cryptographic Manifest:
                </span>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                  {r.artifacts.map((art: DailyReportArtifactResponse) => (
                    <div
                      key={art.artifact_id}
                      className="bg-surface/90 p-2.5 rounded border border-line text-xs flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-sans font-semibold text-secondary">
                            {art.artifact_type}
                          </span>
                          <span className="text-[10px] font-sans text-muted">
                            {(art.file_size_bytes / 1024).toFixed(1)} KB
                          </span>
                        </div>
                        <p className="text-[11px] font-sans text-muted truncate" title={art.file_name}>
                          {art.file_name}
                        </p>
                        <p className="text-[9px] font-sans text-secondary truncate mt-1" title={art.content_sha256}>
                          SHA256: {art.content_sha256}
                        </p>
                      </div>

                      <div className="flex items-center gap-2 mt-3 pt-2 border-t border-line/80">
                        <button
                          onClick={() => onDownloadArtifact(art.artifact_id, art.file_name)}
                          className="flex-1 px-2 py-1 text-[11px] font-semibold bg-cyan-700/80 hover:bg-brand-hover text-white rounded transition-colors"
                        >
                          Download
                        </button>
                        <button
                          onClick={() => handleVerify(art.artifact_id)}
                          disabled={verifyingId === art.artifact_id}
                          className="px-2 py-1 text-[11px] font-sans bg-subtle hover:bg-hover text-secondary rounded border border-line-strong transition-colors"
                        >
                          {verifyingId === art.artifact_id ? "Verifying..." : "Verify"}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
