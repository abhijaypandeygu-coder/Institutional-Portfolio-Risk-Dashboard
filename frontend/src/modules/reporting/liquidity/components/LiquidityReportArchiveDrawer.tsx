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
    <div className="fixed inset-y-0 right-0 w-96 bg-slate-900 border-l border-slate-800 shadow-2xl p-5 z-50 overflow-y-auto flex flex-col justify-between">
      <div>
        <div className="flex justify-between items-center pb-3 border-b border-slate-800 mb-4">
          <div className="flex items-center gap-2">
            <span className="text-base font-bold text-slate-100">Report Lineage & Archive</span>
            <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">
              {reports.length}
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 text-lg leading-none p-1"
          >
            &times;
          </button>
        </div>

        {/* Artifact Export & SHA-256 Verification Section */}
        <div className="bg-slate-950 p-4 rounded border border-slate-800 mb-5">
          <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wide mb-2 flex items-center justify-between">
            <span>Finalized Artifacts</span>
            <span className="text-[10px] text-emerald-400 font-mono">SHA-256 Verified</span>
          </h3>

          <div className="space-y-2 mb-3">
            {artifacts.map((art) => (
              <div key={art.artifact_type} className="flex justify-between items-center text-xs p-1.5 rounded bg-slate-900 border border-slate-800">
                <span className="font-semibold text-slate-200">{art.artifact_type}</span>
                <span className="text-[10px] text-slate-500 font-mono">
                  {art.file_hash.substring(0, 12)}...
                </span>
                <button
                  onClick={() => onVerifyHash(art.artifact_type)}
                  className="px-2 py-0.5 rounded text-[10px] bg-slate-800 hover:bg-slate-700 text-indigo-300 border border-indigo-900"
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
              className="flex-1 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded text-xs transition-colors"
            >
              Download {selectedFormat}
            </button>
            <select
              value={selectedFormat}
              onChange={(e) => setSelectedFormat(e.target.value as LiquidityArtifactType)}
              className="bg-slate-900 border border-slate-700 rounded px-2 text-xs text-slate-200"
            >
              <option value="CSV">CSV</option>
              <option value="HTML">HTML</option>
              <option value="PDF">PDF</option>
            </select>
          </div>
        </div>

        {/* Historical Version Lineage */}
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">
          Historical Report Versions
        </h3>
        <div className="space-y-2">
          {reports.map((r) => (
            <div
              key={r.report_id}
              onClick={() => onSelectReport(r.report_id)}
              className={`p-3 rounded border cursor-pointer transition-colors ${
                r.report_id === currentReportId
                  ? 'bg-emerald-950/40 border-emerald-600'
                  : 'bg-slate-950 border-slate-800 hover:bg-slate-800/60'
              }`}
            >
              <div className="flex justify-between items-start mb-1">
                <span className="text-xs font-bold text-slate-200">{r.report_code}</span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                  v{r.report_version}
                </span>
              </div>
              <div className="text-[11px] text-slate-400 flex justify-between items-center">
                <span>{new Date(r.as_of_timestamp).toLocaleDateString()}</span>
                <span
                  className={`text-[10px] font-semibold ${
                    r.reconciliation_status === 'RECONCILED' ? 'text-emerald-400' : 'text-amber-400'
                  }`}
                >
                  {r.reconciliation_status}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="pt-4 border-t border-slate-800 text-[10px] text-slate-500 text-center">
        Immutable Audit & Version Lineage Engine | M14.05
      </div>
    </div>
  );
};
