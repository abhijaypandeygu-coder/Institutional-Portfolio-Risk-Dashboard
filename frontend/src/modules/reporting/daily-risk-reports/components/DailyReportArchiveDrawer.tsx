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
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 shadow-lg">
      <div className="border-b border-slate-800 pb-3 mb-4">
        <h2 className="text-sm font-semibold text-slate-200">
          Immutable Daily Report Archive &amp; Cryptographic Evidence
        </h2>
        <p className="text-xs text-slate-500">
          Audit-grade version lineage, verifiable artifact hashes, and multi-format exports (PDF, HTML, CSV)
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
              {verificationResult.is_valid ? "✓ SHA-256 INTEGRITY VERIFIED (AUTHENTIC)" : "✗ INTEGRITY MISMATCH DETECTED"}
            </span>
            <button
              onClick={() => setVerificationResult(null)}
              className="text-slate-400 hover:text-slate-200"
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
                  ? "bg-slate-800/80 border-cyan-500/60 shadow-md"
                  : "bg-slate-950/60 border-slate-800 hover:border-slate-700"
              }`}
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-2 mb-3">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => onSelectRun(r.run_id)}
                    className="font-mono text-xs font-bold text-cyan-400 hover:underline"
                  >
                    {r.run_id}
                  </button>
                  <span className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-slate-800 text-slate-300 border border-slate-700">
                    v{r.version_number}
                  </span>
                  <span className="text-xs text-slate-400 font-mono">
                    {r.report_date}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-xs font-mono">
                  <span className="text-slate-500">NAV:</span>
                  <span className="text-slate-200 font-semibold">
                    {r.nav ? `$${r.nav.toLocaleString()}` : "N/A"}
                  </span>
                  <span className="text-slate-500">| Control:</span>
                  <span className={r.critical_breaches_count > 0 ? "text-rose-400 font-bold" : "text-emerald-400"}>
                    {r.overall_control_status}
                  </span>
                </div>
              </div>

              {/* Artifacts for this run */}
              <div className="space-y-2">
                <span className="text-[11px] font-mono uppercase text-slate-500 block">
                  Rendered Artifacts &amp; Cryptographic Manifest:
                </span>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                  {r.artifacts.map((art: DailyReportArtifactResponse) => (
                    <div
                      key={art.artifact_id}
                      className="bg-slate-900/90 p-2.5 rounded border border-slate-800 text-xs flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-mono font-semibold text-slate-200">
                            {art.artifact_type}
                          </span>
                          <span className="text-[10px] font-mono text-slate-500">
                            {(art.file_size_bytes / 1024).toFixed(1)} KB
                          </span>
                        </div>
                        <p className="text-[11px] font-mono text-slate-400 truncate" title={art.file_name}>
                          {art.file_name}
                        </p>
                        <p className="text-[9px] font-mono text-slate-600 truncate mt-1" title={art.content_sha256}>
                          SHA256: {art.content_sha256}
                        </p>
                      </div>

                      <div className="flex items-center gap-2 mt-3 pt-2 border-t border-slate-800/80">
                        <button
                          onClick={() => onDownloadArtifact(art.artifact_id, art.file_name)}
                          className="flex-1 px-2 py-1 text-[11px] font-semibold bg-cyan-700/80 hover:bg-cyan-600 text-white rounded transition-colors"
                        >
                          Download
                        </button>
                        <button
                          onClick={() => handleVerify(art.artifact_id)}
                          disabled={verifyingId === art.artifact_id}
                          className="px-2 py-1 text-[11px] font-mono bg-slate-800 hover:bg-slate-700 text-slate-300 rounded border border-slate-700 transition-colors"
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
