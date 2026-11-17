import React, { useState } from "react";
import {
  PerformanceReportRunResponse,
  PerformanceArtifactSchema,
  PerformanceIntegrityVerificationResponse,
} from "../../../types/performanceReport";

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
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 shadow-lg">
      <div className="border-b border-slate-800 pb-3 mb-4">
        <h2 className="text-sm font-semibold text-slate-200">
          Performance Report Archive &amp; Audit Trail
        </h2>
        <p className="text-xs text-slate-500">
          Historical report run lineage, non-destructive recalculations, and verifiable cryptographic SHA-256 digests
        </p>
      </div>

      {verificationResult && (
        <div className={`p-3 mb-4 rounded border text-xs font-mono ${
          verificationResult.is_valid
            ? "bg-emerald-950/60 border-emerald-800 text-emerald-300"
            : "bg-rose-950/60 border-rose-800 text-rose-300"
        }`}>
          <div className="flex items-center justify-between mb-1">
            <span className="font-bold">
              {verificationResult.is_valid ? "✓ SHA-256 INTEGRITY CERTIFIED (AUTHENTIC)" : "✗ INTEGRITY MISMATCH DETECTED"}
            </span>
            <button
              onClick={() => setVerificationResult(null)}
              className="text-slate-400 hover:text-slate-200"
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
                  ? "bg-slate-800/80 border-cyan-500/60 shadow-md"
                  : "bg-slate-950/60 border-slate-800 hover:border-slate-700"
              }`}
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-2 mb-3">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => onSelectRun(r.id)}
                    className="font-mono text-xs font-bold text-cyan-400 hover:underline"
                  >
                    {r.id}
                  </button>
                  <span className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-slate-800 text-slate-300 border border-slate-700">
                    v{r.report_version}
                  </span>
                  <span className="text-xs text-slate-400 font-mono">
                    {r.reporting_start_date} → {r.reporting_end_date}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-xs font-mono">
                  <span className="text-slate-500">Cum Ret:</span>
                  <span className="text-emerald-400 font-semibold">{cumPct}</span>
                  <span className="text-slate-500">| P&amp;L:</span>
                  <span className="text-slate-200 font-semibold">{pnlFmt}</span>
                </div>
              </div>

              {/* Artifacts */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                {r.artifacts.map((art: PerformanceArtifactSchema) => (
                  <div
                    key={art.id}
                    className="bg-slate-900/90 p-2.5 rounded border border-slate-800 text-xs flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-mono font-semibold text-slate-200">{art.artifact_type}</span>
                        <span className="text-[10px] font-mono text-slate-500">
                          {(art.file_size / 1024).toFixed(1)} KB
                        </span>
                      </div>
                      <p className="text-[11px] font-mono text-slate-400 truncate" title={art.storage_reference}>
                        {art.storage_reference.split("/").pop()}
                      </p>
                      <p className="text-[9px] font-mono text-slate-600 truncate mt-1">
                        SHA256: {art.content_hash}
                      </p>
                    </div>

                    <div className="flex items-center gap-2 mt-3 pt-2 border-t border-slate-800/80">
                      <button
                        onClick={() => onDownloadArtifact(art.id, art.storage_reference.split("/").pop() || "report")}
                        className="flex-1 px-2 py-1 text-[11px] font-semibold bg-cyan-700/80 hover:bg-cyan-600 text-white rounded transition-colors"
                      >
                        Download
                      </button>
                      <button
                        onClick={() => handleVerify(art.id)}
                        disabled={verifyingId === art.id}
                        className="px-2 py-1 text-[11px] font-mono bg-slate-800 hover:bg-slate-700 text-slate-300 rounded border border-slate-700 transition-colors"
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
