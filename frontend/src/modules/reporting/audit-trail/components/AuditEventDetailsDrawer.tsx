import React from 'react';
import { AuditEventItem } from '../../../../types/auditTrail';

interface Props {
  event: AuditEventItem | null;
  onClose: () => void;
}

export const AuditEventDetailsDrawer: React.FC<Props> = ({ event, onClose }) => {
  if (!event) return null;

  return (
    <div className="bg-surface border border-line rounded-xl p-5 mt-6 text-ink shadow-xl">
      <div className="flex items-center justify-between border-b border-line pb-3 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-sans text-xs px-2 py-0.5 bg-subtle text-positive rounded">
              SEQ #{event.chain_sequence}
            </span>
            <span className="text-xs text-muted font-sans">{event.event_id}</span>
          </div>
          <h3 className="text-base font-bold text-ink mt-1">{event.event_type}</h3>
        </div>
        <button
          onClick={onClose}
          className="text-muted hover:text-secondary text-sm font-bold px-2 py-1 bg-subtle rounded"
        >
          ✕ Close
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
        {/* Core Attribution */}
        <div className="space-y-3">
          <h4 className="font-semibold uppercase  text-muted text-[11px]">
            Attribution & Context
          </h4>
          <div className="bg-canvas p-3 rounded-lg border border-line space-y-2 font-sans">
            <div>
              <span className="text-muted">Actor:</span>{' '}
              <span className="text-secondary font-bold">{event.actor_id}</span> ({event.actor_type})
            </div>
            <div>
              <span className="text-muted">Source:</span>{' '}
              <span className="text-secondary">{event.source_module}</span> ({event.source_feature || 'Default'})
            </div>
            <div>
              <span className="text-muted">Target:</span>{' '}
              <span className="text-secondary">{event.target_type}</span> / {event.target_id || 'N/A'}
            </div>
            <div>
              <span className="text-muted">Action & Outcome:</span>{' '}
              <span className="text-secondary">{event.action}</span> →{' '}
              <span className="text-positive font-bold">{event.outcome}</span>
            </div>
            <div>
              <span className="text-muted">Reason / Justification:</span>{' '}
              <span className="text-secondary italic">{event.reason || 'No explicit reason provided.'}</span>
            </div>
            <div>
              <span className="text-muted">Correlation ID:</span>{' '}
              <span className="text-sky-400">{event.correlation_id || 'None'}</span>
            </div>
          </div>
        </div>

        {/* Cryptographic Hash Chaining */}
        <div className="space-y-3">
          <h4 className="font-semibold uppercase  text-muted text-[11px]">
            Tamper Resistance & SHA-256 Chain
          </h4>
          <div className="bg-canvas p-3 rounded-lg border border-line space-y-2 font-sans break-all">
            <div>
              <span className="text-muted block">Current Event Hash:</span>
              <span className="text-positive text-[11px]">{event.integrity_hash}</span>
            </div>
            <div>
              <span className="text-muted block">Previous Chained Hash:</span>
              <span className="text-muted text-[11px]">{event.previous_hash}</span>
            </div>
            <div>
              <span className="text-muted">Verification Status:</span>{' '}
              <span className="text-positive font-bold">{event.verification_status}</span>
            </div>
            <div className="text-[10px] text-muted pt-1">
              H_i = SHA256(Canonical(Event_i) || H_{'{i-1}'})
            </div>
          </div>
        </div>
      </div>

      {/* Configuration Change Diff View */}
      {event.configuration_change && (
        <div className="mt-5 border-t border-line pt-4">
          <h4 className="font-semibold uppercase  text-muted text-[11px] mb-2">
            Configuration Diff (v{event.configuration_change.previous_version} → v{event.configuration_change.new_version})
          </h4>
          <div className="bg-canvas p-3 rounded-lg border border-line text-xs">
            <div className="font-sans text-secondary mb-2">
              Resource: <span className="text-ink">{event.configuration_change.configuration_type}</span> ({event.configuration_change.configuration_id})
            </div>
            <div className="space-y-1">
              {event.configuration_change.changed_fields.map((f) => (
                <div key={f} className="flex items-center gap-2 font-sans text-[11px]">
                  <span className="text-warning">• {f}:</span>
                  <span className="text-negative line-through">
                    {JSON.stringify(event.configuration_change?.old_values_redacted?.[f] ?? 'N/A')}
                  </span>
                  <span className="text-muted">→</span>
                  <span className="text-positive">
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
