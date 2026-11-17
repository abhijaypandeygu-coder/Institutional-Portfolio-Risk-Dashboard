import React from 'react';
import { AlertTimelineEvent } from '../../../types/dashboard';

interface AlertHistoryTimelineProps {
  events: AlertTimelineEvent[];
  loading: boolean;
}

export const AlertHistoryTimeline: React.FC<AlertHistoryTimelineProps> = ({ events, loading }) => {
  if (loading && events.length === 0) {
    return <div className="text-xs text-slate-500 py-3">Loading history timeline...</div>;
  }

  if (events.length === 0) {
    return <div className="text-xs text-slate-500 py-3">No lifecycle transitions recorded.</div>;
  }

  const getEventIcon = (type: string) => {
    switch (type) {
      case 'TRIGGERED':
        return '⚡';
      case 'ACKNOWLEDGED':
        return '📬';
      case 'ASSIGNED':
        return '👤';
      case 'ESCALATED':
        return '🔺';
      case 'RESOLVED':
        return '✅';
      case 'CLOSED':
        return '🔒';
      case 'REOPENED':
        return '🔄';
      default:
        return '📝';
    }
  };

  return (
    <div className="relative pl-6 space-y-4 border-l-2 border-slate-800 ml-2 py-1">
      {events.map((ev) => (
        <div key={ev.event_id} className="relative group">
          <div className="absolute -left-[31px] top-0 w-5 h-5 rounded-full bg-slate-900 border border-slate-700 flex items-center justify-center text-[10px]">
            {getEventIcon(ev.event_type)}
          </div>
          <div>
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-slate-200">
                {ev.event_type}
                {ev.from_status && ev.to_status && (
                  <span className="text-[10px] text-slate-400 font-mono ml-2">
                    ({ev.from_status} → {ev.to_status})
                  </span>
                )}
              </span>
              <span className="text-[10px] text-slate-500 font-mono">
                {new Date(ev.timestamp).toLocaleString()}
              </span>
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">
              By: <span className="text-slate-300 font-mono">{ev.actor_id}</span>
            </div>
            {ev.notes && (
              <div className="mt-1 p-2 rounded bg-slate-950 border border-slate-800 text-[11px] text-slate-300 font-mono">
                {ev.notes}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};
