import React, { useState } from 'react';
import { AlertDetailResponse, AlertTimelineEvent } from '../../../../types/dashboard';
import { AlertHistoryTimeline } from './AlertHistoryTimeline';
import { AlertActionModal } from './AlertActionModals';

interface AlertDetailDrawerProps {
  alert: AlertDetailResponse | null;
  historyEvents: AlertTimelineEvent[];
  loading: boolean;
  onClose: () => void;
  onAcknowledge: (alertId: string, notes?: string) => Promise<void>;
  onAssign: (alertId: string, assignee: string, notes?: string) => Promise<void>;
  onCloseAlert: (alertId: string, rationale: string, notes?: string) => Promise<void>;
  onReopen: (alertId: string, notes?: string) => Promise<void>;
}

export const AlertDetailDrawer: React.FC<AlertDetailDrawerProps> = ({
  alert,
  historyEvents,
  loading,
  onClose,
  onAcknowledge,
  onAssign,
  onCloseAlert,
  onReopen,
}) => {
  const [activeModal, setActiveModal] = useState<'ack' | 'assign' | 'close' | 'reopen' | null>(null);
  const [modalLoading, setModalLoading] = useState(false);

  if (!alert) return null;

  // Normalize alert fields whether nested under alert.alert or flat
  const a: any = alert.alert || alert;
  const alertId = a.alert_id || alert.alert_id || '';
  const title = a.title || alert.title || '';
  const alertType = a.alert_type || alert.alert_type || 'ALERT';
  const priorityScore = a.priority_score ?? alert.priority_score ?? null;
  const severity = a.severity || alert.severity || 'INFO';
  const status = a.status || alert.status || 'OPEN';
  const portfolioId = a.portfolio_id || alert.portfolio_id || '';
  const instrumentId = a.instrument_id || alert.instrument_id || '';
  const triggeredAt = a.triggered_at || alert.triggered_at || new Date().toISOString();
  const assignedTo = a.assigned_to || alert.assigned_to || null;
  const triggerCondition = alert.trigger_condition || a.short_description || 'Condition threshold evaluated';
  const metricName = alert.metric_name || alert.source_metric || a.metric_name || null;
  const triggerVal = alert.trigger_value ?? alert.observed_value ?? a.trigger_value ?? null;
  const thresholdVal = alert.threshold_value ?? a.threshold_value ?? null;
  const unit = alert.unit || alert.metric_unit || a.unit || '';
  const evidence = alert.evidence_payload || {};
  const resolutionNotes = alert.resolution_notes || null;
  const hasLinkedBreach = alert.has_linked_breach || a.has_linked_breach || Boolean(a.related_breach_id);
  const linkedBreachId = alert.linked_breach_id || a.linked_breach_id || a.related_breach_id || null;
  const breachWarningNotice = alert.breach_warning_notice || (hasLinkedBreach ? `Associated limit breach event ${linkedBreachId}` : null);

  const handleAction = async (payload: { notes?: string; rationale?: string; assigned_to?: string }) => {
    setModalLoading(true);
    try {
      if (activeModal === 'ack') {
        await onAcknowledge(alertId, payload.notes);
      } else if (activeModal === 'assign' && payload.assigned_to) {
        await onAssign(alertId, payload.assigned_to, payload.notes);
      } else if (activeModal === 'close' && payload.rationale) {
        await onCloseAlert(alertId, payload.rationale, payload.notes);
      } else if (activeModal === 'reopen') {
        await onReopen(alertId, payload.notes);
      }
      setActiveModal(null);
    } finally {
      setModalLoading(false);
    }
  };

  return (
    <div className="fixed inset-y-0 right-0 z-40 w-full max-w-xl bg-slate-900 border-l border-slate-800 shadow-2xl flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-950">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
              {alertType}
            </span>
            {priorityScore !== null && priorityScore !== undefined && (
              <span className="text-xs font-mono text-slate-400">P:{Number(priorityScore).toFixed(0)}</span>
            )}
          </div>
          <h2 className="text-sm font-bold text-slate-100 mt-1">{title}</h2>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-slate-400 hover:text-slate-100 text-lg px-2"
        >
          ✕
        </button>
      </div>

      {/* Linked Breach Callout if present */}
      {hasLinkedBreach && breachWarningNotice && (
        <div className="p-3 bg-amber-950/70 border-b border-amber-800 text-amber-200 text-xs">
          <div className="font-bold flex items-center gap-1">
            <span>⚠️</span> RISK LIMIT BREACH LINKED ({linkedBreachId})
          </div>
          <div className="mt-1">{breachWarningNotice}</div>
        </div>
      )}

      {/* Content scroll area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5 text-xs text-slate-300">
        {/* Core Attributes */}
        <div className="grid grid-cols-2 gap-3 bg-slate-950/60 p-3 rounded border border-slate-800 font-mono">
          <div>
            <span className="text-slate-500 block text-[10px]">SEVERITY</span>
            <span className="font-semibold text-slate-200">{severity}</span>
          </div>
          <div>
            <span className="text-slate-500 block text-[10px]">STATUS</span>
            <span className="font-semibold text-slate-200">{status}</span>
          </div>
          <div>
            <span className="text-slate-500 block text-[10px]">PORTFOLIO</span>
            <span className="text-slate-200">{portfolioId || 'N/A'}</span>
          </div>
          <div>
            <span className="text-slate-500 block text-[10px]">INSTRUMENT</span>
            <span className="text-slate-200">{instrumentId || 'N/A'}</span>
          </div>
          <div>
            <span className="text-slate-500 block text-[10px]">TRIGGERED AT</span>
            <span className="text-slate-200">{new Date(triggeredAt).toLocaleString()}</span>
          </div>
          <div>
            <span className="text-slate-500 block text-[10px]">ASSIGNED TO</span>
            <span className="text-slate-200">{assignedTo || 'Unassigned'}</span>
          </div>
        </div>

        {/* Trigger Condition & Values */}
        <div>
          <h4 className="text-slate-400 font-semibold mb-1 uppercase tracking-wider text-[11px]">
            Trigger Condition & Evidence
          </h4>
          <div className="p-3 bg-slate-950 rounded border border-slate-800 font-mono space-y-1">
            <div>
              <span className="text-slate-500">Condition:</span> {triggerCondition}
            </div>
            {metricName && (
              <div>
                <span className="text-slate-500">Metric:</span> {metricName}
              </div>
            )}
            {triggerVal !== null && triggerVal !== undefined && (
              <div>
                <span className="text-slate-500">Trigger Value:</span>{' '}
                <span className="text-amber-300">
                  {Number(triggerVal).toLocaleString(undefined, { maximumFractionDigits: 2 })}{' '}
                  {unit}
                </span>
              </div>
            )}
            {thresholdVal !== null && thresholdVal !== undefined && (
              <div>
                <span className="text-slate-500">Threshold:</span>{' '}
                <span className="text-slate-300">
                  {Number(thresholdVal).toLocaleString(undefined, { maximumFractionDigits: 2 })}{' '}
                  {unit}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Evidence Payload */}
        {Object.keys(evidence).length > 0 && (
          <div>
            <h4 className="text-slate-400 font-semibold mb-1 uppercase tracking-wider text-[11px]">
              Snapshot Evidence Data
            </h4>
            <pre className="p-3 bg-slate-950 rounded border border-slate-800 text-[11px] font-mono text-slate-300 overflow-x-auto max-h-48">
              {JSON.stringify(evidence, null, 2)}
            </pre>
          </div>
        )}

        {/* Resolution Notes if closed */}
        {resolutionNotes && (
          <div>
            <h4 className="text-slate-400 font-semibold mb-1 uppercase tracking-wider text-[11px]">
              Resolution Rationale
            </h4>
            <div className="p-3 bg-emerald-950/30 rounded border border-emerald-800/60 text-emerald-300 font-mono">
              {alert.resolution_notes}
              {alert.resolved_at && (
                <div className="text-[10px] text-slate-500 mt-1">
                  Resolved at: {new Date(alert.resolved_at).toLocaleString()}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Lifecycle Audit Timeline */}
        <div>
          <h4 className="text-slate-400 font-semibold mb-2 uppercase tracking-wider text-[11px]">
            Lifecycle Audit History
          </h4>
          <AlertHistoryTimeline events={historyEvents} loading={loading} />
        </div>
      </div>

      {/* Footer Actions */}
      <div className="p-3 border-t border-slate-800 bg-slate-950 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {!alert.is_acknowledged && (
            <button
              type="button"
              onClick={() => setActiveModal('ack')}
              className="px-3 py-1.5 rounded bg-amber-600 hover:bg-amber-500 text-white font-semibold text-xs transition"
            >
              Acknowledge
            </button>
          )}
          <button
            type="button"
            onClick={() => setActiveModal('assign')}
            className="px-3 py-1.5 rounded bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs transition"
          >
            Assign
          </button>
        </div>

        <div className="flex items-center gap-2">
          {alert.status === 'CLOSED' || alert.status === 'RESOLVED' ? (
            <button
              type="button"
              onClick={() => setActiveModal('reopen')}
              className="px-3 py-1.5 rounded bg-slate-700 hover:bg-slate-600 text-white font-semibold text-xs transition"
            >
              Reopen
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setActiveModal('close')}
              className="px-3 py-1.5 rounded bg-emerald-700 hover:bg-emerald-600 text-white font-semibold text-xs transition"
            >
              Close Alert
            </button>
          )}
        </div>
      </div>

      {/* Action Modals */}
      <AlertActionModal
        isOpen={activeModal === 'ack'}
        title="Acknowledge Alert"
        confirmLabel="Confirm Acknowledgement"
        confirmColorClass="bg-amber-600 hover:bg-amber-500"
        onClose={() => setActiveModal(null)}
        onConfirm={handleAction}
        loading={modalLoading}
      />

      <AlertActionModal
        isOpen={activeModal === 'assign'}
        title="Assign Alert"
        confirmLabel="Assign Alert"
        confirmColorClass="bg-indigo-600 hover:bg-indigo-500"
        requiresAssignee
        onClose={() => setActiveModal(null)}
        onConfirm={handleAction}
        loading={modalLoading}
      />

      <AlertActionModal
        isOpen={activeModal === 'close'}
        title="Close Alert"
        confirmLabel="Close Alert with Rationale"
        confirmColorClass="bg-emerald-600 hover:bg-emerald-500"
        requiresRationale
        warningNotice={
          alert.has_linked_breach
            ? 'This alert is linked to an active M11 Risk Limit Breach. Closing this alert will NOT resolve, cure, or dismiss the underlying breach in the Risk Limits & Escalation system.'
            : undefined
        }
        onClose={() => setActiveModal(null)}
        onConfirm={handleAction}
        loading={modalLoading}
      />

      <AlertActionModal
        isOpen={activeModal === 'reopen'}
        title="Reopen Alert"
        confirmLabel="Reopen Alert"
        confirmColorClass="bg-slate-700 hover:bg-slate-600"
        onClose={() => setActiveModal(null)}
        onConfirm={handleAction}
        loading={modalLoading}
      />
    </div>
  );
};
