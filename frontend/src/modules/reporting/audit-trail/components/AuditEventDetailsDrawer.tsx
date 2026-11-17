import React from 'react';
import { AuditEventItem } from '../../../../types/auditTrail';

interface Props {
  event: AuditEventItem | null;
  onClose: () => void;
}

export const AuditEventDetailsDrawer: React.FC<Props> = ({ event, onClose }) => {
  if (!event) return null;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 mt-6 text-slate-100 shadow-xl">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs px-2 py-0.5 bg-slate-800 text-emerald-400 rounded">
              SEQ #{event.chain_sequence}
            </span>
            <span className="text-xs text-slate-400 font-mono">{event.event_id}</span>
          </div>
          <h3 className="text-base font-bold text-white mt-1">{event.event_type}</h3>
        </div>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-slate-200 text-sm font-bold px-2 py-1 bg-slate-800 rounded"
        >
          ✕ Close
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
        {/* Core Attribution */}
        <div className="space-y-3">
          <h4 className="font-semibold uppercase tracking-wider text-slate-400 text-[11px]">
            Attribution & Context
          </h4>
          <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-2 font-mono">
            <div>
              <span className="text-slate-500">Actor:</span>{' '}
              <span className="text-slate-200 font-bold">{event.actor_id}</span> ({event.actor_type})
            </div>
            <div>
              <span className="text-slate-500">Source:</span>{' '}
              <span className="text-slate-200">{event.source_module}</span> ({event.source_feature || 'Default'})
            </div>
            <div>
              <span className="text-slate-500">Target:</span>{' '}
              <span className="text-slate-200">{event.target_type}</span> / {event.target_id || 'N/A'}
            </div>
            <div>
              <span className="text-slate-500">Action & Outcome:</span>{' '}
              <span className="text-slate-200">{event.action}</span> →{' '}
              <span className="text-emerald-400 font-bold">{event.outcome}</span>
            </div>
            <div>
              <span className="text-slate-500">Reason / Justification:</span>{' '}
              <span className="text-slate-300 italic">{event.reason || 'No explicit reason provided.'}</span>
            </div>
            <div>
              <span className="text-slate-500">Correlation ID:</span>{' '}
              <span className="text-sky-400">{event.correlation_id || 'None'}</span>
            </div>
          </div>
        </div>

        {/* Cryptographic Hash Chaining */}
        <div className="space-y-3">
          <h4 className="font-semibold uppercase tracking-wider text-slate-400 text-[11px]">
            Tamper Resistance & SHA-256 Chain
          </h4>
          <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-2 font-mono break-all">
            <div>
              <span className="text-slate-500 block">Current Event Hash:</span>
              <span className="text-emerald-400 text-[11px]">{event.integrity_hash}</span>
            </div>
            <div>
              <span className="text-slate-500 block">Previous Chained Hash:</span>
              <span className="text-slate-400 text-[11px]">{event.previous_hash}</span>
            </div>
            <div>
              <span className="text-slate-500">Verification Status:</span>{' '}
              <span className="text-emerald-400 font-bold">{event.verification_status}</span>
            </div>
            <div className="text-[10px] text-slate-500 pt-1">
              H_i = SHA256(Canonical(Event_i) || H_{'{i-1}'})
            </div>
          </div>
        </div>
      </div>

      {/* Configuration Change Diff View */}
      {event.configuration_change && (
        <div className="mt-5 border-t border-slate-800 pt-4">
          <h4 className="font-semibold uppercase tracking-wider text-slate-400 text-[11px] mb-2">
            Configuration Diff (v{event.configuration_change.previous_version} → v{event.configuration_change.new_version})
          </h4>
          <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 text-xs">
            <div className="font-mono text-slate-300 mb-2">
              Resource: <span className="text-white">{event.configuration_change.configuration_type}</span> ({event.configuration_change.configuration_id})
            </div>
            <div className="space-y-1">
              {event.configuration_change.changed_fields.map((f) => (
                <div key={f} className="flex items-center gap-2 font-mono text-[11px]">
                  <span className="text-amber-400">• {f}:</span>
                  <span className="text-rose-400 line-through">
                    {JSON.stringify(event.configuration_change?.old_values_redacted?.[f] ?? 'N/A')}
                  </span>
                  <span className="text-slate-500">→</span>
                  <span className="text-emerald-400">
                    {JSON.stringify(event.configuration_change?.new_values_redacted?.[f] ?? 'N/A')}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
