import React from 'react';
import { AlertFeedItem, AlertSeverity, AlertStatus } from '../../../types/dashboard';

interface RecentAlertFeedProps {
  alerts: AlertFeedItem[];
  loading: boolean;
  selectedAlertId?: string | null;
  onSelectAlert: (alert: AlertFeedItem) => void;
  onQuickAcknowledge: (alertId: string) => void;
}

export const RecentAlertFeed: React.FC<RecentAlertFeedProps> = ({
  alerts,
  loading,
  selectedAlertId,
  onSelectAlert,
  onQuickAcknowledge,
}) => {
  const getSeverityBadge = (severity: AlertSeverity) => {
    switch (severity) {
      case 'EMERGENCY':
        return <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-red-950 text-red-300 border border-red-700">EMG</span>;
      case 'CRITICAL':
        return <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-orange-950 text-orange-300 border border-orange-700">CRIT</span>;
      case 'WARNING':
        return <span className="px-1.5 py-0.5 text-[10px] font-semibold rounded bg-yellow-950/80 text-yellow-300 border border-yellow-700/80">WARN</span>;
      case 'INFO':
      default:
        return <span className="px-1.5 py-0.5 text-[10px] rounded bg-slate-800 text-slate-300">INFO</span>;
    }
  };

  const getStatusBadge = (status: AlertStatus) => {
    switch (status) {
      case 'TRIGGERED':
        return <span className="text-[10px] font-mono text-amber-400 bg-amber-950/40 px-1.5 py-0.5 rounded border border-amber-800/60">TRIGGERED</span>;
      case 'ACKNOWLEDGED':
        return <span className="text-[10px] font-mono text-blue-400 bg-blue-950/40 px-1.5 py-0.5 rounded border border-blue-800/60">ACKNOWLEDGED</span>;
      case 'INVESTIGATING':
        return <span className="text-[10px] font-mono text-purple-400 bg-purple-950/40 px-1.5 py-0.5 rounded border border-purple-800/60">INVESTIGATING</span>;
      case 'ESCALATED':
        return <span className="text-[10px] font-mono text-rose-400 bg-rose-950/40 px-1.5 py-0.5 rounded border border-rose-800/60">ESCALATED</span>;
      case 'RESOLVED':
        return <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/40 px-1.5 py-0.5 rounded border border-emerald-800/60">RESOLVED</span>;
      case 'CLOSED':
        return <span className="text-[10px] font-mono text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded">CLOSED</span>;
      default:
        return <span className="text-[10px] font-mono text-slate-400">{status}</span>;
    }
  };

  const formatTimestamp = (ts: string) => {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  if (loading && alerts.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 text-center text-slate-500">
        Loading recent alert feed...
      </div>
    );
  }

  if (alerts.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 text-center">
        <div className="text-2xl mb-1">🔕</div>
        <div className="text-slate-300 font-semibold text-sm">No Alerts Triggered</div>
        <div className="text-slate-500 text-xs mt-1">No alerts match the current filter selection.</div>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden shadow-sm">
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-200">Alerts Activity Feed (M12 Engine)</h3>
        <span className="text-xs text-slate-400 font-mono">{alerts.length} items</span>
      </div>
      <div className="divide-y divide-slate-800/80 max-h-[600px] overflow-y-auto">
        {alerts.map((a) => {
          const isSelected = selectedAlertId === a.alert_id;
          return (
            <div
              key={a.alert_id}
              onClick={() => onSelectAlert(a)}
              className={`p-3.5 flex flex-col gap-2 cursor-pointer transition ${
                isSelected ? 'bg-indigo-950/30 border-l-4 border-indigo-500' : 'hover:bg-slate-800/40'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  {getSeverityBadge(a.severity)}
                  {getStatusBadge(a.status)}
                  <span className="text-xs font-mono font-semibold text-slate-400">
                    P:{a.priority_score.toFixed(0)}
                  </span>
                  {a.has_linked_breach && (
                    <span className="text-[10px] px-1 py-0.2 bg-red-900/40 text-red-300 border border-red-700/60 rounded">
                      M11 BREACH
                    </span>
                  )}
                </div>
                <span className="text-[11px] font-mono text-slate-500">
                  {formatTimestamp(a.triggered_at)}
                </span>
              </div>

              <div className="text-xs font-medium text-slate-100 flex items-center justify-between">
                <span>{a.title}</span>
                {a.portfolio_id && (
                  <span className="text-[10px] font-mono text-slate-400 bg-slate-950 px-1.5 py-0.5 rounded border border-slate-800">
                    {a.portfolio_id}
                  </span>
                )}
              </div>

              {(a.metric_name || a.trigger_value !== null) && (
                <div className="text-[11px] font-mono text-slate-400 flex items-center gap-3">
                  {a.metric_name && <span>Metric: {a.metric_name}</span>}
                  {a.trigger_value !== null && a.trigger_value !== undefined && (
                    <span className="text-slate-300">
                      Value: {a.trigger_value.toLocaleString(undefined, { maximumFractionDigits: 2 })}{' '}
                      {a.unit || ''}
                    </span>
                  )}
                  {a.threshold_value !== null && a.threshold_value !== undefined && (
                    <span className="text-slate-500">
                      Limit: {a.threshold_value.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                    </span>
                  )}
                </div>
              )}

              <div className="flex items-center justify-between pt-1 border-t border-slate-800/60">
                <span className="text-[10px] text-slate-500">
                  {a.assigned_to ? `Assigned: ${a.assigned_to}` : 'Unassigned'}
                </span>
                <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                  {!a.is_acknowledged && (
                    <button
                      type="button"
                      onClick={() => onQuickAcknowledge(a.alert_id)}
                      className="px-2 py-0.5 bg-amber-900/50 hover:bg-amber-800 text-amber-200 text-[10px] font-semibold rounded border border-amber-700/50 transition"
                    >
                      Ack
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
