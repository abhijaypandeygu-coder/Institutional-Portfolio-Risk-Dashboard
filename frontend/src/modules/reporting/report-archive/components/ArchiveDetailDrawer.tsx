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
    <div className="fixed inset-y-0 right-0 w-full max-w-2xl bg-surface border-l border-line shadow-2xl p-6 z-50 overflow-y-auto">
      <div className="flex justify-between items-start pb-4 border-b border-line">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-ink font-sans">{detail.archive_id}</h2>
            <span className="text-xs bg-subtle text-brand px-2 py-0.5 rounded font-sans font-bold">
              v{detail.version_number}
            </span>
            <span className="text-xs bg-positive-soft/70 text-positive border border-positive/20 px-2 py-0.5 rounded font-semibold">
              {detail.status}
            </span>
          </div>
          <p className="text-xs text-muted mt-1">{detail.report_title_snapshot}</p>
        </div>
        <button
          onClick={onClose}
          className="text-muted hover:text-ink text-lg font-bold px-2 py-1"
        >
          &times;
        </button>
      </div>

      <div className="grid grid-cols-2 gap-4 py-4 border-b border-line text-xs">
        <div>
          <span className="text-muted block">Portfolio:</span>
          <span className="font-semibold text-secondary">{detail.portfolio_id}</span>
        </div>
        <div>
          <span className="text-muted block">Report Run ID:</span>
          <span className="font-sans text-brand">{detail.report_run_id}</span>
        </div>
        <div>
          <span className="text-muted block">Reporting Period:</span>
          <span className="font-sans text-secondary">
            {new Date(detail.period_start).toLocaleDateString()} &rarr; {new Date(detail.period_end).toLocaleDateString()}
          </span>
        </div>
        <div>
          <span className="text-muted block">Archived At:</span>
          <span className="font-sans text-secondary">{new Date(detail.archived_at).toLocaleString()}</span>
        </div>
      </div>

      {detail.artifact && (
        <div className="my-4 bg-canvas/60 border border-line p-3 rounded-lg text-xs">
          <div className="flex justify-between items-center mb-2">
            <span className="font-semibold text-secondary">Artifact & Cryptographic Integrity</span>
            <button
              onClick={() => onDownload(detail.archive_id)}
              className="bg-brand hover:bg-brand-hover text-white font-medium px-3 py-1 rounded text-xs transition"
            >
              Download {detail.artifact.format} ({(detail.artifact.file_size_bytes / 1024).toFixed(1)} KB)
            </button>
          </div>
          <div className="font-sans text-[11px] text-muted break-all">
            <span className="text-muted">SHA-256: </span>{detail.artifact.artifact_hash}
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-line my-4 text-xs">
        <button
          onClick={() => setActiveTab('provenance')}
          className={`px-4 py-2 font-semibold border-b-2 transition ${
            activeTab === 'provenance'
              ? 'border-cyan-500 text-brand'
              : 'border-transparent text-muted hover:text-secondary'
          }`}
        >
          Provenance Manifest
        </button>
        <button
          onClick={() => setActiveTab('models')}
          className={`px-4 py-2 font-semibold border-b-2 transition ${
            activeTab === 'models'
              ? 'border-cyan-500 text-brand'
              : 'border-transparent text-muted hover:text-secondary'
          }`}
        >
          Models ({prov?.models.length || 0})
        </button>
        <button
          onClick={() => setActiveTab('data')}
          className={`px-4 py-2 font-semibold border-b-2 transition ${
            activeTab === 'data'
              ? 'border-cyan-500 text-brand'
              : 'border-transparent text-muted hover:text-secondary'
          }`}
        >
          Data Sources ({prov?.data_sources.length || 0})
        </button>
        <button
          onClick={() => setActiveTab('history')}
          className={`px-4 py-2 font-semibold border-b-2 transition ${
            activeTab === 'history'
              ? 'border-cyan-500 text-brand'
              : 'border-transparent text-muted hover:text-secondary'
          }`}
        >
          Version History ({versionHistory.length})
        </button>
      </div>

      {/* Tab Contents */}
      {activeTab === 'provenance' && prov && (
        <div className="space-y-4 text-xs">
          <div className="bg-canvas p-3 rounded border border-line">
            <div className="font-semibold text-secondary mb-2">Execution Environment</div>
            <div className="grid grid-cols-2 gap-2 text-muted font-sans text-[11px]">
              <div>App Version: <span className="text-secondary">{prov.application_version}</span></div>
              <div>Environment: <span className="text-secondary">{prov.environment_id}</span></div>
              <div>Trigger Source: <span className="text-secondary">{prov.trigger_source}</span></div>
              <div>Requesting Actor: <span className="text-secondary">{prov.requesting_actor_id}</span></div>
            </div>
          </div>

          <div className="bg-canvas p-3 rounded border border-line">
            <div className="font-semibold text-secondary mb-1">Manifest Hash</div>
            <div className="font-sans text-[11px] text-brand break-all">{prov.manifest_hash}</div>
          </div>

          <div className="bg-canvas p-3 rounded border border-line">
            <div className="font-semibold text-secondary mb-2">Report Run Parameters</div>
            <pre className="text-[11px] font-sans text-secondary bg-surface p-2 rounded overflow-x-auto">
              {JSON.stringify(prov.report_parameters, null, 2)}
            </pre>
          </div>
        </div>
      )}

      {activeTab === 'models' && prov && (
        <div className="space-y-3">
          {prov.models.map((m, idx) => (
            <div key={idx} className="bg-canvas p-3 rounded border border-line text-xs">
              <div className="font-bold text-brand">{m.model_name}</div>
              <div className="grid grid-cols-2 gap-2 text-muted text-[11px] mt-1 font-sans">
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
            <div key={idx} className="bg-canvas p-3 rounded border border-line text-xs">
              <div className="flex justify-between">
                <span className="font-bold text-secondary">{d.source_type}</span>
                <span className="text-positive font-semibold">{d.quality_status}</span>
              </div>
              <div className="text-[11px] text-muted font-sans mt-1">
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
                  ? 'bg-brand-soft/30 border-brand/20'
                  : 'bg-canvas border-line'
              }`}
            >
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-bold text-ink">v{v.version_number}</span>
                  <span className="font-sans text-brand">{v.archive_id}</span>
                  <span className="text-[10px] bg-subtle text-muted px-1.5 py-0.5 rounded">
                    {v.status}
                  </span>
                </div>
                <div className="text-[11px] text-muted mt-1">
                  Generated: {new Date(v.generated_at).toLocaleString()} | Reason: {v.generation_reason}
                </div>
              </div>

              {v.archive_id !== detail.archive_id && (
                <button
                  onClick={() => onCompareVersions(detail.archive_id, v.archive_id)}
                  className="bg-subtle hover:bg-hover text-brand text-xs px-2.5 py-1 rounded"
                >
                  Compare
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Compliance / Legal Hold Actions */}
      <div className="mt-8 pt-4 border-t border-line flex justify-between items-center">
        <button
          onClick={() => setShowHoldModal(true)}
          className="text-xs bg-warning-soft/40 hover:bg-warning-soft/60 text-warning border border-warning/20 px-3 py-1.5 rounded transition"
        >
          {detail.has_active_legal_hold ? 'Manage Legal Holds' : 'Place Under Legal Hold'}
        </button>

        <span className="text-[11px] text-muted font-sans">
          Governed by M14.07 Audit Trail
        </span>
      </div>

      {showHoldModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50">
          <div className="bg-surface border border-line-strong p-6 rounded-lg max-w-md w-full">
            <h3 className="font-bold text-ink text-sm mb-2">Apply Compliance Legal Hold</h3>
            <p className="text-xs text-muted mb-4">
              A legal hold immutably protects this report archive from automated retention policy expiration or disposal.
            </p>
            <textarea
              value={holdReason}
              onChange={(e) => setHoldReason(e.target.value)}
              placeholder="Document regulatory, audit, or legal justification..."
              rows={3}
              className="w-full bg-subtle border border-line-strong text-secondary text-xs p-2 rounded mb-4"
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowHoldModal(false)}
                className="bg-subtle text-secondary text-xs px-3 py-1.5 rounded"
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
                className="bg-amber-600 hover:bg-amber-500 text-ink font-medium text-xs px-3 py-1.5 rounded"
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
