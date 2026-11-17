import React from 'react';
import { ReportArchiveSummary, ArchiveStatus } from '../../../../types/reportArchive';

interface Props {
  items: ReportArchiveSummary[];
  loading: boolean;
  onSelectArchive: (archiveId: string) => void;
  onDownload: (archiveId: string, filename?: string) => void;
  onVerifyIntegrity: (archiveId: string) => void;
}

export const ArchiveResultsTable: React.FC<Props> = ({
  items,
  loading,
  onSelectArchive,
  onDownload,
  onVerifyIntegrity,
}) => {
  if (loading) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-12 text-center text-slate-400">
        Loading historical archive records...
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-12 text-center text-slate-500">
        No archived reports matched the search criteria.
      </div>
    );
  }

  const getStatusBadge = (status: ArchiveStatus, hasHold: boolean) => {
    let color = 'bg-slate-800 text-slate-300';
    if (status === 'AVAILABLE') color = 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/40';
    if (status === 'SUPERSEDED') color = 'bg-amber-950/60 text-amber-400 border border-amber-800/40';
    if (status === 'RESTATED') color = 'bg-blue-950/60 text-blue-400 border border-blue-800/40';
    if (status === 'WITHDRAWN') color = 'bg-purple-950/60 text-purple-400 border border-purple-800/40';
    if (status === 'QUARANTINED') color = 'bg-rose-950/60 text-rose-400 border border-rose-800/40 animate-pulse';

    return (
      <div className="flex items-center gap-1.5">
        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${color}`}>{status}</span>
        {hasHold && (
          <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40" title="Legal Hold Active">
            HOLD
          </span>
        )}
      </div>
    );
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-slate-800/70 text-slate-400 uppercase font-semibold border-b border-slate-800">
            <tr>
              <th className="py-3 px-4">Archive / Run ID</th>
              <th className="py-3 px-4">Portfolio</th>
              <th className="py-3 px-4">Report Title / Type</th>
              <th className="py-3 px-4">Reporting Period</th>
              <th className="py-3 px-4 text-center">Version</th>
              <th className="py-3 px-4">Status</th>
              <th className="py-3 px-4">Generated At</th>
              <th className="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {items.map((row) => (
              <tr key={row.archive_id} className="hover:bg-slate-800/40 transition">
                <td className="py-3 px-4 font-mono">
                  <div className="font-semibold text-cyan-400 cursor-pointer hover:underline" onClick={() => onSelectArchive(row.archive_id)}>
                    {row.archive_id}
                  </div>
                  <div className="text-[10px] text-slate-500">Run: {row.report_run_id}</div>
                </td>
                <td className="py-3 px-4">
                  <div className="font-medium text-slate-200">{row.portfolio_id}</div>
                  <div className="text-[10px] text-slate-500">{row.portfolio_name_snapshot || 'Primary Fund'}</div>
                </td>
                <td className="py-3 px-4">
                  <div className="font-medium text-slate-200">{row.report_title_snapshot}</div>
                  <div className="text-[10px] text-cyan-400/80">{row.report_type}</div>
                </td>
                <td className="py-3 px-4 font-mono text-[11px] text-slate-400">
                  {new Date(row.period_start).toLocaleDateString()} &rarr; {new Date(row.period_end).toLocaleDateString()}
                </td>
                <td className="py-3 px-4 text-center">
                  <span className="font-bold text-slate-200 bg-slate-800 px-2 py-0.5 rounded text-[11px]">
                    v{row.version_number}
                  </span>
                </td>
                <td className="py-3 px-4">{getStatusBadge(row.status, row.has_active_legal_hold)}</td>
                <td className="py-3 px-4 text-[11px] text-slate-400 font-mono">
                  {new Date(row.generated_at).toLocaleString()}
                </td>
                <td className="py-3 px-4 text-right">
                  <div className="flex justify-end gap-1.5">
                    <button
                      onClick={() => onSelectArchive(row.archive_id)}
                      className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 px-2 py-1 rounded"
                    >
                      Detail
                    </button>
                    <button
                      onClick={() => onDownload(row.archive_id, row.artifact?.format)}
                      disabled={row.status === 'QUARANTINED' || row.status === 'EXPIRED'}
                      className="text-xs bg-cyan-900/40 hover:bg-cyan-800/60 disabled:opacity-40 text-cyan-300 border border-cyan-700/50 px-2 py-1 rounded"
                    >
                      Download
                    </button>
                    <button
                      onClick={() => onVerifyIntegrity(row.archive_id)}
                      className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-400 px-1.5 py-1 rounded"
                      title="Verify SHA-256 Hash"
                    >
                      Verify
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
