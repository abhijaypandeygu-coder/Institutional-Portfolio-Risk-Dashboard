import React, { useState } from 'react';
import {
  LiquidityReportSummaryResponse,
  LiquidityArtifact,
  LiquidityArtifactType,
} from '../../../../types/liquidityReport';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  reports: LiquidityReportSummaryResponse[];
  currentReportId: string;
  onSelectReport: (id: string) => void;
  artifacts: LiquidityArtifact[];
  onVerifyHash: (artifactType: LiquidityArtifactType) => void;
  verifiedStatus: Record<string, boolean>;
}

export const LiquidityReportArchiveDrawer: React.FC<Props> = ({
  isOpen,
  onClose,
  reports,
  currentReportId,
  onSelectReport,
  artifacts,
  onVerifyHash,
  verifiedStatus,
}) => {
  const [selectedFormat, setSelectedFormat] = useState<LiquidityArtifactType>('CSV');

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 w-96 bg-surface border-l border-line shadow-2xl p-5 z-50 overflow-y-auto flex flex-col justify-between">
      <div>
        <div className="flex justify-between items-center pb-3 border-b border-line mb-4">
          <div className="flex items-center gap-2">
            <span className="text-base font-bold text-ink">Report Lineage & Archive</span>
            <span className="text-xs px-2 py-0.5 rounded bg-subtle text-muted font-sans">
              {reports.length}
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-muted hover:text-secondary text-lg leading-none p-1"
          >
            &times;
          </button>
        </div>

        {/* Artifact Export & SHA-256 Verification Section */}
        <div className="bg-canvas p-4 rounded border border-line mb-5">
          <h3 className="text-xs font-semibold text-secondary uppercase  mb-2 flex items-center justify-between">
            <span>Finalized Artifacts</span>
            <span className="text-[10px] text-positive font-sans">SHA-256 Verified</span>
          </h3>

          <div className="space-y-2 mb-3">
            {artifacts.map((art) => (
              <div key={art.artifact_type} className="flex justify-between items-center text-xs p-1.5 rounded bg-surface border border-line">
                <span className="font-semibold text-secondary">{art.artifact_type}</span>
                <span className="text-[10px] text-muted font-sans">
                  {art.file_hash.substring(0, 12)}...
                </span>
                <button
                  onClick={() => onVerifyHash(art.artifact_type)}
                  className="px-2 py-0.5 rounded text-[10px] bg-subtle hover:bg-hover text-brand border border-brand/20"
                >
                  {verifiedStatus[art.artifact_type] ? '✓ Valid' : 'Verify'}
                </button>
              </div>
            ))}
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => {
                alert(`Exporting ${selectedFormat} artifact for current report.`);
              }}
              className="flex-1 py-1.5 bg-brand hover:bg-brand-hover text-white font-semibold rounded text-xs transition-colors"
            >
              Download {selectedFormat}
            </button>
            <select
              value={selectedFormat}
              onChange={(e) => setSelectedFormat(e.target.value as LiquidityArtifactType)}
              className="bg-surface border border-line-strong rounded px-2 text-xs text-secondary"
            >
              <option value="CSV">CSV</option>
              <option value="HTML">HTML</option>
              <option value="PDF">PDF</option>
            </select>
          </div>
        </div>

        {/* Historical Version Lineage */}
        <h3 className="text-xs font-semibold text-muted uppercase  mb-3">
          Historical Report Versions
        </h3>
        <div className="space-y-2">
          {reports.map((r) => (
            <div
              key={r.report_id}
              onClick={() => onSelectReport(r.report_id)}
              className={`p-3 rounded border cursor-pointer transition-colors ${
                r.report_id === currentReportId
                  ? 'bg-positive-soft/40 border-positive/20'
                  : 'bg-canvas border-line hover:bg-subtle/60'
              }`}
            >
              <div className="flex justify-between items-start mb-1">
                <span className="text-xs font-bold text-secondary">{r.report_code}</span>
                <span className="text-[10px] font-sans px-1.5 py-0.5 rounded bg-subtle text-secondary">
                  v{r.report_version}
                </span>
              </div>
              <div className="text-[11px] text-muted flex justify-between items-center">
                <span>{new Date(r.as_of_timestamp).toLocaleDateString()}</span>
                <span
                  className={`text-[10px] font-semibold ${
                    r.reconciliation_status === 'RECONCILED' ? 'text-positive' : 'text-warning'
                  }`}
                >
                  {r.reconciliation_status}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="pt-4 border-t border-line text-[10px] text-muted text-center">
        Immutable Audit & Version Lineage Engine | M14.05
      </div>
    </div>
  );
};
