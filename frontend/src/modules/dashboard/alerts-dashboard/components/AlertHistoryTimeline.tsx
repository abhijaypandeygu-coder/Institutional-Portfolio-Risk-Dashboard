import React from 'react';
import { 
  Zap, 
  Mail, 
  User, 
  ArrowUpRight, 
  CheckCircle2, 
  Lock, 
  RefreshCw, 
  FileText 
} from 'lucide-react';
import { AlertTimelineEvent } from '../../../../types/dashboard';

interface AlertHistoryTimelineProps {
  events: AlertTimelineEvent[];
  loading: boolean;
}

export const AlertHistoryTimeline: React.FC<AlertHistoryTimelineProps> = ({ events, loading }) => {
  if (loading && events.length === 0) {
    return <div className="text-xs text-muted py-3">Loading history timeline...</div>;
  }

  if (events.length === 0) {
    return <div className="text-xs text-muted py-3">No lifecycle transitions recorded.</div>;
  }

  const renderEventIcon = (type: string) => {
    switch (type) {
      case 'TRIGGERED':
        return <Zap className="size-2.5 text-yellow-400" />;
      case 'ACKNOWLEDGED':
        return <Mail className="size-2.5 text-brand" />;
      case 'ASSIGNED':
        return <User className="size-2.5 text-info" />;
      case 'ESCALATED':
        return <ArrowUpRight className="size-2.5 text-negative" />;
      case 'RESOLVED':
        return <CheckCircle2 className="size-2.5 text-positive" />;
      case 'CLOSED':
        return <Lock className="size-2.5 text-muted" />;
      case 'REOPENED':
        return <RefreshCw className="size-2.5 text-warning" />;
      default:
        return <FileText className="size-2.5 text-muted" />;
    }
  };

  return (
    <div className="relative pl-6 space-y-4 border-l-2 border-line ml-2 py-1">
      {events.map((ev) => (
        <div key={ev.event_id} className="relative group">
          <div className="absolute -left-[31px] top-0 w-5 h-5 rounded-full bg-surface border border-line-strong flex items-center justify-center">
            {renderEventIcon(ev.event_type)}
          </div>
          <div>
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-secondary">
                {ev.event_type}
                {ev.from_status && ev.to_status && (
                  <span className="text-[10px] text-muted font-sans ml-2">
                    ({ev.from_status} → {ev.to_status})
                  </span>
                )}
              </span>
              <span className="text-[10px] text-muted font-sans">
                {ev.occurred_at || ev.timestamp ? new Date(ev.occurred_at || ev.timestamp!).toLocaleString() : '—'}
              </span>
            </div>
            <div className="text-[11px] text-muted mt-0.5">
              By: <span className="text-secondary font-sans">{ev.actor_id}</span>
            </div>
            {ev.notes && (
              <div className="mt-1 p-2 rounded bg-canvas border border-line text-[11px] text-secondary font-sans">
                {ev.notes}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};
