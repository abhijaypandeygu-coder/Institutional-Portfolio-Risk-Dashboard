import React from 'react';
import { BellOff } from 'lucide-react';
import { AlertFeedItem, AlertSeverity, AlertStatus } from '../../../../types/dashboard';

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
  const getSeverityBadge = (severity: AlertSeverity | string) => {
    switch (severity) {
      case 'EMERGENCY':
        return <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-negative-soft text-negative border border-negative/20">EMG</span>;
      case 'CRITICAL':
        return <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-orange-950 text-orange-300 border border-orange-700">CRIT</span>;
      case 'HIGH':
        return <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-orange-900/60 text-orange-300 border border-orange-700/60">HIGH</span>;
      case 'WARNING':
      case 'MEDIUM':
        return <span className="px-1.5 py-0.5 text-[10px] font-semibold rounded bg-yellow-950/80 text-yellow-300 border border-yellow-700/80">WARN</span>;
      case 'LOW':
      case 'INFO':
      default:
        return <span className="px-1.5 py-0.5 text-[10px] rounded bg-subtle text-secondary">{severity || 'INFO'}</span>;
    }
  };

  const getStatusBadge = (status: AlertStatus | string) => {
    switch (status) {
      case 'OPEN':
      case 'TRIGGERED':
        return <span className="text-[10px] font-sans text-warning bg-warning-soft/40 px-1.5 py-0.5 rounded border border-warning/20">OPEN</span>;
      case 'ACKNOWLEDGED':
        return <span className="text-[10px] font-sans text-brand bg-brand-soft/40 px-1.5 py-0.5 rounded border border-brand/20">ACKNOWLEDGED</span>;
      case 'ASSIGNED':
      case 'INVESTIGATING':
        return <span className="text-[10px] font-sans text-info bg-info-soft/40 px-1.5 py-0.5 rounded border border-info/20">{status}</span>;
      case 'ESCALATED':
        return <span className="text-[10px] font-sans text-negative bg-negative-soft/40 px-1.5 py-0.5 rounded border border-negative/20">ESCALATED</span>;
      case 'RESOLVED':
        return <span className="text-[10px] font-sans text-positive bg-positive-soft/40 px-1.5 py-0.5 rounded border border-positive/20">RESOLVED</span>;
      case 'CLOSED':
        return <span className="text-[10px] font-sans text-muted bg-subtle px-1.5 py-0.5 rounded">CLOSED</span>;
      default:
        return <span className="text-[10px] font-sans text-muted">{status}</span>;
    }
  };

  const formatTimestamp = (ts: string) => {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  if (loading && alerts.length === 0) {
    return (
      <div className="bg-surface border border-line rounded-lg p-6 text-center text-muted">
        Loading recent alert feed...
      </div>
    );
  }

  if (alerts.length === 0) {
    return (
      <div className="bg-surface border border-line rounded-lg p-6 text-center flex flex-col items-center">
        <div className="size-9 rounded-full bg-subtle/80 border border-line-strong/60 flex items-center justify-center text-muted mb-2">
          <BellOff className="size-4" />
        </div>
        <div className="text-secondary font-semibold text-sm">No Alerts Triggered</div>
        <div className="text-muted text-xs mt-1">No alerts match the current filter selection.</div>
      </div>
    );
  }

  return (
    <div className="bg-surface border border-line rounded-lg overflow-hidden shadow-sm">
      <div className="px-4 py-3 border-b border-line flex items-center justify-between">
        <h3 className="text-sm font-semibold text-secondary">Alerts Activity Feed (M12 Engine)</h3>
        <span className="text-xs text-muted font-sans">{alerts.length} items</span>
      </div>
      <div className="divide-y divide-slate-800/80 max-h-[600px] overflow-y-auto">
        {alerts.map((a) => {
          const isSelected = selectedAlertId === a.alert_id;
          return (
            <div
              key={a.alert_id}
              onClick={() => onSelectAlert(a)}
              className={`p-3.5 flex flex-col gap-2 cursor-pointer transition ${
                isSelected ? 'bg-brand-soft/30 border-l-4 border-indigo-500' : 'hover:bg-subtle/40'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  {getSeverityBadge(a.severity)}
                  {getStatusBadge(a.status)}
                  {a.priority_score !== undefined && a.priority_score !== null && (
                    <span className="text-xs font-sans font-semibold text-muted">
                      P:{Number(a.priority_score).toFixed(0)}
                    </span>
                  )}
                  {a.has_linked_breach && (
                    <span className="text-[10px] px-1 py-0.2 bg-negative-soft/40 text-negative border border-negative/20 rounded">
                      M11 BREACH
                    </span>
                  )}
                </div>
                <span className="text-[11px] font-sans text-muted">
                  {formatTimestamp(a.triggered_at)}
                </span>
              </div>

              <div className="text-xs font-medium text-ink flex items-center justify-between">
                <span>{a.title}</span>
                {a.portfolio_id && (
                  <span className="text-[10px] font-sans text-muted bg-canvas px-1.5 py-0.5 rounded border border-line">
                    {a.portfolio_id}
                  </span>
                )}
              </div>

              {(a.metric_name || a.trigger_value !== null) && (
                <div className="text-[11px] font-sans text-muted flex items-center gap-3">
                  {a.metric_name && <span>Metric: {a.metric_name}</span>}
                  {a.trigger_value !== null && a.trigger_value !== undefined && (
                    <span className="text-secondary">
                      Value: {a.trigger_value.toLocaleString(undefined, { maximumFractionDigits: 2 })}{' '}
                      {a.unit || ''}
                    </span>
                  )}
                  {a.threshold_value !== null && a.threshold_value !== undefined && (
                    <span className="text-muted">
                      Limit: {a.threshold_value.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                    </span>
                  )}
                </div>
              )}

              <div className="flex items-center justify-between pt-1 border-t border-line/60">
                <span className="text-[10px] text-muted">
                  {a.assigned_to ? `Assigned: ${a.assigned_to}` : 'Unassigned'}
                </span>
                <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                  {!a.is_acknowledged && (
                    <button
                      type="button"
                      onClick={() => onQuickAcknowledge(a.alert_id)}
                      className="px-2 py-0.5 bg-warning-soft/50 hover:bg-warning-soft text-warning text-[10px] font-semibold rounded border border-warning/20 transition"
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
