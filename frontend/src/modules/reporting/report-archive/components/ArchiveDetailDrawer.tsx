import React, { useState } from 'react';
import { ReportArchiveDetail, ReportArchiveSummary } from '../../../../types/reportArchive';

interface Props {
  detail: ReportArchiveDetail;
  versionHistory: ReportArchiveSummary[];
  onClose: () => void;
  onDownload: (archiveId: string) => void;
  onCompareVersions: (baseId: string, otherId: string) => void;
  onApplyLegalHold: (archiveId: string, reason: string) => void;
}

export const ArchiveDetailDrawer: React.FC<Props> = ({
  detail,
  versionHistory,
  onClose,
  onDownload,
  onCompareVersions,
  onApplyLegalHold,
}) => {
  const [activeTab, setActiveTab] = useState<'provenance' | 'history' | 'models' | 'data'>('provenance');
  const [holdReason, setHoldReason] = useState('');
  const [showHoldModal, setShowHoldModal] = useState(false);

  const prov = detail.provenance;

  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-2xl bg-slate-900 border-l border-slate-800 shadow-2xl p-6 z-50 overflow-y-auto">
      <div className="flex justify-between items-start pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-white font-mono">{detail.archive_id}</h2>
            <span className="text-xs bg-slate-800 text-cyan-400 px-2 py-0.5 rounded font-mono font-bold">
              v{detail.version_number}
            </span>
            <span className="text-xs bg-emerald-950/70 text-emerald-400 border border-emerald-800/40 px-2 py-0.5 rounded font-semibold">
              {detail.status}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">{detail.report_title_snapshot}</p>
        </div>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-white text-lg font-bold px-2 py-1"
        >
          &times;
        </button>
      </div>

      <div className="grid grid-cols-2 gap-4 py-4 border-b border-slate-800 text-xs">
        <div>
          <span className="text-slate-500 block">Portfolio:</span>
          <span className="font-semibold text-slate-200">{detail.portfolio_id}</span>
        </div>
        <div>
          <span className="text-slate-500 block">Report Run ID:</span>
          <span className="font-mono text-cyan-400">{detail.report_run_id}</span>
        </div>
        <div>
          <span className="text-slate-500 block">Reporting Period:</span>
          <span className="font-mono text-slate-300">
            {new Date(detail.period_start).toLocaleDateString()} &rarr; {new Date(detail.period_end).toLocaleDateString()}
          </span>
        </div>
        <div>
          <span className="text-slate-500 block">Archived At:</span>
          <span className="font-mono text-slate-300">{new Date(detail.archived_at).toLocaleString()}</span>
        </div>
      </div>

      {detail.artifact && (
        <div className="my-4 bg-slate-950/60 border border-slate-800 p-3 rounded-lg text-xs">
          <div className="flex justify-between items-center mb-2">
            <span className="font-semibold text-slate-300">Artifact & Cryptographic Integrity</span>
            <button
              onClick={() => onDownload(detail.archive_id)}
              className="bg-cyan-600 hover:bg-cyan-500 text-white font-medium px-3 py-1 rounded text-xs transition"
            >
              Download {detail.artifact.format} ({(detail.artifact.file_size_bytes / 1024).toFixed(1)} KB)
            </button>
          </div>
          <div className="font-mono text-[11px] text-slate-400 break-all">
            <span className="text-slate-500">SHA-256: </span>{detail.artifact.artifact_hash}
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-slate-800 my-4 text-xs">
        <button
          onClick={() => setActiveTab('provenance')}
          className={`px-4 py-2 font-semibold border-b-2 transition ${
            activeTab === 'provenance'
              ? 'border-cyan-500 text-cyan-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Provenance Manifest
        </button>
        <button
          onClick={() => setActiveTab('models')}
          className={`px-4 py-2 font-semibold border-b-2 transition ${
            activeTab === 'models'
              ? 'border-cyan-500 text-cyan-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Models ({prov?.models.length || 0})
        </button>
        <button
          onClick={() => setActiveTab('data')}
          className={`px-4 py-2 font-semibold border-b-2 transition ${
            activeTab === 'data'
              ? 'border-cyan-500 text-cyan-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Data Sources ({prov?.data_sources.length || 0})
        </button>
        <button
          onClick={() => setActiveTab('history')}
          className={`px-4 py-2 font-semibold border-b-2 transition ${
            activeTab === 'history'
              ? 'border-cyan-500 text-cyan-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Version History ({versionHistory.length})
        </button>
      </div>

      {/* Tab Contents */}
      {activeTab === 'provenance' && prov && (
        <div className="space-y-4 text-xs">
          <div className="bg-slate-950 p-3 rounded border border-slate-800">
            <div className="font-semibold text-slate-300 mb-2">Execution Environment</div>
            <div className="grid grid-cols-2 gap-2 text-slate-400 font-mono text-[11px]">
              <div>App Version: <span className="text-slate-200">{prov.application_version}</span></div>
              <div>Environment: <span className="text-slate-200">{prov.environment_id}</span></div>
              <div>Trigger Source: <span className="text-slate-200">{prov.trigger_source}</span></div>
              <div>Requesting Actor: <span className="text-slate-200">{prov.requesting_actor_id}</span></div>
            </div>
          </div>

          <div className="bg-slate-950 p-3 rounded border border-slate-800">
            <div className="font-semibold text-slate-300 mb-1">Manifest Hash</div>
            <div className="font-mono text-[11px] text-cyan-400 break-all">{prov.manifest_hash}</div>
          </div>

          <div className="bg-slate-950 p-3 rounded border border-slate-800">
            <div className="font-semibold text-slate-300 mb-2">Report Run Parameters</div>
            <pre className="text-[11px] font-mono text-slate-300 bg-slate-900 p-2 rounded overflow-x-auto">
              {JSON.stringify(prov.report_parameters, null, 2)}
            </pre>
          </div>
        </div>
      )}

      {activeTab === 'models' && prov && (
        <div className="space-y-3">
          {prov.models.map((m, idx) => (
            <div key={idx} className="bg-slate-950 p-3 rounded border border-slate-800 text-xs">
              <div className="font-bold text-cyan-400">{m.model_name}</div>
              <div className="grid grid-cols-2 gap-2 text-slate-400 text-[11px] mt-1 font-mono">
                <div>Model Ver: {m.model_version}</div>
                <div>Impl Ver: {m.implementation_version || 'N/A'}</div>
                <div>Param Set: {m.parameter_set_id || 'DEFAULT'}</div>
                <div>Hash: {m.model_artifact_hash ? m.model_artifact_hash.substring(0, 16) + '...' : 'N/A'}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {activeTab === 'data' && prov && (
        <div className="space-y-3">
          {prov.data_sources.map((d, idx) => (
            <div key={idx} className="bg-slate-950 p-3 rounded border border-slate-800 text-xs">
              <div className="flex justify-between">
                <span className="font-bold text-slate-200">{d.source_type}</span>
                <span className="text-emerald-400 font-semibold">{d.quality_status}</span>
              </div>
              <div className="text-[11px] text-slate-400 font-mono mt-1">
                <div>Source ID: {d.source_id}</div>
                <div>Snapshot ID: {d.snapshot_id || 'LIVE_CURRENT'}</div>
                <div>Data As Of: {new Date(d.data_as_of).toLocaleString()}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {activeTab === 'history' && (
        <div className="space-y-2">
          {versionHistory.map((v) => (
            <div
              key={v.archive_id}
              className={`p-3 rounded border text-xs flex justify-between items-center ${
                v.archive_id === detail.archive_id
                  ? 'bg-cyan-950/30 border-cyan-700/60'
                  : 'bg-slate-950 border-slate-800'
              }`}
            >
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-bold text-white">v{v.version_number}</span>
                  <span className="font-mono text-cyan-400">{v.archive_id}</span>
                  <span className="text-[10px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded">
                    {v.status}
                  </span>
                </div>
                <div className="text-[11px] text-slate-500 mt-1">
                  Generated: {new Date(v.generated_at).toLocaleString()} | Reason: {v.generation_reason}
                </div>
              </div>

              {v.archive_id !== detail.archive_id && (
                <button
                  onClick={() => onCompareVersions(detail.archive_id, v.archive_id)}
                  className="bg-slate-800 hover:bg-slate-700 text-cyan-300 text-xs px-2.5 py-1 rounded"
                >
                  Compare
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Compliance / Legal Hold Actions */}
      <div className="mt-8 pt-4 border-t border-slate-800 flex justify-between items-center">
        <button
          onClick={() => setShowHoldModal(true)}
          className="text-xs bg-amber-950/40 hover:bg-amber-900/60 text-amber-300 border border-amber-800/40 px-3 py-1.5 rounded transition"
        >
          {detail.has_active_legal_hold ? 'Manage Legal Holds' : 'Place Under Legal Hold'}
        </button>

        <span className="text-[11px] text-slate-500 font-mono">
          Governed by M14.07 Audit Trail
        </span>
      </div>

      {showHoldModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-700 p-6 rounded-lg max-w-md w-full">
            <h3 className="font-bold text-white text-sm mb-2">Apply Compliance Legal Hold</h3>
            <p className="text-xs text-slate-400 mb-4">
              A legal hold immutably protects this report archive from automated retention policy expiration or disposal.
            </p>
            <textarea
              value={holdReason}
              onChange={(e) => setHoldReason(e.target.value)}
              placeholder="Document regulatory, audit, or legal justification..."
              rows={3}
              className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-xs p-2 rounded mb-4"
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowHoldModal(false)}
                className="bg-slate-800 text-slate-300 text-xs px-3 py-1.5 rounded"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  if (holdReason) {
                    onApplyLegalHold(detail.archive_id, holdReason);
                    setShowHoldModal(false);
                    setHoldReason('');
                  }
                }}
                className="bg-amber-600 hover:bg-amber-500 text-white font-medium text-xs px-3 py-1.5 rounded"
              >
                Confirm Hold
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
