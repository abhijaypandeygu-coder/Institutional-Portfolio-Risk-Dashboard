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
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 text-slate-100 shadow-xl">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
            Export Jobs & Artifact Archive
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Immutable versioned export executions, cryptographic SHA-256 digests, and validation logs.
          </p>
        </div>
        <button
          onClick={onRefresh}
          className="px-3 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 rounded border border-slate-700 flex items-center gap-1.5"
        >
          <span>Refresh</span>
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-slate-800 text-slate-400 uppercase font-mono">
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
                <td colSpan={8} className="py-8 text-center text-slate-500 italic">
                  No export executions recorded. Use the control bar above to generate multi-format artifacts.
                </td>
              </tr>
            ) : (
              jobs.map((job) => (
                <tr key={job.id} className="hover:bg-slate-800/30 transition-colors">
                  <td className="py-3 px-3 font-mono font-medium text-slate-200">
                    {job.export_code}
                  </td>
                  <td className="py-3 px-3">
                    <span className="font-semibold text-white">{job.dataset_id}</span>
                    <span className="text-[10px] text-slate-400 block font-mono">
                      Module: {job.source_module}
                    </span>
                  </td>
                  <td className="py-3 px-3 font-mono text-slate-300">
                    {job.portfolio_id || 'PORTFOLIO_AGG'}
                  </td>
                  <td className="py-3 px-3">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                        job.export_status === 'COMPLETED'
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                          : job.export_status === 'COMPLETED_WITH_WARNINGS'
                          ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                          : job.export_status === 'FAILED'
                          ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                          : 'bg-sky-500/20 text-sky-400 border border-sky-500/30'
                      }`}
                    >
                      {job.export_status}
                    </span>
                  </td>
                  <td className="py-3 px-3 font-mono text-slate-300">
                    {job.processed_records} / {job.total_records}
                  </td>
                  <td className="py-3 px-3">
                    {job.validation_summary ? (
                      <span className="text-[11px] text-slate-300 flex items-center gap-1 font-mono">
                        <span className="w-2 h-2 rounded-full bg-emerald-500" />
                        {job.validation_summary.validation_status}
                      </span>
                    ) : (
                      <span className="text-slate-500 italic">Pending</span>
                    )}
                  </td>
                  <td className="py-3 px-3">
                    <div className="flex flex-wrap gap-1.5">
                      {job.artifacts.map((art) => (
                        <button
                          key={art.artifact_id}
                          onClick={() => onDownloadArtifact(job.id, art.artifact_id, art.file_name)}
                          className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded text-[11px] font-medium flex items-center gap-1 transition-all"
                          title={`SHA-256: ${art.file_hash}`}
                        >
                          <span className="text-emerald-400 font-bold">{art.artifact_type}</span>
                          <span className="text-slate-400 text-[10px]">
                            ({(art.file_size_bytes / 1024).toFixed(1)} KB)
                          </span>
                        </button>
                      ))}
                    </div>
                  </td>
                  <td className="py-3 px-3 text-[11px] text-slate-400 font-mono">
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
