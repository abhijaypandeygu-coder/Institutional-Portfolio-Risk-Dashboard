import React from 'react';
import { ExportJobSummary } from '../../../../types/exportEngine';

interface Props {
  jobs: ExportJobSummary[];
  onRefresh: () => void;
  onDownloadArtifact: (jobId: number, artifactId: number, fileName: string) => void;
}

export const ExportHistoryTable: React.FC<Props> = ({
  jobs,
  onRefresh,
  onDownloadArtifact,
}) => {
  return (
    <div className="bg-surface border border-line rounded-xl p-5 text-ink shadow-xl">
      <div className="flex items-center justify-between border-b border-line pb-3 mb-4">
        <div>
          <h3 className="text-sm font-semibold uppercase  text-secondary">
            Export Jobs & Artifact Archive
          </h3>
          <p className="text-xs text-muted mt-0.5">
            Immutable versioned export executions, cryptographic SHA-256 digests, and validation logs.
          </p>
        </div>
        <button
          onClick={onRefresh}
          className="px-3 py-1 text-xs bg-subtle hover:bg-hover text-secondary rounded border border-line-strong flex items-center gap-1.5"
        >
          <span>Refresh</span>
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-line text-muted uppercase font-sans">
              <th className="py-2.5 px-3">Export Code</th>
              <th className="py-2.5 px-3">Dataset / Module</th>
              <th className="py-2.5 px-3">Scope</th>
              <th className="py-2.5 px-3">Status</th>
              <th className="py-2.5 px-3">Records</th>
              <th className="py-2.5 px-3">Validation</th>
              <th className="py-2.5 px-3">Artifacts & Downloads</th>
              <th className="py-2.5 px-3">Timestamp (UTC)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-sans">
            {jobs.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-8 text-center text-muted italic">
                  No export executions recorded. Use the control bar above to generate multi-format artifacts.
                </td>
              </tr>
            ) : (
              jobs.map((job) => (
                <tr key={job.id} className="hover:bg-subtle/30 transition-colors">
                  <td className="py-3 px-3 font-sans font-medium text-secondary">
                    {job.export_code}
                  </td>
                  <td className="py-3 px-3">
                    <span className="font-semibold text-ink">{job.dataset_id}</span>
                    <span className="text-[10px] text-muted block font-sans">
                      Module: {job.source_module}
                    </span>
                  </td>
                  <td className="py-3 px-3 font-sans text-secondary">
                    {job.portfolio_id || 'PORTFOLIO_AGG'}
                  </td>
                  <td className="py-3 px-3">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase  ${
                        job.export_status === 'COMPLETED'
                          ? 'bg-brand/20 text-positive border border-emerald-500/30'
                          : job.export_status === 'COMPLETED_WITH_WARNINGS'
                          ? 'bg-amber-500/20 text-warning border border-amber-500/30'
                          : job.export_status === 'FAILED'
                          ? 'bg-rose-500/20 text-negative border border-rose-500/30'
                          : 'bg-sky-500/20 text-sky-400 border border-sky-500/30'
                      }`}
                    >
                      {job.export_status}
                    </span>
                  </td>
                  <td className="py-3 px-3 font-sans text-secondary">
                    {job.processed_records} / {job.total_records}
                  </td>
                  <td className="py-3 px-3">
                    {job.validation_summary ? (
                      <span className="text-[11px] text-secondary flex items-center gap-1 font-sans">
                        <span className="w-2 h-2 rounded-full bg-brand" />
                        {job.validation_summary.validation_status}
                      </span>
                    ) : (
                      <span className="text-muted italic">Pending</span>
                    )}
                  </td>
                  <td className="py-3 px-3">
                    <div className="flex flex-wrap gap-1.5">
                      {job.artifacts.map((art) => (
                        <button
                          key={art.artifact_id}
                          onClick={() => onDownloadArtifact(job.id, art.artifact_id, art.file_name)}
                          className="px-2 py-1 bg-subtle hover:bg-hover text-secondary border border-line-strong rounded text-[11px] font-medium flex items-center gap-1 transition-opacity"
                          title={`SHA-256: ${art.file_hash}`}
                        >
                          <span className="text-positive font-bold">{art.artifact_type}</span>
                          <span className="text-muted text-[10px]">
                            ({(art.file_size_bytes / 1024).toFixed(1)} KB)
                          </span>
                        </button>
                      ))}
                    </div>
                  </td>
                  <td className="py-3 px-3 text-[11px] text-muted font-sans">
                    {new Date(job.requested_at).toISOString().replace('T', ' ').substring(0, 19)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
