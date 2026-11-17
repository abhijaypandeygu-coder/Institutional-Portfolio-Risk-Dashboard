import React from 'react';
import { RecentAlertSummaryResponse } from '../../../../types/dashboard';

interface RecentAlertSummaryProps {
  summary: RecentAlertSummaryResponse | null;
  loading: boolean;
}

export const RecentAlertSummary: React.FC<RecentAlertSummaryProps> = ({ summary, loading }) => {
  if (loading && !summary) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-slate-900 border border-slate-800 rounded-lg p-4 animate-pulse h-20" />
        ))}
      </div>
    );
  }

  const s = summary || {
    total_alerts_24h: 0,
    unacknowledged_alerts: 0,
    high_priority_alerts: 0,
    under_investigation: 0,
    as_of: new Date().toISOString(),
  };

  const cards = [
    {
      label: 'Alerts (Last 24h)',
      value: s.total_alerts_24h,
      color: 'text-slate-100',
      bgColor: 'bg-slate-900/80',
      border: 'border-slate-800',
      icon: '🔔',
    },
    {
      label: 'Unacknowledged',
      value: s.unacknowledged_alerts,
      color: s.unacknowledged_alerts > 0 ? 'text-amber-400 font-bold' : 'text-slate-300',
      bgColor: s.unacknowledged_alerts > 0 ? 'bg-amber-950/30' : 'bg-slate-900/80',
      border: s.unacknowledged_alerts > 0 ? 'border-amber-800/60' : 'border-slate-800',
      icon: '📬',
    },
    {
      label: 'High Priority (P≥75)',
      value: s.high_priority_alerts,
      color: s.high_priority_alerts > 0 ? 'text-rose-400 font-bold' : 'text-slate-300',
      bgColor: s.high_priority_alerts > 0 ? 'bg-rose-950/30' : 'bg-slate-900/80',
      border: s.high_priority_alerts > 0 ? 'border-rose-800/60' : 'border-slate-800',
      icon: '🔥',
    },
    {
      label: 'Under Investigation',
      value: s.under_investigation,
      color: 'text-indigo-400 font-semibold',
      bgColor: 'bg-slate-900/80',
      border: 'border-slate-800',
      icon: '🔍',
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      {cards.map((c, idx) => (
        <div
          key={idx}
          className={`${c.bgColor} ${c.border} border rounded-lg p-3.5 flex flex-col justify-between shadow-sm transition hover:border-slate-700`}
        >
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>{c.label}</span>
            <span>{c.icon}</span>
          </div>
          <div className={`text-2xl mt-1 tracking-tight ${c.color}`}>{c.value}</div>
        </div>
      ))}
    </div>
  );
};
