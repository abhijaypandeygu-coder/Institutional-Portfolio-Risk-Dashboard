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
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
      <div className="p-4 border-b border-slate-800 flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
          Cryptographically Chained Audit Stream
        </h3>
        <span className="text-xs text-slate-400 font-mono">
          {events.length} Records Loaded
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-slate-800 text-slate-400 uppercase font-mono bg-slate-950/40">
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
                <td colSpan={8} className="py-8 text-center text-slate-500 italic">
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
                        ? 'bg-emerald-950/30 border-l-2 border-emerald-500'
                        : 'hover:bg-slate-800/40'
                    }`}
                  >
                    <td className="py-3 px-3 font-mono font-bold text-slate-300">
                      #{e.chain_sequence}
                    </td>
                    <td className="py-3 px-3 font-mono text-slate-200 truncate max-w-[150px]">
                      {e.event_id}
                    </td>
                    <td className="py-3 px-3">
                      <span className="font-semibold text-white block">{e.event_type}</span>
                      <span className="text-[10px] text-slate-400 font-mono">
                        [{e.source_module}] {e.event_category}
                      </span>
                    </td>
                    <td className="py-3 px-3">
                      <span className="text-slate-200 font-medium">{e.actor_id}</span>
                      <span className="text-[10px] text-slate-500 block">({e.actor_type})</span>
                    </td>
                    <td className="py-3 px-3 font-mono text-slate-300">
                      {e.target_id || e.target_type || '—'}
                    </td>
                    <td className="py-3 px-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                          e.outcome === 'SUCCESS'
                            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                            : e.outcome === 'FAILURE'
                            ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                            : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                        }`}
                      >
                        {e.outcome}
                      </span>
                    </td>
                    <td className="py-3 px-3 font-mono text-[10px] text-slate-400 truncate max-w-[120px]">
                      {e.integrity_hash}
                    </td>
                    <td className="py-3 px-3 text-[11px] text-slate-400 font-mono">
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
