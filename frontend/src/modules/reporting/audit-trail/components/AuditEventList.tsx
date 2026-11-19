import React from 'react';
import { AuditEventItem } from '../../../../types/auditTrail';

interface Props {
  events: AuditEventItem[];
  selectedEvent: AuditEventItem | null;
  onSelectEvent: (event: AuditEventItem) => void;
}

export const AuditEventList: React.FC<Props> = ({
  events,
  selectedEvent,
  onSelectEvent,
}) => {
  return (
    <div className="bg-surface border border-line rounded-xl overflow-hidden shadow-xl">
      <div className="p-4 border-b border-line flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase  text-secondary">
          Cryptographically Chained Audit Stream
        </h3>
        <span className="text-xs text-muted font-sans">
          {events.length} Records Loaded
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-line text-muted uppercase font-sans bg-canvas/40">
              <th className="py-2.5 px-3">Seq #</th>
              <th className="py-2.5 px-3">Event ID</th>
              <th className="py-2.5 px-3">Category / Type</th>
              <th className="py-2.5 px-3">Actor</th>
              <th className="py-2.5 px-3">Target</th>
              <th className="py-2.5 px-3">Outcome</th>
              <th className="py-2.5 px-3">SHA-256 Hash</th>
              <th className="py-2.5 px-3">Occurred At (UTC)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-sans">
            {events.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-8 text-center text-muted italic">
                  No audit events found matching the selected filter criteria.
                </td>
              </tr>
            ) : (
              events.map((e) => {
                const isSelected = selectedEvent?.id === e.id;
                return (
                  <tr
                    key={e.id}
                    onClick={() => onSelectEvent(e)}
                    className={`cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-positive-soft/30 border-l-2 border-emerald-500'
                        : 'hover:bg-subtle/40'
                    }`}
                  >
                    <td className="py-3 px-3 font-sans font-bold text-secondary">
                      #{e.chain_sequence}
                    </td>
                    <td className="py-3 px-3 font-sans text-secondary truncate max-w-[150px]">
                      {e.event_id}
                    </td>
                    <td className="py-3 px-3">
                      <span className="font-semibold text-ink block">{e.event_type}</span>
                      <span className="text-[10px] text-muted font-sans">
                        [{e.source_module}] {e.event_category}
                      </span>
                    </td>
                    <td className="py-3 px-3">
                      <span className="text-secondary font-medium">{e.actor_id}</span>
                      <span className="text-[10px] text-muted block">({e.actor_type})</span>
                    </td>
                    <td className="py-3 px-3 font-sans text-secondary">
                      {e.target_id || e.target_type || '—'}
                    </td>
                    <td className="py-3 px-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase  ${
                          e.outcome === 'SUCCESS'
                            ? 'bg-brand/20 text-positive border border-emerald-500/30'
                            : e.outcome === 'FAILURE'
                            ? 'bg-rose-500/20 text-negative border border-rose-500/30'
                            : 'bg-amber-500/20 text-warning border border-amber-500/30'
                        }`}
                      >
                        {e.outcome}
                      </span>
                    </td>
                    <td className="py-3 px-3 font-sans text-[10px] text-muted truncate max-w-[120px]">
                      {e.integrity_hash}
                    </td>
                    <td className="py-3 px-3 text-[11px] text-muted font-sans">
                      {new Date(e.occurred_at).toISOString().replace('T', ' ').substring(0, 19)}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
