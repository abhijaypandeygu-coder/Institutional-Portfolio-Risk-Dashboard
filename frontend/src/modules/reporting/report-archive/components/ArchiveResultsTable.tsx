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
      <div className="bg-surface border border-line rounded-lg p-12 text-center text-muted">
        Loading historical archive records...
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="bg-surface border border-line rounded-lg p-12 text-center text-muted">
        No archived reports matched the search criteria.
      </div>
    );
  }

  const getStatusBadge = (status: ArchiveStatus, hasHold: boolean) => {
    let color = 'bg-subtle text-secondary';
    if (status === 'AVAILABLE') color = 'bg-positive-soft/60 text-positive border border-positive/20';
    if (status === 'SUPERSEDED') color = 'bg-warning-soft/60 text-warning border border-warning/20';
    if (status === 'RESTATED') color = 'bg-brand-soft/60 text-brand border border-brand/20';
    if (status === 'WITHDRAWN') color = 'bg-info-soft/60 text-info border border-info/20';
    if (status === 'QUARANTINED') color = 'bg-negative-soft/60 text-negative border border-negative/20 ';

    return (
      <div className="flex items-center gap-1.5">
        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${color}`}>{status}</span>
        {hasHold && (
          <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-amber-500/20 text-warning border border-amber-500/40" title="Legal Hold Active">
            HOLD
          </span>
        )}
      </div>
    );
  };

  return (
    <div className="bg-surface border border-line rounded-lg overflow-hidden shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs text-secondary">
          <thead className="bg-subtle/70 text-muted uppercase font-semibold border-b border-line">
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
              <tr key={row.archive_id} className="hover:bg-subtle/40 transition">
                <td className="py-3 px-4 font-sans">
                  <div className="font-semibold text-brand cursor-pointer hover:underline" onClick={() => onSelectArchive(row.archive_id)}>
                    {row.archive_id}
                  </div>
                  <div className="text-[10px] text-muted">Run: {row.report_run_id}</div>
                </td>
                <td className="py-3 px-4">
                  <div className="font-medium text-secondary">{row.portfolio_id}</div>
                  <div className="text-[10px] text-muted">{row.portfolio_name_snapshot || 'Primary Fund'}</div>
                </td>
                <td className="py-3 px-4">
                  <div className="font-medium text-secondary">{row.report_title_snapshot}</div>
                  <div className="text-[10px] text-brand/80">{row.report_type}</div>
                </td>
                <td className="py-3 px-4 font-sans text-[11px] text-muted">
                  {new Date(row.period_start).toLocaleDateString()} &rarr; {new Date(row.period_end).toLocaleDateString()}
                </td>
                <td className="py-3 px-4 text-center">
                  <span className="font-bold text-secondary bg-subtle px-2 py-0.5 rounded text-[11px]">
                    v{row.version_number}
                  </span>
                </td>
                <td className="py-3 px-4">{getStatusBadge(row.status, row.has_active_legal_hold)}</td>
                <td className="py-3 px-4 text-[11px] text-muted font-sans">
                  {new Date(row.generated_at).toLocaleString()}
                </td>
                <td className="py-3 px-4 text-right">
                  <div className="flex justify-end gap-1.5">
                    <button
                      onClick={() => onSelectArchive(row.archive_id)}
                      className="text-xs bg-subtle hover:bg-hover text-secondary px-2 py-1 rounded"
                    >
                      Detail
                    </button>
                    <button
                      onClick={() => onDownload(row.archive_id, row.artifact?.format)}
                      disabled={row.status === 'QUARANTINED' || row.status === 'EXPIRED'}
                      className="text-xs bg-brand-soft/40 hover:bg-brand-hover-soft/60 disabled:opacity-40 text-brand border border-brand/20 px-2 py-1 rounded"
                    >
                      Download
                    </button>
                    <button
                      onClick={() => onVerifyIntegrity(row.archive_id)}
                      className="text-xs bg-subtle hover:bg-hover text-muted px-1.5 py-1 rounded"
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
